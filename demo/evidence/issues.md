# 已确认问题清单（5 条）

> 采集时间：2026-11-06 11:54–11:56　｜　被测站点：https://www.zhengguannews.cn
> 原始数据：`measurements.json`　｜　截图：`shots/`
> 说明：以下均为**可复现的站点现状**，对应测试用例中的 5 条 `xfail`。

| 缺陷号 | 用例 | 问题 | 优先级 |
|---|---|---|---|
| DEF-01 | A06 | 搜索 302 → 下载页 | P1 |
| DEF-02 | A19 | 未知路径软 404 | P2 |
| DEF-03 | A20 | sitemap 软 404 | P2 |
| DEF-04 | A29 | 特殊字符搜索跳下载页 | P2 |
| DEF-05 | V08 | 移动端播放器溢出 | P1 |


---

## A06｜搜索结果被重定向到客户端下载页

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 用例 | `tests/test_search.py::test_search_results` |
| 现象 | 访问 `/search.html/正观` → **302** → `/down.html`（客户端下载页），无搜索结果页 |
| 影响 | 站内搜索不可用；用户被导流到下载页；搜索流量与 SEO 受损 |
| 证据 | `shots/01-search-redirect.png`；落地页 title「客户端下载 居中、守正、观天下 - 正观新闻」 |

**复现**

```bash
curl -sI "https://www.zhengguannews.cn/search.html/%E6%AD%A3%E8%A7%82" | head
# HTTP/2 302  location: /down.html
```

**建议**：恢复搜索结果路由；或在无结果时返回搜索页并给出「未找到」提示，而不是跳下载页。

---

## A19｜未知路径返回 HTTP 200 + 404 内容（软 404）

| 项 | 内容 |
|---|---|
| 优先级 | P2 |
| 用例 | `tests/test_http_api.py::test_unknown_path_soft_404` |
| 现象 | 随机不存在路径 `/this-path-not-exist-<uuid>.html` 返回 **HTTP 200**，正文仅 22 字节：`<h1>404,请求资源不存在了!</h1>` |
| 影响 | 搜索引擎可能收录无效 URL；监控/日志无法按状态码识别 404；缓存与 CDN 策略失真 |
| 证据 | `shots/02-soft-404-unknown.png`；`measurements.json → soft_404_unknown` |

**复现**

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://www.zhengguannews.cn/this-path-not-exist-$(uuidgen).html"
# 200
```

**建议**：未知路径返回 **404** 状态码 + 404 页面；保留现有文案即可。

---

## A20｜sitemap.xml 返回 HTTP 200 + HTML 404

| 项 | 内容 |
|---|---|
| 优先级 | P2 |
| 用例 | `tests/test_http_api.py::test_sitemap_soft_404` |
| 现象 | `/sitemap.xml` 返回 **200**，`Content-Type: text/html`，正文 `<h1>404,请求资源不存在了!</h1>` |
| 影响 | 搜索引擎无法抓取 sitemap；新内容收录变慢；与 robots 声明不一致 |
| 证据 | `measurements.json → soft_404_sitemap` |

**复现**

```bash
curl -sI "https://www.zhengguannews.cn/sitemap.xml" | grep -i content-type
# content-type: text/html; charset=utf-8
```

**建议**：返回 `application/xml` 的合法 sitemap；没有 sitemap 时明确 404，不要 200 + HTML。

---

## A29｜特殊字符/超长关键词搜索同样跳转下载页

| 项 | 内容 |
|---|---|
| 优先级 | P2 |
| 用例 | `tests/test_search_edge.py::test_search_edge` |
| 现象 | 输入 `测试<>&%20` + 30 个「长」→ 点击搜索 → `/down.html` |
| 影响 | 边界输入无反馈；与 A06 同根因；特殊字符处理不透明 |
| 证据 | `shots/04-search-special-chars.png`；`measurements.json → search_special_chars` |

**建议**：与 A06 一并修复；前端对关键词做 encodeURIComponent 与长度限制，后端做参数校验。

---

## V08｜390 视口下播放器固定 1240px，页面横向溢出

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 用例 | `tests/test_video.py::test_video_mobile_layout` |
| 现象 | 390×844 移动端上下文：`video` 渲染 **1240×702**，`documentElement.scrollWidth = 1412`，而 `clientWidth = 390` |
| 影响 | 移动端横向滚动、内容被裁切；播放器控件可能超出屏幕，影响观看与转化 |
| 证据 | `shots/05-mobile-video-overflow.png`（红线为 390px 视口边界）；`measurements.json → mobile_video` |

**复现**

```text
390×844 打开 https://www.zhengguannews.cn/video/23172.html
video.getBoundingClientRect().width = 1240
document.documentElement.scrollWidth = 1412
```

**建议**：播放器容器 `width:100%; max-width:100%`，视频 `aspect-ratio:16/9; height:auto`；断点内取消固定 1240px。

---

## 汇总

| 编号 | 问题 | 优先级 | 状态 |
|---|---|---|---|
| A06 | 搜索 302 → 下载页 | P1 | 待修复（xfail） |
| A19 | 未知路径软 404 | P2 | 待修复（xfail） |
| A20 | sitemap 软 404 | P2 | 待修复（xfail） |
| A29 | 特殊字符搜索跳下载页 | P2 | 待修复（xfail） |
| V08 | 移动端播放器溢出 | P1 | 待修复（xfail） |

> 修复后：删除对应用例中的 `pytest.xfail(...)`，让断言恢复为正常通过，即可作为回归门禁。
