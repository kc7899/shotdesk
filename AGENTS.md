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

`public_media_url` 是用户自己的 Shotdesk 公网HTTPS地址，与上表模型服务地址不同。火山参考视频或虚拟素材入库的签名链接需要该地址；没有公网地址可留空，图片和音频参考仍可使用。不得把火山的 `/api/v3` 地址填在素材公网地址中。

## Seedance虚拟角色同步（试验）

首次引导用户在方舟签署AIGC虚拟素材授权，开通所需权益，并在私有 `video_providers` 的对应ark服务填写 `asset_access_key`、`asset_secret_key`、`asset_project`（默认default）和 `public_media_url`。AK/SK不等于视频api_key；只能从私有设置读取，不要索要用户在聊天公开。GET只返回asset_credentials_configured。留空保留原凭据，clear_asset_credentials:true清除。当前只支持官方地址，不对中转站发送AK/SK。

读取 `GET /api/projects/<pid>/ark-assets` 获取独立同步记录。提交 `POST /api/projects/<pid>/sync-ark-asset {model:"cloud-服务id",resource_id:"角色id或造型id"}`，进入统一asset_sync队列。后台自动CreateAssetGroup（同角色共用）、CreateAsset和GetAsset；相同图片已有asset_id时仅查询，不重复上传。Active才可用，Processing仍在审核，Failed展示原因；Unknown表示上次提交结果不明，必须先核对方舟记录，不重复创建。任务completed仍需检查result.status，Processing不能当作审核通过。

同步记录独立保存项目ark-assets.json，不能在/save里伪造审核状态。造型与身份分别绑定当前图片和SHA256；视频提交自动选当前造型的Active素材ID，图片切换或内容变化后拒绝沿用旧ID。没有同步记录的参考图保留原图传递行为，不宣称已获认可。云端项目必须匹配；不影响本地/H3图片路径。只有模拟接口和签名验证通过，不能宣称真实账号审核已通过。

素材库凭据的界面路径为：服务连接 → 云端视频 → 对应“Seedance · 火山方舟”服务卡片 → 虚拟角色素材库 · AK/SK 配置。该区域直接展开，位于服务基础字段下方，不是独立的顶层菜单。

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

## LLM Skill配置与加载

项目设置新增 `llm_skill_mode`：`auto`（默认）按任务使用内置规范与已启用、适用于当前环节的补充Skill；`builtin`只用内置规范，不加载补充。没有关闭全部规范的总开关。编剧、资产提取、现有分镜引擎保留其任务原生完整指令，不重复注入；匹配资产、单镜头提示词、描述优化使用对应环节的精简适配规范，不能把资产提取或整个分镜的JSON schema叠加到另一种任务。Skill是当前任务的补充参考，不能改变稳定ID、造型归属、语言、字段结构或停止规则。

`GET /api/llm-skills` 提供阶段目录与默认方案。私有 `GET/POST /api/settings` 的 `llm_skills` 列表配置补充项，每项 `{id,name,content,stages,enabled}`；stages可选script/assets/matching/storyboard/prompts/optimization。ID唯一，正文单项不超过12000字、合计不超过24000字、最多12项。整体更新列表须保留其他项；空列表清除所有补充配置。UI路径：服务连接 → LLM Skill方案 → 配置本地补充Skill。可粘贴或导入.md/.txt正文，必须选择适用环节并保存。不会扫描OpenCode，不执行脚本，不抓取链接，不递归读取references；需要的关联内容必须整理到正文，不能把单文件导入说成完整安装了技能包。导入只更新本机私有设置，不发布到GitHub、不随项目导出；用户不得在正文粘贴密钥。

每个任务首次调用LLM时固定本次模式与补充配置；后续步骤按环节使用同一份配置。jobs中的 `llm_skill_trace` 仅包含实际选择的名称、阶段、来源、正文SHA256和delivery，不包含补充正文。task-native表示使用原任务已固定的完整规范，adapter为新任务的精简适配规则，reference为用户补充。私有任务文件保存配置快照用于核查，公开jobs接口过滤`_llm_skill_config`。任务队列可展开“已加载规范”查看。修改配置不会自动重写已有提示词；要应用新规范，明确选择覆盖并重新执行相应任务。平台内部LLM自动加载不代表外部Agent会自动加载；外部Agent须读取本说明、目录和当前任务规范自行遵循。

## 本机自定义Skill目录刷新

服务连接 → LLM Skill方案 → 配置本地补充Skill → “刷新列表”。目录为部署数据目录下的 `custom-skills/`（默认项目 `data/custom-skills/`；默认Docker内 `/app/data/custom-skills/`，宿主机为所挂载数据目录对应的custom-skills）。它属于已忽略的私有data目录，不进入GitHub和项目导出。可放平铺.md/.txt，或 `<自定义名称>/SKILL.md`。不递归扫描references或脚本，不读取符号链接和目录外路径。

`GET /api/llm-skills/files` 读取目录，返回directory/files/warnings，列表不包含正文；`POST /api/llm-skills/import {file:"相对文件名或子目录/SKILL.md"}` 读取单项正文及稳定ID，不直接写配置。界面点“导入或更新”后选择适用环节，保存服务连接才生效。更新已有同路径条目时保留适用环节和启用状态；文件改动、删除或刷新本身都不会静默替换/移除已保存配置。实际执行继续使用settings中的固定文本快照，运行中任务不受目录变化影响。新导入项默认适用环节为空，须明确选择；不会把目录中的所有文件全部自动加载。仅支持UTF-8正文，仍服从单项12000字、合计24000字上限。

## 分镜补充要求

项目字段 `storyboard_requirements` 为可选字符串，最多6000字，通过项目/save保存。UI位于分镜生成按钮下的“分镜补充要求（选填）”，已有分镜和空分镜页均可填写。示例：增加打戏的时长，结合人物能力和场景，适当扩写打斗动作与攻防细节，保持剧情因果、胜负结果和原有台词不变。

生成分镜/仅规划时，该要求传给当前H3结构化规划的每个剧本片段，也传入拆分重试；模型只在当前片段范围内增加相关反应镜头、细节、调度、攻防过程及合理时长，不把要求机械套用到所有镜头。原有资产ID、造型归属、对白编号、说话人与模型时长限制继续生效。新增事件、角色或台词应先修改并审核剧本；这里不能绕过原台词校验。不会自动改写script或已有分镜。

单镜头/批量准备的视频提示词也读取该字段，但仍以description、已选资产和已有duration为准，不能以全局要求擅自扩写另一段剧情或更改固定时长。自动提示词指纹包含该字段，手动提示词默认仍保留；需要覆盖时明确选择覆盖。修改要求会使旧分镜规划断点失配，运行中若要求变化则旧规划结果不覆盖当前项目。

## 指定剧本段落时长

在内容与剧本页选中剧本文字 → “设置段落时长” → 选择minimum（至少）或approximate（大约）及秒数 → 保存。条目可定位、编辑、重新选取或移除；并显示该段已规划的镜头时长。单条1–600秒，选区1–6000个Unicode字符，最多20条，不支持重叠选区。“大约”容差为目标的10%或2秒取较大者。修改只影响下一次分镜生成，不自动更改剧本或已有分镜。

项目/save保存 `segment_timings:[{id,quote,start,end,before,after,script_fingerprint?,seconds,mode}]`。start/end是Unicode码点位置，不是JS UTF-16偏移；end-start必须等于quote字符数。before/after各最多100字符。script_fingerprint是轻量文本版本定位标记，不是安全校验；当前标记匹配且原位置原文一致时用精确位置，否则用唯一原文或唯一上下文重新定位。无法定位或重叠时，UI提示重新选取；生成前拒绝启动而不是把时长套给另一段。不要用裸关键词匹配重复段落。

当前H3结构化规划按选区边界划分片段，传入独立timing_constraint预算。若不足，会有限次请求新的中间镜头（不重复台词、不增加事件和终局），并在每镜模型上限内分配实际生成时长；近似目标过长时只缩减无对白部分，不压缩说话时间。最终核对每个约束的合计规划秒数，不能把其他段落或复制旧片段算进去。始终达不到目标时保留原分镜，不宣称通过。

对应镜头记录timing_constraint_id与timing_constraint_quote；任务记录segment_timing_report。程序核对的是规划时长，尚未验收实际生成视频的有效长度、动作连续性和画面内容。后续采用、裁切或续接会影响实际成片长度，仍须媒体验收。段落要求参与任务并发变更与断点复用检查，不能将旧要求下的规划覆盖新要求。新增约束后请重新生成分镜，不是把单个H3镜头设成120秒。
