# 视频与媒体播放器测试设计

## 1. 被测实现

- 视频频道：`/list/26.html`
- 视频详情：`/video/{id}.html`（例如 `/video/23172.html`）
- 播放器：原生 `<video>` + 阿里 Prism 播放器外壳
- 媒体：MP4 直链（`media.zhengguannews.cn/...mp4`），**不是 HLS**
- 资源：约 130MB，支持 `Range: bytes=...` 返回 206

## 2. 测试分层

| 层 | 测什么 | 用例 |
|---|---|---|
| 页面/导航 | 视频频道卡片、详情页入口 | V01 |
| 播放器初始化 | `<video>`、Prism 容器、duration、分辨率、readyState | V02 |
| 播放控制 | play/pause、seek、mute/volume | V03–V05 |
| 播放器 UI | 控制条、进度条、音量控件、大播放按钮 | V06 |
| 媒体交付 | MP4 HEAD、Content-Type、Content-Length、Range 206 | V07 |
| 响应式 | 390x844 下播放器宽度/横向溢出 | V08 |

## 3. 用例设计要点

1. **不依赖自动播放**：Chrome 策略可能阻止有声自动播放，测试先 `muted=true` 再 `play()`。
2. **用媒体属性断言，不靠像素**：`paused`、`currentTime`、`duration`、`videoWidth/Height`、`readyState` 比截图稳定。
3. **seek 要留缓冲时间**：设置 `currentTime=10` 后等待 1s 左右再读，避免关键帧/缓冲导致瞬时值。
4. **媒体接口单独测**：HEAD 校验类型/大小；Range 请求校验 206 与 `Content-Range`，不下载完整 130MB。
5. **移动端单独视口**：`is_mobile` + 390x844，检查 `video` 宽度和 `scrollWidth`，能发现固定宽度播放器溢出。
6. **HLS 不适用**：当前是 MP4 progressive；若后续切换 HLS，再加 manifest、分片、码率切换用例。

## 4. 当前结果

| 用例 | 结果 |
|---|---|
| V01 视频频道列表 | ✅ |
| V02 播放器加载/元数据 | ✅ |
| V03 播放/暂停 | ✅ |
| V04 进度跳转 | ✅ |
| V05 音量/静音 | ✅ |
| V06 播放器控件 | ✅ |
| V07 MP4/Range | ✅ |
| V08 移动端播放器 | ⚠️ xfail：播放器固定 1240px，390 视口横向溢出 |

## 5. 后续可补

- 缓冲/卡顿：`waiting`/`canplay` 事件、弱网 route delay；
- 播放错误：404/损坏 URL 的 `error` 事件与提示；
- 全屏：`requestFullscreen` 与退出；
- 字幕/倍速（若播放器提供）；
- 视频列表分页、相关推荐跳转；
- 播放埋点/统计请求。
