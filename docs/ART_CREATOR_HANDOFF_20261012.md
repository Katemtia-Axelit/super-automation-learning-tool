# 美术资源绘制交接｜2026-10-12 最终检测版

**受众：独立美术绘制对话。只负责画图与导出，不改业务代码。**

**结论：可以正式开始素材设计；SVG 自动导入链路尚未安全验收，不得直接批量接入生产。**

项目根目录：`D:\Axelit\.工作\trae\超级自动化学习工具`。权威机器清单：`static/assets/art-manifest.json`；资源生成器：`scripts/art-asset-registry.js`；生成的样式：`static/assets/art-overrides.css`；真实页面入口：`src/index.html`。历史草案：`docs/M1_5_ASSET_SEAM_CONTRACT_20261012.md`，与当前清单有路径冲突，**勿按草案盲目导出**。

## 检测结果
- 2026-10-12 20:08，本机注册器测试 60/60 PASS，隔离真实 Factory 页面 Playwright A–G 7/7 PASS，check/list 退出码0，八学科无素材时 Chromium 样式等价，无图像请求。
- 目前 `static/assets/` 中 SVG **0张**；没有完成实际生产素材注入。Batch 18/18已结算、0未结算；修复 SVG 安全的 S 仅创建 Envelope，尚未 Batch 登记/派发。
- **安全红线：**TEMP 复现显示当前注册器会接受 SVG 的 onload 和 CSS @import，遇 script 标签也可能成功退出并覆盖 CSS。正式导入前须由 Controller 完成安全修复与隔离测试，绘图对话不能自行运行生产 `build`。

## 美术风格
复古幻想魔法卡牌：金属边饰、纸张纹理、线刻、精致而非过度现代极简。卡面中部文字区留白，卡背可丰富；八学科用色区分但保持风格统一。计时器采用机械表盘/怀表与真实数字嵌入的一体化设计，保持进度条清晰可见，**不要将精确时间或百分比画死在素材里**。禁止素材遮挡按钮、焦点环、反馈表单和任务标题。

## 第一批建议制作：现有清单路径及 CSS 槽位
所有下列路径均相对于 `static/assets/`，不可随意改名。

| 文件路径 | 建议 viewBox | 说明 |
|---|---|---|
| `cards/faces/theme-math/front-bg.svg` | 0 0 700 440 | 数学蓝色网格/几何 |
| `cards/faces/theme-lang/front-bg.svg` | 0 0 700 440 | 语言绿/自然 |
| `cards/faces/theme-history/front-bg.svg` | 0 0 700 440 | 历史琥珀/羊皮纸 |
| `cards/faces/theme-code/front-bg.svg` | 0 0 700 440 | 编程青绿/机械 |
| `cards/faces/theme-write/front-bg.svg` | 0 0 700 440 | 写作紫/羽毛笔 |
| `cards/faces/theme-science/front-bg.svg` | 0 0 700 440 | 科学蓝紫/实验 |
| `cards/faces/theme-review/front-bg.svg` | 0 0 700 440 | 复习金/循环 |
| `cards/faces/theme-default/front-bg.svg` | 0 0 700 440 | 通用中性金边 |
| `cards/backs/common/back-pattern.svg` | 0 0 700 440 | 通用卡背纹理 |
| `deck/deck-base.svg` | 0 0 280 196 | 抽卡牌堆 |
| `discard/discard-back.svg` | 0 0 280 196 | 弃牌堆（页面会变灰） |
| `dock/frame.svg` | 0 0 480 160 | 计时器 Dock 外框 |
| `progress/progress-ticks.svg` | 细长且可平铺 | 金色动态进度条刻度，不能遮挡填充 |
| `flying/flying-card.svg` | 0 0 700 440 | 飞行卡装饰，动作仍由程序控制 |
| `ui/modal-frame.svg` | 0 0 1040 720 | 通用弹窗边框，内区透明 |

**特别注意：**历史文档里的牌堆/弃牌为 `cards/deck/`、`cards/discard/`；当前机器清单是 `deck/`、`discard/`，以上表为准。

## 第二批：绘图可启动，但尚未可靠接线
- `cards/backs/common/emblem.svg`（144×144）；`dock/pocket-watch.svg`（机械表盘）；`care/care-illust-success.svg`（640×400）；`feedback/feedback-paper.svg`（1040×720）：有机器清单，但缺有效 CSS 消费者或与通用 modal 变量冲突，不保证自动显示。
- `ui/multi-thumb.svg`（44×44）：清单的 display/content 变量与页面实际 enable 变量不一致，待接线。
- `cards/ornaments/corner-all.svg`：清单为合并四角，但页面是小块独立卡角，几何不匹配；建议先提供四角各 28×28 的源稿，正式路径待确定。
- `cards/backs/per-theme/theme-{theme}/back-pattern.svg`：现有 fallback 可能将首个主题卡背用于全部主题，**不是独立逐主题切换**。
- 用户特别希望 `study / exercise / work / life / other` 五类**任务类型卡背**；与八种学科主题不同，当前程序没有可靠任务类型→卡背映射。请先做五种概念图与方案，不自创生产路径。
- 草案中的四角单独文件、header-band、body-pattern、watch-ticks、progress-fill 等不是现有自动绑定完整项，可绘制源稿但不得声称放入路径即可显示。

## 技术/交付红线
交付可编辑矢量源、**透明 SVG** 和 PNG 预览；PNG 用于沟通，不用于当前自动绑定。SVG 必须 `viewBox`，避免外链、script、foreignObject、onload 等事件、style/@import、SVG 内置动画与外部字体；不要假设作为外部 CSS 背景加载的 SVG 能继承网页 currentColor/主题 CSS 变量。建议单张卡面≤24KB、弹窗≤32KB；当前工具技术上限64KB/张，首版全套建议≤500KB。

最终导入步骤由开发 Controller 执行：完成 S 的 SVG 安全验收后，将正式资源放入 `static/assets`，依次 `node scripts/art-asset-registry.js list`、`check`、`build`，再进行真实页面、时钟/进度条、弹窗与 Factory A–G 复测。安全修复前只进行独立绘制和审核，**不得执行对不受信任 SVG 的生产 build**。

## 请美术对话直接执行
先完成八学科卡面+一张通用卡背的同风格草图/可读性预览。用户确认方向后再完成牌堆、弃牌和计时器机械面板/进度条。清楚区分“素材设计完成”“资源文件已审核”和“程序已接线”三个状态；不要参与代码开发。

**本文件是可以给画师执行的绘制交接，不是美术资源接口已全部验收的声明。**
