---
name: 圆桌会议 (Roundtable)
about: 多模型 / 多 Agent 席位的结构化讨论，Issue 是过程权威
title: "[RT-<YYYYMMDD>-<nn>] <议题>"
labels: ["type:roundtable", "stage:proposal"]
assignees: ''
---

> 完整规范见 [`docs/ROUNDTABLE_PROTOCOL.md`](../../docs/ROUNDTABLE_PROTOCOL.md)。
> 本 Issue 是**过程权威**（讨论与分歧在此）；结论摘要入库到
> `docs/ROUNDTABLE_<date>.md`。

## 议题

<!-- 一句话说清本次会议要解决什么。 -->

## 席位与模型

| 席位 | 模型 | 职责 |
|---|---|---|
| `chair` | | 主持、收敛、宣布结束 |
| `architect` | | 架构与实现路径 |
| `critic` | | 反对意见与风险 |
| `analyst` | | 证据、基线与数据 |

> 席位标识必须用**固定席位名**（`chair`/`architect`/`critic`/`analyst`），
> **禁止用 Tab 序号**。同一席位跨轮次名字不得改变。

## 轮次计划

| 轮次 | 主题 | 预期产出 |
|---|---|---|
| 1 | | |

## 主持人

<!-- chair 是谁（人 / Agent / 模型）。 -->

## 结束判据

<!-- 什么条件下宣布结束。必须是可判定的条件。 -->

## 每条评论的固定头部（强约束）

每条席位评论**必须**以固定头部开始，否则视为**无效发言**，编排器不采信：

```text
[席位] architect
[模型] claude-opus-5.5
[轮次] 1
[会议] RT-20261127-01
[幂等键] <sha256 前 16 位>
[回复对象] <comment-id 或 none>

<正文>
```

**席位 Agent 必须自己发自己的评论。编排器只负责把全部评论注入下一轮提示词，
不得代写评论内容。**

## 结束时的收尾

- [ ] chair 发布结束评论
- [ ] 产出 `docs/ROUNDTABLE_<date>.md` 摘要（摘要 + 链接回本 Issue）
- [ ] 所有外部写操作记入 [`docs/external-write-log.md`](../../docs/external-write-log.md)
