# QA 检验台迁移说明

升级不修改 `cases.json` 或旧运行证据。首次产品 schema 迁移发现旧 SQLite 表时，使用 SQLite backup API 生成 `<ZG_DB>.pre-qa-v1.bak`（包含 WAL 中已提交数据），然后通过事务创建 `qa_schema_migrations`、`qa_objects`、`qa_users`、`qa_audit` 和 `qa_runner_slot`。版本 2 增加人员邮箱，版本 3 增加运行槽 PID/owner/host。迁移幂等，SQLite 开启 WAL、foreign_keys 与 15000ms busy timeout。

已有人工用例按原 nodeid 去重导入 DB 并分配稳定 UUID；名称、描述、优先级、域、标签等元数据原样保留，现有 38 条人工测试仍在原文件中。生成正式用例仅保存在 DB，不写回 `cases.json`。升级后新增人工元数据会在后续启动时导入；已有 DB 人工元数据不被启动流程覆盖。

旧 `runs`、`pipelines`、`bugs`、`mails` 表和 `defects.json` 保留，QA/管理员在 `/history` 只读查看（每张旧表最近 100 条）。旧ID只作历史标识，不伪造 UUID 或混入新状态机；新业务对象全部 UUID 关联。旧 POST API 返回 410，不再允许旧 pipeline 绕过评审、直接关闭缺陷或发送邮件。

草稿资产写入 `tests/generated/<需求UUID>/case_<草稿UUID>_v<版本>.py`，使用固定模板、安全字面量与不可变版本文件名。pytest 默认发现忽略 generated；即便显式指定文件，也必须提供执行中心生成的精确路径/hash 清单才能收集模块。服务端在发布、预留执行时再次核验 hash、需求及草稿版本。拥有本机文件/环境完全控制权的操作者属于本机信任边界。

代码同步默认使用 `<ZG_DB>.assets.git` 独立仓库，使用临时 index、commit-tree 和 update-ref CAS，仅包含选中的 generated 文件。仓库不配置远程、不 push。配置 `ZG_ASSET_REPO` 时必须指向专用资产仓库，不能复用用户工作仓库的 `.git`。备份时将 DB、对应 generated 文件、资产仓库和管理员令牌权限一起保留；只恢复 DB 不恢复代码会被 hash/文件门禁阻止执行。

运行槽保存 PID、进程 UUID、主机；本机进程确认死亡才在启动时自动回收为 aborted，记录审计。RD 自回测中断回到 fix_failed，QA 回测中断回到 pending_qa。未知旧槽或异机槽需管理员确认停机后使用恢复 API 并填写原因；已知本机活进程不会被抢占。共享网络磁盘上的多机执行不在当前 SQLite 单机执行器支持范围内。

回退前停止升级版服务，独立保存升级后 DB 和资产；使用备份在单独位置启动旧版进行读取核验。不要在旧版服务运行时覆盖其 DB/WAL。升级后数据不会自动反向写入旧 schema。
