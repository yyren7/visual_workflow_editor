# LangChain 聊天模块

本模块基于 LangChain 框架实现了聊天功能，支持 DeepSeek API 进行对话，并能够集成流程图相关工具。

## 功能特点

1. **上下文感知对话**：自动收集当前流程图信息、用户信息和全局变量作为上下文
2. **会话管理**：支持创建、保存和恢复会话历史
3. **工具集成**：提供流程图创建、修改和查询工具
4. **可配置**：通过配置文件可自定义聊天行为

## 目录结构

```
backend.langchainchat/
├── __init__.py             # 模块初始化
├── config.py              # 配置设置
├── api/                   # API接口
│   ├── __init__.py
│   └── chat_router.py     # 聊天路由
├── utils/                 # 工具函数
│   ├── __init__.py
│   ├── logging.py         # 日志设置
│   └── context_collector.py # 上下文收集器
├── models/                # 模型定义
│   ├── __init__.py
│   └── llm.py             # LLM模型包装
├── memory/                # 记忆组件
│   ├── __init__.py
│   └── conversation_memory.py # 会话记忆
├── prompts/               # 提示模板
│   ├── __init__.py
│   └── chat_prompts.py    # 聊天提示模板
├── services/              # 服务组件
│   ├── __init__.py
│   └── chat_service.py    # 聊天服务
└── tools/                 # 工具定义
    ├── __init__.py
    └── flow_tools.py      # 流程图工具
```

## 使用方法

### 直接通过 API 使用

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.langchainchat import chat_service

async def process_message(message: str, db: Session = Depends(get_db)):
    """处理聊天消息"""
    result = await chat_service.process_message(
        user_input=message,
        db=db,
        use_context=True  # 使用上下文
    )
    return result
```

### 工具使用示例

```python
from backend.langchainchat.tools.flow_tools import get_flow_tools

# 获取所有流程图工具
tools = get_flow_tools()

# 创建节点
create_node_tool = tools[0]
result = create_node_tool._run(
    node_type="process",
    node_label="处理数据",
    properties={"description": "这是一个处理数据的节点"}
)
```

## 配置项

主要配置项在`config.py`中定义，可通过环境变量覆盖：

- `DEEPSEEK_API_KEY`: DeepSeek API 密钥
- `DEEPSEEK_BASE_URL`: DeepSeek API 基础 URL
- `CHAT_MODEL_NAME`: 聊天模型名称
- `TEMPERATURE`: 温度参数，控制随机性
- `MAX_TOKENS`: 最大生成令牌数
- `SESSIONS_DB_PATH`: 会话保存路径

## 开发

克隆仓库后，确保安装了必要的依赖：

```bash
pip install -r requirements.txt
```

然后可以通过 API 或在 Python 代码中直接使用聊天服务。
