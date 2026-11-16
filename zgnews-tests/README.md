# 正观新闻 Python UI 自动化测试

> 产品化升级入口已替换旧流水线。下方早期运行记录仅作历史背景；当前鉴权、门禁、邮件与 API 以本节及 `MIGRATION.md`、`QA_API.md` 为准。

## 当前版本：QA 检验台

独立入口：总览 `/`、需求 `/requirements`、AI 工厂 `/factory`、Prompt `/prompts`、正式库 `/cases`、执行 `/runs`、缺陷 `/defects`、报告 `/reports`、发件箱 `/outbox`、设置 `/settings`；升级前数据在 `/history` 只读查看。`/pipeline` 进入新工厂，旧写入 API 返回 410。

本轮交付与尚未完成的扩展逐项列在 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)，不要将完整需求中的所有细项视为已经实现。

启动示例（先在项目目录运行，以下路径均相对于当前项目）：

```bash
ZG_DB=/tmp/zgqa-demo.db \
ZG_ADMIN_TOKEN='替换为至少32字符的随机令牌' \
ZG_HOST=127.0.0.1 ZG_PORT=8092 ./start.sh
```

未设置 `ZG_ADMIN_TOKEN` 且数据库尚无用户时，平台在 `<ZG_DB>.admin-token` 创建权限 `0600` 的本机管理员令牌文件，并在启动日志中打印位置。页面填写令牌登录；API 使用 `Authorization: Bearer <token>`。管理员在设置页创建 QA、RD、viewer 账号，令牌仅显示一次，数据库只存哈希。角色不能通过前端 role 参数冒充。旧 `ZG_AUTH` 可继续保护页面，但 `/api/qa/` 单独使用 Bearer，不需要同时提交 Basic。此最小认证适用于可信本机/团队环境，尚未接入企业 SSO、令牌轮换或找回。

AI 配置只在服务端提供，设置页显示掩码。完整环境变量示例见 [.env.example](.env.example)，示例文件不会自动加载；`ZG_AI_TIMEOUT` 默认 60 秒，可配置到 300 秒。

管理员还可创建测试负责人、技术负责人和项目负责人账号；这些角色可以查看工作与质量证据，不能修改测试或缺陷状态。Prompt 管理支持创建新版本、启用历史版本回滚，回滚后再次保存仍使用递增版本号，不覆盖历史。

```bash
ZG_AI_BASE_URL=https://your-compatible-provider.example/v1 \
ZG_AI_KEY='your-secret' ZG_AI_MODEL='your-model' \
ZG_DB=/tmp/zgqa-demo.db ./start.sh
```

未配置 AI：真实生成和评审明确返回未配置；可选择“本地规则演示”生成设计草稿，来源为 `demo-local-rules`，绝不以本地规则自动评分通过。调用失败不静默降级。生成与独立评审分别使用可版本化 Prompt；默认六类为 generation、review、summary、report、email、defect（缺陷通知）。摘要、报告和邮件当前使用真实证据固定模板，记录对应 Prompt 版本，**不声称已经调用模型撰写报告/邮件**。

操作闭环：

1. 需求中心填写标题、描述、验收标准、负责人、范围、域和风险。
2. 工厂生成草稿，可编辑目标、前置条件、步骤、预期、测试类型、smoke、automation、实现及风险；保存新版本即使代码未变也需重审。手工设计可保留，不能发布为自动执行用例。当前自动化执行只支持六类受限 HTTP/HTML 检查，不执行模型给出的 Python。
3. “查看代码 / diff”预览；“同步代码到本地 Git”真实提交当前一份 generated 版本资产，记录 commit、hash、diff。默认独立 bare 仓库为 `<ZG_DB>.assets.git`，可用 `ZG_ASSET_REPO` 指向专用资产仓库；隔离 index 精确提交选定文件，不改变本项目 HEAD、用户 index 或其他改动，不 push。
4. 独立 AI 评审使用八维规则，后端重算加权总分；至少 80 分、前四维至少 70，blocking、安全问题、重复、环境阻碍、证据缺口均拒绝。逐条问题含位置、理由与建议。人工确认绑定草稿版本、需求版本、评审、代码 hash、commit；零通过不入库。
5. 执行中心支持 full、smoke、selected/scope、requirement、area、priority、tag。full 包含当前所有正式人工及生成用例，过期资产阻止启动而非被静默漏掉。结果要求 JUnit 精确覆盖每一 nodeid、无重复/未知项、有效退出码且未取消；普通执行保留 xfail 单列，修复回测必须全部实 pass。
6. 失败创建 UUID 缺陷，按管理员域路由关联 RD。配置 RD 邮箱后真正生成 DB 发件箱通知；缺少邮箱时显示 `needs-recipient`。RD 只看到分配/认领缺陷及关联用例、需求、回测，不能读取评审/代码同步/邮件或取消别人的运行。
7. RD 提交 commit/PR 与说明后实际自回测，通过才待 QA；独立 QA 再实际回测通过为 fixed，验收者才能关闭。失败、skip、xfail、缺失 JUnit 均不能算修复。修复 commit/PR 是用户提供的证明，平台不访问远程验证其业务内容。
8. 完成的全量 run 生成不可变快照；失败也可生成风险报告。未解决 P0/P1 必须标风险。邮件默认收件人/抄送来自设置，可编辑正文，但 `.eml` 总附后端不可移除的证据风险摘要。有更新全量 run 后旧报告邮件不能再发送，只可归档。发送只表示写入本地 outbox，**任何 SMTP 环境配置都不会触发真实外发**。

SQLite 使用 WAL、15 秒 busy timeout、写事务、schema 迁移记录和操作审计。运行槽在同一事务中占用，保存 PID/进程 UUID/主机；启动仅自动回收本机已死亡进程的槽，标记 aborted 并审计。未知旧槽或异机槽需管理员调用恢复接口并填写原因；活 PID 拒绝抢占。PID 被复用时采取保守策略，不会自动抢锁。

验证命令：

```bash
.venv/bin/python -m pytest platform-tests -q
# 若 PATH 没有 node，可使用本项目 Playwright 自带的 Node：
.venv/lib/python3.9/site-packages/playwright/driver/node --check web/assets/center.js
```

独立测试使用临时 DB、代码目录、独立资产 Git、stub AI/runner，以及仅监听 127.0.0.1 的假 HTTP/API，不运行原站。迁移/备份见 `MIGRATION.md`，请求格式、状态流转及示例见 `QA_API.md`。

生成资产可通过 `ZG_GIT_REPO` 指定专用本地 bare 仓库路径（`ZG_ASSET_REPO` 优先）；初建分支使用 `ZG_GIT_BRANCH`，作者使用 `ZG_GIT_AUTHOR_NAME` / `ZG_GIT_AUTHOR_EMAIL`。普通工作仓库的 `.git` 会被拒绝。生成文件在主工程中忽略，但会由独立资产仓库版本化，不触碰平台开发代码的提交。

浏览器验收脚本在工作区根目录：`verify_upgrade_ui.py` 检查全部导航的桌面/移动布局，`verify_upgrade_flow.py` 验证隔离服务中的需求、草稿、同步和单条运行选择。验收结果保存到 `reports/`，不提交凭据或运行数据库。

## 1. 背景
参考 `../metersphere-3.x/unit58框架代码`（Selenium + unittest + Excel + HTMLTestRunner）。该框架是 Windows 环境（`D:\Python312`、`chromedriver.exe`），Mac 不能直接跑。

本项目保留其“页面对象 + 数据驱动 + HTML 报告”思路，改为：

- Python 3.9 + pytest + Playwright Python；
- 使用本机 Google Chrome，不额外下载浏览器；
- 提供可点击的 Web 测试平台：发现用例、勾选运行、实时日志、历史、报告。

## 2. 平台能力
- **多页面**：总览 / 用例库 / 运行与日志 / 测试报告 / 环境与设置，不再是一整页；
- **可视化**：Chart.js 有效通过率趋势、最近结果环图、测试点覆盖条形图；
- **口径**：有效通过率 = passed /（passed + failed），xfail 单列、不计入分母；
- **Allure 报告**：每次运行自动生成 Allure，平台报告页作为默认报告；
- **设计规范**：`DESIGN.md`（检验台风格；avoid-ai-design 扫描 0 findings）；
- 用例自动发现：`pytest --collect-only` 扫描 `tests/`，新增 `test_*.py` 自动出现；
- 元数据：`cases.json` 配置名称、描述、优先级、标签；
- 运行：勾选/全部运行、取消运行、实时日志；
- headed：勾选“显示浏览器”+慢动作，可看到真实 Chrome；
- 历史：SQLite `platform.db`；
- 报告：每次运行生成独立 HTML。

技术栈：FastAPI + Jinja2 + SQLite + pytest + Playwright Python + Chart.js + Allure + 本机 Chrome。

## 3. 运行平台

本机访问：

```bash
cd ~/Downloads/media-test-lab/zgnews-tests
./start.sh
```

打开 **http://127.0.0.1:8090/**

局域网（让同事访问）：

```bash
ZG_HOST=0.0.0.0 ./start.sh
```

1. 查本机 IP：`ipconfig getifaddr en0`（Wi-Fi）或 `ipconfig getifaddr en1`（有线）；
2. 同事打开 `http://<你的IP>:8090/`，例如 `http://172.26.73.50:8090/`；
3. 需在同一 Wi-Fi / VPN；macOS 防火墙首次会弹“允许接受传入连接”，点 **允许**；
4. 同一网络支持 mDNS 时也可用 `http://<主机名>.local:8090/`。

建议开启访问控制（HTTP Basic Auth）：

```bash
ZG_HOST=0.0.0.0 ZG_AUTH=qa:换成你的密码 ./start.sh
```

同事首次访问输入账号密码即可。**不要把无密码的 8090 直接暴露到公网。**

只跑命令行：
```bash
.venv/bin/python -m pytest -q --html=reports/report.html --self-contained-html
```

### 健康检查与维护

```bash
# 健康检查（db / reports / evidence）
curl http://127.0.0.1:8090/api/health
.venv/bin/python scripts/check_platform.py

# 冒烟：平台“冒烟运行”，或按标签触发
curl -X POST http://127.0.0.1:8090/api/run \
  -H 'Content-Type: application/json' -d '{"tags":["smoke"]}'

# 命令行冒烟（8 条，约 20–40 秒）
.venv/bin/python -m pytest -m smoke -q
./scripts/run_smoke.sh

# 平台单测（隔离 DB，不访问站点）
.venv/bin/python -m pytest platform-tests -q

# 维护预览（默认 dry-run，不删任何东西）
.venv/bin/python scripts/maintenance.py
# 确认后再执行（会先备份 platform.db）
.venv/bin/python scripts/maintenance.py --apply
```

可选环境变量：`ZG_HOST`（0.0.0.0 开局域网）、`ZG_PORT`、`ZG_AUTH=user:pass`、`ZG_DB`（隔离数据库，便于演练）。

## 4. 看到浏览器执行
默认 headless，不会弹窗。要看真实浏览器：

- 平台工具栏勾选 **“显示浏览器”**，慢动作 300/700ms；
- 或命令行：
```bash
ZG_HEADLESS=0 ZG_SLOWMO=500 .venv/bin/python -m pytest tests/test_home.py -q
```
说明：用例主要是“打开页面 + 断言”，窗口只会短暂出现；想看完整过程请单条运行 + 700ms。

## 5. Allure 报告

本机没有 Java，Allure 工具链放在项目 `.tools/`：

```bash
# JRE 17
.tools/jdk-17.0.21+9-jre/Contents/Home/bin/java -version
# Allure CLI
.tools/allure-2.46.1/bin/allure --version
```

每次平台运行会自动执行：

```bash
pytest --alluredir allure-results/<run-id>
allure generate allure-results/<run-id> -o reports/allure-<run-id> --clean
```

报告页显示 Allure 卡片；历史表同时保留 HTML 和 Allure 链接。

## 6. 用例清单（38 条）
| 文件 | 覆盖 |
|---|---|
| `tests/test_home.py` | 首页标题、导航、新闻链接、搜索框 |
| `tests/test_navigation.py` | 点击“郑州”进入 `/list/16.html` |
| `tests/test_list.py` | 列表页标题、新闻条目 |
| `tests/test_article.py` | 新闻详情正文、标题 |
| `tests/test_search.py` | 搜索弹层、结果页（已知问题 xfail） |
| `tests/test_responsive.py` | 390x844 H5 首页 |
| `tests/test_seo.py` | 首页/详情页 title、description、canonical |
| `tests/test_security.py` | HTTPS、X-Frame-Options、nosniff、Cookie |
| `tests/test_links.py` | 导航/新闻链接状态码 |
| `tests/test_performance.py` | DOMContentLoaded、资源数 |
| `tests/test_accessibility.py` | 标题层级、图片 alt、输入框 |
| `tests/test_http_api.py` | HTTP 契约、HEAD、robots、静态资源、图片 CDN、软 404 |
| `tests/test_video.py` | 视频列表、播放器元数据、播放/暂停、seek、音量、控件、MP4 Range、移动端 |
| `tests/test_metadata.py` | NewsArticle JSON-LD、OG、canonical |
| `tests/test_share.py` | 微信/微博分享组件 |
| `tests/test_footer.py` | 页脚合规链接与备案 |
| `tests/test_login_modal.py` | 短信/密码登录弹层 |
| `tests/test_special.py` | 正观早参专题日历 |
| `tests/test_channels.py` | 16 个频道可用性 |
| `tests/test_home_sections.py` | 首页视频/专题栏目 |
| `tests/test_search_edge.py` | 空关键词/特殊字符 |
| `tests/test_download.py` | 客户端下载页 |

详细步骤/预期见 `TEST_SPEC.md`，测试点拆分见 `TEST_POINTS.md`，视频设计见 `VIDEO_TESTING.md`。

## 7. 当前结果（原站）

最近一次全量运行：2026-11-06 15:12（run `20261106-151242-c818a1`，38 条，154.1s）。

```text
33 passed, 5 xfailed（共 38 条）
有效通过率 33/33 = 100%
```

口径说明：**有效用例 = passed + failed**。xfail 是已确认的站点现状（缺陷或限制），单独展示，**不计入通过率分母**；平台“有效通过率”按此口径计算。

5 条 xfail 对应问题：

1. A06 搜索结果页被重定向到 `/down.html`；
2. A19 未知路径返回 HTTP 200 + 404 内容（软 404）；
3. A20 `sitemap.xml` 返回 HTTP 200 + 404 内容（软 404）；
4. A29 特殊字符搜索同样被重定向到 `/down.html`；
5. V08 移动端播放器固定 1240px，390 视口横向溢出。

## 8. 已发现的站点问题
1. 全站没有 `h1`（首页仅 h3），SEO/可访问性建议补；
2. Web 搜索重定向到 `/down.html`，无结果页；
3. `csrfToken` Cookie 未见 Secure/HttpOnly；
4. 视频详情页移动端播放器固定 1240px，390 视口横向溢出；
5. 未知路径与 `sitemap.xml` 返回 200 + 404 内容（软 404）。

## 9. 测试范围与合规
- 只测公开页面，不做压测/渗透/批量造数；
- 压测、安全扫描需站点方书面授权；
- 本项目不是站点源码克隆，无法拉取原站源码。

## 10. 新增用例
1. 在 `tests/` 新建 `test_xxx.py`；
2. 在 `cases.json` 加元数据（可选）；
3. 平台点“刷新用例”自动出现。

## 11. 与 MeterSphere 的关系
MeterSphere CE 不能直接执行 Playwright/Python UI 脚本。本平台是独立外部执行器：

- MeterSphere 管计划、验收、缺陷；
- 本平台管 Python UI 执行与报告；
- 在测试计划里登记平台地址和报告链接。

## 12. CI 与冒烟门禁

- `.github/workflows/platform-unit.yml`：push/PR 跑平台单测（隔离 DB，不访问站点）；
- `.github/workflows/smoke.yml`：每天 09:00（UTC 01:00）与手动触发，跑 8 条 smoke；仓库变量 `ZG_BASE_URL` 可覆盖被测地址；
- 本地等价命令：`./scripts/run_smoke.sh`。

> 若 Git 仓库根是 `media-test-lab` 而不是 `zgnews-tests`，请把两个 workflow 移到仓库根 `.github/workflows/`，并给 job 加 `defaults.run.working-directory: zgnews-tests`。

## 13. 旧 AI 流水线（历史说明，写入已停用）

旧版本的自动串行流水线现已拆成独立模块。`/pipeline` 转入 AI 用例工厂，旧流水线和邮件记录通过 `/history` 查阅。当前人员路由与收件人在“环境与设置”管理，配置存入数据库，不再使用旧 `pipeline_config.json` 驱动新模块。请按本文顶部的新流程操作。

## 14. 参考与 Roadmap
- [Playwright Python](https://github.com/microsoft/playwright-python)（15k stars）
- [Chart.js](https://github.com/chartjs/Chart.js)（65k stars，本地 vendor）
- [pytest-html](https://github.com/pytest-dev/pytest-html)（779 stars）
- [Allure](https://github.com/allure-framework/allure2)（5.5k stars）
- [ReportPortal](https://github.com/reportportal/reportportal)（2k stars）
- [Kiwi TCMS](https://github.com/kiwitcms/Kiwi)（1.2k stars）
- 平台仪表盘参考 Allure/ReportPortal 的“趋势 + 最近结果 + 覆盖”布局，但保持轻量、自研。
- 完整 TMS 备选：Kiwi TCMS、ReportPortal（暂不引入）；
- 持续计划见 `ROADMAP.md`。
