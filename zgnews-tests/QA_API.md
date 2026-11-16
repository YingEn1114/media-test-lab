# API、状态与本地演示

所有新 API 使用 `Authorization: Bearer <服务端令牌>`。列表 `GET /api/qa/{collection}`，详情 `GET /api/qa/{collection}/{UUID}`，创建 `POST /api/qa/{collection}`，操作 `POST /api/qa/{collection}/{UUID或new}/{action}`。请求 JSON；业务错误返回 `{"error":"原因"}`，未认证 401、无权 403、对象不存在 404、版本/状态冲突 409、AI/规格不合法 422、AI 调用失败 502。

| collection | 常用 action / 请求字段 |
|---|---|
| requirements | create `{title,description,acceptance,owner,scope,area,priority,tags,risk}`；update 必须传当前 version；delete 保留 tombstone |
| drafts | new/generate `{requirement_id,demo:false}`；update `{version,spec}`；review `{}`；diff `{}`；sync `{confirm:true}`；publish `{confirm:true}`；delete |
| prompts | create `{category,text}` 自动新版本；`{UUID}/activate` 启用历史版本；category 为 generation/review/summary/report/email/defect |
| cases | 只读正式库，UUID 对应 nodeid；生成用例包含 draft/version/review/hash/commit |
| runs | create `{scope,value?,ids?:[caseUUID]}`；cancel `{}`；new/recover `{reason}` 仅管理员 |
| defects | assign `{owner_id:RD用户UUID}`；claim `{}`；fix `{note,commit或pr}`；verify `{}` 实际QA回测；close `{}` |
| reports | create `{run_id,title?}`，仅完成的 full run |
| outbox | create `{report_id,to?,cc?,subject?,body?}`；update 相同可编辑字段；send `{}` 仅本地；archive `{}` |
| settings | new/update `{routing:{域名:RD用户UUID,default:RD用户UUID},qa:[邮箱],leaders:[邮箱],capabilities:{browsers:[],accounts:"说明",video:false}}` |
| users | create `{name,role,email}` 返回一次性展示的token；role 为 qa/rd/viewer/test_lead/tech_lead/project_lead/admin；update `{email}` |
| audit / history / overview | 只读审计 / 升级前历史 / 聚合计数 |

`GET /api/qa/me` 返回服务端身份；`GET /api/qa/outbox/{UUID}/eml`（亦支持 `/download`）下载完整 RFC822 邮件，包含自定义正文及不可移除的证据风险摘要。系统永不因 SMTP 环境变量发真实邮件。

需求 `active → deleted`；内容更新递增 version。草稿 `draft → reviewed/rejected → published`；实际内容更新递增 version 并清除评审绑定。发布幂等，同一草稿版本多次确认只产生一条正式用例；修改已发布草稿后旧正式记录保留追溯，但执行门禁会要求重审重发布。

评审遵循仓库根 `AI_REVIEW_POLICY.md`：requirement_coverage 20%、step_completeness 15%、expected_result_clarity 15%、automation_feasibility 15%、stability 10%、maintainability 10%、risk_coverage 10%、duplication_control 5%。后端 ROUND_HALF_UP 重算，至少80且前四>=70；任何阻塞/安全/重复/环境阻碍/证据缺口拒绝。模型 decision 不能覆盖后端门禁。逐条输出 candidate_id/version/hash 必须匹配，仅允许一个对应结论。完整评审输入、Prompt、模型、代码、环境能力、正式库与同批候选快照留存。

执行 `queued → running → passed/failed/cancelled`；崩溃回收 `aborted`。scope/selected 使用正式用例 UUID 列表，requirement/value 为需求 UUID，其余过滤为域、priority或tag字符串。full 忽略传入的缩小选择，始终包含全部已发布用例。缺失/重复/未知JUnit testcase、退出码异常、收集错误、取消不能通过。普通运行允许已知 xfail 单列，skip 不算通过；修复回测 xfail/skip 均不能作为通过。

缺陷：

```text
open/reopened → claimed → rd_running
rd_running → pending_qa（实pass） / fix_failed
pending_qa → qa_running
qa_running → fixed（独立QA实pass） / reopened
fixed → closed（实际QA验收者）
```

修复证明为 commit 哈希或 PR URL 加说明，平台重跑关联正式用例；不能直接通过 accept 参数关单。RD 仅可读取分配/认领缺陷及关联 case/requirement/回测；工厂、评审、同步、配置、报告、邮件等集合返回403。RD 不可任意创建执行，仅通过修复工作流启动自己的关联回测，也不能取消他人运行。

本地演示建议：使用单独临时 DB；管理员创建 QA、RD 并配置 RD 邮箱及域路由；QA 新建需求，在工厂选择“演示生成”观察草稿编辑和同步。无真实 AI 配置时评审显示未配置，不会自动入库。如果需要无真实 key 的完整自动验证，运行 `platform-tests`，测试会在临时目录使用 stub AI 和 runner，并使用本地假 HTTP 真正执行固定模板；不会访问外部被测站点。

请求示例（仅供用户在自己的隔离服务中手动执行，不连接外部被测站点）：

```bash
export QA_URL=http://127.0.0.1:8092
export QA_TOKEN='替换为服务端签发令牌'

# 验证真实服务端身份。
curl -s "$QA_URL/api/qa/me" -H "Authorization: Bearer $QA_TOKEN"

# 创建需求，保存响应中的 UUID。
curl -s "$QA_URL/api/qa/requirements" \
  -H "Authorization: Bearer $QA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"本地首页验收","description":"仅针对本地假HTTP服务","acceptance":"首页返回200且标题包含QA","owner":"QA","scope":"本地HTTP","area":"首页","priority":"P1","tags":["local"],"risk":"不代表完整业务功能"}'

# 将下方需求 UUID 替换为上一步响应 id；显式演示仅产生草稿。
curl -s "$QA_URL/api/qa/drafts/new/generate" \
  -H "Authorization: Bearer $QA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"requirement_id":"替换为需求UUID","demo":true}'

# 查看草稿 / 新系统聚合 / 只读历史，不触发测试执行。
curl -s "$QA_URL/api/qa/drafts" -H "Authorization: Bearer $QA_TOKEN"
curl -s "$QA_URL/api/qa/overview" -H "Authorization: Bearer $QA_TOKEN"
curl -s "$QA_URL/api/qa/history" -H "Authorization: Bearer $QA_TOKEN"
```

上述演示不会绕过评审。只有同步、真实独立评审与人工确认均完成后才可发布；若要真实执行，请由用户另行配置 `ZG_BASE_URL` 为自己授权的目标并在执行中心明确启动。本次开发验证只使用临时目录与本地假 HTTP。

接口演示示例（仅操作自己启动的隔离平台，示例不触发测试执行或外发）：

```bash
export QA_DEMO_URL='http://127.0.0.1:8092'
export QA_DEMO_TOKEN='替换为该隔离数据库的管理员令牌'

curl --fail-with-body "$QA_DEMO_URL/api/qa/me" \
  -H "Authorization: Bearer $QA_DEMO_TOKEN"

curl --fail-with-body "$QA_DEMO_URL/api/qa/requirements" \
  -H "Authorization: Bearer $QA_DEMO_TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"本地首页验收","description":"检查首页可用性","acceptance":"首页HTTP状态码200","owner":"QA","area":"首页","priority":"P1","scope":"本地假HTTP","tags":["demo"]}'

# 将上一步返回的需求UUID替换到requirement_id：
curl --fail-with-body "$QA_DEMO_URL/api/qa/drafts/new/generate" \
  -H "Authorization: Bearer $QA_DEMO_TOKEN" -H 'Content-Type: application/json' \
  -d '{"requirement_id":"替换为需求UUID","demo":true}'

curl --fail-with-body "$QA_DEMO_URL/api/qa/drafts" \
  -H "Authorization: Bearer $QA_DEMO_TOKEN"
```

运行时的同步与发布是两个不同动作：`POST drafts/{草稿UUID}/sync` 加 `{"confirm":true}` 会真实提交该 generated 版本到独立本地资产仓库；`POST drafts/{草稿UUID}/publish` 加相同确认只在评审有效、代码及commit匹配时入库。完整的真实AI闭环需要服务端配置模型，不应将演示草稿或 stub 测试结论作为产品环境 AI 已验收的证据。

| 服务端配置 | 示例 / 行为 |
|---|---|
| `ZG_DB` | `/tmp/zgqa-demo.db`；父目录须已存在 |
| `ZG_ADMIN_TOKEN` | 仅首次无用户bootstrap时读取；改环境变量不会重置已有管理员 |
| `ZG_ASSET_REPO` | 可省略，默认 `<ZG_DB>.assets.git`；必须使用专用资产仓库 |
| `ZG_AI_BASE_URL` / `ZG_AI_KEY` / `ZG_AI_MODEL` | OpenAI兼容模型；密钥不由浏览器提交或回显 |
| `ZG_AI_TIMEOUT` | 单次 AI 请求超时秒数，默认60，范围大于0且不超过300 |
| `ZG_GIT_REPO` / `ZG_GIT_BRANCH` / `ZG_GIT_AUTHOR_NAME` / `ZG_GIT_AUTHOR_EMAIL` | 专用本地bare资产仓库、初建分支、提交作者；不接受普通工作仓库 `.git` 或远程URL |
| `ZG_BASE_URL` | **运行测试时**的真实目标，例如你自建的 `http://127.0.0.1:18080`；本次升级验证不运行外部站点 |
| `ZG_HOST` / `ZG_PORT` | 建议隔离验证使用 `127.0.0.1` 与空闲端口，不影响已运行服务 |
| `ZG_AUTH` | 可选旧页面Basic；新 `/api/qa/` 仍独立使用Bearer |
| `ZG_SMTP_*` | 不启用外发；当前实现始终outbox |

当前限制：六种 HTTP/HTML 自动化检查，不支持任意 AI 代码、复杂 UI 步骤或企业SSO；手工设计保留完整字段，不能自动执行。报告、摘要、通知当前使用证据模板（非模型生成文本）。仅单机进程内后台线程执行，不是持久分布式任务队列；恢复保守检测进程存活，不能自动判断PID复用或异机活性。管理员用户当前仅支持创建及修改邮箱，令牌撤销/轮换需后续完善。
