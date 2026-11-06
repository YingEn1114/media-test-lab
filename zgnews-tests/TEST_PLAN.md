# 正观新闻站点测试计划

## 1. 被测对象
- 站点：https://www.zhengguannews.cn/
- 类型：新闻门户（服务端渲染 + jQuery）
- 测试方式：公开页面黑盒测试；压测/渗透需授权

## 2. 测试项矩阵

| 编号 | 测试项 | 优先级 | 当前状态 | 工具/说明 |
|---|---|---|---|---|
| T01 | 首页/导航/频道 | P0 | ✅ 已实现 | Playwright |
| T02 | 列表页/分页 | P0 | ✅ 列表页；分页待补 | Playwright |
| T03 | 新闻详情/正文/图片 | P0 | ✅ | Playwright |
| T04 | 搜索 | P1 | ⚠️ 搜索弹层可用；结果页重定向下载页 | Playwright + xfail |
| T05 | 响应式/H5 | P1 | ✅ 390x844 | Playwright |
| T06 | SEO（title/meta/canonical） | P1 | ✅；无 h1 为缺陷 | Playwright |
| T07 | 安全响应头/Cookie | P1 | ✅ 被动检查 | requests |
| T08 | 链接可用性 | P1 | ✅ 抽样 8 条 | requests + BS4 |
| T09 | 性能基线 | P2 | ✅ DCL/资源数 | Playwright Performance |
| T10 | 可访问性 | P2 | ✅ 基础；缺 h1 | Playwright |
| T11 | 浏览器兼容 | P1 | ⏳ 待补 Safari/Firefox | Playwright projects |
| T12 | 弱网/异常 | P2 | ⏳ 待补 | route/CDP |
| T13 | 图片/媒体资源 | P2 | ⏳ 待补 | 资源状态/尺寸 |
| T14 | 接口/API | P2 | ⏳ 待补 | 抓包后补 |
| T15 | 兼容/分辨率矩阵 | P2 | ⏳ 待补 | 多 viewport |
| T16 | 监控巡检 | P3 | ⏳ 待补 | 定时任务 |

## 3. 入口/出口
- 入口：站点可访问、首页 200、Chrome 可用；
- 出口：P0 全通过；P1 **有效通过率**（passed /（passed + failed），xfail 不计入分母）≥ 95%；无新增 Blocker；已知问题有记录。

## 4. 执行
- Runner：http://127.0.0.1:8090/
- 命令行：`.venv/bin/python -m pytest -q --html=reports/report.html`
- 报告：`reports/`

## 5. 风险
- 第三方站点内容/结构随时变化，用例需定期维护；
- 无授权不做压测/渗透；
- 搜索结果页当前不可用，属于站点现状，不是脚本问题。
