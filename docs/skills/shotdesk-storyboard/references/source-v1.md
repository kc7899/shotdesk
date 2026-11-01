---
name: shotdesk-storyboard
description: 根据剧本选择简洁的镜头拍法与已有角色造型。
metadata:
  version: 2026-10-30.1
---

# 分镜摄影

<!-- source-owned-events -->
<!-- planning:start -->
<!-- source-dialogue -->
<!-- group-dialogue -->
<!-- contiguous-dialogue -->
<!-- natural-performance -->
<!-- completion-first -->
<!-- fixed-dialogue-slots -->
<!-- dialogue-events -->
<!-- event-cut-times -->
<!-- stable-reference-labels -->
<!-- single-fragment -->

根据每个unit的剧情，按schema返回recipes：标题、景别、运镜、关注人物和已有造型。原剧本指定的拍法优先；其余以画面清楚、动作连贯为准。固定机位即可时不强加运镜。

只选择提供的角色和各自造型；continuity_ids可选最多3条有用的前情编号。动作、台词、时长和资源编号由平台处理，无须重写。

最终视频提示词直接描述画面、动作、对白和声音。不写“原文动作”“前情说明”、核对过程或规则套话。

H3格式来源见references/sources.json；旧任务兼容规范见references/legacy-v8.md。
