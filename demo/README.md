# 演示包（P0）

面向领导演示的“自动化测试能力”材料包。目标：10 分钟内讲清**能跑、可信、有发现**。

## 目录

```text
demo/
├── DEMO.md                     10 分钟演示脚本（含 Q&A、检查清单）
├── QA-Capability-Brief.docx    一页纸《自动化测试能力说明》可编辑版
├── QA-Capability-Brief.pdf     一页纸 PDF（发群/打印）
├── Defect-Cards.docx           缺陷卡片（A4，3 张/页）
├── Defect-Cards.pdf            缺陷卡片 PDF（打印/带走）
├── build_brief.py              一页纸生成脚本（改数据后重跑）
├── build_defect_cards.py       缺陷卡片生成脚本（读 defects.json）
├── capture_evidence.py         证据采集脚本（重新跑一遍现场）
└── evidence/
    ├── index.html              证据包首页（离线可开，演示用）
    ├── issues.md               5 个问题的文字版（可建缺陷单）
    ├── measurements.json       现场采集的原始数据
    └── shots/                  平台、报告、问题截图
```

## 三步开始

1. 启动平台（若未启动）：`cd zgnews-tests && ./start.sh`
2. 打开演示脚本：`demo/DEMO.md`
3. 演示时按顺序打开：
   - 平台 http://127.0.0.1:8090/
   - 证据包 `demo/evidence/index.html`
   - 一页纸 `demo/QA-Capability-Brief.pdf`

## 数据口径

- 用例：38 条 / 22 个文件 / 12 个测试域；
- 最近运行：`20261106-151242-c818a1`，33 passed + 5 xfail，154.1s；
- **有效通过率 = passed /（passed + failed）= 33/33 = 100%**；
- xfail 是已确认的站点问题，单列展示，不计入分母。

## 重新生成缺陷卡片

数据源：`zgnews-tests/defects.json`（平台“已知问题”页也读这份）。

```bash
cd demo
"/Applications/DSH Desktop.app/Contents/Resources/office-runtime/primary-runtime/dependencies/python/bin/python3" build_defect_cards.py
ELECTRON_RUN_AS_NODE=1 "/Applications/DSH Desktop.app/Contents/Frameworks/DSH Desktop Helper.app/Contents/MacOS/DSH Desktop Helper" \
  "/Applications/DSH Desktop.app/Contents/Resources/office-cli.mjs" \
  convert --input Defect-Cards.docx --output Defect-Cards.pdf
```

## 重新采集证据

```bash
cd demo
../zgnews-tests/.venv/bin/python capture_evidence.py
```

会刷新 `evidence/shots/` 与 `measurements.json`（需要平台 8090 在跑，且能访问外网站点）。
如果换了 run id：

```bash
ZG_RUN_ID=<新的 run id> ../zgnews-tests/.venv/bin/python capture_evidence.py
```

## 重新生成一页纸

```bash
cd demo
"/Applications/DSH Desktop.app/Contents/Resources/office-runtime/primary-runtime/dependencies/python/bin/python3" build_brief.py
ELECTRON_RUN_AS_NODE=1 "/Applications/DSH Desktop.app/Contents/Frameworks/DSH Desktop Helper.app/Contents/MacOS/DSH Desktop Helper" \
  "/Applications/DSH Desktop.app/Contents/Resources/office-cli.mjs" \
  convert --input QA-Capability-Brief.docx --output QA-Capability-Brief.pdf
```

> PDF 导出不会覆盖同名文件，先删除旧 PDF。

## 注意

- 证据与站点强相关：文章、频道、视频 ID 变化时，需同步更新用例与采集脚本；
- 5 条 xfail 是**已知问题**，不是跳过；修复后请删除用例中的 `pytest.xfail(...)`；
- 演示前 30 分钟预热一次，并保留最近一份 Allure 目录作离线兜底。
