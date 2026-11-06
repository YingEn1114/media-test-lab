---
version: alpha
name: ZG QA 检验台
description: 正观新闻自动化测试执行台，给 QA 与研发负责人提供运行、报告与缺陷证据；像一张被荧光笔标记过的检验单，而不是营销页。
colors:
  ground: "#E9EDF0"
  surface: "#FFFFFF"
  surface-2: "#F4F6F8"
  ink: "#101820"
  muted: "#55636F"
  line: "#C7D0D6"
  line-strong: "#7C8B96"
  navy: "#123B5E"
  red: "#B3261E"
  green: "#1E6B45"
  amber: "#7A4A00"
  highlight: "#FFE066"
  focus: "#0B5FFF"
typography:
  display:
    fontFamily: "IBM Plex Sans"
    fontSize: 30px
    fontWeight: 600
    letterSpacing: "-0.02em"
  body:
    fontFamily: "IBM Plex Sans, PingFang SC"
    fontSize: 13px
    lineHeight: 1.6
  mono:
    fontFamily: "IBM Plex Mono"
    fontSize: 11.5px
rounded:
  sm: 2px
  md: 2px
spacing:
  sm: 8px
  md: 16px
  lg: 24px
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
---

## Overview

正观新闻的自动化测试执行台，面向 QA、研发负责人与需要看证据的管理者。它的工作是让一次运行、一个失败、一条缺陷在几秒内被看懂。

视觉来自 QA 工作台本身：打印出来的检验单、荧光笔划过的行、盖在结果栏上的状态章、方格纸、设备读数。没有衬线标题、没有装饰编号、没有奶油纸张——那些是“看起来有设计”的默认，不是这个产品的材料。

## Colors

- **Ground `#E9EDF0`：** 冷灰的办公纸，不是米色。叠 24px 方格，像检验单的坐标纸。
- **Ink `#101820`：** 正文与标题，白底 17.9:1，灰底 15.2:1。
- **Muted `#55636F`：** 次级信息，白底 6.2:1，灰底 5.3:1，均过 AA。
- **Navy `#123B5E`：** 唯一的行动色，用于主按钮、图表主线、当前状态；白字 11.6:1。
- **Red `#B3261E`：** 失败与 P1，只表示状态，不做装饰。
- **Green `#1E6B45`：** 通过。
- **Amber `#7A4A00`：** xfail、P2、运行中；在白底 7.5:1。
- **Highlight `#FFE066`：** 荧光笔，只用于当前导航与行悬停；上面压 ink 13.7:1。
- **Focus `#0B5FFF`：** 键盘焦点环，2px 外扩。

## Typography

IBM Plex Sans 做界面与标题，IBM Plex Mono 只出现在真正需要对齐扫描的数据：用例 nodeid、耗时、日志、报告文件名。中文回退 PingFang SC。没有展示衬线，没有全大写的 eyebrow，没有用等宽字体做装饰标签。

字号：30 / 20 / 16 / 14 / 13 / 12 / 11。数字一律 `tabular-nums`。

## Layout

64px 顶栏 + 220px 左侧索引 + 最大 1320px 的工作区。索引是活页夹的标签，不是深色侧边栏；当前项用荧光笔色块标记，不用竖条。总览的 KPI 是一条被横线切开的读数带，不是五张卡片。

## Elevation & Depth

没有阴影。层级只用 1px 线、底色差和字重表达。卡片的边界就是纸上的框。

## Shapes

统一 2px 圆角；状态章也是 2px。没有胶囊、没有 12px 大圆角。图片与图表使用直角边框。

## Components

- **顶栏：** 品牌方块 + 被测目标 / 环境 / 版本，底部 2px 墨线。
- **索引：** 六个入口，无编号；当前项荧光笔底。
- **按钮：** 2px 圆角，1px 边；主按钮 navy 实心，次按钮白底；`:hover`、`:active`、`:focus-visible`、`:disabled` 全有。
- **状态章：** 1px 描边、大写、2px 圆角，颜色即语义（通过绿 / 失败红 / xfail 琥珀）。
- **表格：** 表头 1px 墨线，行悬停荧光笔淡底，数字等宽对齐。

## Do's and Don'ts

- Do 每个页面复用同一套 token、顶栏、索引与状态章。
- Do 在页面里新增 token 前，先写进本文件。
- Don't 使用：奶油底 + 陶土色（SD1）、装饰性 01/02/03（SD6）、全大写 eyebrow / 等宽小标签 / 中点分隔的元信息（SD4）、标题里单独染一个词（SD5）。
- Don't 使用：彩色左边条（K4）、卡片阴影（K2）、胶囊徽章、衬线展示字、`→` 焊在按钮上。
- Don't 把 mono 用在装饰性小标签上；它只为代码、ID、耗时和日志服务。

## Signature

荧光笔色块标出“当前所在”，状态章盖出“结果是什么”。两件事都来自真实的检验动作，不是装饰。
