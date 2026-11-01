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

## Seedance素材选择（优先简便路径）

角色/造型卡的“选择 Seedance 素材”可登记名称、素材 ID 与本地缩略图，并从列表绑定或解除绑定。不需要 AK/SK 或公网地址；这两项仍完整保留供自动上传审核使用。公共虚拟人像库的素材在账号开通所需权限、同意相关条款后可用 `asset://asset-…` 引用，私有库只能使用账号有权访问的素材。公共 ID 不等于任意账号私有 ID 可跨账号使用。

`GET /api/projects/<pid>/ark-assets` 返回 resources 和 catalog。`POST /api/projects/<pid>/manage-ark-asset` 接收 model:"cloud-服务id" 及 operation。register: {name,asset_id,thumbnail?}（thumbnail只能为当前项目本地图片URL）；bind: {resource_id,catalog_key}；unbind: {resource_id}；remove: {catalog_key}（须先解除引用）。绑定前需给当前角色/造型上传与该ID对应的图片，避免本地展示与云端人物不符。手动登记状态为 Manual，只表示用户提供ID，绝不表示已查询审核通过；远端可能拒绝无权限或失效ID。通过原有 /generate 队列自动传 asset://ID，本地/H3生成仍使用本地图片。图片或文件内容变化会阻止沿用旧绑定。选择造型不会自动继承身份图的素材ID。目录只保存用户登记的条目，不宣称自动枚举公共库；官方 ListAssets 需要AK/SK，视频API Key不能替代。

官方可信原始产物是另一条独立路径，不要求先获得素材ID：截至2026-11-02，官方文档列出同一方舟账号近30天内 Seedream 5.0 lite/pro/flash **文生图**原始含脸图片，以及 Seedance 2.0/2.5 原始含脸视频及其对应尾帧（须符合各自生效日期）。不是所有火山模型、图生图、其他账号或第三方站点产物都受信。禁止把“火山生成”直接标为永久可信；压缩、编辑、转发可能使信任失效，超期不可依赖此路径。保留原始文件，推荐原始结果直接转存TOS；不要只记录模型名称就自动断言能过审。输入可信也不保证输出审核通过。

依据：[官方肖像素材指南](https://docs.volcengine.com/docs/ark/seedance-portrait-asset-guide?lang=zh)、[公共虚拟人像库](https://docs.volcengine.com/docs/ark/avatar-library?lang=zh)。
