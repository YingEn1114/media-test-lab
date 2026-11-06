# MediaCMS 版本回归测试计划

> 本文档针对 **MediaCMS**（`mediacms/`，Playwright + MeterSphere）。  
> 正观新闻（`zgnews-tests/`）的测试计划与统计口径见 `zgnews-tests/TEST_PLAN.md`、`zgnews-tests/README.md`。

## 1. 计划信息

| 项 | 内容 |
|---|---|
| 计划名称 | MediaCMS 版本回归 |
| MeterSphere 计划 ID | `1722507388658917376` |
| 所属项目 | MediaCMS 测试项目（`1721461186165219328`） |
| 被测系统 | MediaCMS（http://localhost/） |
| 测试范围 | 媒体站 Web、视频播放器、HLS、上传/评论、H5、后端 API |
| 执行周期 | 每个版本 / 迭代回归 |
| 入口准则 | 环境部署完成、媒体可播放、API `/api/v1/media` 返回 200 |
| 出口准则 | P0/P1 用例 100% 通过；P2 通过率 ≥ 95%；无 Blocker 缺陷 |

## 2. 用例分层（推荐做法）

| 层级 | 放在哪里 | 内容 |
|---|---|---|
| 自动化 UI | Git + CI（Playwright） | 17 条 Web/播放器/H5 用例，结果归档 HTML/JUnit |
| 自动化 API | MeterSphere | `MediaCMS 冒烟场景 v4`，原生执行、原生报告 |
| 手工验收 | MeterSphere 功能用例 | 5 条面向业务的验收用例，不跟自动化一一对应 |

> 不建议把 17 条 Playwright 一对一建成 17 条功能用例：会造成双份维护、执行状态对不上、审计噪音大。自动化的价值在 CI 证据，测试计划的价值在业务验收和发布门禁。

## 3. 手工验收用例（建议建在 MeterSphere 用例库）

| 编号 | 用例 | 验收点 |
|---|---|---|
| TP-01 | 首页、搜索与分类 | 首页可访问、搜索 Test 有结果、分类页可打开 |
| TP-02 | 视频播放器核心 | 播放/暂停/进度/音量/倍速/全屏/清晰度 |
| TP-03 | 上传与 HLS | 上传视频、转码成功、HLS 可播放 |
| TP-04 | 登录与评论 | admin 登录、评论提交、权限控制 |
| TP-05 | 移动端 H5 | 390x844 下首页/播放页可用 |

## 4. 自动化映射

| 自动化文件 | 对应验收用例 |
|---|---|
| `home.spec.mjs`、`web.spec.mjs`（搜索/分类） | TP-01 |
| `video.spec.mjs`、`player-controls.spec.mjs` | TP-02 |
| `upload.spec.mjs`、API 场景 v4（HLS） | TP-03 |
| `web.spec.mjs`（登录/评论） | TP-04 |
| `mobile.spec.mjs` | TP-05 |

## 5. 执行流程

```
Jenkins:
  1. Playwright（17 条）→ playwright-report + results.xml
  2. MeterSphere 场景 v4 → 原生报告
  3. 归档报告 + 在计划里登记构建链接
GitHub Actions:
  Playwright（BASE_URL 指向可达环境）→ artifact
```

发布门禁：

1. Playwright 0 失败；
2. MeterSphere 场景 v4 SUCCESS；
3. 5 条手工验收用例通过；
4. 无 Blocker / 严重缺陷。

## 6. 缺陷与报告

- 自动化失败：先看 Playwright trace/screenshot，再提单；
- API 失败：看 MeterSphere 报告详情（状态码/响应时间）；
- 缺陷关联到测试计划，修复后回归对应自动化用例；
- 报告入口：Playwright HTML + MeterSphere 场景报告。

## 7. 在 MeterSphere 中完成最后关联

计划已创建，但 3.6.10 没有直接给“场景关联”的公开 API，需要在 UI 完成一次：

1. 测试计划 → `MediaCMS 版本回归`；
2. 关联场景 → 选择 `MediaCMS 冒烟场景 v4`；
3. 用例库 → 新建 TP-01 ~ TP-05 五条功能用例；
4. 测试计划 → 关联功能用例；
5. 后续每次回归在计划里执行/登记结果。

这样职责清晰：**MeterSphere 管计划、验收、缺陷；Git/CI 管自动化代码与执行证据。**
