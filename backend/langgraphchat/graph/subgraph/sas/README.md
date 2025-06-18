# SAS (Step-by-Step Automation System) Subgraph

SAS 子图负责将用户的自然语言描述转换为可执行的机器人工作流程 XML。

## 目录结构

```
sas/
├── README.md              # 本文档
├── state.py              # 状态定义 (RobotFlowAgentState)
├── graph_builder.py      # 图构建器和路由逻辑
├── nodes/                # 各个处理节点
│   ├── __init__.py
│   ├── user_input_to_task_list.py      # 步骤1: 用户输入转任务列表
│   ├── process_description_to_module_steps.py  # 步骤2: 任务转模块步骤
│   ├── parameter_mapping.py             # 步骤3: 参数映射
│   ├── review_and_refine.py            # 审查和优化节点
│   ├── generate_individual_xmls.py      # 生成单个XML文件
│   ├── generate_individual_xmls_llm.py  # LLM版本的XML生成
│   ├── generate_relation_xml.py         # 生成关系XML
│   ├── understand_input.py              # 理解用户输入
│   ├── merge_xml.py                     # 合并XML文件
│   └── concatenate_xml.py              # 连接XML文件
├── prompts/              # 提示词模板
│   └── (各种提示词文件)
├── utils/                # 工具函数
│   ├── __init__.py
│   ├── xml_utils.py      # XML处理工具
│   ├── file_utils.py     # 文件操作工具
│   └── validation.py     # 验证工具
└── config/               # 配置
    ├── __init__.py
    └── defaults.py       # 默认配置

```

## 主要流程

### 1. 初始化阶段

- `initialize_state_node`: 初始化状态，设置输出目录等

### 2. 任务分解阶段 (Step 1)

- `user_input_to_task_list_node`: 将用户输入转换为任务列表
- 生成 `sas_step1_generated_tasks`

### 3. 模块步骤生成阶段 (Step 2)

- `process_description_to_module_steps_node`: 将任务转换为具体的模块步骤
- 生成 `sas_step2_module_steps`

### 4. 参数映射阶段 (Step 3)

- `parameter_mapping_node`: 将逻辑参数映射到实际参数
- 生成 `sas_step3_parameter_mapping` 和 `sas_step3_mapping_report`

### 5. XML 生成阶段

- `generate_individual_xmls_node`: 为每个步骤生成单独的 XML
- `generate_relation_xml_node`: 生成关系 XML
- `generate_final_flow_xml_node`: 合并生成最终的流程 XML

### 6. 审查和优化

- `review_and_refine_node`: 允许用户审查和修改生成的内容

## 状态管理

所有状态都存储在 `RobotFlowAgentState` 中，主要字段包括：

- **输入相关**: `user_input`, `current_user_request`, `active_plan_basis`
- **对话状态**: `dialog_state` (控制流程进度)
- **SAS 输出**:
  - `sas_step1_generated_tasks`: 任务列表
  - `sas_step2_module_steps`: 模块步骤
  - `sas_step3_parameter_mapping`: 参数映射
- **XML 相关**: `generated_node_xmls`, `final_flow_xml_content`
- **错误处理**: `is_error`, `error_message`

## 路由逻辑

路由函数根据当前状态决定下一步：

- `route_after_initialize_state`: 初始化后的路由
- `route_after_sas_step1`: 任务列表生成后的路由
- `route_after_sas_step2`: 模块步骤生成后的路由
- `route_after_sas_step3`: 参数映射后的路由
- `route_after_sas_review_and_refine`: 审查后的路由

## 使用示例

```python
from backend.langgraphchat.graph.subgraph.sas.graph_builder import create_robot_flow_graph
from langchain_google_genai import ChatGoogleGenerativeAI

# 创建 LLM
llm = ChatGoogleGenerativeAI(model="gemini-pro")

# 创建图
graph = create_robot_flow_graph(llm)

# 运行图
initial_state = {
    "user_input": "创建一个抓取红色方块的任务",
    "config": {
        "OUTPUT_DIR_PATH": "/workspace/output",
        "NODE_TEMPLATE_DIR_PATH": "/workspace/database/node_database/quick-fcpr-new-default"
    }
}

result = await graph(initial_state)
```

## 注意事项

1. **模板路径**: 确保 `NODE_TEMPLATE_DIR_PATH` 指向正确的模板目录
2. **输出目录**: `OUTPUT_DIR_PATH` 会自动创建如果不存在
3. **错误处理**: 检查 `is_error` 和 `error_message` 字段
4. **语言设置**: 通过 `language` 字段控制输出语言（默认 "zh"）
