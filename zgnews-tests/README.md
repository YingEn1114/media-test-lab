# 正观新闻 Python UI 自动化测试

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

## 13. 参考与 Roadmap
- [Playwright Python](https://github.com/microsoft/playwright-python)（15k stars）
- [Chart.js](https://github.com/chartjs/Chart.js)（65k stars，本地 vendor）
- [pytest-html](https://github.com/pytest-dev/pytest-html)（779 stars）
- [Allure](https://github.com/allure-framework/allure2)（5.5k stars）
- [ReportPortal](https://github.com/reportportal/reportportal)（2k stars）
- [Kiwi TCMS](https://github.com/kiwitcms/Kiwi)（1.2k stars）
- 平台仪表盘参考 Allure/ReportPortal 的“趋势 + 最近结果 + 覆盖”布局，但保持轻量、自研。
- 完整 TMS 备选：Kiwi TCMS、ReportPortal（暂不引入）；
- 持续计划见 `ROADMAP.md`。
