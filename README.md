# MoviePilot 插件：yosebench通知

把 MoviePilot 的通知转发到 [yosebench](https://github.com/yosefzhang/yosebench) 通知中心。
参考官方 `wpushmsg` 插件（`plugins.v3/wpushmsg`）的结构，只把推送目标换成 yosebench 的自定义 webhook。

## 安装

MoviePilot v3，`plugins.v3/` + `package.v3.json` 布局。

1. 把本仓库放到 MoviePilot 容器能看到的位置，例如挂载到 `/plugin-src`。
2. 系统设置 → 本地插件仓库目录（`PLUGIN_LOCAL_REPO_PATHS`）填该路径。
3. 插件市场 → 本地插件 → 安装 `yosebench通知`。

也可以把 `plugins.v3/yosebenchwebhook/` 整个目录拷到 MoviePilot 的 `app/plugins/` 下（重启后失效，仅供临时调试）。

## 配置

| 配置项 | 说明 |
|---|---|
| 启用插件 | 打开后开始转发 |
| yosebench Webhook 地址 | `http://<yosebench>/api/v1/notify/hook/ybwh_xxx`，地址本身是凭证 |
| yosebench 图片密钥 | 可选，`img_xxx`。填了才会转发图片；与 Webhook 地址是两把不同的钥匙 |
| 来源标识 | 写入 `source` 字段，默认 `moviepilot` |
| 消息类型 | 只转发选中的类型，留空为全部 |

## 转发规则

- 监听 `EventType.NoticeMessage`。
- 消息里已经指定了专用渠道（`channel` 非空）时跳过，避免和 WPUSH/飞书等推送插件重复。
- 等级按通知类型映射：`Plugin` / `Agent` / `Manual` → `warning`，其余 → `info`。
- 请求体：

```json
{
  "source": "moviepilot",
  "level": "warning",
  "title": "通知标题",
  "message": "通知正文",
  "metadata": { "type": "Download" }
}
```

不传 `timestamp`，由 yosebench 用服务器时间入库。成功以响应 JSON `{"status": "ok"}` 判定。

## 图片

MoviePilot 的通知里带 `image`（http/https URL）且配置了图片密钥时：

1. 下载源图，只接受 png / jpeg / webp / gif，单张 ≤ 8 MiB
2. `POST {base}/api/v1/notify/images`（`X-Image-Key`）上传，拿回带 token 的 URL
3. 把该 URL 放进 webhook 的 `image` 字段

上传失败（下载失败、格式不支持、超限、密钥错误）只丢图，通知照常发文字。图片 URL 的
上传接口由 Webhook 地址推导：`/notify/hook/<key>` → `/notify/images`。

注意：yosebench 只认自己上传的图片；外部图床 URL 直接塞进 `image` 会被忽略。

## 注意

Webhook 地址含 `users.webhook_key`，泄露后别人就能往通知箱里塞消息。插件日志不会输出该地址。
