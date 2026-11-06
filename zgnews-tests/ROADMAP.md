# 自研 Python 测试平台 Roadmap

## 定位
MeterSphere CE 不能执行 Playwright/Python UI 脚本，本平台作为 **外部执行器**：
Python 用例即资产，平台负责发现、运行、历史、报告；MeterSphere 负责计划/验收/缺陷。

## Phase 1（已完成）
- [x] FastAPI + SQLite 平台骨架
- [x] pytest 用例自动发现（新增 `tests/test_*.py` 自动出现）
- [x] 用例元数据（名称/描述/优先级/标签）`cases.json`
- [x] 勾选运行 / 全部运行
- [x] 实时 pytest 日志
- [x] 每次运行 HTML 报告
- [x] 运行历史（状态、耗时、用例数、报告链接）
- [x] Playwright Python + 本机 Chrome
- [x] UI v0.3：仪表盘、统计、筛选、控制台、历史
- [x] 取消运行、测试细则文档
- [x] 多页面 UI（总览/用例/运行/报告/设置）
- [x] Chart.js 趋势/环图/覆盖可视化
- [x] Allure 报告（本地 JRE + Allure CLI）
- [x] 可视化：有效通过率趋势（xfail 单列）、最近结果环图、测试点覆盖
- [x] v0.7 通过率口径统一：有效通过率 = passed/(passed+failed)，文档/API/UI 三处一致
- [x] v0.8 已知问题视图：defects.json + /defects 页面 + 总览 KPI + 可打印缺陷卡片
- [x] 界面重设计：Inspection Sheet 设计系统（DESIGN.md），avoid-ai-design 扫描 0 findings
- [x] 平台可靠性：启动自愈、/api/health、安全响应头、WAL、returncode 落库
- [x] 冒烟运行：按 smoke 标签跑 8 条核心用例（约 20–40 秒）
- [x] 测试数据去硬编码：文章/频道/专题改为首页发现，去掉 2026 硬断言
- [x] 运维脚本：check_platform.py、maintenance.py（默认 dry-run）
- [x] 平台单测：8 条，隔离 DB 覆盖筛选/计数/自愈/健康/安全头/鉴权
- [x] 冒烟门禁：pytest -m smoke（8 条约 22 秒）+ GitHub Actions
- [x] 本地冒烟脚本 scripts/run_smoke.sh
- [x] 视频播放器测试：列表/元数据/播放暂停/seek/音量/控件/MP4 Range
- [x] 38 条原站用例（含 HTTP 接口、视频、结构化数据/分享/登录/专题/频道）（首页/导航/列表/详情/搜索/H5/SEO/安全/链接/性能/可访问性）

## Phase 2（下一步）
- [ ] 标签/优先级筛选与搜索
- [ ] pytest-xdist 并行执行
- [ ] pytest-rerunfailures 失败重试
- [ ] 失败自动截图/录屏归档
- [ ] 用例启用/禁用（不删代码）
- [ ] 运行取消

## Phase 3（平台化）
- [ ] APScheduler 定时巡检
- [ ] Webhook/企业微信/钉钉通知
- [ ] 简单登录与角色（管理员/执行者）
- [ ] 环境配置页面（BASE_URL、浏览器、headless）
- [ ] 多项目/多站点

## Phase 4（测试类型补齐）
- [ ] Chromium/Firefox/WebKit 多浏览器
- [ ] 弱网/超时/异常
- [ ] 图片与静态资源完整性
- [ ] 接口 API 测试（requests/pytest）
- [ ] Lighthouse 性能/SEO
- [ ] 安全被动扫描（响应头/Cookie/TLS）
- [ ] 视觉回归（截图对比）

## Phase 5（集成）
- [ ] MeterSphere 测试计划链接/结果回写
- [ ] Kiwi TCMS / ReportPortal 选型（如需完整 TMS）
- [ ] GitHub Actions / Jenkins 触发
- [ ] Allure 报告（可选）

## 参考的开源组件（GitHub）
- `microsoft/playwright-python`：浏览器自动化
- `pytest-dev/pytest` + `pytest-html`：用例与报告
- `fastapi/fastapi` + `encode/uvicorn`：平台后端
- `pytest-dev/pytest-xdist`、`pytest-dev/pytest-rerunfailures`：并行/重试（待接）
- `agronholm/apscheduler`：定时任务（待接）
- 完整 TMS 备选：`kiwitcms/Kiwi`、`reportportal/reportportal`（较重，暂不引入）
