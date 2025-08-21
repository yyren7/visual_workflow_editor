# SAS LangGraph 多智能体系统技术复用指南

## 1. 引言 (Introduction)

`sas` 系统是一个基于 LangGraph 构建的多智能体（Multi-Agent System）框架，其核心设计思想是将复杂的自然语言任务，通过一系列分工明确的智能体协作，逐步分解、细化并最终生成确定性的、可供机器执行的代码。在当前实现中，它专注于将机器人控制任务的自然语言描述转换为结构化的 Blockly XML 流程文件。

本文档旨在为开发者提供一份清晰、详尽的指南，说明如何将这一强大的任务分解与代码生成框架，从现有的“机器人代码生成”领域，成功适配并复用到一个全新的领域——“工业图像处理”。通过遵循本指南，开发者将能够理解系统的核心可复用组件，识别领域特定的部分，并按部就班地完成适配工作。

## 2. 核心可复用架构 (Core Reusable Architecture)

`sas` 系统的强大之处在于其大部分核心组件是领域无关的。这些组件共同构成了一个通用的“自然语言到代码”的转换引擎，可以被无缝复用到其他技术领域。

以下是系统中与具体业务领域**无关**的核心组件：

- **主工作流图 (Main Workflow Graph):**
  在 `backend/sas/graph_builder.py` 中定义的 LangGraph 状态机是完全通用的。它编排了从输入到输出的整个流程：`输入解析 -> 任务分解 -> 人机审核 -> 代码生成 -> 最终整合`。这条主管线不关心具体的业务逻辑，只负责驱动数据在不同处理节点间的流转和状态转移，因此可以直接复用。

- **状态管理 (State Management):**
  定义于 `backend/sas/state.py` 的 `RobotFlowAgentState`（可重命名为更通用的 `AgentState`）是系统的“数据总线”。它以一个 Pydantic 模型贯穿所有节点，携带了从用户输入、中间产物（如任务列表）到最终结果的全部状态信息。这种中心化的状态管理机制是领域无关的，为任何类型的任务流提供了坚实的数据基础。

- **人机协同节点 (Human-in-the-Loop Node):**
  `sas_review_and_refine` 节点（定义于 `backend/sas/nodes/review_and_refine.py`）的设计思想是作为一个通用的审核与校对关口。它允许用户在流程的关键节点（如任务列表生成后）介入，对 AI 生成的内容进行审核、修改或批准。这种“人机协同”的模式对于确保生成结果的准确性至关重要，适用于任何需要高质量输出的领域。

- **Schema 驱动的输入解析 (Schema-Driven Input Parsing):**
  `user_input_to_task_list` 节点（定义于 `backend/sas/nodes/user_input_to_task_list.py`）的核心方法论是可复用的。它利用大语言模型（LLM）将非结构化的自然语言输入，转换为严格遵循 Pydantic Schema（如 `TaskDefinition`）的结构化数据（JSON）。这种“LLM + Pydantic”的模式，是连接自然语言与结构化世界的强大桥梁，可以被用来解析任何领域的任务描述。

## 3. 领域特定组件 (Domain-Specific Components)

为了将系统适配到新领域，我们需要识别并替换或修改当前与“机器人代码生成”领域强绑定的组件。这些组件构成了系统的“领域知识”。

- **知识库 (Knowledge Base):**
  位于 `database/node_database/` 目录下的 XML 文件是机器人领域的“原子能力”定义。例如，`moveL.xml` 定义了线性移动这一具体操作。在适配新领域时，整个知识库需要被替换为新领域的原子能力集合。

- **提示词工程 (Prompt Engineering):**
  位于 `database/prompt_database/` 目录下的提示词模板，特别是 `step1_user_input_to_process_description_prompt.md`，包含了大量机器人领域的示例（如“移动机械臂”、“抓取物体”）和术语。这些内容需要被完全替换，以引导 LLM 理解新领域的概念和任务。

- **最终代码生成器 (Final Code Generator):**
  `generate_individual_xmls` 节点（位于 `backend/sas/nodes/generate_individual_xmls.py`）是当前系统的代码生成器。它的逻辑与生成 Blockly XML 格式强相关。在适配新领域时，此节点的核心逻辑（从模板生成结构化文本）可以复用，但需要修改其输出，使其生成 JSON 对象片段而非 XML。后续的 `merge` 和 `concatenate` 节点也需要调整为处理 JSON 数据。

## 4. 适配新领域（工业图像处理）的详细步骤

以下是将 `sas` 框架从“机器人代码生成”适配到“工业图像处理”，并生成 **JSON 工具调用流程**的详细分步指南。

### 步骤 1：定义新的“原子能力”知识库

这是最基础也是最关键的一步。我们需要为工业图像处理领域定义一套全新的“原子能力”。这些能力将以 JSON 文件的形式存在，描述每个工具函数的名称、功能和参数。

1.  **创建新的知识库目录**:
    建议在 `database/` 下创建一个新目录，例如 `image_processing_knowledge_base/`。

2.  **定义原子能力文件**:
    在该目录中，为每一个图像处理的基础操作（如导入图片、触发相机、应用滤镜）创建一个描述其接口的 JSON 文件。例如：
    - `trigger_camera.json`:
      ```json
      {
        "name": "trigger_camera",
        "description": "触发指定相机进行拍照。",
        "parameters": [
          {
            "name": "camera_id",
            "type": "int",
            "description": "要触发的相机ID。"
          }
        ]
      }
      ```
    - `apply_gaussian_blur.json`:
      ```json
      {
        "name": "apply_gaussian_blur",
        "description": "对图像应用高斯模糊以减少噪声。",
        "parameters": [
          {
            "name": "kernel_size",
            "type": "int",
            "description": "模糊核的大小，必须是正奇数。"
          }
        ]
      }
      ```

### 步骤 2：更新提示词（Prompts）

更新提示词是为了让 LLM “忘记”机器人，转而成为一个图像处理流程编排专家。

1.  **修改 `step1_user_input_to_task_list_prompt`**:

    - 将所有与机器人相关的示例（如“拾取”、“放置”）替换为图像处理的示例（如“拍照”、“应用滤镜”、“保存图片”）。
    - 在提示词的知识部分，明确告知 LLM 新的可用工具集，即步骤 1 中定义的图像处理原子能力列表。

2.  **修改 `step2_process_description_to_module_steps_prompt`**:
    - 同样地，更新此提示词中的 few-shot 示例，使其反映从一个宏观图像处理任务（如“检测产品缺陷”）到一系列原子能力调用的分解过程。

### 步骤 3：泛化 Agent 状态（AgentState）

为了使状态管理更具通用性，建议进行重构。

1.  **重命名 `RobotFlowAgentState`**:
    在 `backend/sas/state.py` 中，将 `RobotFlowAgentState` 重命名为更通用的 `AgentState`。

2.  **调整或替换特定字段**:
    - `generated_node_xmls`: 可重命名为 `generated_tool_calls`，其类型 `GeneratedXmlFile` 也应相应修改为 `GeneratedToolCall`，用于存放单个 JSON 工具调用对象。
    - `final_flow_xml_path`: 可重命名为 `final_flow_json_path`。

### 步骤 4：修改代码生成与整合节点

这是适配工作的核心编码任务，目标是生成 JSON 而非 XML。

1.  **修改 `generate_individual_xmls_node`**:

    - 建议将其重命名为 `generate_individual_tool_calls_node`。
    - 修改其核心逻辑：不再加载 `.xml` 模板，而是读取步骤 1 中定义的 `.json` 原子能力描述。
    - 它的输出不再是 XML 字符串，而是一个个独立的 JSON 对象，每个对象代表一个工具调用，包含 `name` 和 `parameters` 字段。这些 JSON 对象将被存入 `AgentState.generated_tool_calls`。

2.  **修改 `sas_merge_xmls` 和 `sas_concatenate_xmls` 节点**:
    - 这两个节点的功能需要被重新实现，以处理 JSON 数据。
    - 新的逻辑将是：将 `AgentState.generated_tool_calls` 列表中的所有独立 JSON 对象，整合到一个单一的 JSON 数组中。
    - 最终，将这个完整的 JSON 数组写入到输出目录下的一个 `.json` 文件中。这比处理复杂的 XML 嵌套要简单得多。

### 步骤 5：调整验证 Schema

为了匹配新领域的任务结构，需要更新输入解析阶段的 Pydantic 模型。

1.  **修改 `TaskDefinition`**:
    在 `backend/sas/state.py` 中，根据图像处理任务的特点调整 `TaskDefinition` 模型。`details` 字段应能更好地描述一个包含参数的工具调用步骤。

2.  **更新 `user_input_to_task_list` 节点的提示**:
    确保 `user_input_to_task_list` 节点使用的提示词中，提供的 JSON 输出示例与更新后的 `TaskDefinition` Schema 完全匹配。

## 5. 接口定义 (Interface Definition)

经过上述步骤成功适配后，系统的核心接口保持不变，但其输出产物发生了变化。

- **输入 (Input):**

  - **格式:** 依然是自然语言描述。
  - **内容:** 用户提供关于图像处理任务的描述，例如：“请触发 1 号相机拍照，然后对图片进行高斯模糊处理，最后将结果保存到 `/output/result.png`。”

- **输出 (Output):**
  - **格式:** `.json` 文件。
  - **内容:** 系统将生成一个结构化的 JSON 文件，该文件包含一个工具调用对象的数组，详细描述了需要依次执行的图像处理函数及其参数。例如：
    ```json
    [
      {
        "name": "trigger_camera",
        "parameters": {
          "camera_id": 1
        }
      },
      {
        "name": "apply_gaussian_blur",
        "parameters": {
          "kernel_size": 5
        }
      },
      {
        "name": "save_image",
        "parameters": {
          "path": "/output/result.png"
        }
      }
    ]
    ```
