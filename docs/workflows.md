# 导入 ComfyUI 工作流

普通画布JSON包含nodes/links，不能直接作为执行图；请从ComfyUI导出API格式，形如 `{"3":{"class_type":"KSampler","inputs":{...}}}`。平台既支持在界面设置映射，也支持直接导入以下封装：

```json
{
  "id":"my-image-workflow",
  "name":"我的图片工作流",
  "kind":"image",
  "max_references":0,
  "output_node":"9",
  "bindings":{"prompt":[["6","text"]],"seed":[["3","seed"]],"width":[["5","width"]],"height":[["5","height"]]},
  "graph":{"请替换":"真实API执行图"}
}
```

以上仅是结构说明，不是可执行图；完整示例见examples。

- `kind`：image/video；视频还需modes，例如 `["text"]`、`["first_frame"]`、`["reference"]`。
- bindings的值是 `[节点ID, 输入名]` 列表，同一参数可以写入多个输入。节点ID必须对应graph中的真实节点。
- prompt、seed、width、height、duration（秒）、frames、fps可映射；首帧使用first_frame；资产参考使用image_0起连续编号。max_references须与实际映射一致。
- 图像上传到ComfyUI后，将实际文件名填入LoadImage等节点。只使用本项目提供的图片data URL，不自行抓取任意远程文件。
- 帧数按duration × fps计算，支持frame_alignment/frame_offset约束，如4n+1帧。fps默认16；这些是工作流约束，不代表模型支持任意时长。
- output_node是保存结果的节点。支持ComfyUI history中的images/gifs/videos/audio字段；请先验证实际输出结构。
- `dependencies`可记录模型/插件要求。检查依赖会调用object_info，识别缺失节点与枚举值；不会下载权重，也不保证图中所有连线正确或生成质量。
- 输入数量必须匹配；不会静默丢弃多余参考图或使用旧图代替缺失图片。

通用适配器暂不处理声音参考、视频参考或表演迁移的输入上传；这些需专用适配器。平台会明确拒绝这类通用导入，避免“按钮能选、实际不传资源”。
