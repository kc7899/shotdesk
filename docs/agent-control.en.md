# Shotdesk API workflow

Read [AGENTS.md](/AGENTS.md) for the current operating rules. Discover live fields through `/api/shot-schema`, `/api/asset-schema` and `/api/agent-info`. Write requests use JSON. Read the latest project before editing; do not reuse IDs from old conversations.

1. **Project and script:** GET/POST `/api/projects`, GET `/api/projects/<pid>`, POST `/api/projects/<pid>/save` for partial updates. `/plan` generates only a script. Obtain review before extracting assets.
2. **References:** POST project `/extract-assets`, then explicitly confirm candidates through `/apply-extracted-assets`. Clothing variants belong to the character's `looks`. Keep identity images, outfits and voice samples separate.
3. **Storyboard:** GET `/api/storyboard-skill?project_id=<pid>` for the current `h3-structured-v2` instructions. POST project `/storyboard` with `{"stage":"all"}`. Replacing existing shots requires user authorization and `replace_existing:true`. Do not inject historical storyboard instructions.
4. **Asset bindings:** Use stable `asset_ids` and `character_looks` IDs. `@label` binds through `prompt_mentions[label]={asset_id,look_id}`. Preview actual `image_inputs`, `reference_bindings` and `compiled_prompt` through project `/preview-prompt`. A name in prose alone does not supply an image.
5. **Generation:** POST project `/generate` with `{"target":"shot","id":"actual-shot-id","kind":"image"}` or `"video"`. `/generate-batch` adds another round on every call; do not repeat without authorization. Follow project defaults or per-shot overrides. Reference-to-video does not require a first frame.
6. **Progress and stopping:** GET `/api/jobs` or project `/jobs`. POST project `/jobs/<jid>/stop`, or `/api/jobs/stop-all`. Never clear other clients' shared ComfyUI tasks. Stopping does not mean resources have already been released.
7. **Inspection:** Fetch the actual media. Prompts, filenames and metadata are not visual evidence. Remote server paths are not local file paths. Inspect video and audio directly. Versions are ordered newest first by `created`; identify them by stable `id`/`url`, not array position.
8. **Read and completion:** Project `/read-media` or `/consume-media` takes `version_ids`. A blue dot means unread, not failed review. Human and Agent share read state. `/shot-completion` takes `{shot_id,kind,completed}` and records production completion separately.
9. **Export:** Select versions, then POST project `/compose`. A project JSON export is not a full media backup; back up the data volume as well.

GET/POST `/api/settings` manages sanitized connection settings; `/api/settings/test` checks a connection. Never put secrets in project prompts or exports. Workflow import uses `/api/workflows/import {workflow,replace:false}` and dependency checks use `/api/workflows/check {id}`. Generic import requires the portable adapter and explicit parameter mappings; it does not install weights or verify generation quality.

With access protection enabled, supply a Bearer password/token or login cookie. Clear shots/assets only with explicit authorization, current `confirm_name`, `expected_updated` and reset epochs. Deleting a project keeps it in Trash for seven days.

Interface language (`shotdesk.uiLanguage` in the browser) is independent of the project's `prompt_language` (`zh`/`en`). Changing the interface does not translate scripts, prompts, asset names or API enum values. Preserve original dialogue and user-authored content.

## Cloud video providers

Read the redacted `video_providers` array from `/api/settings`. Configure providers through the guarded settings endpoint with stable `id`, `name`, `protocol` (`ark`, `minimax`, `replicate`, `fal`), `url`, actual `model`, private `api_key`, native `resolution`, `max_references`, `modes` and `enabled`. Preserve other entries when replacing the array. Blank keys retain existing secrets; `clear_key:true` removes them. Choose the returned `cloud-<id>` from the model catalogue, then use the same generation and preview APIs as local workflows. The official full-quality H3 model is `MiniMax-H3` over MiniMax V2, 768P/2K, integer 4–15 seconds. Current cloud support covers text, first-frame and image references, not audio/video references or last frames. Each fal endpoint must declare its actual single generation mode.

Cloud task IDs are persisted for restart recovery; never resubmit an ambiguous paid request automatically. A running official H3 task cannot immediately be cancelled. Keep cancellation pending until upstream termination is confirmed; billing may continue. Configured and mock-tested do not mean live-generation verified.
