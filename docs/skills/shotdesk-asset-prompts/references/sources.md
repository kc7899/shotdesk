# 提示词设计依据

整理日期：2026-10-27。提炼方法，不复制完整官方提示词，不声明对任何模型的效果保证。

- [Black Forest Labs：FLUX.2提示词指南](https://docs.bfl.ai/guides/prompting_guide_flux2)：用明确的主体、关键属性和上下文描述目标；多参考图须说明各自用途；服饰组合与人物一致性可分配不同参考角色。该页主要讨论pro/max，本项目只借鉴写法，不把其API参数或效果照搬给本地Klein工作流。
- [QwenLM：Qwen-Image-2.1官方编辑提示词规范](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/prompt_rewrite/prompts/system_prompt_edit.txt)：身份由参考图锚定，具体描述要变化的属性；不要为了保持身份而反复用文字重画五官；把歧义意图落实为明确可执行的选择。只借鉴身份与属性分离原则，不强行把Qwen的图像标签语法用于其他工作流。

根据剧情补全性别外观、年龄及服装并单列inferred_details，是用户明确要求的本应用美术设计策略，不是原作事实识别，也不是以上文档规定的通用事实推断规则。
