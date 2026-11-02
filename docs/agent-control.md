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

## 逐镜头准备与连续执行

分镜工作台以各镜头 `description`（“剧情 · 动作 · 台词”）为当前内容依据，不回读旧h3_plan替代用户修改。单镜头可“匹配资产”“生成视频提示词”；列表顶部提供全部匹配、全部提示词、“一键准备全部镜头”（先匹配再写提示词）。更多执行选项中可明确覆盖，或“准备并生成视频”（可能产生生成费用）。默认仅准备，不生成媒体。旧的“重写提示词”也按当前description执行。

`POST /api/projects/<pid>/prepare-shots` 接收 `{operation:"assets"|"prompts"|"prepare"|"prepare_video",scope:"missing"|"all",shot_ids?:[真实ID],confirm_generate?:true}`。省略shot_ids选择全部；prepare_video必须显式confirm_generate:true。不要猜ID，不直接调用供应商绕过队列。任务operation=prepare_shots，kind=text，target=project；通过统一jobs接口读取preparation_progress、preparation_results和result。completed仅表示执行结束；result.failed和needs_review非零时仍需处理对应镜头。单镜失败保留其他镜头成功结果，不重建镜头，不删媒体，不改description或duration。

scope=missing默认保留已有手动关联与提示词，跳过输入/输出未变化的自动结果；自动结果的description/时长/资源/模式变化会使相应步骤重做，手动改过自动输出则保留。scope=all明确覆盖对应步骤。每步立即保存，preparation记录输入指纹、输出指纹和待确认事项，可用相同范围新建任务继续失败或未完成部分。服务中断后不得重复提交结果不明的媒体任务；先查询子任务child_job_ids与现有队列。

匹配只使用现有角色、该角色自己的造型、场景、道具。缺失或歧义进入warnings，不造新ID；提示词不另增资产或换造型，按当前模式及prompt_language编写，保留引用台词，未保证模型画面质量。生成视频阶段有待确认事项的镜头不提交；已有视频跳过。首帧模式缺首帧时先生成首帧并等待完成，再生成视频；引用其他驱动资源的模式仍需事先准备其资源，缺失会记入该镜头失败。停止父任务也会尝试停止当前子媒体任务；上游取消仍服从供应商能力。仅准备步骤不会调用图片/视频生成接口。

已有项目历史遗留的失效镜头资产引用不会阻塞无关资产或造型保存；新引入失效引用或直接删除仍被引用的资产仍拦截。不要自动删旧引用或猜测替代人物，请运行匹配并审核。
