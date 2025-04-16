# 数据库管理

本目录负责管理项目的数据存储，包括关系型数据库（模型定义、连接、迁移）和可能的向量/文档存储。

## 项目结构

```
database/
├── flow_editor.db          # SQLite 数据库文件 (主要的关系型数据存储)
├── node_database/          # 存储节点定义的目录 (似乎是 XML 格式)
│   ├── mg400/              # 可能与特定设备/机器人 (MG400) 相关的节点
│   ├── condition.xml
│   ├── loop.xml
│   ├── moveL.xml
│   ├── return.xml
│   ├── select_robot.xml
│   └── set_motor.xml
├── document_database/      # 存储文档定义 (XML 格式)
│   ├── mg400/              # 可能与特定设备/机器人 (MG400) 相关的文档
│   └── flow.xml            # 流程定义文档
├── embedding/              # 文本嵌入相关服务
│   ├── api.py              # 提供嵌入服务的 API 接口 (可能被后端调用)
│   ├── config.py           # 嵌入服务配置
│   ├── __init__.py
│   ├── lmstudio_client.py  # 与 LM Studio (本地 LLM 服务) 交互的客户端
│   ├── __pycache__/
│   ├── service.py          # 嵌入服务核心逻辑
│   └── utils.py            # 嵌入服务工具函数
├── migrations/             # 数据库模式迁移脚本
│   ├── fix_flow_variables.py # 修复 flow_variables 表结构的迁移脚本
│   ├── __init__.py
│   ├── migrate_chat_preference.py # 迁移聊天偏好设置的脚本
│   ├── migrate_user_preference.py # 迁移用户偏好设置的脚本
│   └── __pycache__/
├── __pycache__/            # Python 缓存
├── vectorstore/            # 向量数据库存储目录 (目前为空，可能计划使用)
├── visuall/                # 数据库可视化和分析工具及输出
│   ├── db_relationships.png # 数据库表关系图
│   ├── db_report.html      # 数据库分析报告 (HTML)
│   ├── db_summary.json     # 数据库结构摘要 (JSON)
│   ├── db_visualize.py     # 生成数据库可视化图表的脚本
│   ├── db_visualizer.py    # 数据库可视化核心逻辑
│   ├── flows.json          # flows 表数据导出 (JSON)
│   ├── flows_column_types.png # flows 表列类型图
│   ├── flows_creation_timeline.png # flows 表记录创建时间线图
│   ├── flow_variables.json # flow_variables 表数据导出 (JSON)
│   ├── json_embeddings.json # (可能用于存储嵌入向量的 JSON 文件)
│   ├── user_flow_preferences.json # user_flow_preferences 表数据导出 (JSON)
│   ├── user_flow_preferences_column_types.png # user_flow_preferences 表列类型图
│   ├── users.json          # users 表数据导出 (JSON)
│   ├── users_column_types.png # users 表列类型图
│   ├── users_creation_timeline.png # users 表记录创建时间线图
│   ├── version_info.json   # version_info 表数据导出 (JSON)
│   ├── version_info_column_types.png # version_info 表列类型图
│   └── version_info_creation_timeline.png # version_info 表记录创建时间线图
├── config.py               # 数据库相关配置 (可能包含连接参数等)
├── connection.py           # 数据库连接管理 (建立会话 Session)
├── __init__.py             # database 包初始化
├── init_db.py              # 数据库初始化脚本 (创建表)
├── models.py               # SQLAlchemy 数据模型定义 (对应数据库表结构)
└── version.json            # 数据库版本或相关元数据
```

## 核心组件

- **`models.py`**: 定义了使用 SQLAlchemy ORM 映射的 Python 类，这些类对应数据库中的表结构。是数据库模式的核心定义文件。
- **`connection.py`**: 负责建立和管理数据库连接。通常会创建一个数据库引擎 (Engine) 和会话工厂 (Session factory)，供应用的其他部分使用以与数据库交互。
- **`config.py`**: 存储数据库连接字符串、路径或其他配置参数。
- **`flow_editor.db`**: 项目主要的 SQLite 数据库文件。存储了应用运行所需的大部分关系型数据（如用户信息、工作流、变量等）。
- **`migrations/`**: 包含用于修改数据库模式的脚本。当 `models.py` 中的模型发生变化时（例如添加新表、新列），会创建新的迁移脚本来更新现有数据库结构，而不是重新创建整个数据库。这对于维护生产环境数据至关重要。
- **`init_db.py`**: 用于从头开始创建数据库和所有在 `models.py` 中定义的表。通常在首次部署或需要完全重置数据库时运行。
- **`embedding/`**: 包含与文本嵌入相关的服务代码。`lmstudio_client.py` 表明可能与本地运行的 LLM (如 LM Studio) 交互以生成嵌入向量。
- **`node_database/` & `document_database/`**: 这两个目录似乎存储了与流程编辑器节点和文档相关的配置或定义，格式为 XML。
- **`vectorstore/`**: 计划用于存储向量数据的目录，目前为空，但可能与 `embedding/` 服务配合使用，用于相似性搜索等功能。

## 数据库初始化与迁移

- **初始化数据库**: 如果是首次设置项目或需要清空并重建数据库，可以运行：

  ```bash
  python database/init_db.py
  ```

  _警告：这将删除 `flow_editor.db` 文件（如果存在）并创建一个新的空数据库。_

- **应用迁移**: 当数据模型 (`models.py`) 更新后，通常需要运行迁移脚本来更新现有数据库的结构。具体的运行方式取决于项目是否使用了像 Alembic 这样的迁移工具，或者是否需要手动执行 `migrations/` 目录下的特定脚本。请检查是否有主迁移脚本或相关说明。
  例如，如果需要手动运行某个迁移脚本：
  ```bash
  python database/migrations/migrate_some_change.py
  ```
  _(请将 `migrate_some_change.py` 替换为实际需要运行的脚本名称)_。

## 可视化工具

`visuall/` 目录包含用于分析和可视化数据库结构的工具 (`db_visualize.py`, `db_visualizer.py`) 以及它们生成的各种输出文件（`.png` 图表, `.json` 数据导出, `.html` 报告）。这对于理解数据模型、表关系和数据分布非常有帮助。

可以运行以下命令重新生成可视化报告和图表：

```bash
python database/visuall/db_visualize.py
```

_(请确认此脚本的运行方式和依赖)_。

## 技术栈提示

- **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/) (根据 `models.py` 和 `connection.py` 的结构推断)
- **数据库:** [SQLite](https://www.sqlite.org/index.html) (基于 `flow_editor.db` 文件)
- **迁移:** 自定义脚本 (`migrations/` 目录)，可能未使用 Alembic 等标准库。
- **嵌入:** 可能使用了本地 LLM 服务 (如 LM Studio) 或其他嵌入模型库 (需查看 `embedding/service.py` 确认)。
