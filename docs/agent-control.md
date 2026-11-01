# Shotdesk API 操作流程

以 [AGENTS.md](../AGENTS.md) 为当前规则；实时字段见 `/api/shot-schema`、`/api/asset-schema`、`/api/agent-info`。所有写入接口使用JSON。

- 项目：GET/POST `/api/projects`；GET `/api/projects/<pid>`；POST `/save` 部分更新。
- 文字：项目下 `/plan`（剧本）、`/extract-assets`、`/apply-extracted-assets`、`/storyboard`（分镜/提示词）。
- 媒体：项目下 `/generate`、`/generate-batch`、`/preview-prompt`、`/compose`；工作流不会从文字里的资产名自动生成输入图片。
- 状态：GET `/api/jobs`；单任务停止POST项目下 `/jobs/<jid>/stop`；全停POST `/api/jobs/stop-all`。
- 已读：`/read-media` 或 `/consume-media`，body含version_ids。完成状态：`/shot-completion {shot_id,kind,completed}`。
- 服务：GET/POST `/api/settings`；POST `/api/settings/test {service:llm/comfy/speech,url,api_key:可选}`。响应不返回密钥。
- 导入：POST `/api/workflows/import {workflow,replace:false}`；POST `/api/workflows/check {id}`。仅通用适配器支持。

启用访问密码时，请求需Bearer令牌或登录Cookie。不得通过私有服务器文件路径绕过接口。自动生成前读最新项目，授权覆盖前确认目标与影响范围。
