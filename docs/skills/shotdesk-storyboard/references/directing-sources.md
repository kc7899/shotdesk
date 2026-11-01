# 导演与剪辑来源（查阅：2026-10-28）

这些是教育资料与创作者经验，不是统一的“大片认证标准”，不改写MiniMax官方格式和原文快照。

- Walter Murch本人访谈，六项剪辑考虑与优先级：情绪、故事、节奏、视线、二维关系、三维连续性。https://www.provideocoalition.com/aotc-murch-books/amp/
- 纽约电影学院，The 5 Stages of Blocking a Scene：机位由场景重要内容决定，调度和镜头表可迭代。https://www.nyfa.edu/film-school-blog/the-5-stages-of-blocking-a-scene/
- FilmSkills，Blocking Actors：人物相对摄影机的移动，为什么/何时/向哪/怎样移动。https://www.training.filmskills.com/fst/lesson/blocking-actors
- Filmmakers Academy，Continuity Editing：正反打、动作匹配、视线匹配、画面运动方向等连续性方法。https://www.filmmakersacademy.com/glossary/continuity-editing/
- 哥伦比亚大学电影语言词典，180-Degree Rule：空间理解与有意越轴的表现作用。https://filmglossary.ccnmtl.columbia.edu/term/180-degree-rule/
- 俄克拉荷马州立大学开放教材，Editing：连续性剪辑、30度原则等。https://open.library.okstate.edu/introfilmtv/part/editing/
- Adobe，Shot/reverse shot：对话空间与连续性。https://www.adobe.com/uk/creativecloud/video/production/cinematography/camera-shots-and-angles/reverse-shot.html
- Learn About Film，Continuity：轴线、视线、动作方向、持续环境声与J/L-cut。https://learnaboutfilm.com/film-language/sequence/

平台适配判断：把摄影决定写进现有description、image_prompt和video_prompt，避免增加冗余层级。竖屏可读性、优先简单可执行运动、独立生成片段边界与不假装实现跨文件J/L剪辑，是针对Shotdesk的工程/创作建议，不冒充上述资料的逐字规则。30/180度原则均允许有目的例外；不加固定切镜秒数或伪科学评分。术语不保证模型正确执行，完成品的动作、方向、节奏与声音仍需实际观看核验。


## Cinematic Director选择性参考（2026-10-28）

上游：wuwangzhang1216/DirectorSKILL，入口name=cinematic-director，版本2.1.0；固定commit c65ae0d14457053efb1e354c7e7f7e120d97fad1。已阅读入口、blocking-and-staging、continuity-bible；URL及SHA256见cinematic-director-sources.json。MIT版权声明保留于cinematic-director-LICENSE.txt。上游不是电影行业认证标准，其模型稳定性与数值经验不视为通用定律。

本地重新组织的规则：人物目标/阻力和有依据的潜台词、场景视点与信息揭示、叙事节拍、人物起始→移动/操作→结束状态、从调度选择机位；连续性分固定资产与临时状态，并核对知情/情绪因果。第二阶段附全局分析与批次前后镜头简要规划，避免三镜一批导致边界信息丢失。

未移植：13步完整制作流程、导演风格套件、额外交付文档、固定3–5秒/字数/距离/焦距、未经实测的质量评分与失败阈值；不强制生成首帧，不重复编写身份外貌或覆盖造型资产，不增加额外审核LLM调用。来源资料不逐任务全文加载，正式运行只冻结本地精简Skill及官方H3指南。

2026-10-28.10：根据真实失败复盘，内部资源引用统一为单一references，H3固定段落由程序组装，按阶段加载精简本地Skill。此为Shotdesk工程适配，不是Cinematic Director或MiniMax上游原文要求。原始官方文件、来源校验和许可保持。


## 2026-10-30：场面调度与覆盖重建

- [MiniMax官方H3 Ref2VA](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt)：首次清晰出现交代外观、位置、动作；镜头切点与声音/主体绑定。固定原文文件及校验保留在sources.json。
- [官方ComfyUI H3指南](https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide)：场景→镜头；对白关联可见事件；多说话者仍可能归属错误。
- [StudioBinder Film Coverage](https://www.studiobinder.com/blog/film-coverage/)：定场、master、说话者/反应与正反打覆盖，保持轴线关系。
- Huobao本机storyboard_breaker.md / prompt_generator.md：参考其段内镜头与资源关联职责，不复制固定时长或代码。

单次视频默认一个具体机位和一个发声主体，是本平台低清试片后的保守实现选择，不宣称是官方/好莱坞统一标准。不叠加旧十八道质量关卡。
