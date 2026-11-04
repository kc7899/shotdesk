# 运维、备份与故障恢复

## 任务失败与停止

- 查看统一任务队列，或 GET `/api/projects/<pid>/jobs`。保留失败任务 ID，先读日志再重试；重复点击批量生成会追加任务。
- 单任务停止：POST `/api/projects/<pid>/jobs/<jid>/stop {}`。全停仅在用户明确要求时调用 `/api/jobs/stop-all`；不调用 ComfyUI 全局清队列。
- 停止中表示尚未确认远端停止，不代表显存已释放。ComfyUI 正在执行别人的任务时，不能为停止自己的任务打断别人。
- 服务恢复后重新检查连接及工作流。生成失败不删除剧本、参考资产和已完成版本。不要通过清空数据目录修复网络错误。

## 工作台重启

更新前先等待任务完成，或针对本项目停止并确认释放。执行 `docker compose restart shotdesk` 只重启工作台，不重启模型服务。

重启后：排队任务恢复；已有 ComfyUI prompt ID 的任务继续查询原任务，不重复提交；已完成结果保留。提交瞬间崩溃且未保存远端 ID 的任务会标失败，提示结果不明，需核对远端后再试，避免重复生成。正在执行的文字/合片任务没有可靠恢复点时也可能标失败；用户内容保留，不能宣称所有任务无缝续跑。

## 备份

项目 JSON 导出不包含完整媒体、设置或工作流，不能代替备份。

原生安装：停止 Shotdesk 后备份完整 `data/` 和 `workflows/`，也保存自己的启动配置。数据目录包含私有设置，备份不可公开。

Docker 安装：先在工作台完成停止，再运行以下命令。目录名 `backup-日期` 自行替换，不覆盖旧备份。

```bash
docker compose stop shotdesk
mkdir backup-日期
# 从同一服务卷复制完整目录；服务仍保持停止，不读写生产任务。
docker compose run --rm --no-deps --entrypoint tar shotdesk -C /app -cf - data workflows > backup-日期/shotdesk.tar
# 检查归档包含数据与工作流后，再启动。
tar -tf backup-日期/shotdesk.tar
docker compose start shotdesk
```

Shell 的重定向由宿主机完成。备份文件包含密钥，限制访问。若采用额外的外部工作流目录、反向代理或环境令牌，还需单独备份对应私有配置。

恢复到一个**新的空部署**，不要覆盖有任务的现有卷。先检查归档来源及成员路径，确认只有 `data/`、`workflows/`；通过临时服务挂载目标卷后解包，并让运行用户 UID 1000 可以读写。恢复后检查项目、历史媒体和服务连接，再启动生成。不要用 `docker compose down -v` 升级；它会删除数据卷。

## 升级与退回

1. 记录当前发布版本及镜像 ID，备份数据和私有配置。
2. 在独立目录验证新版。不要直接把 GitHub 源码覆盖正在运行的目录。
3. 无活动任务时替换工作台镜像并启动，检查项目、媒体、模型目录。
4. 出现问题先停新工作台，使用原镜像和升级前备份在隔离环境恢复；数据格式若有变化，不能盲目把旧程序指向新版写过的数据。

## 网络与凭据

默认只开放到本机。需要给其他机器访问时设置工作台密码/令牌与 HTTPS，再配置监听地址。工作台认证不保护独立开放的 ComfyUI/LLM/IndexTTS 端口。本版为单用户预览工具，没有账户隔离、团队权限或公网托管承诺。


## Browser polling performance

Browser job polling uses `?view=summary` to exclude prompts, input images, reference bindings and generated result bodies while preserving task states, timings, logs and controls. Default job endpoints retain their existing full response for Agents. JSON responses negotiate gzip above 2 KiB. Task histories and media are preserved.
