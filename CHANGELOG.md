# 变更记录

## Unreleased

- Experimental official Ark virtual-character asset sync: private AK/SK setup, per-character groups, per-look review status, stale-image protection and automatic approved asset references. Live account review remains unverified.

- Added cloud video providers: Seedance via Volcano Ark, Replicate and fal, plus official full-quality MiniMax H3 V2 and compatible gateways. Shared asset binding, task persistence, cancellation confirmation and local media history. Provider credentials stay private. Real cloud inference is not yet verified.

## 2026-11-01 · 动态选择默认LLM

服务连接从/v1/models获取默认模型下拉列表；保留原选择，仅一个模型时自动选中，多个时显式选择。获取不到列表可切换手动ID；过期响应不会覆盖新服务，清除密钥测试不会复用旧密钥。

## 2026-11-01 · 独立安装候选

- 保留h3-structured-v2当前分镜方案，未改动h3_structured.py。
- 增加服务连接、连接测试、密钥脱敏存储及可选访问密码。
- 增加独立ComfyUI API图导入、参数映射、依赖检查和实际提交。
- 增加自己的Dockerfile、默认仅本机访问的Compose、示例工作流及CI。
- 本机专用网络/模型/配音/工作流留在私有.local配置；公开候选不依赖其他仓库。
- 白名单导出候选，排除项目、媒体、回收站、备份、私有模型表及可选Huobao原文包。
- 原始代码许可证和第三方参考资料的公开再分发确认仍待所有者决定；未自动发布GitHub。

更早的本机研发记录保存在迁移前完整备份与私有.local目录，不作为首次安装指南。

## 2026-11-01 · Product branding and interface languages

- Unified visible product branding as Shotdesk / 片场; replaced the historical third-party task label with neutral storyboard wording. Kept compatibility fields and required source notices.
- Added persistent Chinese / English interface selection across the studio, connections, tasks, login and Agent entry. Added an English API workflow guide.
- Kept UI language independent of project prompt language and preserved user text, enum values and asset bindings.

## 0.1.0-preview.1 · First public candidate

- MIT original-code license, retained third-party notices, excluded unlicensed verbatim upstream references.
- Agent setup Skill, read-only diagnosis, guarded connection configuration, two-shot smoke tool and installation/recovery guides.
- Release integrity/readiness gate and sanitized acceptance record.
- Fixed script JSON escape handling with a bounded format retry; allowed scene/prop-only storyboard projects; queued-task deletion no longer sends unnecessary interrupts.
- Clarified the connection indicator as ComfyUI, independently of local/remote deployment.

- Added a Seedance asset-ID catalogue and thumbnail picker for character identities/looks, without requiring AK/SK or a public media URL. Existing automatic sync remains available; manual IDs are explicitly unverified. Documented the official same-account original-image trust conditions.
