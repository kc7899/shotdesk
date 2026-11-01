# Local setup and Agent configuration

Version: 0.1.0-preview.1. Shotdesk connects existing OpenAI-compatible LLM, ComfyUI and optional dedicated IndexTTS services. Installing the studio does not install inference models.

Give Codex or another Agent with terminal access this instruction:

> Read AGENTS.md and docs/skills/shotdesk-setup/SKILL.md. Check this environment, reuse existing services, configure Shotdesk and verify a two-shot project. Preserve existing projects. Explain effects before large downloads, paid calls or restarting shared services. Report connection, dependency and actual generation results separately.

Agents without Skill discovery can read the file directly. A running server exposes `/agent/setup-skill.md`; installation also requires host terminal access.

## Install

Install Docker Engine and Compose v2, extract the public release into a separate directory, then run:

```bash
cp .env.example .env
docker compose up -d --build
```

Open <http://127.0.0.1:1258>. Initial builds download Python and FFmpeg packages. The studio does not require a GPU; model requirements depend on the model and inference backend. Alternatively use Python 3.12+, FFmpeg/ffprobe and `python3 server.py` with no additional Python packages.

For a model on the same native host use `127.0.0.1`; from Docker use a reachable network service name or `host.docker.internal`. Inside a container, localhost means that container. For another machine use its reachable LAN address or HTTPS domain. Test from the studio's network.

## Diagnose and configure

```bash
python3 scripts/shotdesk_setup.py doctor
# Optional: probe a few known loopback ports, without starting services.
python3 scripts/shotdesk_setup.py doctor --probe-local
```

The report distinguishes not configured, unreachable and connected. Connection success does not set generation verification. Missing host FFmpeg does not mean it is missing in the server container.

Fetch the LLM's real model IDs from `/v1/models`. Create a private JSON file with `llm_url`, `llm_model` and `comfy_url`; optionally add `llm_api_key`. Use actual values, not placeholders. Never commit credentials.

```bash
chmod 600 private-settings.json
python3 scripts/shotdesk_setup.py configure --config private-settings.json
python3 scripts/shotdesk_setup.py doctor
```

The helper tests endpoints before saving through the guarded API. It does not edit projects or restart services. Use `--allow-offline` only when intentionally saving offline endpoints. With studio access protection, place `--token-file <private-file>` before the subcommand or set `SHOTDESK_TOKEN`. Remove temporary credential files after use.

The ComfyUI and dedicated IndexTTS connectors currently do not support independent authentication. A studio password does not authenticate or protect the model servers. A cloud video API is not a ComfyUI URL, and arbitrary TTS endpoints are not compatible.

## Workflows and verification

Import a ComfyUI **API-format** graph, map prompt/seed/size/duration and reference inputs, then check dependencies. [Workflow format](workflows.md). Examples demonstrate mapping only; weights and custom nodes are not installed or distributed. IndexTTS is optional and uses this project's specific `/api/generate`, `/api/jobs` and `/audio/` contract.

Once you have imported real working image/video models, replace IMAGE_ID and VIDEO_ID below:

```bash
python3 scripts/shotdesk_smoke.py --image-model IMAGE_ID --video-model VIDEO_ID --video-mode text --allow-generate --report smoke-report.json
```

This creates a new test project, generates an asset image and two videos, exports a film and probes it. `reference` and `first_frame` modes require matching workflows. `--with-llm` additionally generates script/storyboard and limits the new project's compute run to its first two shots. Respect your model's native sizes and durations. Each task has a timeout; only that test task is stopped on timeout. Re-running creates a new project rather than overwriting existing work.

If FFmpeg/ffprobe is only in Docker:

```bash
docker compose exec shotdesk python3 /app/scripts/shotdesk_smoke.py --image-model IMAGE_ID --video-model VIDEO_ID --video-mode text --allow-generate --report /app/data/smoke-report.json
```

Watch and listen to actual output afterwards. Valid media streams and successful jobs do not prove artistic quality or correct dialogue attribution. Test reports contain project/job IDs; media and service credentials are excluded from the public release.

## Recovery

Keep the data/workflow volumes and private settings. JSON project exports are not full backups. Do not use `docker compose down -v` to upgrade. Wait for tasks or stop and confirm them before restarting. On restart, saved remote task IDs are polled rather than resubmitted; unknown submission outcomes fail visibly to avoid duplicates. Some text/export tasks cannot resume transparently.

See [operations](operations.md), [support and limits](release-notes.md), and the [detailed Chinese guide](local-setup.md). This is a single-user preview, without direct cloud video support or automatic model installation.
