# AGENTS.md - 超级自动化学习工具（项目指南）

> 2026-08-05 重写。本文件是 Cursor/任何 AI 助手在本项目工作时的**唯一权威指南**。
> 旧文档（docs/README.md、使用说明.txt）已删除，结构以本文件 + 真实代码为准。

## 项目定位

AI 笔记 + 任务抽卡学习系统：抽卡抽取学习任务、计时器、日程/睡眠追踪、知识库浏览、状态评估。

## 真实目录结构（2026-08-05 核对）

```
超级自动化学习工具/
├── server/
│   ├── backend_api.py      # Flask 后端 API（全部路由 + SQLite）
│   └── serve_static.py     # 静态文件服务入口
├── static/
│   ├── app.js              # 前端主逻辑（~2700 行，唯一前端逻辑文件）
│   └── test.js             # 历史探测脚本（失效，可清理）
├── src/
│   └── notes/              # 知识库（Obsidian vault）——【红线：绝不提交 git】
├── tests/
│   ├── e2e-manual.js       # E2E 测试（playwright-core，26 用例）
│   └── e2e.spec.js
├── scripts/                # 启停/备份/验收/资料处理脚本
├── config/
│   └── config.json         # 配置（端口/API Key/路径）
├── data/
│   └── task_publisher.db   # SQLite 数据库
├── docs/                   # 权威文档（README 在根目录，docs 只放参考）
└── _archive/               # 归档区（分类存放过期/一次性文件）
```

## 启动/停止/备份（用 scripts/ 实际脚本）

- 启动：`scripts/启动学习工具.bat`（或 `start_web_safe.bat`，自动建 venv + 装依赖 + 健康检查）
- 停止：`scripts/stop_web_safe.bat` / `stop_server.py`
- 备份：`scripts/backup_user_data.bat`
- 开发直启：`python server/backend_api.py`（注意本机 python 是 stub，用完整路径）

## 测试

- E2E：`node tests/e2e-manual.js`（需先启动服务，playwright-core 用固定 chromium 路径）
- 当前基线：26/26 全绿（2026-08-05 R3 收尾）
- ⚠️ E2E 盲区：单浏览器测不出 SQLite 并发、大数据量、跨浏览器

## 红线（唯一一条，其余全部撤销于 2026-08-05）

> **知识库文件（src/notes/）绝不提交 git。**

## 文档导航

- 根目录 README.md = 项目入口
- docs/STRUCTURE_MAP_2026-08-04_auto.md = 结构参考
- docs/FRONTEND_BUG_LIST_2026-08-04.md = P3 待办清单
- 执行中踩坑 → 记录到 docs/WORK_LOG.md（用户级规则强制）

## 工作纪律（继承用户级规则）

- 证据纪律：结论必须附证据，禁止"修好了"式自报
- 已知坑检查：编码/路径/Python stub 先查规则再动手
- 过程记录：错误必须写 WORK_LOG.md
- 不确定 → 标注"需验证"或询问，不编造
