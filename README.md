# 片场 · Shotdesk

**0.1.0-preview.1 · 本地服务预览版**

## 让 AI Agent 主导短剧制作，力求一键成片

Shotdesk 是面向 **AI Agent** 的短剧制作工作台。Agent 读取项目说明后，即可了解操作方式，按标准流程推进制作：

**内容 → 剧本 → 资产 → 分镜 → 首帧（按需）→ 视频 → 合片**

我们的目标是让 Agent 自主完成整个流程，尽量无需人工介入，直接交付成片。

工作台将 Agent 的制作进度、分镜和生成结果直观呈现。人工主要负责审查，也可以随时介入，对单个镜头进行调整、优化或重新生成，再交由 Agent 继续完成制作。

当前预览版已提供 Agent 操作说明与制作接口；自动完成的程度取决于所用 Agent、模型和工作流。“无人介入、一键成片”是项目持续推进的目标。

**AI Agent–driven short drama production, aiming for one-click filmmaking.**

Shotdesk is a production workspace built for AI agents. By reading the project instructions, an agent can learn how to operate it and follow the production workflow: content → script → assets → storyboard → optional first frames → video → final assembly.

Our goal is autonomous production from start to finish, with as little human intervention as possible. The workspace makes the agent’s progress, storyboards and generated results visible. People primarily review the work and can adjust or regenerate individual shots at any time before handing production back to the agent. Full unattended, one-click filmmaking is the goal; current automation depends on the agent, models and workflows in use.

界面支持中文 / English，顶部可切换并记住选择；界面语言与项目提示词语言独立，不会翻译已有内容。

[English setup guide](docs/local-setup.en.md) · [Agent 自动配置与本地安装](docs/local-setup.md) · [运维和备份](docs/operations.md) · [支持范围与已知限制](docs/release-notes.md)

## 独立安装

需要 Docker Compose；LLM 服务由你提供，图片可连接自己的 ComfyUI；视频可选 ComfyUI 或云端 API。使用本地模型时由你自行部署 ComfyUI。本仓库不下载模型权重、不自动启动 GPU 服务。

```bash
cp .env.example .env
docker compose up -d --build
```

打开 <http://127.0.0.1:1258>，点击顶部“服务连接”：

1. 填写 LLM 的 OpenAI 兼容 `/v1` 地址及可选密钥，获取模型列表后选择。仅一个模型时自动选中，多个时保留已有选择或请你选择；不支持模型列表的服务可手动填写模型ID。
2. 填写 ComfyUI 地址并测试。Docker 访问宿主机通常使用 `http://host.docker.internal:8188`，不能使用容器内的 `localhost` 指代宿主机。
3. IndexTTS 是可选服务；不使用角色配音可留空。此适配器要求服务提供 `/api/jobs`、`/api/generate` 和 `/audio/<文件>`，并不是任意TTS端点。
4. 保存后导入 ComfyUI 的 API 格式 JSON，确认参数映射。`examples/` 提供图片、视频配置示例，默认不注册，模型权重缺失时会明确提示。

无需配置任何服务也能打开工作台、新建项目、编辑剧本与上传资产；AI生成需要对应服务和工作流。

也可使用 Python 3.12+ 和系统 FFmpeg：`python3 server.py`，默认仅监听本机。代码只使用 Python 标准库和原生浏览器 JavaScript，不需要 npm 构建。

## 第一个项目

1. 新建短剧，填写故事，生成并审核剧本。
2. 提取并确认角色、场景、道具；角色可包含多个造型和可选声线。
3. 上传或生成参考图，在“模型设置”选择导入的视频工作流与生成方式。
4. 生成分镜，检查人物、造型、对白和画面安排。默认方案为 **h3-structured-v2**，本次独立化改造不改变它的创作规则。
5. 首帧方案先生成/选定首帧；资产参考方案直接使用关联资产，不读取旧首帧。
6. 按镜头生成视频，可批量追加多轮。任务队列记录进展与耗时，并支持停止。
7. 选择采用版本，标记完成，按镜头顺序合片导出。

依赖检查通过只表示节点和选项存在，不代表工作流已完成实际推理验收。请先用低分辨率、短片段验证，尤其检查参考图顺序和台词说话人。

## 工作流

支持 ComfyUI API 格式图，通过节点输入映射 prompt、seed、width、height、duration/frames/fps、first_frame 或 image_0…N。可直接导入含 `graph` 和 `bindings` 的 Shotdesk 工作流配置，或在界面为原生 API JSON 设置映射。详细格式见 [工作流接入](docs/workflows.md)。

默认安装不会出现本机未提供的几十个模型。已导入、依赖检查和实机验证是不同状态。通用适配器当前支持图片、文字生视频、首帧和资产参考；音频/视频参考输入需要对应专用适配器，导入时不会伪装成支持。

## 云端视频：Seedance 与 MiniMax H3

在顶部 **服务连接 → 云端视频 → 添加云端视频服务**，选择协议，填写 API Key 和实际开放的模型 ID，保存后在项目“模型设置”选择该服务。可以添加多个服务，镜头仍支持独立选择。

- **火山方舟 / 兼容中转**：Seedance，默认地址 `https://ark.cn-beijing.volces.com/api/v3`。
- **MiniMax 官方 V2 / 兼容中转**：默认 `https://api.minimax.io`、`MiniMax-H3`，官方高质量完整模型，支持原生 768P / 2K、4–15整秒；与本地蒸馏工作流分开。
- **Replicate**：默认 `bytedance/seedance-2.5`，使用平台 API Key。
- **fal**：默认资产参考端点 `bytedance/seedance-2.5/reference-to-video`。文字、首帧端点需分别添加，并只勾选对应生成方式。

每种协议都支持自定义服务地址；中转站必须兼容所选协议，不是任意网址都能使用。默认模型 ID 是配置示例，请核对账号实际开放的版本、能力和收费。

角色采用所选造型图，参考图按关联资产顺序传入。首帧模式只传首帧，不混用资产图。云端支持文字、首帧和图片资产参考。火山方舟另支持在资产参考模式中显式勾选音频、视频联合参考：图片和音频用 data URL；视频由平台生成6小时有效、绑定单个任务和文件内容的签名链接。上传/生成音频可继续使用 IndexTTS。未勾选的素材不传入，首帧与联合参考不混用。尾帧输入仍未接通。

使用火山参考视频前，在该服务配置中填写“素材公网地址”，例如你已部署并可从公网访问的 Shotdesk HTTPS 域名。只需配置一次，平台自动产生每段视频的临时链接；不自动打洞、打开端口或公开整个目录。纯局域网地址无法供火山下载视频，未配置会在付费提交前提示。Files API 的 file_id 不等于视频生成的 asset:// 素材 ID，本版不会混用。

任务进入统一队列，结果下载到项目并保留历史。密钥仅保存在私有服务设置，留空保留、勾选清除才删除。保存设置不产生付费任务；提交结果不明时不会自动重提。停止受服务商限制：官方 H3 运行中无法立即取消，平台等待上游结束，期间可能继续计费。本次接口测试使用模拟服务，实际账号推理和画面质量须单独验证。

Cloud video providers are configured under **Service connections → Cloud video**. Supported protocols: Volcano Ark / compatible gateways, official MiniMax H3 V2, Replicate Seedance, and fal Seedance. Configure your own key and actual model ID, then select the service in project model settings. The integration supports text, first-frame and image-reference generation. Ark additionally supports explicitly enabled audio/video references alongside images. Audio uses data URLs; video uses single-file signed links valid for six hours and requires a one-time public HTTPS studio URL. No automatic public exposure or network tunnelling is performed. Credentials stay private; jobs share the queue and downloaded version history. Saving does not submit a paid job. Running official H3 jobs cannot be cancelled immediately. Protocol tests use local fake services; live paid generation still requires separate verification.

## Seedance 虚拟角色素材库（试验）

角色身份图和每个造型卡可点击“同步到 Seedance”，在工作台查看上传、审核中、可使用或拒绝原因。审核通过后，火山资产参考生成自动使用对应的 `asset://` ID；本地和 H3 仍使用图片。切换图片会提示需更新，不沿用旧图的审核结果。刷新审核只查询现有ID，不重复上传。

首次需在[方舟私域虚拟人像库](https://docs.volcengine.com/docs/ark/private-virtual-avatar-library-guide-preview?lang=zh)签署虚拟素材授权并开通所需权益；在“服务连接 → 火山方舟 → 虚拟角色素材库”配置 [AK/SK](https://console.volcengine.com/iam/keymanage)、项目名称与素材公网HTTPS地址。AK/SK 与视频 API Key 不同，素材和视频调用必须属于相同火山项目。官方素材库只接受可访问URL，本功能复用6小时单文件签名链接，不自动开放网络。普通视频服务不需要这些额外设置。

当前仅接入官方 AIGC 虚拟人像素材库，不做真人认证，不向中转站发送AK/SK。每个角色共用一个素材组，身份与造型各自审核。审核拒绝不自动反复上传，网络中断导致提交结果不明时保留记录并要求核对；停止同步仅停止本地等待，不删除已上传素材。审核超过10分钟时保存Processing状态，可稍后刷新。

同步映射独立保存在项目目录的 `ark-assets.json`，避免编辑保存覆盖审核结果；备份数据卷时保留此文件。项目JSON导出不包含这份映射。当前完成了本地模拟接口测试与官方SDK签名对照，尚未使用真实账号提交入库，真实审核能否通过取决于火山。

## 数据、备份与访问

Docker 默认使用两个独立命名卷：`shotdesk-data` 保存项目/媒体/设置，`shotdesk-workflows` 保存导入配置；实际名称由Compose项目名前缀决定，可用 `docker volume ls` 查看。重新构建镜像不会清空卷。不要使用 `docker compose down -v`，除非确实要删除所有数据。

原生运行的数据默认在 `data/`，可用 `SHOTDESK_DATA_DIR` 指定。服务设置保存在私有 `settings.json`，密钥不会返回给前端或进入项目导出。已有项目字段保持兼容。

默认仅本机访问。需要局域网使用时，先在服务连接里设置访问密码，再修改 `.env` 的 `SHOTDESK_BIND`；可设置 `SHOTDESK_ACCESS_TOKEN` 与 `SHOTDESK_REQUIRE_AUTH=1`。Agent 使用 `Authorization: Bearer <访问密码或环境令牌>`。远程部署请在可信反向代理后使用 HTTPS；本版是单用户工具，不提供多用户权限隔离。

## 常见问题

- **LLM模型列表为空**：检查 `/v1` 地址、密钥及服务实际公布的模型名；支持多个模型的网关可以直接接入。
- **ComfyUI连接成功但生成失败**：检查导入工作流的自定义节点、权重、输出节点及参数映射。只有画布格式的JSON不能直接运行。
- **参考图没生效**：先看实际提交预览，确认工作流为资产参考方案且所有参考图输入都已映射；不能仅靠提示词中的名字传图。
- **离线服务**：不影响已保存项目和媒体查看；不会自动切到其他模型或云端。
- **停止中**：远端服务是否支持精确取消会影响释放时间；没有确认停止时不会显示已停止。

## Agent、研发与发布

[Agent说明](AGENTS.md) · [API流程](docs/agent-control.md) · [研发说明](DEVELOPMENT.md) · [第三方来源](THIRD_PARTY_NOTICES.md)

发布候选由 `python3 scripts/export_release.py --output /tmp/shotdesk-release` 生成。使用明确白名单，排除数据、回收站、备份、截图、私有模型表和本机连接。原开发目录不是可直接上传的发布目录。

原始代码采用 [MIT](LICENSE)。第三方材料保留各自许可，见来源说明；不包含模型权重、私人数据或未明确许可的上游提示词原文。从本仓库 Releases 下载预览版发布包。发布前可运行 `python3 scripts/export_release.py --check-ready <候选目录>`，检查许可、验收记录和文件完整性。
