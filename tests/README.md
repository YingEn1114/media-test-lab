# MediaCMS Web / 视频播放器自动化测试

## 环境
- Node 20.8.1（MeterSphere 仓库自带：`../../metersphere-3.x/frontend/.node/node-v20.8.1-darwin-x64`）
- 本地默认系统 Google Chrome；CI 使用 Playwright Chromium

## 运行
```bash
cd ~/Downloads/media-test-lab/tests
export PATH="/Users/yangjingwen/Downloads/metersphere-3.x/frontend/.node/node-v20.8.1-darwin-x64/bin:$PATH"
npx playwright test --config=playwright.config.mjs
```

## 环境变量
| 变量 | 默认值 | 说明 |
|---|---|---|
| `BASE_URL` | `http://localhost` | 被测 MediaCMS 地址 |
| `PW_CHANNEL` | `chrome` | 浏览器通道；CI 用 `chromium` |
| `MS_BASE_URL` | `http://127.0.0.1:8081` | MeterSphere 地址 |
| `MS_USERNAME` / `MS_PASSWORD` | `admin` / `metersphere` | MeterSphere 服务账号，CI 自动登录 |
| `MS_TOKEN` / `MS_CSRF` | 无 | 可选，直接复用会话（会过期） |
| `MS_PROJECT_ID` / `MS_SCENARIO_ID` | 无 | 项目与场景 ID |
| `MEDIACMS_TOKEN` | 无 | 上传用例清理用；MediaCMS admin API Token，未设置则跳过清理 |

## 用例（17 条）
| 文件 | 覆盖 |
|---|---|
| `specs/home.spec.mjs` | 首页标题、导航、媒体卡片、Test Video |
| `specs/video.spec.mjs` | HLS master.m3u8、video.js、640x360、播放/暂停 |
| `specs/player-controls.spec.mjs` | 静音/音量、进度条 seek、倍速、全屏、设置菜单、弱网 HLS |
| `specs/web.spec.mjs` | 搜索、分类、登录、上传跳转/上传页、评论框、评论提交 |
| `specs/upload.spec.mjs` | 真实上传 1 秒测试视频 |
| `specs/mobile.spec.mjs` | 390x844 移动端首页与播放页 |

## 报告
```bash
npx playwright show-report playwright-report
```
- HTML：`playwright-report/index.html`
- JUnit：`results.xml`
- 截图：`screenshots/`
- 上传夹具：`fixtures/e2e-upload.mp4`（24KB）
- 上传清理：设置 `MEDIACMS_TOKEN` 后，用例结束会调用 MediaCMS API 删除刚上传的媒体

## CI
- GitHub Actions：`.github/workflows/e2e.yml`（需设置仓库变量 `MEDIA_BASE_URL`）
- Jenkins：`Jenkinsfile`（`MEDIA_BASE_URL`、`MS_USERNAME`、`MS_PASSWORD`、`MS_PROJECT_ID`、`MS_SCENARIO_ID`）
- MeterSphere 触发：`node scripts/run-ms-scenario.mjs`
  - 有 `MS_USERNAME/MS_PASSWORD` 时自动 RSA 登录换 token；
  - 也兼容 `MS_TOKEN/MS_CSRF`。

手动登录并打印 token：
```bash
MS_USERNAME=admin MS_PASSWORD=metersphere node scripts/ms-login.mjs
```

## 被测对象
- MediaCMS: http://localhost/
- 视频: http://localhost/view?m=juMSnf8VT
- HLS: http://localhost/media/hls/4b2c62d9ee1e4643af54949706180754/master.m3u8

## 测试计划
公司级回归计划与用例分层见：`../TEST_PLAN.md`
