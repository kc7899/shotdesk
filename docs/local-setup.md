# 本地安装、Agent 配置与排错

适用版本：0.1.0-preview.1。支持已有 OpenAI 兼容 LLM、ComfyUI 和可选的专用 IndexTTS 服务。Shotdesk 本身不安装模型、不提供任意云端视频或通用 TTS 接入。

## 交给 Agent

对 Codex 或其他有终端权限的 Agent 说：

> 读取这个 Shotdesk 目录中的 AGENTS.md 和 docs/skills/shotdesk-setup/SKILL.md。检查当前环境，优先复用已有服务，配置 Shotdesk 并执行两镜头验收。修改已有服务、下载模型或消耗付费额度前说明影响。保留现有项目。完成后分别报告连接、依赖和实际生成结果。

不支持自动发现 Skill 的 Agent 也可直接读取该文件，无须安装插件。只给网站地址时，读取 `/AGENTS.md` 与 `/agent/setup.md`；安装检查需要取得主机终端权限，HTTP 权限不能代替终端权限。

## 安装工作台

需要 Docker Engine 和 Compose v2。下载发布包并解压到独立目录：

```bash
cp .env.example .env
docker compose up -d --build
```

默认入口：<http://127.0.0.1:1258>。不要把另一套生产环境的 `.env` 或私有 Compose 覆盖文件复制过来。若端口被占用，在 `.env` 设置 `SHOTDESK_PORT`。首次联网构建需要下载 Python 基础镜像与 FFmpeg；运行工作台不要求 GPU。AI 推理机器的 GPU、内存和磁盘要求由实际模型决定，不能仅依据工作台的最低要求采购设备。

已有 Python 3.12+ 和 FFmpeg/ffprobe 时，也可运行 `python3 server.py`。原生运行建议使用独立目录或虚拟环境；本项目没有额外 Python 依赖。

## 地址怎么填

| 部署位置 | Shotdesk 中填写 |
| --- | --- |
| 原生运行，同机模型服务 | `http://127.0.0.1:端口` |
| Docker 工作台，模型在宿主机 | `http://host.docker.internal:端口`；模型服务需接受该容器来源的连接 |
| 同一 Docker 网络 | 对应服务名，例如 `http://comfyui:8188` |
| 另一台机器 | 可访问的局域网地址或带 HTTPS 的服务域名 |

容器里的 `127.0.0.1` 指容器自己。必须从工作台所在的网络测试，不是只在你的浏览器里打开服务首页。

## 自动检查和配置

在解压目录运行（主机需 Python；也可在容器内用相同脚本）：

```bash
python3 scripts/shotdesk_setup.py doctor
# 可选：检查少量已知本机端口，不扫描局域网，不启动模型。
python3 scripts/shotdesk_setup.py doctor --probe-local
```

输出区分 `not_configured`、`unreachable`、`connected`。`generation_verified:false` 是正常的：访问成功还不是实际生成验证。主机没有 FFmpeg 不代表容器内没有；合片所需工具要检查实际执行环境。

LLM 地址使用 OpenAI 兼容 `/v1`，从服务 `/models` 获取真实模型 ID。不要把云端视频 API 填到 LLM 或 ComfyUI 地址。配音可留空；当前 ComfyUI/IndexTTS 连接器不支持独立 Bearer/Basic 密钥，不支持需要认证的端点，不能通过在 URL 中嵌入密码绕过。工作台密码仅保护 Shotdesk，不保护直接开放的模型服务端口。

如需自动保存，将以下模板另存为私有 JSON，填写真实地址和服务公布的模型 ID。API 密钥只在需要时加入 `llm_api_key` 字段；不需要的可选字段直接删除。

```json
{
  "llm_url": "http://host.docker.internal:8000/v1",
  "llm_model": "实际模型ID",
  "comfy_url": "http://host.docker.internal:8188"
}
```

```bash
chmod 600 private-settings.json
python3 scripts/shotdesk_setup.py configure --config private-settings.json
python3 scripts/shotdesk_setup.py doctor
```

脚本先测试，再通过 API 保存；有活动任务时服务端拒绝改配置。它不修改项目、不重启服务。只有明确要保留暂时离线的地址时才使用 `--allow-offline`；若服务不提供模型列表但已确认聊天接口可用，也可用它保存明确填写的模型 ID，之后必须实际验证。保存后妥善移除临时凭据文件，正式设置由服务端私有保存。不要把配置文件、令牌或终端输出中的私有内容提交 GitHub。

启用密码时，命令的 `--token-file <私有令牌文件>` 放在 `doctor`/`configure` 前，也可通过 `SHOTDESK_TOKEN` 环境变量传入。不要把真实令牌写在示例、URL 或公开命令行中。

## 安装模型与工作流

本版优先复用用户已有的 LLM 与 ComfyUI；没有服务时，由 Agent 根据用户设备和选定模型的官方部署说明另行安装。不要自动下载一个预设的大模型或重启其他服务。

导入 ComfyUI **API 格式**，不是画布 JSON。参数映射见 [workflows.md](workflows.md)。`examples/sd15-image.json` 和 `examples/wan21-video.json` 是格式示例，不代表已安装权重，也不是所有硬件的推荐模型。资产参考必须有相应参考图输入映射；不要为没有参考能力的工作流填写一个虚假的名额。

上传定义：POST `/api/workflows/import {"workflow":定义,"replace":false}`；检查：POST `/api/workflows/check {"id":"实际工作流ID"}`。检查依赖不下载模型，不执行 GPU 推理。已存在同名工作流时先确认，不直接覆盖。

IndexTTS 可选适配器要求：GET `/api/jobs`、POST `/api/generate`、任务列表返回任务状态与 `takes` 信息；结果通过 GET `/audio/<文件名>` 下载。`/api/generate` 接收 `text`、`emotion`、base64 `audio`、`filename`、用于去重的 `label`；没有独立上传声线接口要求。以 `server.py` 中的 speech 调用为契约，不把任意 TTS 端点当兼容服务。本版没有独立语音服务安装包或自动模型下载器。

## 第一次两镜头验收

准备已导入且依赖通过的图片、视频工作流。以下 `IMAGE_ID`、`VIDEO_ID` 均替换成目录中的实际 ID；不要照抄占位名。

```bash
python3 scripts/shotdesk_smoke.py --image-model IMAGE_ID --video-model VIDEO_ID --video-mode text --allow-generate --report smoke-report.json
```

默认创建一个全新的测试项目：生成一张桌面场景参考、两个短视频、合片，再用 ffprobe 检查可播放的视频流。支持 `--video-mode reference` 和 `first_frame`，但工作流必须支持相应输入。`--with-llm` 额外实际生成剧本与分镜，并只取新测试项目中的前两镜执行；耗时和视频长度由模型输出决定。模型有原生最小尺寸/时长时使用其支持范围，不以低于范围的参数试验。脚本不对每一类硬件承诺相同预览尺寸。

主机没有 ffprobe 时，可在包含 FFmpeg 的 Shotdesk 容器内运行脚本，把报告保存在 `/app/data/`，例如：

```bash
docker compose exec shotdesk python3 /app/scripts/shotdesk_smoke.py --image-model IMAGE_ID --video-model VIDEO_ID --video-mode text --allow-generate --report /app/data/smoke-report.json
```

每项任务有明确超时；超时只请求停止自己的任务，不停共享 ComfyUI 的其他任务。失败报告保留新项目和任务 ID，可在任务队列查看；重新运行会创建新的测试项目，不会覆盖旧项目。脚本不自动删除测试项目、不自动重试付费生成。

生成成功后仍要亲自播放视频、听声音，检查画面、资源和台词关系。技术验收通过不等于艺术质量合格。测试图、视频和工作流由你自己的服务产生；发布包不包含私人素材。

## 常见问题的定位顺序

1. 工作台打不开：检查容器启动、端口和数据目录权限。
2. 401/403：核对服务类型与对应密钥；Shotdesk 密码不是模型密钥。
3. 连接失败：从工作台网络测试地址，先解决 DNS/端口，不急于改模型。
4. 依赖失败：核对 API 图、自定义节点、权重名和映射，先做单项测试。
5. 推理失败：查看该任务与 ComfyUI 的具体日志；不要连续追加全量任务。
6. 视频不播放：实际下载并用 ffprobe 检查；合片需要工作台执行环境内的 FFmpeg。

停止、重启和恢复行为及备份操作见 [operations.md](operations.md)。支持边界见 [release-notes.md](release-notes.md)。
