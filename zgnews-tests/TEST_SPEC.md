# 正观新闻测试细则 v4（原站，38 条）

## 1. 自动化用例

| ID | 用例 | 优先级 | 步骤 | 预期 | 自动化文件 |
|---|---|---|---|---|---|
| A01 | 首页加载 | P0 | 打开 `/` | 200；title 含“正观新闻”；导航 ≥10；新闻链接 ≥10；搜索框存在 | `test_home.py` |
| A02 | 频道导航 | P0 | 首页点击“郑州” | 进入 `/list/16.html`；title 含“郑州” | `test_navigation.py` |
| A03 | 列表页 | P0 | 打开 `/list/16.html` | 200；title 含“郑州”；新闻链接 ≥5 | `test_list.py` |
| A04 | 新闻详情 | P0 | 首页取第一条新闻进入 | 200；`.post-content` 非空；有 h1/h2 | `test_article.py` |
| A05 | 搜索弹层 | P1 | 点搜索图标 | 弹层可见；输入“正观”值正确 | `test_search.py` |
| A06 | 搜索结果页 | P1 | 打开 `/search.html/正观` | 无 404；线上重定向为已知问题（xfail） | `test_search.py` |
| A07 | 移动端 H5 | P1 | 390x844 打开首页 | 标题正确；viewport 存在；导航存在 | `test_responsive.py` |
| A08 | 首页 SEO | P1 | 打开首页 | description 非空；canonical 存在 | `test_seo.py` |
| A09 | 详情 SEO | P1 | 打开任一新闻 | title 含站点名；description 非空 | `test_seo.py` |
| A10 | 安全响应头 | P1 | GET 首页 | nosniff、X-Frame-Options、X-XSS-Protection | `test_security.py` |
| A11 | 链接可用性 | P1 | 抽 8 条导航/新闻链接 | 状态码 <400 | `test_links.py` |
| A12 | 性能基线 | P2 | 打开首页 | DCL <15s；资源数 >10 | `test_performance.py` |
| A13 | 可访问性 | P2 | 打开首页 | 有标题；alt 缺失 ≤80%；搜索框有 placeholder | `test_accessibility.py` |
| A14 | 首页 HTTP 契约 | P1 | GET `/` | text/html；nosniff；gzip/br；正文 >5000 | `test_http_api.py` |
| A15 | HEAD 首页 | P1 | HEAD `/` | 200；text/html | `test_http_api.py` |
| A16 | robots.txt | P1 | GET `/robots.txt` | 200；含 User-agent/Disallow | `test_http_api.py` |
| A17 | 静态资源 CDN | P1 | 取首页 CSS/JS | 200；类型 css/javascript；体积 >100B | `test_http_api.py` |
| A18 | 图片 CDN | P1 | 取首页 3 张图 | 200；image/*；体积 >1KB | `test_http_api.py` |
| A19 | 未知路径 | P1 | GET 随机不存在路径 | 200 且内容 404（软 404，xfail） | `test_http_api.py` |
| A20 | sitemap.xml | P2 | GET `/sitemap.xml` | 200 且内容 404（软 404，xfail） | `test_http_api.py` |
| V01 | 视频频道列表 | P1 | 打开 `/list/26.html` | 视频卡片/链接 ≥5 | `test_video.py` |
| V02 | 播放器加载 | P1 | 打开首个视频详情 | `<video>` 有元数据/尺寸/readyState | `test_video.py` |
| V03 | 播放/暂停 | P1 | muted play() 后暂停 | paused 状态切换 | `test_video.py` |
| V04 | 进度跳转 | P1 | currentTime=10 | 位置落在 8–20s | `test_video.py` |
| V05 | 音量/静音 | P1 | 设置 muted/volume | 属性生效 | `test_video.py` |
| V06 | 播放器控件 | P1 | 检查 Prism 控件 | 控制条/进度/音量存在 | `test_video.py` |
| V07 | MP4 Range | P1 | HEAD + Range 0-1023 | video/mp4、206、1024B | `test_video.py` |
| V08 | 移动端播放器 | P1 | 390x844 打开视频 | 视频宽度 ≤390（线上溢出，xfail） | `test_video.py` |
| A21 | 新闻 JSON-LD | P1 | 打开详情页 | NewsArticle 含 headline/date/image/author/publisher | `test_metadata.py` |
| A22 | OG / canonical | P1 | 打开详情页 | og:type/title/url/image；canonical=URL | `test_metadata.py` |
| A23 | 分享组件 | P2 | 打开详情页 | 微信/微博图标 ≥3；“分享至”文案 | `test_share.py` |
| A24 | 页脚合规 | P1 | 打开首页 | 关于/协议/隐私/版权/ICP；内部链接 200 | `test_footer.py` |
| A25 | 登录弹层 | P1 | 点击“登录” | 短信/密码登录、输入框、验证码 | `test_login_modal.py` |
| A26 | 正观早参专题 | P1 | 打开 `/special/2708.html` | 标题含“正观早参”；日历存在 | `test_special.py` |
| A27 | 全部频道 | P1 | 16 个频道链接 | 均 200 且 HTML | `test_channels.py` |
| A28 | 首页栏目 | P1 | 打开首页 | 视频 swiper ≥3、专题入口 ≥3 | `test_home_sections.py` |
| A29 | 搜索边界 | P2 | 空关键词/特殊字符 | 空不跳转；特殊字符现状跳下载页（xfail） | `test_search_edge.py` |
| A30 | 下载页 | P2 | 打开 `/down.html` | 标题、应用市场链接 | `test_download.py` |

## 2. 基础测试项覆盖

| 测试项 | 状态 |
|---|---|
| 首页/导航/列表/详情 | ✅ |
| 搜索（弹层/结果） | ✅（结果页 xfail） |
| 响应式 H5 | ✅ |
| SEO | ✅ |
| 安全响应头 | ✅ |
| 链接/静态资源/图片 CDN | ✅ |
| HTTP 接口契约（HEAD/robots） | ✅ |
| 性能基线 | ✅ |
| 可访问性基础 | ✅ |
| 软 404（未知路径/sitemap） | ✅（xfail） |
| 分页 | ⏳ 原站列表未提供稳定分页结构 |
| 多浏览器/弱网/视觉回归 | ⏳ Phase 4 |
| 压测/渗透 | ⛔ 需授权 |

## 3. 执行结果

最近一次全量运行：2026-11-06 15:12（run `20261106-151242-c818a1`，38 条，154.1s）。

```text
33 passed, 5 xfailed（共 38 条）
有效通过率 33/33 = 100%
```

口径：**有效用例 = passed + failed**；xfail 为已确认的站点现状，单独统计，不计入通过率分母。5 条 xfail 为 A06、A19、A20、A29、V08。

## 4. 已知缺陷/问题

1. 全站无 `h1`（首页仅 h3）；
2. Web 搜索重定向到 `/down.html`；
3. `csrfToken` Cookie 未见 Secure/HttpOnly；
4. 未知路径与 `sitemap.xml` 返回 **HTTP 200 + 404 内容**（软 404）；
5. 视频详情页移动端播放器固定 1240px，390 视口横向溢出；
6. 特殊字符搜索同样被重定向到 `/down.html`。

## 5. 维护规则

- 新增用例：`tests/test_*.py` + `cases.json` 元数据；
- 平台“刷新用例”自动发现；
- 测试点拆分见 `TEST_POINTS.md`；
- 线上站变化时先判断是站点变更还是脚本问题。
