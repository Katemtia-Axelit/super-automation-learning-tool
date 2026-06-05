# 🎓 学习工具 - Learning Tool (整合版 v2.0)

系统整合了 **任务发布系统** 和 **笔记处理系统**，提供统一的任务管理和知识库管理功能。

## 📁 项目结构

```
超级自动化学习工具/
├── index.html                    # 前端主页面
├── 启动学习工具.bat              # 一键启动脚本
│
├── server/                       # 后端服务
│   └── backend_api.py            # Flask后端API (整合两个系统的数据)
│
├── config/                       # 配置管理
│   └── config.json               # 统一配置文件
│
├── tools/                        # 工具脚本
│   └── migrate_data.py           # 数据迁移工具
│
├── docs/                         # 文档说明
│   ├── README.md                 # 主文档
│   └── 使用说明.txt              # 快速使用指南
│
├── 任务发布系统/                 # ⚠️ 原系统（保持完整不动）
│   ├── main.py                   # 原PySide6桌面端入口
│   ├── src/models/task.py        # 任务数据模型
│   ├── src/ui/                   # 原UI组件
│   ├── data/task_publisher.db    # 统一任务数据库
│   ├── StateOS/                  # 状态管理系统
│   ├── AI_自然语言模板.md        # AI指令模板
│   └── requirements.txt          # Python依赖
│
├── 笔记处理系统/                 # ⚠️ 原系统（保持完整不动）
│   ├── 笔记/                     # 笔记和知识点目录
│   │   ├── 知识点/               # 知识点文件 (~500+个.md)
│   │   │   ├── 大学物理/         # 大学物理知识点
│   │   │   ├── 高等数学/         # 高等数学知识点
│   │   │   ├── 线性代数/         # 线性代数知识点
│   │   │   ├── 电子技术/         # 电子技术知识点
│   │   │   ├── 计算机/           # 计算机知识点
│   │   │   └── 英语四级/         # 英语四级知识点
│   │   ├── 大学物理/             # 物理笔记
│   │   ├── 电子技术/             # 电子技术笔记
│   │   └── 参照系.md             # 通用笔记
│   ├── 工具/                     # 笔记处理工具 (13个脚本)
│   ├── 提示词/                   # AI Agent提示词 (4个)
│   ├── 报告/                     # 知识库质量报告
│   ├── 已分类/                   # 原始转写材料 (35+篇)
│   └── 未分类/                   # 待处理文件
│
└── super-automation-learning-tool/  # 重构项目（保留不动）
```

## 🚀 快速开始

### 1. 启动统一服务
双击运行 `启动学习工具.bat`，自动：
- ✅ 检查Python环境
- ✅ 安装依赖（flask/flask-cors）
- ✅ 加载配置
- ✅ 启动后端API服务
- ✅ 打开前端页面

### 2. 手动启动（可选）
```bash
# 安装依赖
pip install flask flask-cors

# 启动服务
python server/backend_api.py
```

### 3. 启动原任务系统（独立运行）
```bash
cd 任务发布系统
pip install PySide6
python main.py
```

## ⚙️ 配置说明

配置文件位于 `config/config.json`：

```json
{
    "server": {
        "port": 5000,          # 服务端口
        "host": "0.0.0.0",     # 监听地址
        "debug": true           # 调试模式
    },
    "obsidian": {
        "vault_path": "",      # Obsidian库路径
        "notes_directory": "笔记处理系统/笔记"
    },
    "api": {
        "openai_api_key": "",  # OpenAI API Key
        "claude_api_key": ""   # Claude API Key
    },
    "database": {
        "task_db_path": "任务发布系统/data/task_publisher.db"
    }
}
```

## 🌐 访问地址

| 资源 | 地址 |
|------|------|
| **前端页面** | `http://localhost:5000` |
| **API** | `http://localhost:5000/api` |
| **健康检查** | `http://localhost:5000/api/health` |

## 🛠️ 技术栈

| 层次 | 技术 | 用途 |
|------|------|------|
| **前端** | HTML5 + CSS3 + JavaScript | 用户界面 |
| **后端** | Python 3.8+, Flask | API服务 |
| **数据库** | SQLite | 数据持久化 |
| **桌面端(原)** | PySide6, PyQt6 | 原始桌面应用 |

## 📊 数据统计

| 数据类型 | 数量 |
|----------|------|
| 任务数据库 | 1个 (task_publisher.db) |
| 笔记文件 | ~200+篇 Markdown |
| 知识点文件 | ~500+个 |
| 工具脚本 | 13个 (笔记处理系统/工具/) |
| AI提示词 | 4个 |
| 原始转写材料 | 35+篇 |

## 🔧 常见问题

### Q: Obsidian打开笔记失败？
A: 确保已将 `笔记处理系统/笔记` 目录添加到Obsidian库中。

### Q: 端口被占用？
A: 修改 `config/config.json` 中的端口号，重启服务。

### Q: 数据不显示？
A: 检查 `config/config.json` 中的路径是否正确，确保后端服务正常运行。

### Q: 原任务系统的桌面端还能用吗？
A: 可以。进入 `任务发布系统/` 目录，双击 `启动任务发布器.bat` 即可启动原PySide6桌面版。

## 📜 合并说明

本次整合遵循以下原则：
1. **不修改原系统文件**：`任务发布系统/` 和 `笔记处理系统/` 内部结构完全保持
2. **统一配置入口**：所有配置集中在 `config/config.json`
3. **统一启动方式**：`启动学习工具.bat` 一键启动
4. **功能互补**：新Web界面访问任务和知识库，原桌面端可独立运行
5. **路径兼容**：所有文件引用路径保持向后兼容