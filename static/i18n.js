/* UI-only localization. Template substitutions and persisted project data are never translated. */
(()=>{
'use strict';
const storageKey='shotdesk.uiLanguage';
let locale='zh';try{locale=localStorage.getItem(storageKey)==='en'?'en':'zh'}catch{}
const translations={};
const entries=`
填写你自己的 Shotdesk 公网 HTTPS 地址，不是模型服务地址。参考视频或角色入库需要；普通图片、音频直接生成可留空。|Enter your own public HTTPS Shotdesk URL, not the model API URL. Required for video references or character library sync; optional for direct image/audio generation.

虚拟角色素材库 · AK/SK 配置|Virtual character library · AK/SK settings
获取 AK/SK ↗|Get AK/SK ↗
首次授权与权益说明 ↗|Initial agreement and entitlement guide ↗
仅火山官方虚拟角色入库需要；视频 API 密钥不能替代 AK/SK。|Only required for the official Ark virtual character library; the video API key cannot replace AK/SK.
留空保留已配置凭据|Leave blank to retain saved credentials
火山项目名称|Ark project name
清除素材库凭据|Clear asset library credentials
首次请在方舟控制台签署虚拟素材授权、开通对应权益，并填写上方素材公网地址；之后上传与审核状态可在角色卡操作。|First sign the virtual asset agreement and enable the required entitlement in Ark, then configure the public media URL above. Afterwards upload and check review status from character cards.
请输入凭据|Enter credentials
需更新|Needs update
可使用|Ready
审核中|Under review
未通过|Rejected
提交失败|Submission failed
结果待核对|Needs reconciliation
上传中|Uploading
未同步|Not synced
同步中…|Syncing…
刷新审核|Refresh review
同步到 Seedance|Sync to Seedance
素材同步已加入任务队列|Asset sync added to the task queue
素材同步|Asset sync

按服务商接口文档选择；中转站使用其自己的地址、模型 ID 和密钥。|Choose the protocol in the provider's API documentation. Gateways use their own URL, model ID and key.
官方默认：|Official default:
接口文档 ↗|API documentation ↗
查找模型 ID ↗|Find model IDs ↗
从模型详情或调用示例的 model 字段复制，以账号实际开通的版本为准。|Copy the model field from the model page or API example; use a version enabled for your account.
获取 API 密钥 ↗|Get an API key ↗
登录官方控制台 → API Keys，使用视频按量付费密钥。|Sign in to the official console → API Keys. Use a pay-as-you-go video API key.
登录服务商控制台创建密钥，仅粘贴在此处。|Create a key in the provider console and paste it only here.
填写你自己的 Shotdesk 公网 HTTPS 地址，不是模型服务地址。仅参考视频需要；没有可留空，图片与音频仍可使用。|Enter your own public HTTPS Shotdesk URL, not the model API URL. Only video references require it; leave it blank for image/audio references.

素材公网地址（视频参考）|Public media URL (video references)
引用所选音频|Use selected audio reference
引用参考视频|Use video reference
上传参考音频|Upload audio reference
上传参考视频|Upload video reference
配音与已有音频|Speech and existing audio
音频直接传入；视频由平台生成临时链接，需要服务配置中的素材公网地址。未勾选的素材不会使用。提示词中用“音频1”“视频1”说明用途。|Audio is sent directly. Video uses a temporary signed link and requires a public media URL in service settings. Unchecked inputs are not sent. Describe their purpose as audio 1 / video 1 in the prompt.

云端视频|Cloud video
Seedance、MiniMax H3 官方完整模型及兼容中转服务；按服务商计费。|Seedance, full official MiniMax H3, and compatible gateways; provider charges apply.
＋ 添加云端视频服务|＋ Add cloud video provider
服务名称|Service name
接口协议|API protocol
服务地址|Service URL
模型 ID|Model ID
原生分辨率|Native resolution
最多参考图|Maximum reference images
启用|Enabled
清除密钥|Clear key
移除服务|Remove service
请输入 API 密钥|Enter API key
填写服务实际开放的模型 ID。fal 每个端点对应一种生成方式，请分别添加。留空密钥保留原配置；保存不执行付费生成。|Enter an available model ID. Add each fal generation endpoint separately. Leave the key blank to keep it. Saving does not submit paid jobs.
● 云端视频已配置|● Cloud video configured

片场 · 短剧工作台|Shotdesk · Short drama studio
进入片场|Sign in to Shotdesk
Agent 接入 · 片场|Agent access · Shotdesk
你的下一部短剧|YOUR NEXT STORY
片场|Shotdesk
选择项目|Select project
正在加载剧集…|Loading projects…
＋ 新建短剧|＋ New project
删除当前项目|Delete current project
删除项目|Delete project
项目管理|Project management
回收站|Trash
检查连接中…|Checking connection…
服务连接|Connections
模型设置|Models
导出项目|Export project
▷ 查看成片|▷ View film
↗ 合片导出|↗ Export film
项目名称|Project name
从一个想法，到一部短剧。|From an idea to a short drama.
正在加载项目|Loading project
内容与剧本|Story & script
参考资产|Reference assets
分镜工作台|Storyboard
视频阶段可选择首帧生视频或资产参考生视频（R2V），首帧不是必经步骤|Video can use a first frame or reference assets (R2V). First frames are optional.
内容 → 剧本 → 资产 → 分镜 → 视频|Story → Script → Assets → Storyboard → Video
查看所有项目的任务进展|View tasks across all projects
任务队列|Task queue
暂无进行中任务|No active tasks
Agent 接入|Agent access
画幅|Aspect ratio
用于新生成的分镜描述、首帧与视频提示词；台词保留原文，不改已有内容|Applies to new shot descriptions and prompts. Dialogue and existing content stay unchanged.
提示词语言|Prompt language
中文|Chinese
H3结构化：LLM输出结构化镜头，程序编译视频提示词|H3 structured: the LLM plans shots; the app compiles video prompts.
分镜方案|Storyboard method
H3 结构化（默认）|H3 structured (default)
LLM 大模型|LLM
图片模型|Image model
默认生成方式|Default video method
首帧图片|First-frame image
视频模型|Video model
视频分辨率|Video resolution
宽 × 高|Width × Height
视频宽度|Video width
视频高度|Video height
正文保留，@引用按实际参考图序展开。更换设置只影响新任务。|Text is preserved; @mentions follow the actual reference order. Settings apply to new tasks only.
正在加载工作台…|Loading studio…
统一任务队列|Unified task queue
关闭任务队列|Close task queue
全部|All
进行中|Active
历史记录|History
停止所有项目当前排队、执行和停止中的任务|Stop all queued, running and stopping tasks across projects
■ 停止所有|■ Stop all
文字 · 图片 · 视频 · 合片，统一记录|Text · Images · Video · Film export in one place
预计时间基于同模型历史，仅供参考；样本不足不显示。|Estimates use past tasks for the same model and appear when enough samples exist.
删除满 7 天后，每天北京时间凌晨 4 点自动清理。停机期间错过的清理会在启动后补做。|Deleted projects are kept for 7 days and cleaned daily at 04:00 China time. Missed cleanups run on startup.
清理日志|Cleanup log
清空回收站|Empty trash
关闭 ×|Close ×
你的短剧已就绪|Your film is ready
下载成片|Download film
跟随项目 / 模型默认|Project / model default
当前模型不可用|Current model unavailable
请选择兼容模型|Select a compatible model
镜头独立视频模型|Video model for this shot
镜头生成方案|Video method for this shot
默认跟随项目，可独立设置|Use project settings or override for this shot
超低清预览|Very low-resolution preview
预览|Preview
原生 768P|Native 768P
自定义尺寸|Custom size
侧面近景|Side-profile close-up
导入，未验证|Imported, unverified
8步|8 steps
6步|6 steps
文生/首帧|Text / first frame
资产参考|Asset references
首帧|First frame
跟随项目|Use project settings
工作流默认尺寸|Workflow default size
工作流默认|Workflow default
沿用所选工作流尺寸|Use selected workflow dimensions
原生480P/768P，5–15整秒|Native 480P/768P, 5–15 whole seconds
仅影响新任务|New tasks only
此模型沿用工作流默认尺寸|This model uses workflow dimensions
镜头视频宽度|Shot video width
镜头视频高度|Shot video height
5–15整秒|5–15 whole seconds
镜头分辨率|Shot resolution
音频资产缺失|Audio asset missing
当前对白音频|Current dialogue audio
尚无音频|No audio
未设声音|No voice assigned
配音生成中…|Generating speech…
生成配音 · IndexTTS|Generate speech · IndexTTS
未上传|Not uploaded
与镜头时长不同|Differs from shot duration
采用音频时长|Use audio duration
指定音乐驱动：使用已选音频资产或上传音乐，不做对白配音。|Music-driven: use selected or uploaded music, without dialogue synthesis.
指定音频驱动：使用已选对白音频；可由角色音色＋IndexTTS生成，也可上传。|Audio-driven: use dialogue audio uploaded or generated with a character voice and IndexTTS.
说话人|Speaker
选择人物|Select character
配音语气|Speech delivery
语气，例如轻声、迟疑|Delivery, e.g. soft or hesitant
本镜台词：单镜单说话人，最多300字|Dialogue: one speaker per shot, up to 300 characters
本镜台词|Shot dialogue
采用音频|Use audio
本镜配音／直接上传|Shot speech / upload
上传音频|Upload audio
不会自动裁切或变速。|Audio is not automatically trimmed or retimed.
沿用输入视频音轨，不引用角色音色或对白音频。|Uses the input video's audio, without character voice or dialogue references.
原生有声：模型自行生成声音，不引用角色声音参考或已选对白音频；台词由视频提示词描述。|Native audio: the model generates sound without character voice samples or selected dialogue audio. Put dialogue in the video prompt.
已就绪|Ready
使用当前镜头视频|Use current shot video
更换|Replace
上传|Upload
查看|View
移除|Remove
参考视频|Reference video
参考音视频最多48MB|Reference audio/video must be under 48 MB
素材已上传，项目已切换，请重新选择素材|Media uploaded, but the project changed. Select the media again.
上传对白音频|Upload dialogue audio
已读状态未保存|Read status not saved
请先登录片场|Please sign in to Shotdesk
请求失败|Request failed
有修改，正在保存…|Saving changes…
正在保存…|Saving…
✓ 已保存到本机|✓ Saved locally
保存失败|Save failed
正在读取任务状态|Loading task status
项目已打开，任务状态暂未加载|Project opened; task status could not be loaded
点击画面放大查看|Click to enlarge
放大查看视频|Enlarge video
首帧或参考图|First frame or reference
点击放大查看|Click to enlarge
素材就绪后，让故事动起来|Bring your story to life when assets are ready
把这一刻，变成画面|Turn this moment into an image
按当前方案生成，保留每次结果|Generate with current settings; keep every result
生成首帧，或上传已有图片|Generate a first frame or upload an image
未查看|Unread
个镜头| shots
暂无项目|No projects
暂无短剧项目|No drama projects yet
新建一个项目开始制作|Create a project to get started
创建你的下一部短剧|Create your next short drama
点击新建短剧开始制作。|Click New project to get started.
当前项目已切换，请重新删除|Project changed; select the project to delete again
项目会从工作台移除，剧本、素材和历史记录会在回收站保留 7 天，之后自动永久清理。|The project leaves the studio. Its script, media and history stay in Trash for 7 days before permanent deletion.
项目已删除，文件已移入本地回收目录|Project moved to local Trash
写下故事、风格、时长和镜头要求|Describe the story, style, duration and shot requirements
✧ 生成剧本|✧ Generate script
正在生成剧本…|Generating script…
对白、动作、场次|Dialogue, actions and scenes
故事内容|Story
从想法或原文开始|Start with an idea or source text
按短剧编剧规范，结合故事与现有角色资料生成；不创建资产或分镜。再次生成只替换剧本。|Generate a script from your story and character notes. Assets and shots are created separately. Regenerating replaces only the script.
查看编剧规范 ↗|Screenwriting guide ↗
剧本|Script
可直接编辑，也可由 Agent 写入|Edit directly or let an Agent write it
下一步：准备资产|Next: prepare assets
审核并修改剧本后，到参考资产页提取和完善资产，再到分镜工作台生成镜头。|Review the script, extract and refine reference assets, then generate shots in Storyboard.
剧本任务已加入队列，可在队列中停止|Script task queued; you can stop it in the task queue
重新规划会替换当前|Replanning replaces the current
个镜头及历史关联，参考资产保留，原媒体文件不删除。继续？| shots and their history links. Reference assets and media files are kept. Continue?
规划任务已加入队列，完成后先审核镜头|Planning queued; review the shots when finished
一键分镜任务已加入队列|Storyboard task queued
重写所有镜头的视频提示词？保留分镜描述、台词、资源及已有媒体。|Rewrite all video prompts? Shot descriptions, dialogue, references and existing media are kept.
视频提示词任务已加入队列，不重新规划镜头|Prompt writing queued; shot planning is unchanged
正在为当前镜头编写提示词|Writing a prompt for this shot
正在检查…|Checking…
检查分镜|Check storyboard
首帧版本|First-frame version
视频版本|Video version
的首帧| first frame
当前采用|Selected
点击采用|Click to select
生成后在这里保留每个版本|Generated versions appear here
未完成|Incomplete
点击标记|Mark as
未关联场景|No scene linked
场景尚无参考图|Scene has no reference image
把剧本，变成镜头。|Turn your script into shots.
根据已审核剧本和现有参考资产生成分镜，自动关联人物造型、场景与道具。|Generate shots from the reviewed script and link character looks, scenes and props automatically.
完善剧本|Refine script
添加镜头|Add shot
有新生成内容|New media available
有新的首帧或视频，点击镜头查看|New first frame or video; click the shot to view
镜头独立方案|Shot-specific method
跟随项目默认方案|Project default method
生成中|Generating
已出片|Video ready
首帧就绪|First frame ready
待制作|Not started
导演草稿待审核：已采用基础构图，请检查后生成。|Director draft: basic composition used. Review before generation.
剧情 · 动作 · 台词|Story · Action · Dialogue
首帧提示词|First-frame prompt
首帧生成中…|Generating first frame…
✧ 生成首帧|✧ Generate first frame
下载片段 ↗|Download clip ↗
首帧已变更，当前视频来自旧首帧，可按需重新生成。|First frame changed. This video used an earlier frame; regenerate if needed.
已保留原文与资源关联，采用基础方案完成|Text and references preserved; a basic plan was used
基础方案 · 可润色|Basic plan · Can be refined
视频生成中…|Generating video…
▷ 生成视频|▷ Generate video
有未结束任务时不可清空；保留剧本和参考资产|Finish or stop active tasks first. Script and assets are kept.
清空全部分镜|Clear all shots
仅补缺失结果|Generate missing results only
仅为当前生成方案需要首帧的镜头生成图片|Generate images only for shots that require a first frame
生成全部首帧（如有）|Generate all first frames (if needed)
生成全部视频|Generate all videos
每点一次追加一轮；每轮随机种子|Each click adds a round with random seeds
镜头信息|Shot details
镜头前移|Move shot earlier
镜头后移|Move shot later
删除镜头|Delete shot
标题|Title
关联参考资产|Linked references
首帧图|First-frame image
上传首帧|Upload first frame
支持 @ 资产引用|Supports @asset mentions
首帧历史|First-frame history
镜头视频|Shot video
视频提示词|Video prompt
重写提示词|Rewrite prompt
视频时长（秒）|Video duration (seconds)
手填大于0的秒数，可含小数；与提示词 Duration 行同步，实际范围取决于工作流|Enter seconds greater than zero; decimals allowed. Synced with the Duration line. Limits depend on the workflow.
当前镜头独立生成|Generate only this shot
视频历史|Video history
请填写大于0的秒数|Enter a duration greater than zero
请填写有效的正数时长|Enter a valid positive duration
提示词时长须为大于0的秒数|Prompt duration must be greater than zero
提示词仍引用此资产，请先移除对应的 @ 引用|Remove this asset's @mention from the prompt first
删除此镜头？已有媒体文件仍会保留。|Delete this shot? Existing media files are kept.
提示词已指定造型，请先修改对应的 @ 引用|Change the look's @mention in the prompt first
宽高须为128–4096之间的偶数|Width and height must be even numbers from 128 to 4096
本轮新增|Added this round: 
个，跳过|; skipped: 
提交中…|Submitting…
排队中…|Queued…
停止中…|Stopping…
生成中…|Generating…
生成造型图|Generate look
正在提交造型任务…|Submitting look task…
造型任务已加入队列|Look task queued
造型任务提交失败|Could not submit look task
已加入任务队列，提示词保持原样|Task queued; prompt kept unchanged
上传图片|Upload image
文件超过|File exceeds 
该资源已被移除，请重新上传|Resource removed; upload again
未配置|Not configured
在线|Online
未启动/加载中|Offline / loading
用于剧本、分镜、资产提取和描述优化。未启动的模型可选择，需先在AI控制台启动后再生成。|Used for scripts, storyboards, asset extraction and description refinement. Start offline models in your AI console before generating.
优化排队中…|Refinement queued…
优化中…|Refining…
优化提示词|Refine prompt
优化描述|Refine description
请重试|Please retry
优化失败|Refinement failed
原文保留。|Original text kept.
已采用优化描述|Refined description applied
优化建议 · 原文尚未修改|Suggestion · Original unchanged
未找到可保留的造型信息；采用将清空描述。|No usable look details found. Applying clears the description.
已采用|Applied
描述或要求已变，请重新优化|Description or requirements changed; refine again
采用并收起|Apply & close
保留原文并收起|Keep original & close
优化后的造型描述|Refined look description
描述优化已加入文字任务队列，结果确认后再采用|Refinement queued. Review the result before applying.
优化描述失败|Description refinement failed
描述或出图要求已修改，请重新优化|Description or image requirements changed; refine again
道具只保留自身信息，默认方形、纯灰色无缝背景；描述中的其他物品、墙面、地面仍可能被带入，可用「优化提示词」清理。|Describe only the prop. Default: square image with a seamless grey background. Refine the prompt to remove unwanted objects or surroundings.
身份图用于确定脸和发型；默认是正面头肩像。|Identity reference defines the face and hair; default: front head-and-shoulders portrait.
造型图用于确定全身穿着；默认是单人正面全身。|Look reference defines the outfit; default: one person, front view, full body.
默认纯白无缝摄影背景；描述中的公寓、阳台或日照等场景词仍可能被带入。|Default: seamless white backdrop. Scene details in the description may still appear.
出图要求|Image requirements
可编辑，可清空|Editable; can be cleared
查看实际提交提示词|View submitted prompt
实际提交提示词|Submitted prompt
只提交描述＋上方出图要求，没有隐藏的构图或背景附加词。没有填写描述时无法生成。|Only the description and requirements above are submitted. No hidden composition or backdrop text. A description is required.
保留一个默认声线，可直接更换样本|Keep one default voice; replace its sample if needed
声线被镜头引用，请先改为默认声线|Voice used by a shot; switch that shot to the default voice first
音色参考|Voice reference
✓ 默认|✓ Default
设为默认|Set default
更换声音样本|Replace voice sample
上传声音样本|Upload voice sample
已设置|Configured
未设置 · 不影响原生有声视频|Not set · Native-audio video still works
声线名称|Voice name
添加声线|Add voice
样本仅用于IndexTTS配音。可添加正常、沙哑等不同声线。|Samples are used only for IndexTTS speech. Add normal, hoarse or other variants.
点击放大参考图|Click to enlarge reference
尚无可用参考图|No reference image available
暂无图|No image
取消关联|Unlink
关联资产|Link asset
未有图|No image
默认项跟随人物默认造型，其他造型仅用于本镜头|Default follows the character's default look; overrides apply only to this shot
已关联|Linked
点击名称关联|Click name to link
资产较多时，可在此区域上下滚动查看更多|Scroll this area to see more assets
缺失资产|Missing asset
缺图|No image
所选造型缺图|Selected look has no image
头像（默认造型回退）|Portrait (default look fallback)
缺少身份图|Identity image missing
本镜采用的首帧|Selected first frame
文字提示词|Text prompt
按所选方案输入|Inputs follow the selected method
尚未关联参考资产|No reference assets linked
指定音频|Selected audio
不引用人物声线／对白音频|No character voice / dialogue reference
实际输入|Actual inputs
本镜声线|Shot voice
体型参考|Body reference
未设置体型参考|No body reference
默认造型未设置图片，将使用人物头像。|Default look has no image; the portrait will be used.
此造型尚无图片，选用前需上传或生成。|Upload or generate an image before using this look.
暂未生成造型图|No look image yet
生成或上传后显示在这里|Generated or uploaded image appears here
造型版本|Look version
服装参考已上传|Clothing reference uploaded
造型名称|Look name
造型描述|Look description
保留造型信息，去掉姿势和场景，不重复出图要求|Keep look details, remove poses and scenes, and avoid repeating image requirements
描述服装、鞋饰、发型等；保持人物身份|Describe clothes, shoes, accessories and hair; preserve identity
生成历史|Generation history
直接上传已完成的造型图片|Upload a finished look image
上传造型图|Upload look
上传衣服或穿搭图片，作为生成造型时的参考|Upload clothing or outfit references for look generation
衣服参考|Clothing reference
衣服参考可用商品图或穿搭图；填写造型描述后点「生成造型主图」，结合人物身份图生成穿着效果。|Use a product or outfit photo as clothing reference. Describe the look, then generate it using the character's identity image.
补充身材比例；衣服图片请放到造型卡。|Optional body proportions. Put clothing photos on the look card.
添加造型|Add look
身份图历史|Identity history
单件道具参考图 · 新生成固定方形 1:1|Single prop · New images use 1:1
新生成场景图 · 横版 16:9，不跟随短剧画幅|New scenes use landscape 16:9, independent of the drama ratio
描述道具本身的形状、材质、颜色、尺寸和状态|Describe the prop's shape, material, colour, size and condition
描述场景空间、布局、材质和需要保留的环境细节|Describe space, layout, materials and essential environment details
道具描述|Prop description
场景描述|Scene description
生成道具图|Generate prop
生成场景图|Generate scene
个造型| looks
个声线| voices
对白／配音|Dialogue / speech
音乐|Music
音效|Sound effect
音频用途|Audio use
人物描述|Character description
音频说明，不等于识别出的实际内容|Audio notes, not a transcription
人物信息：外貌、身材、性格等。生成身份参考图时直接使用这里的描述|Character appearance, build and personality. Used directly to generate the identity reference.
参考图生成提示词|Reference image prompt
生成身份／参考图|Generate identity reference
身份图版本|Identity version
道具版本|Prop version
场景版本|Scene version
资产名称|Asset name
删除此资产？被引用时需先解除引用，历史媒体文件保留。|Delete this asset? Unlink it first if referenced. Historical media files are kept.
此造型被镜头引用，请先解除引用|Unlink this look from shots first
保留一个默认造型，可直接更换图片|Keep one default look; replace its image if needed
短剧名称|Project name
正在合片…|Composing film…
合片任务已入队，完成后可查看成片|Film export queued; view the film when finished
增强现有图片|Enhance existing image
模型目录暂未加载|Model catalogue unavailable
LLM列表暂未加载|LLM list unavailable
请在服务连接中配置ComfyUI|Configure ComfyUI in Connections
● ComfyUI 已连接|● ComfyUI connected
生成服务暂未连接|Generation service unavailable
项目加载失败|Project loading failed
重新加载|Reload
正在请求停止…|Requesting stop…
停止所有项目当前的|Stop the current
项任务，不删除历史结果| tasks across all projects? History is kept.
项等待停止或释放资源| tasks awaiting stop / resource release
本次|This round
项 · 已结束| tasks · Finished
项进行中| active
条记录| records
执行 |Running 
排队 |Queued 
停止中 |Stopping 
所有项目任务|Tasks across all projects
排队中|Queued
执行中|Running
停止中|Stopping
已停止|Stopped
已完成|Completed
失败|Failed
配音|Speech
文字|Text
合片|Film export
生成任务|Generation task
分析剧情与时长|Analysing story and timing
分镜 · 已保存|Storyboard · Saved
编写 H3 提示词|Writing H3 prompts
检查完成|Checks complete
批次|Batch
结束 |Finished 
等待执行|Waiting
正在释放生成资源|Releasing resources
完成 · 约剩|to finish · About
已复用|Reused
段规划，继续未完成部分| planned segments; continuing unfinished work
条视频提示词| video prompts
条生成提醒，部分镜头可能需要审核| generation notes; some shots need review
已自动修复|Automatically repaired
处规划数据| planning issues
停止尚未确认|Stop not confirmed
复制错误|Copy error
查看结果 ↗|View result ↗
恢复配音结果|Recover speech result
再次停止|Retry stop
■ 停止|■ Stop
提交 |Submitted 
开始 |Started 
执行耗时|Elapsed
暂无任务|No tasks
错误信息已复制|Error copied
已选中错误信息，可按 Ctrl+C 复制|Error selected; press Ctrl+C to copy
正在停止…|Stopping…
已发出|Sent stop requests for
项任务的停止请求| tasks
当前没有需要停止的任务|No tasks to stop
停止请求失败|Stop request failed
个项目| projects
删除于|Deleted
最早清理|Earliest cleanup
恢复项目|Restore project
恢复|Restore
回收站是空的|Trash is empty
项异常记录未处理| unresolved records
项目已恢复|Project restored
永久删除回收站中的|Permanently delete
清空后无法恢复。|This cannot be undone.
已清理|Removed
个项目，释放约| projects, freeing about
部分项目清理失败，请查看日志|Some projects could not be removed; check the log
手动清空|Manual cleanup
自动清理|Automatic cleanup
清理异常|Cleanup error
暂无清理记录|No cleanup records
媒体放大查看|Media viewer
滚轮缩放 · 拖动画面移动|Scroll to zoom · Drag to pan
缩小|Zoom out
放大|Zoom in
适应窗口|Fit to window
关闭放大查看|Close viewer
图片放大查看|Image viewer
提示词按|Prompt written for
编写，当前视频模型为|; current video model:
方式编写，当前为|method; current method:
时长已修改，结构化时间轴已过期|Duration changed; the structured timeline is outdated
需重新生成提示词|Regenerate the prompt
点“重写提示词”。|Click Rewrite prompt.
首次安装与 Agent 自动配置|Setup & Agent configuration
连接你自己的模型服务；设置保存在本机，不随项目导出。|Connect your own model services. Settings stay on this installation and are excluded from project exports.
文字与分镜|Text & storyboards
OpenAI 兼容服务地址|OpenAI-compatible URL
默认文字模型|Default text model
请先获取模型列表|Fetch the model list first
手动填写服务实际使用的模型 ID|Enter the model ID used by the service
手动模型 ID|Manual model ID
手动填写模型 ID|Enter model ID manually
从服务动态获取，无需记忆模型名称。|Fetch models from your service; no need to remember their names.
API 密钥|API key
可选；留空保留已有密钥|Optional; leave blank to keep the saved key
图片分析模型|Vision model
可选，须支持图片输入|Optional; must accept images
清除已保存的 API 密钥|Clear saved API key
获取模型列表 / 测试连接|Fetch models / Test connection
图片与视频|Images & video
ComfyUI 地址|ComfyUI URL
测试 ComfyUI 连接|Test ComfyUI
角色配音|Character speech
IndexTTS 服务地址|IndexTTS URL
不使用配音可留空|Leave blank if speech is not needed
测试配音连接|Test speech service
访问保护|Access protection
设置访问密码|Set access password
至少10个字符；留空不修改|At least 10 characters; leave blank to keep unchanged
默认仅本机访问。开放局域网前请设置密码，其他 Agent 可使用 Bearer 访问密码。|Local access by default. Set a password before enabling LAN access. Agents can use it as a Bearer token.
保存服务连接|Save connections
工作流|Workflow
导入 ComfyUI 的 API 格式 JSON；不包含或下载模型权重。|Import ComfyUI API-format JSON. Model weights are not included or downloaded.
正在获取模型…|Fetching models…
请选择模型|Select a model
请获取列表，或使用手动填写|Fetch the list or enter an ID manually
未在此服务列表中|Not listed by this service
已保存|Saved
原选择不在当前列表，请重新选择，或明确改用手动填写。|The saved model is not listed. Select another or use manual entry.
服务提供一个模型，已自动选中。|The service provides one model; selected automatically.
已获取 |Fetched 
个模型，请选择；保留已有选择。| models. Select one; your saved selection is kept.
无法获取模型列表，可手动填写模型 ID。|Could not fetch models. You can enter a model ID manually.
返回列表选择|Choose from list
正在获取模型列表…|Fetching model list…
连接成功，模型列表已更新。|Connected; model list updated.
无法获取模型列表|Could not fetch model list
可使用手动填写。|Manual entry is available.
当前保留本机专用工作流；现有模型与工作流不变。通用导入在独立安装版启用。|Local workflows and models are preserved. Generic import is available in the standalone installation.
已导入 · 未实机验证|Imported · Not yet tested
检查依赖|Check dependencies
尚未导入工作流，可以先创建项目与编写剧本。|No workflows imported yet. You can create projects and write scripts first.
节点与模型依赖检查通过；尚未执行生成|Node and model dependencies passed; generation has not been tested
正在读取连接设置…|Loading connection settings…
已配置；留空保留已有密钥|Configured; leave blank to keep the saved key
访问密码已设置|Access password set
尚未设置访问密码|Access password not set
服务地址已更改，请先获取模型列表，或使用手动填写|Service URL changed. Fetch models or use manual entry.
请获取模型列表后选择模型，或手动填写模型 ID|Fetch models and select one, or enter a model ID manually
原模型不在当前服务列表中，请重新选择，或改为手动填写|Saved model not listed. Select another or use manual entry.
正在测试连接…|Testing connection…
工作流文件最多4MB|Workflow file must be under 4 MB
这是画布格式，请从 ComfyUI 导出 API 格式|This is canvas format. Export API format from ComfyUI.
请选择有效的API工作流JSON|Select valid API workflow JSON
不映射|Not mapped
提示词（必填）|Prompt (required)
随机种子|Random seed
宽度|Width
高度|Height
时长（秒）|Duration (seconds)
帧数|Frame count
帧率|Frame rate
首帧输入|First-frame input
第1张参考图|Reference image 1
第2张参考图|Reference image 2
第3张参考图|Reference image 3
第4张参考图|Reference image 4
首次导入需确认一次参数映射，之后生成自动填入。|Confirm input mappings once; future tasks fill them automatically.
视频生成方式|Video method
文字生成|Text-to-video
音频驱动|Audio-driven
音乐驱动|Music-driven
图像＋视频参考|Image + video references
视频放大|Video upscale
视频补帧|Video interpolation
提取参考资产|Extract reference assets
生成剧本|Generate script
生成分镜|Generate storyboard
生成视频提示词|Write video prompts
输出节点|Output node
计算帧数时使用的帧率|Frame rate for frame-count calculation
视频须映射“时长”或“帧数”。资产参考须按顺序映射参考图；依赖检查通过也不代表实际生成已验证。|Map duration or frame count for video, and reference images in order. Dependency checks do not verify generation quality.
确认映射并导入|Confirm mappings & import
已导入 |Imported 
请点击检查依赖，再做一次低分辨率生成验证。|Check dependencies, then test a low-resolution generation.
从剧本提取资产|Extract assets from script
正在提取资产…|Extracting assets…
准备参考资产|Prepare reference assets
从已审核剧本提取，确认人物、造型、场景与道具后再生成分镜。|Extract from the reviewed script. Confirm characters, looks, scenes and props before creating shots.
下一步：分镜|Next: storyboard
有未结束任务时不可清空；清空前会确认并保留备份|Finish or stop active tasks first. Confirmation and a backup are required before clearing.
清空全部资产|Clear all assets
规划检查通过|Planning checks passed
发现待处理问题|Issues need attention
镜待编写提示词| shots need prompts
基于检查时内容；不检查实际图片或视频质量。|Checks the content at that time, not actual image or video quality.
✧ 继续完成分镜|✧ Continue storyboard
✧ 生成分镜|✧ Generate storyboard
正在生成分镜…|Generating storyboard…
自动规划、关联资源、编写提示词并检查；可恢复的写作问题在内部处理|Plan, link references, write prompts and check automatically. Recoverable writing issues are handled internally.
更多操作|More actions
仅重新规划|Replan only
仅编写提示词|Write prompts only
重写已有提示词|Rewrite existing prompts
分镜规范 ↗|Storyboard guide ↗
当前没有可清空的|Nothing to clear:
项参考资产（含人物造型、声线与音频资产）？| reference assets (including looks, voices and audio assets)?
保留剧本、分镜及已生成的镜头媒体，解除资产关联；提示词中的 @引用转为普通文字。旧提取候选失效。|Keeps script, shots and generated media. Unlinks assets and converts @mentions to plain text. Old extraction candidates expire.
个分镜及镜头历史关联？| shots and their history links?
保留剧本和参考资产，取消当前合片入口。|Keeps the script and assets; clears the current film link.
会保留清空前的数据备份，原媒体文件不删除。|A data backup is kept. Original media files are not deleted.
项资产| assets
个分镜| shots
已清空|Cleared
清空前数据已备份|Data backed up before clearing
未清空|Not cleared
本轮没有此类候选，请结合剧本核对。|No candidates of this type this round; check against the script.
旧结果没有此类候选，建议重新提取检查遗漏。|Old results have no candidates of this type; extract again to check omissions.
待确认|Pending review
正在识别人物、场景、道具和造型，可在任务队列停止。|Identifying characters, scenes, props and looks. Stop from the task queue if needed.
提取已停止|Extraction stopped
资产提取未完成|Asset extraction incomplete
已有资产保持不变。|Existing assets are unchanged.
资产已清空，旧候选已失效。请重新提取。|Assets cleared; old candidates expired. Extract again.
这是旧版提取结果，请重新提取，生成完整的身份与妆造提示词。|Old extraction format. Extract again for complete identity and look prompts.
剧本已修改，请重新提取后确认。|Script changed. Extract again before confirming.
已确认|Confirmed
身份图出图提示词|Identity image prompt
出图提示词|Image prompt
可在参考资产中补充。|Add details in Reference assets.
查看推演补全项|View inferred details
采用新提示词替换已有描述|Replace existing description with the new prompt
复用|Reuse
未明确服装细节|Clothing details unspecified
已有造型将复用|Existing look will be reused
若为已有造型，采用新提示词|For an existing look, use the new prompt
角色造型 · 勾选后新增或复用|Character looks · Select to add or reuse
保存到|Save to
的资产匹配| asset match
没有识别到需要新增的资产，可继续使用现有资产生成分镜。|No new assets found. Continue with existing assets.
资产提取候选|Extracted asset candidates
资产候选|Asset candidates
确认前不会写入参考资产|Assets are saved only after confirmation
出图规范 ↗|Image guide ↗
确认选中资产|Confirm selected assets
保留现有并收起|Keep existing & close
查看下方资产|View assets below
默认保留已有文字；勾选更新时只替换提示词，保留图片、历史、默认造型和声线。不自动出图。|Existing text is kept by default. Updating replaces prompts only, keeping images, history, default looks and voices. Images are not generated automatically.
资产提取已加入队列，完成后在参考资产页确认候选|Extraction queued. Review candidates in Reference assets when finished.
正在确认…|Confirming…
已更新|Updated
处提示词| prompts
个造型，复用| looks; reused
先整理参考资产？|Prepare reference assets first?
目前还没有参考资产。可先从剧本提取并确认，也可以继续生成分镜，稍后再补资源。|No reference assets yet. Extract and confirm them now, or create shots and add assets later.
先提取资产|Extract assets first
继续生成分镜|Continue storyboard
跟随本镜造型 / 默认造型|Shot look / default look
指定造型|Specific look
输入 @ 选择角色造型、场景或道具|Type @ to select a look, scene or prop
输入 @ 关联资产|Type @ to link assets
@ 插入|@ Insert
查看实际提交|View actual inputs
尚无图片|No image yet
没有匹配的角色、造型、场景或道具|No matching characters, looks, scenes or props
原文保留，@引用按实际传图顺序展开；这不保证模型正确分配台词。|Text is kept; @mentions follow actual reference order. This does not guarantee correct dialogue attribution.
所选造型|Selected look
参考图|Reference image
请输入这台片场设置的访问密码。|Enter this installation's access password.
访问密码|Access password
进入工作台|Enter studio
登录失败|Sign-in failed
返回工作台|Back to studio
把操作规范交给你的 Agent，让它按真实字段、接口和任务状态制作短剧。|Give your Agent the operating guide so it uses real fields, APIs and task states.
完整控制手册|Full control guide
分镜字段|Shot schema
接口发现|API discovery
给外部 Agent 的一句话|Instructions for your Agent
请先读取本平台 /AGENTS.md 和 /agent/guide.md，再通过 HTTP API 操作。创作内容由你直接保存，生成任务确认 completed 后再继续。不要重复提交抽卡任务，不覆盖已有镜头和历史版本；没有实际检查结果时不要标记审核通过。|Read /AGENTS.md and /agent/guide.md first, then use the HTTP API. Save creative content directly and confirm generation tasks are completed before proceeding. Do not resubmit generation tasks or overwrite existing shots and versions. Do not mark media approved without inspecting it.
当前能力|Capabilities
HTTP API 已可用。先读取项目和字段规则，再保存剧本、资产和分镜，按项目默认或镜头独立方案，使用参考资产直出视频或首帧生成视频，再合片。|Read project data and schemas through the HTTP API. Save scripts, assets and shots, generate from reference assets or first frames with project or per-shot settings, then compose the film.
需要 Agent 有 HTTP 或终端工具，且网络能访问此平台。当前没有已部署的 MCP 服务；已接入人物造型/声音包、音频资产与IndexTTS配音、真实图片独立观察、共享已读与制作完成标记；观察仍可能误判，尚无视频分析或自动审核、放行、重试执行器。|Your Agent needs HTTP or terminal tools and network access to Shotdesk. No MCP server is deployed. Character looks and voices, audio assets, IndexTTS, image inspection, shared read states and completion marks are available. Inspection may be wrong; automated video review and retry execution are not available.
完整操作说明|Operating guide
正在读取控制手册…|Loading control guide…
读取失败|Could not load
请点击上方「完整控制手册」直接读取。|Open Full control guide above to read it directly.
任务|Task
角色|Character
人物|Character
场景|Scene
道具|Prop
音频|Audio
图片|Image
视频|Video
声线|Voice
造型|Look
默认|Default
未完成|Incomplete
完成|Complete
收起|Close
关闭|Close
镜头|Shot
时长|Duration
秒|s
小时|h
分|min
预计|Estimated
约 |About 
暂无|None
新增|Added
新建|Create
新|New
全身参考|Full-body reference
服装参考|Clothing reference
添加角色|Add character
添加|Add
删除|Delete
取消|Cancel
可选|Optional
类型|Type
资产|Assets
清空|Clear
开始|Started
提交|Submitted
人|C
段| segments
条| records
个| items
项| tasks
镜| shots
`;
for(const line of entries.split('\n')){const i=line.indexOf('|');if(i>0)translations[line.slice(0,i)]=line.slice(i+1)}
// Longest match first. Only source-authored UI fragments reach this function.
const keys=Object.keys(translations).sort((a,b)=>b.length-a.length);
const pattern=new RegExp(keys.map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'g');
function translate(s){return locale==='en'?String(s).replace(pattern,k=>translations[k]):String(s)}
function fragment(s){
 // Keep enum values, selectors and binding attributes intact, even when Chinese.
 return String(s).split(/((?:\b(?:value|data-[\w-]+|id|class|name|href|src)\s*=\s*)(?:"[^"]*"|'[^']*'))/g).map((x,i)=>i%2?x:translate(x)).join('');
}
function text(s,...values){if(Array.isArray(s)&&Object.hasOwn(s,'raw'))return s.reduce((out,part,i)=>out+fragment(part)+(i<values.length?values[i]:''),'');return fragment(s)}
function apply(root=document){root.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=translate(el.dataset.i18n));for(const attr of ['title','placeholder','aria-label'])root.querySelectorAll('[data-i18n-'+attr+']').forEach(el=>el.setAttribute(attr,translate(el.getAttribute('data-i18n-'+attr))));document.documentElement.lang=locale==='en'?'en':'zh-CN';if(document.documentElement.dataset.title)document.title=translate(document.documentElement.dataset.title)}
async function setLanguage(value){try{await globalThis.ShotdeskBeforeLocaleChange?.();locale=value==='en'?'en':'zh';try{localStorage.setItem(storageKey,locale)}catch{};location.reload()}catch(error){const select=document.querySelector('.ui-language');if(select)select.value=locale;alert(error.message)}}
function mount(){apply();const select=document.createElement('select');select.className='ui-language';select.setAttribute('aria-label','界面语言 / Interface language');select.innerHTML='<option value="zh">中文</option><option value="en">English</option>';select.value=locale;select.onchange=()=>setLanguage(select.value);const target=document.querySelector('header .spacer')||document.querySelector('.agent-top')||document.querySelector('form');if(target)target.insertAdjacentElement(target.matches('.spacer')?'beforebegin':'afterbegin',select)}
globalThis.ShotdeskI18n={text,translate,apply,setLanguage,get language(){return locale}};
if(typeof document!=='undefined'){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount()}
})();
