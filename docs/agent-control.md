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
