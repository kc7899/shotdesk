# Third-party sources and distribution scope

Original Shotdesk code is licensed under MIT; see LICENSE. The owner selected this license on 2026-11-01. Third-party material retains its own terms and is not relicensed by that choice.

- **MiniMax H3 references:** pinned repository, URLs and SHA-256 values are recorded in `docs/skills/shotdesk-storyboard/references/sources.json`. At commit `d21241f0a4b3acbb34c97dae47fa417b7065e438`, no LICENSE/COPYING/NOTICE path was found in the upstream tree. Public exports and images therefore exclude the three verbatim upstream reference files. Links/hashes remain for provenance; public availability alone is not treated as permission to redistribute. The default `h3-structured-v2` engine does not load those files. Optional historical tests requiring them are explicitly skipped in the public candidate. Local private originals are preserved.
- **Cinematic Director reference:** `wuwangzhang1216/DirectorSKILL`, commit `c65ae0d14457053efb1e354c7e7f7e120d97fad1`, MIT, copyright (c) 2026 wangzhang-wu. Preserve the complete license at `docs/skills/shotdesk-storyboard/references/cinematic-director-LICENSE.txt` and its provenance record. No endorsement or official affiliation is implied.
- **Optional historical Huobao package:** the locally archived upstream license identifies CC-BY-NC-SA-4.0. Its original package and Agent implementation are not included in the default public candidate or image. No blanket relicensing is asserted.
- **Local external media adapter:** this is an optional private integration. The public candidate does not copy its implementation, private workflows, model weights or media.
- **Python and FFmpeg:** provided by the container distribution or user installation. Preserve installed package copyright/license files when distributing an image. Their own licenses continue to apply.
- **Examples:** project-authored parameter-mapping examples, not bundled model weights or custom nodes. Users must obtain their own models, workflow rights and service accounts.

The dated source inventory is `docs/source-audit.json`. This notice records packaging boundaries; it does not replace the licenses themselves or determine rights in user-provided inputs and outputs.
