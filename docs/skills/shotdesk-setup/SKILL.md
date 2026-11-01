---
name: shotdesk-setup
description: Install, configure and diagnose Shotdesk with existing local or LAN LLM, ComfyUI and optional IndexTTS services. Use for environment setup and connection failures; use the normal Shotdesk guide for creative production.
---

# Shotdesk setup and diagnosis

Read `README.md` and `docs/local-setup.md` from the checkout first. If given only a running URL, read `/AGENTS.md` and `/agent/setup.md` to find deployment instructions. Reuse installed services. A cloud video API is not a ComfyUI endpoint. Do not replace a user's working model, storyboard scheme, projects or workflows.

1. Run `python3 scripts/shotdesk_setup.py --url <studio> doctor`. This is read-only. `--probe-local` optionally probes a few documented loopback ports; it does not discover other machines or start models. For authentication use `SHOTDESK_TOKEN` or a private `--token-file`, never a token in a URL or printed shell argument.
2. If Shotdesk is absent, use an isolated checkout and the standard Compose file. The server and model services are separate installations. Confirm available GPU/storage and the desired models before downloading weights or installing custom nodes. Follow the selected model's current upstream instructions; there is no universal GPU requirement.
3. For Docker, test URLs from the Shotdesk container's network. Container `localhost` is not the host. Prefer existing network service names or `host.docker.internal`; another machine needs its reachable address. Do not change exposure or firewall rules to solve a hostname mistake.
4. Fetch the service's `/v1/models`. Keep the existing model if valid, auto-select only a sole model, otherwise ask the user to choose or honor their named model. Do not invent model IDs. Store supplied settings in a private temporary JSON file, then run `configure --config <file>` through the guarded settings API. The helper tests connections before saving and refuses settings changes while tasks are active. Remove temporary credential files when finished. An active service configuration is not a generation-quality claim.
5. Import the user's ComfyUI API workflow through `/api/workflows/import` and explicitly map inputs. Run `/api/workflows/check`. Report missing nodes/weights without silently replacing them. Preview reference bindings before generation. IndexTTS is optional and requires this project's documented API contract; arbitrary TTS URLs are incompatible.
6. With authorization for a bounded compute test, run `scripts/shotdesk_smoke.py` as described in `docs/local-setup.md`. It creates a new test project, never edits a user project, and stops only its own task on timeout. A passed media probe is not visual approval. Inspect the actual exported video separately if tools permit.
7. Report connected, dependencies checked and generation verified separately, with actual project/job IDs. If a service fails, preserve existing project data, identify the layer (address/auth/dependency/inference/media export), apply one supported correction and retest. Stop after two unsuccessful repair attempts and report evidence; do not loop, globally interrupt ComfyUI, restart shared services or repeatedly submit billable tasks.

Existing user authorization remains applicable. Obtain missing credentials or authorization only for actions that require them, such as paid calls, large downloads or restarting a shared service. Deliver a working configuration and real verification results, or explicitly name the remaining external blocker.
