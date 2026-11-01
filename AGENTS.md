# Shotdesk · Agent 操作入口

安装、配置或连接故障：先读 [部署诊断 Skill](docs/skills/shotdesk-setup/SKILL.md) 和 [本地安装说明](docs/local-setup.md)。网站入口为 `/agent/setup.md`；正常制作继续使用下面流程。

先读取 `GET /api/agent-info`、`/api/shot-schema`、`/api/asset-schema`、`/api/model-catalog` 和当前项目；不要依赖旧对话里的模型、ID、版本号或路径。启用密码时发送 `Authorization: Bearer <访问密码或环境令牌>`。

## 当前方案

默认分镜方案是 `h3-structured-v2`，实际指令与规则由 `h3_structured.bundle` 提供，使用 `GET /api/storyboard-skill?project_id=<pid>` 获取。独立化改造不改变镜头创作、对白编号、造型归属、H3渲染与有限修复规则。兼容旧项目与历史版本，不能自动替换为Huobao方案。界面已移除Huobao回滚选项；旧格式仅作历史兼容，不自动改写已有分镜。

## 工作步骤

1. `GET /api/projects`，读取所选 `GET /api/projects/<pid>`。故事和剧本分别为content/script；修改用 `/save` 部分更新，不覆盖并发产生的媒体。
2. 生成剧本：`POST /api/projects/<pid>/plan {}`，只写剧本，不创建分镜；用户审核后再提取资产。
3. 提取资产：`POST /api/projects/<pid>/extract-assets {}`。结果是候选，不是已经创建的资产。经授权选择后用 `/apply-extracted-assets`，发送真实job_id、candidate_id、asset_id和look_ids。同一角色的服装变体归looks，不另建人物。
4. 准备参考资产。角色身份图与造型图分开；选中造型有图时传造型图，无造型图且未明确指定时回退身份图。声音是音频样本，不是图；原生有声视频不等于引用了角色声线。
5. `POST /api/projects/<pid>/storyboard {"stage":"all"}` 生成分镜。已有分镜必须取得用户替换授权后加replace_existing:true。`stage:prompts` 可重写已有镜头提示词，scope=missing/all，可选shot_id。读取任务的真实结果与警告，不能把“任务完成”等同于“全剧覆盖或画面合格”。
6. 镜头关联使用asset_ids与character_looks的稳定ID。提交前用 `/preview-prompt {shot_id,kind:"video"}` 核对实际image_inputs、reference_bindings和compiled_prompt。不要用手写图号代替真实关联。
7. `POST /generate {target:"shot",id:"真实镜头ID",kind:"image"或"video"}`；批量 `/generate-batch {kind:"video",mode:"all"}` 每次调用追加一轮。仅在用户明确要求时批量生成，避免误追加成本。
8. 通过 `/api/jobs` 或项目 `/jobs` 轮询；停止单项用 `/jobs/<jid>/stop`，全停用 `/api/jobs/stop-all`。不得清空共享ComfyUI的其他任务。停止中不等于已释放资源。
9. 实际获取媒体后用 `/consume-media` 或 `/read-media {version_ids:[...]}` 同步已读。蓝点只代表是否读过，不代表质量。人工和Agent共用已读状态。完成状态使用 `/shot-completion {shot_id,kind,completed}`，不要把已读当完成。
10. 按镜头选片后 `/compose {}` 合片。项目导出不是完整媒体备份；数据备份需要包含整个数据卷。

## 图片与文件

仅从 `/media/<pid>/media/<文件名>` 的实际内容判断画面；元数据、生成提示词和文件名不是视觉观察。远程路径是服务端路径，不是本地文件路径；需要下载或使用可访问URL，不能把 `/media/` 当本机目录。视频须查看实际视频和听音，不能用一张首帧代替。

历史versions按created降序，version是显示序号，稳定身份是id/url。不要用数组位置猜“V7”；采用前核对同一个实际文件。API检查和模型文字判断均不能代替媒体验收。

## 服务与工作流

`GET /api/settings` 返回脱敏服务配置。`POST /api/settings/test` 测试连接；`POST /api/settings` 在无活动任务时保存。不得把API密钥写进项目提示词或导出文件。

独立安装的 `/api/workflows/import` 接收 `{workflow:定义,replace:false}`；`/api/workflows/check {id}` 检查节点与选项。导入API图需要明确参数映射。没有配套输入适配的方案不能虚报支持；不自动下载权重或启动GPU服务。

## 数据保护

仅在用户明确要求时清空分镜、资产或删除项目。清空接口 `/clear-shots`、`/clear-assets` 需要当前confirm_name与expected_updated；保存数组须回传最新reset_epochs，防止复活已清空内容。删除项目进入七天回收站，不直接永久删除。

保留版本、完成状态、已读状态和原项目设置。任何工作中的异常先读实际代码、接口和任务记录；不要回滚到旧分镜方案或把历史Skill叠加到当前方案。

## 界面语言

界面支持中文 / English，浏览器以 `shotdesk.uiLanguage` 保存选择；它与项目的 `prompt_language` 分开。切换界面不修改剧本、人物/造型名称、提示词、对白或API枚举值（例如 `角色`、`场景`、`道具`）。英文操作手册见 `/agent/guide.en.md`。历史字段名保留兼容，不代表当前产品品牌或创作方案。

## 云端视频服务

`GET /api/settings` 的 `video_providers` 是脱敏云端连接列表；使用 `POST /api/settings {video_providers:[...]}` 配置。每项包含稳定 `id`、`name`、`protocol`（ark/minimax/replicate/fal）、`url`、真实 `model`、`api_key`、`resolution`、`max_references`、`modes`（text/first_frame/reference）、`enabled`。列表整体替换，保留其他服务；空密钥保留，clear_key:true 清除。接口只返回 key_configured。不得将密钥写入项目或提示词。无活动任务时才能改连接。

配置后以模型目录返回的 `cloud-<id>` 选择项目 video_model 或镜头 video_override.model，继续使用现有 /generate 和 /generate-batch，不直接调用服务商绕过队列。用 /preview-prompt 核对实际造型、图序；图片通过 data URL 传递。官方完整 H3 的协议是 minimax，model 为 MiniMax-H3，分辨率为 768P/2K，4–15整秒；不要用 Max/Highspeed/Lite 的名字猜测其质量或能力。项目分辨率使用 preset:768p 或 2k；Seedance 使用所选服务实际支持的档位。fal 每种端点单独配置对应 modes，不把单一端点宣称支持所有方式。火山方舟参考资产模式可通过镜头 cloud_use_audio:true、cloud_use_video:true 显式引用 audio_source/reference_audio、reference_video；其余云端协议尚不传音视频参考。视频需要该服务 public_media_url 为已配置的公网HTTPS片场地址，平台创建6小时有效的单文件签名链接，不直接传内网URL，也不自动开放网络。音频和图像使用data URL；未勾选不发送。尾帧和自定义宽高仍未支持。

云端任务记录 cloud_task_id 和 cloud_provider，服务重启后按原ID查询，不重新提交。提交阶段中断而无ID时结果不明，先人工核对供应商记录。停止使用平台原接口；官方 H3 运行中不能立即取消，cancelling 期间可能继续计费，不得宣称资源已释放。配置/模拟接口通过不等于真实账号出片或质量已验收。

## 引导用户获取云端配置

用户询问模型ID、服务地址、协议或密钥时，先确认其实际使用的是官方平台还是中转站，再提供对应入口；不能把不同供应商的密钥、地址混用。界面字段旁会随协议显示帮助链接。

| 协议 | 官方服务地址 | 密钥获取 | 模型ID与接口说明 |
|---|---|---|---|
| ark | `https://ark.cn-beijing.volces.com/api/v3` | [方舟 API Key](https://ark.volcengine.com/region:cn-beijing/apikey) | [方舟模型控制台](https://console.volcengine.com/ark/region:cn-beijing/overview)、[视频接口文档](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)；复制实际开放模型调用示例的 model 字段 |
| minimax | `https://api.minimax.io` | [MiniMax 官方控制台](https://platform.minimax.io) → API Keys，使用视频按量付费密钥 | [H3 V2模型文档](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)；官方完整高质量模型为 `MiniMax-H3` |
| replicate | `https://api.replicate.com/v1` | [API Tokens](https://replicate.com/account/api-tokens) | [Seedance 模型页](https://replicate.com/bytedance/seedance-2.5)，复制实际模型 owner/name |
| fal | `https://queue.fal.run` | [API Keys](https://fal.ai/dashboard/keys) | [Seedance 参考端点](https://fal.ai/models/bytedance/seedance-2.5/reference-to-video/api)，复制实际端点ID，并按对应生成方式配置 |

中转站的地址、模型ID、密钥由中转站提供，协议必须与其文档匹配。预填模型ID只是示例，不代表用户已经开通；不要自动改写用户当前设置。引导用户在平台私有设置里填写密钥，不要求其在对话或截图里公开密钥，也不把“已保存”说成“已验证出片”。

`public_media_url` 是用户自己的 Shotdesk 公网HTTPS地址，与上表模型服务地址不同。仅火山参考视频的签名链接需要该地址；没有公网地址可留空，图片和音频参考仍可使用。不得把火山的 `/api/v3` 地址填在素材公网地址中。
