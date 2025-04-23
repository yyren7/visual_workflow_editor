# 数据库管理

本目录负责管理项目的数据存储，包括关系型数据库（模型定义、连接、迁移）和可能的向量/文档存储。

## 项目结构

```
database/
├── alembic/                # Alembic 数据库模式迁移目录
│   ├── versions/           # Alembic 生成的迁移脚本
│   ├── env.py              # Alembic 配置文件 (环境设置)
│   └── script.py.mako      # Alembic 迁移脚本模板
├── node_database/          # 存储节点定义的目录 (XML 格式)
│   ├── mg400/              # 可能与特定设备/机器人 (MG400) 相关的节点
│   ├── quick-fcpr/         # (新增) 与 quick-fcpr 相关的节点
│   ├── condition.xml
│   ├── loop.xml
│   ├── moveL.xml
│   ├── return.xml
│   ├── select_robot.xml
│   └── set_motor.xml
├── document_database/      # 存储文档定义 (XML 格式)
│   ├── mg400/              # 可能与特定设备/机器人 (MG400) 相关的文档
│   ├── quickfcpr/          # (新增) 与 quickfcpr 相关的文档目录
│   ├── flow.xml            # 流程定义文档
│   └── quickfcpr.md        # (新增) quickfcpr 相关 Markdown 文档
├── embedding/              # 文本嵌入相关服务
│   ├── api.py              # 提供嵌入服务的 API 接口 (可能被后端调用)
│   ├── config.py           # 嵌入服务配置
│   ├── __init__.py
│   ├── lmstudio_client.py  # 与 LM Studio (本地 LLM 服务) 交互的客户端
│   ├── __pycache__/
│   ├── service.py          # 嵌入服务核心逻辑
│   └── utils.py            # 嵌入服务工具函数
├── flow_database/          # (新增) 存放从旧 SQLite 导出的 Flow 数据 (JSON)
├── migrations/             # (可选) 自定义数据迁移或一次性脚本目录
│   ├── fix_flow_variables.py # 示例: 修复 flow_variables 表数据的脚本
│   ├── __init__.py
│   ├── migrate_chat_preference.py # 示例: 迁移聊天偏好设置的脚本
│   ├── migrate_user_preference.py # 示例: 迁移用户偏好设置的脚本
│   └── __pycache__/
├── __pycache__/            # Python 缓存
├── vectorstore/            # 向量数据库存储目录 (目前为空，可能计划使用)
├── visuall/                # 数据库可视化和分析工具及输出 (需要适配 PostgreSQL)
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
├── alembic.ini             # Alembic 主配置文件 (通常在 database/ 目录下)
├── config.py               # 数据库相关配置 (包含 PostgreSQL 连接参数)
├── connection.py           # 数据库连接管理 (建立 PostgreSQL 会话 Session)
├── export_flow_data_sqlite.py # (新增) 从旧 SQLite 数据库导出 Flow 数据的脚本
├── __init__.py             # database 包初始化
├── init_db.py              # (已弃用) 旧的数据库初始化脚本
├── models.py               # SQLAlchemy 数据模型定义 (对应数据库表结构)
└── version.json            # 数据库版本或相关元数据
```

## 核心组件

- **`models.py`**: 定义了使用 SQLAlchemy ORM 映射的 Python 类，这些类对应数据库中的表结构。是数据库模式的核心定义文件。
- **`connection.py`**: 负责建立和管理 PostgreSQL 数据库连接。创建一个数据库引擎 (Engine) 和会话工厂 (Session factory)，供应用的其他部分使用。
- **`config.py`**: 存储数据库连接字符串（指向 PostgreSQL）、路径或其他配置参数。**请确保这里的配置指向正确的 PostgreSQL 实例。**
- **`alembic/` 和 `alembic.ini`**: 使用 [Alembic](https://alembic.sqlalchemy.org/en/latest/) 工具管理数据库模式迁移。`alembic/` 目录包含迁移脚本和环境配置，`alembic.ini` 是主配置文件。
- **`migrations/`**: (可选) 此目录可能包含**自定义的数据迁移脚本**或只需要运行一次的脚本，用于处理 Alembic 自动迁移无法覆盖的数据转换或修复。模式迁移应使用 Alembic。
- **`init_db.py`**: **(已弃用)** 此脚本用于创建旧的 SQLite 数据库和表。在使用 Alembic 和 PostgreSQL 后已不再需要。
- **`embedding/`**: 包含与文本嵌入相关的服务代码。`lmstudio_client.py` 表明可能与本地运行的 LLM (如 LM Studio) 交互以生成嵌入向量。
- **`node_database/` & `document_database/`**: 这两个目录似乎存储了与流程编辑器节点和文档相关的配置或定义，格式为 XML。
- **`vectorstore/`**: 计划用于存储向量数据的目录，目前为空，但可能与 `embedding/` 服务配合使用，用于相似性搜索等功能。
- **`flow_database/` & `export_flow_data_sqlite.py`**: 用于从迁移前的 SQLite 数据库 (`flow_editor.db`) 提取 Flow 相关数据并保存为 JSON 文件（存放于 `flow_database/`）。在完全迁移或不再需要旧数据后，这些可能可以移除。

## 数据库初始化与迁移 (使用 Alembic)

项目现在使用 Alembic 来管理数据库模式的演变。

- **首次初始化/应用所有迁移**: 要将数据库更新到最新的模式版本（包括首次创建所有表），请运行：

  ```bash
  cd /workspace/database  # 确保在包含 alembic.ini 的目录下
  alembic upgrade head
  ```

  _注意：这需要你的 `alembic.ini` 和 `alembic/env.py` 文件已正确配置 PostgreSQL 数据库连接信息。_

- **生成新的迁移脚本**: 当你修改了 `models.py` 中的 SQLAlchemy 模型后，需要生成一个新的迁移脚本来反映这些更改：

  ```bash
  cd /workspace/database
  alembic revision --autogenerate -m "描述你所做的模型更改"
  ```

  这会基于模型和当前数据库状态的差异，在 `alembic/versions/` 目录下创建一个新的脚本文件。**请务必检查生成的脚本**，确保它准确反映了你的意图，特别是对于复杂更改。

- **应用特定迁移或回滚**: Alembic 也支持升级到特定版本或降级。详情请查阅 [Alembic 文档](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。

- **自定义数据迁移**: 如果需要执行 `migrations/` 目录下的自定义数据迁移脚本，请按照脚本本身的说明或项目约定来运行。例如：
  ```bash
  python /workspace/database/migrations/migrate_some_data.py
  ```

## 可视化工具

`visuall/` 目录包含用于分析和可视化数据库结构的工具 (`db_visualize.py`, `db_visualizer.py`)。

**重要**: 这些脚本最初可能是为 SQLite 设计的。你需要**检查并更新**这些脚本中的数据库连接逻辑，使其能够连接到 PostgreSQL 数据库，然后才能重新生成准确的可视化报告和图表。

更新后，可以运行以下命令重新生成可视化内容：

```bash
python database/visuall/db_visualize.py
```

_(请确认此脚本的运行方式和依赖，并确保它已适配 PostgreSQL)_。

## 技术栈提示

- **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/)
- **数据库:** [PostgreSQL](https://www.postgresql.org/)
- **迁移:** [Alembic](https://alembic.sqlalchemy.org/en/latest/) (用于模式迁移), 自定义脚本 (`migrations/` 目录，用于数据迁移)
- **嵌入:** 可能使用了本地 LLM 服务 (如 LM Studio) 或其他嵌入模型库 (需查看 `embedding/service.py` 确认)。
