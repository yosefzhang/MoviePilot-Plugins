"""yosebench 通知插件：把 MoviePilot 的通知转发到 yosebench 通知中心。"""

from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.network import RequestUtils

# MoviePilot 的通知没有严重级别，这里按类型给出默认档位，其余一律 info
TYPE_LEVELS = {
    NotificationType.Plugin: "warning",
    NotificationType.Agent: "warning",
    NotificationType.Manual: "warning",
}

# yosebench 图片接口：按文件内容只收这四种，单张默认上限 8 MiB
IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}
IMAGE_MAX_BYTES = 8 * 1024 * 1024


class YosebenchWebhook(_PluginBase):
    """yosebench Webhook 通知插件。

    监听 ``EventType.NoticeMessage``，把通知转发到 yosebench 的
    ``POST /api/v1/notify/hook/<key>``。地址本身就是凭证，日志里不输出。
    """

    # 插件名称
    plugin_name = "yosebench通知"
    # 插件描述
    plugin_desc = "把 MoviePilot 通知转发到 yosebench 通知中心（Webhook）。"
    # 插件版本
    plugin_version = "1.1.0"
    # 插件作者
    plugin_author = "Yosef"
    # 作者主页
    author_url = "https://github.com/yosefzhang"
    # 插件配置项ID前缀
    plugin_config_prefix = "yosebenchwebhook_"
    # 加载顺序
    plugin_order = 32
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _webhook_url: Optional[str] = None
    _image_key: Optional[str] = None
    _source = "moviepilot"
    _msgtypes: List[str] = []

    def init_plugin(self, config: dict = None) -> None:
        """根据插件配置初始化运行状态。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._webhook_url = (config.get("webhook_url") or "").strip() or None
        self._image_key = (config.get("image_key") or "").strip() or None
        self._source = (config.get("source") or "").strip() or "moviepilot"
        self._msgtypes = config.get("msgtypes") or []

    def get_state(self) -> bool:
        """获取插件启用状态（需启用且地址是 http/https）。"""
        return bool(
            self._enabled
            and self._webhook_url
            and self._webhook_url.startswith(("http://", "https://"))
        )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """当前插件不注册远程命令。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """当前插件不注册后端 API。"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """拼装插件配置页面：启用开关、Webhook 地址、来源标识与消息类型。"""
        msg_type_options = [
            {"title": item.value, "value": item.name}
            for item in NotificationType
        ]
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "webhook_url",
                                            "label": "yosebench Webhook 地址",
                                            "placeholder": "http://<yosebench>/api/v1/notify/hook/ybwh_xxx",
                                            "hint": "地址就是凭证，泄露后别人就能往你的通知箱里推送，不要公开分享。",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "image_key",
                                            "label": "yosebench 图片密钥（可选）",
                                            "placeholder": "img_xxx",
                                            "type": "password",
                                            "hint": "填了才会把通知里的图片上传到 yosebench；留空只发文字。它与 Webhook 地址是两把不同的钥匙。",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "source",
                                            "label": "来源标识",
                                            "placeholder": "moviepilot",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "multiple": True,
                                            "chips": True,
                                            "model": "msgtypes",
                                            "label": "消息类型（留空为全部）",
                                            "items": msg_type_options,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": (
                                                "只转发未指定专用渠道的通知，已配置其他推送渠道的消息不会重复发送。"
                                                "等级按类型映射：插件/智能体/手动处理为 warning，其余为 info。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "webhook_url": "",
            "image_key": "",
            "source": "moviepilot",
            "msgtypes": [],
        }

    def get_page(self) -> Optional[List[dict]]:
        """无详情页。"""
        return None

    def _payload(
            self, msg_type: Optional[NotificationType], title: str, text: str
    ) -> Dict[str, Any]:
        """按 yosebench webhook 契约拼装请求体（字段全部可选，不传 timestamp 用服务器时间）。"""
        payload: Dict[str, Any] = {
            "source": self._source[:64],
            "level": TYPE_LEVELS.get(msg_type, "info"),
            "title": (title or "")[:256],
            "message": text or "",
            "metadata": {"type": msg_type.name} if msg_type else {},
        }
        return payload

    def _images_url(self) -> Optional[str]:
        """从 Webhook 地址推导图片上传接口：/notify/hook/<key> → /notify/images。"""
        marker = "/notify/hook/"
        url = self._webhook_url or ""
        if marker not in url:
            return None
        return url.split(marker, 1)[0] + "/notify/images"

    def _upload_image(self, source: Optional[str]) -> Optional[str]:
        """把通知里的图片上传到 yosebench，返回带 token 的 URL。

        任何一步失败都只丢图，通知照常发文字；日志不输出图片密钥和 token。
        """
        if not self._image_key or not source:
            return None
        if not source.startswith(("http://", "https://")):
            return None

        upload_url = self._images_url()
        if not upload_url:
            logger.warn("yosebench 图片上传失败：无法从 Webhook 地址推导出图片接口")
            return None

        try:
            res = RequestUtils().get_res(source, allow_redirects=True)
            if res is None or res.status_code != 200:
                logger.warn(
                    f"yosebench 图片上传失败：下载源图失败（{getattr(res, 'status_code', '无响应')}）"
                )
                return None
            declared_size = res.headers.get("Content-Length") or "0"
            if declared_size.isdigit() and int(declared_size) > IMAGE_MAX_BYTES:
                logger.warn("yosebench 图片上传失败：源图超过 8 MiB")
                return None
            content = res.content or b""
            content_type = (res.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            ext = IMAGE_TYPES.get(content_type)
            if not ext:
                logger.warn(f"yosebench 图片上传失败：不支持的类型 {content_type or '未知'}")
                return None
            if not content or len(content) > IMAGE_MAX_BYTES:
                logger.warn("yosebench 图片上传失败：源图为空或超过 8 MiB")
                return None

            up = RequestUtils().post_res(
                upload_url,
                files={"file": (f"image.{ext}", content, content_type)},
                headers={"X-Image-Key": self._image_key},
                allow_redirects=False,
            )
            if up is None or up.status_code != 200:
                logger.warn(
                    f"yosebench 图片上传失败，HTTP 状态码：{getattr(up, 'status_code', '无响应')}"
                )
                return None
            image_url = (up.json() or {}).get("url")
            if isinstance(image_url, str) and image_url:
                logger.info("yosebench 图片已上传")
                return image_url
            logger.warn("yosebench 图片上传失败：响应里没有 url")
            return None
        except Exception as err:
            logger.warn(f"yosebench 图片上传异常，{err}")
            return None

    def _send(self, payload: Dict[str, Any]) -> bool:
        """POST 到 yosebench，成功以响应 JSON status=ok 判定。

        :param payload: 通知请求体
        :return: 是否发送成功
        """
        if not self._webhook_url:
            logger.warn("yosebench 通知发送失败：未配置 Webhook 地址")
            return False

        # 凭证在 URL 里，禁用重定向，日志也不输出地址
        res = RequestUtils(content_type="application/json").post_res(
            self._webhook_url,
            json=payload,
            allow_redirects=False,
        )
        if res is None:
            logger.warn("yosebench 通知发送失败，未获取到返回信息")
            return False
        if res.status_code != 200:
            logger.warn(
                f"yosebench 通知发送失败，HTTP 状态码：{res.status_code}，原因：{res.reason}"
            )
            return False

        try:
            ret_json = res.json()
        except Exception as err:
            logger.warn(f"yosebench 通知发送失败，响应非 JSON：{err}")
            return False

        if ret_json.get("status") == "ok":
            logger.info(f"yosebench 通知已推送：{payload.get('title')}")
            return True

        logger.warn(f"yosebench 通知发送失败，响应：{ret_json}")
        return False

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event) -> None:
        """消息发送事件：未指定专用渠道时转发到 yosebench。"""
        if not self.get_state():
            return

        if not event.event_data:
            return

        msg_body = event.event_data
        # 已指定专用通知渠道时交给对应插件，避免重复推送
        if msg_body.get("channel"):
            return

        msg_type: Optional[NotificationType] = msg_body.get("type")
        title = msg_body.get("title") or ""
        text = msg_body.get("text") or ""

        if not title and not text:
            logger.warn("yosebench 通知：标题和内容不能同时为空")
            return

        if msg_type and self._msgtypes and msg_type.name not in self._msgtypes:
            return

        try:
            payload = self._payload(msg_type, title, text)
            image_url = self._upload_image(msg_body.get("image"))
            if image_url:
                payload["image"] = image_url
            self._send(payload)
        except Exception as msg_e:
            logger.error(f"yosebench 通知发送异常，{str(msg_e)}")

    def stop_service(self) -> None:
        """退出插件。"""
        return None
