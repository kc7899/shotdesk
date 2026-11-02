# Shotdesk 研发

Python 3.12+标准库后端、原生HTML/CSS/JS；FFmpeg负责音视频检查和合片。不需要npm构建。

- server.py：项目/资产/媒体API、提示词实际绑定、HTTP与访问保护。
- runtime_config.py：服务设置、私有凭据、单用户会话。
- workflow_transport.py：独立ComfyUI工作流导入/依赖检查/参数映射。
- task_queue.py：持久队列、任务级停止、输入快照、提交保护。
- h3_structured.py：当前h3-structured-v2创作方案，本次不改创作规则。
- storyboard.py及历史导演模块：方案分派与旧格式兼容。可选回滚包不属于独立版必备组件。
- review_contract.py、trash_manager.py：审核挂钩及七天回收站。

运行测试：
```bash
python3 -m unittest discover -s tests -t . -p 'test_*.py'
for f in tests/frontend/test_*.js; do node "$f" || exit; done
```
历史模型能力测试使用`tests/support.py` 静态目录，不要求本机安装模型或存在其他仓库；通用适配器另有假的ComfyUI服务进行HTTP端到端测试。真实GPU推理须独立记录，不把mock测试称为画面验收。

本机迁移：原compose和专用模型连接保留在.gitignore忽略的.local/及.env；日常docker compose通过本机COMPOSE_FILE叠加，不属于公开安装依赖。公开候选只使用标准compose、Dockerfile和默认通用适配器。

发布：scripts/export_release.py使用白名单生成候选，不直接上传工作目录。它不发布GitHub、不恢复用户项目、不自动选择代码许可证。第三方材料按THIRD_PARTY_NOTICES检查。

## UI localization and branding

Product branding is Shotdesk / 片场. Historical protocol fields remain compatible; do not display another project's branding as a current feature. Keep required credits in THIRD_PARTY_NOTICES.md.

`static/i18n.js` owns the zh/en UI catalogue. Use `ui('authored label')` or the `ui` template tag for source-authored UI text. Template substitutions are deliberately left untouched: escape user content with `esc` before interpolating HTML. Do not pass entire rendered markup, user prompts or project names through translation. Preserve enum values and ID bindings; translate only their labels. Static HTML uses `data-i18n` and `data-i18n-title`/`placeholder`/`aria-label`. The browser locale is independent of `project.prompt_language`. Switching saves pending edits first and refreshes without a fixed delay. Unknown server errors and user-generated task details remain verbatim.

Run `node tests/frontend/test_i18n.js`, the existing JS checks, and `python3 -m unittest tests.backend.test_portable` after changes to shared locale delivery or authentication. Check desktop and narrow layouts in both languages. No external translation service or runtime dependency is required.

## Preview release acceptance

0.1.0-preview.1 adds scripts/shotdesk_setup.py (read-only doctor / guarded configure), scripts/shotdesk_smoke.py (opt-in new-project compute test), and docs/skills/shotdesk-setup/SKILL.md. Export with scripts/export_release.py, then --check-ready the exported directory. The checker rejects missing license/evidence, file tampering, unexpected files and unlicensed upstream originals. Keep controlled HTTP tests separate from GPU inference evidence in docs/release-validation.json.

The script output parser preserves literal invalid JSON escapes and makes at most one format retry; incomplete/truncated output never replaces a script. Scene/prop-only H3 storyboards do not require fabricated characters. Queue cancellation does not send an interrupt for tasks already removed from the upstream queue. Original Shotdesk code uses MIT; upstream verbatim references without a redistribution grant stay private.

## 测试目录

`tests/backend/` 存放当前后端测试，`tests/frontend/` 存放界面测试，`tests/legacy/` 保留历史方案兼容测试，`tests/support.py` 提供共享测试数据。请从项目根目录运行上述命令；使用平台不需要手动运行测试。

## Optional Ark AIGC asset sync

`ark_assets.py` implements the official CreateAssetGroup/CreateAsset/GetAsset flow without extra runtime dependencies. Its HMAC-SHA256 output is checked against an independently generated official Python SDK SignerV4 test vector. Upstream reference: https://github.com/volcengine/volc-sdk-python/blob/main/volcengine/auth/SignerV4.py (not redistributed). Local HTTP tests cover signed media fetches, review rejection, credentials, stale images, group reuse and no duplicate upload. These tests are not evidence of live account entitlement or review acceptance. Keep credentials in private settings and mappings in the project sidecar; never mix them into editable assets.

H3 codec dimension alignment: task_queue.align_h3_encoder_inputs inserts ImageResizeKJ (existing KJNodes dependency) with width/height=0, divisible_by=32, crop=disabled before minimaxh3video BlehTAEVideoEncode. This corrects odd intermediate dimensions from fractional upscaling without cropping. The helper is idempotent and runs for both legacy and portable transports. ComfyUI failures extract execution_error node/type/message, never current_inputs tensors. Installed-node CPU regression: 819×461 → 800×448, pixel_unshuffle(2) succeeds; this is not a full video quality check.
