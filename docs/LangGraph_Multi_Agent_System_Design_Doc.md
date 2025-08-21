# **LangGraph 多智能体系统设计文档**

## **1. 系统概述**

- **目标**：该智能体系统旨在解决的核心问题是将用户的自然语言输入，通过多智能体协作，自动、高效地转换为结构化的、可供机器人执行的 Blockly XML 流程文件。
- **架构图**：
  ```mermaid
  graph TD
      A[用户输入] --> B(Supervisor: create_robot_flow_graph);
      subgraph Supervisor State Machine
          direction LR
          C(INITIALIZE_STATE) --> D(SAS_USER_INPUT_TO_TASK_LIST);
          D --> E{route_after_task_list};
          E --> F(SAS_REVIEW_AND_REFINE);
          F -- 修改 --> D;
          F -- 接受 --> G(SAS_TASK_LIST_TO_MODULE_STEPS);
          G --> H(GENERATE_INDIVIDUAL_XMLS);
          H --> I(SAS_PARAMETER_MAPPING);
          I --> J(SAS_MERGE_XMLS);
          J --> K(SAS_CONCATENATE_XMLS);
      end
      B --> C;
      K --> L[最终机器人流程XML];
  ```

## **2. 主智能体（Supervisor）状态机详解**

- **目标**：定义和解释主智能体在 LangGraph 中的核心状态节点（State Nodes）和状态转移逻辑（Conditional Edges）。主智能体通过 `RobotFlowAgentState` Pydantic 模型管理整个流程的状态，并利用 `route_after_*` 函数根据 `dialog_state` 和 `is_error` 字段进行条件路由。
- **状态定义表**：

| 状态节点 (State Node)           | 职责描述 (Description)                                                  | 输入 (Input)                                      | 输出 (Output)                                 | 下一个可能的状态 (Possible Next States)                                              |
| :------------------------------ | :---------------------------------------------------------------------- | :------------------------------------------------ | :-------------------------------------------- | :----------------------------------------------------------------------------------- |
| `INITIALIZE_STATE`              | 初始化状态，设置输出目录等环境参数。                                    | 初始用户请求                                      | 已初始化的 `RobotFlowAgentState`              | `SAS_USER_INPUT_TO_TASK_LIST`                                                        |
| `SAS_USER_INPUT_TO_TASK_LIST`   | **(子智能体)** 将用户自然语言输入转换为结构化的任务列表 (JSON)。        | `RobotFlowAgentState.messages` (用户请求)         | `RobotFlowAgentState.task_list`               | `SAS_REVIEW_AND_REFINE`                                                              |
| `SAS_REVIEW_AND_REFINE`         | **(人机交互节点)** 作为审查关口，处理用户对生成物的反馈（接受或修改）。 | `RobotFlowAgentState.task_list` 或 `module_steps` | 更新后的 `dialog_state`，可能包含用户修改意见 | `SAS_USER_INPUT_TO_TASK_LIST` (如果修改), `SAS_TASK_LIST_TO_MODULE_STEPS` (如果接受) |
| `SAS_TASK_LIST_TO_MODULE_STEPS` | **(子智能体)** 将任务列表中的每个任务分解为详细的模块化步骤。           | `RobotFlowAgentState.task_list`                   | `RobotFlowAgentState.module_steps`            | `GENERATE_INDIVIDUAL_XMLS`                                                           |
| `GENERATE_INDIVIDUAL_XMLS`      | **(子智能体)** 将每个模块化步骤转换为一个独立的 Blockly XML 文件。      | `RobotFlowAgentState.module_steps`                | `RobotFlowAgentState.individual_xmls_path`    | `SAS_PARAMETER_MAPPING`                                                              |
| `SAS_PARAMETER_MAPPING`         | **(子智能体)** 将逻辑参数映射到物理参数（例如 "安全点" -> "P1"）。      | 包含逻辑参数的 XML 文件                           | 包含物理参数的 XML 文件                       | `SAS_MERGE_XMLS`                                                                     |
| `SAS_MERGE_XMLS`                | 将属于同一个任务的多个独立 XML 文件合并成一个任务级的 XML 文件。        | `RobotFlowAgentState.individual_xmls_path`        | `RobotFlowAgentState.merged_xml_path`         | `SAS_CONCATENATE_XMLS`                                                               |
| `SAS_CONCATENATE_XMLS`          | 将所有任务级的 XML 文件最终连接成一个完整的机器人流程 XML 文件。        | `RobotFlowAgentState.merged_xml_path`             | 最终的完整 XML 文件路径                       | `END` (流程结束)                                                                     |

## **3. 子智能体（Sub-Agents）设计原则**

- **目标**：为系统中的每一个功能性子智能体建立标准化的设计档案。

- **3.1 `user_input_to_task_list_node`**

  - **角色 (Persona)**：自然语言理解专家，擅长将模糊的用户需求转化为精确、结构化的执行计划。
  - **核心职责 (Core Responsibilities)**：
    - 理解用户输入的自然语言需求。
    - 将需求分解为一系列机器可理解的任务序列。
    - 生成格式严格的 JSON 任务列表。
  - **工具集 (Tools)**：
    - `LLM`: 使用 `get_sas_step1_task_list_generation_prompt` 提示词驱动的大语言模型。
    - `Pydantic Validation`: 使用 `TaskDefinition` 模型验证和解析 LLM 的输出。
  - **Prompt 核心原则 (Prompt Principles)**：
    - **指令 (Instruction)**：提供清晰的分步指令，引导模型如何分析用户输入并提取关键任务。
    - **约束与限制 (Constraints)**：输出必须严格遵守 `TaskDefinition` Pydantic 模型定义的 JSON Schema。
    - **输入/输出格式 (I/O Format)**：输入为用户对话历史，输出为特定结构的 JSON 数组。
    - **知识边界 (Knowledge Boundary)**：仅依赖当前对话上下文进行任务提取，不进行外部知识查询。

- **3.2 `task_list_to_module_steps_node`**

  - **角色 (Persona)**：流程规划师，精通将高级任务分解为具体、详细且可执行的原子操作步骤。
  - **核心职责 (Core Responsibilities)**：
    - 接收结构化的任务列表。
    - 为列表中的每一个任务，生成详细的模块化步骤。
  - **工具集 (Tools)**：
    - `LLM (并行调用)`: 使用 `asyncio.gather` 并行处理多个任务，提高效率。
    - `动态提示词`: 根据任务类型，从文件系统加载不同的提示词模板和知识库。
  - **Prompt 核心原则 (Prompt Principles)**：
    - **指令 (Instruction)**：指令模型将单个宏观任务（如“抓取物体”）分解为一系列具体的机器人原子操作。
    - **约束与限制 (Constraints)**：生成的步骤必须使用知识库中提供的可用原子操作（Block 节点）。
    - **输入/输出格式 (I/O Format)**：输入为单个任务的 JSON 对象，输出为描述步骤的文本列表。
    - **知识边界 (Knowledge Boundary)**：严格依赖根据任务类型动态加载的提示词模板和包含可用原子操作描述的知识库文件。

- **3.3 `generate_individual_xmls_node`**

  - **角色 (Persona)**：代码生成引擎，一个精确、高效的翻译器，将文本指令转换为结构化代码。
  - **核心职责 (Core Responsibilities)**：
    - 将文本描述的模块步骤转换为结构化的 Blockly XML 代码。
  - **工具集 (Tools)**：
    - `模板引擎 (基于XML)`: **不使用 LLM**。读取预定义的 XML 模板文件。
    - `正则表达式`: 从步骤描述中提取块类型 (`block_type`) 和参数。
    - `XML库 (xml.etree.ElementTree)`: 加载模板，填充参数，生成 XML 文件。
  - **Prompt 核心原则 (Prompt Principles)**：
    - 该节点为确定性节点，不使用 Prompt。其行为完全由预定义的规则和模板决定。

- **3.4 `parameter_mapping_node`**
  - **角色 (Persona)**：实体链接工程师，负责连接抽象的逻辑世界与具体的物理世界。
  - **核心职责 (Core Responsibilities)**：
    - 将 XML 文件中的逻辑参数（如 "初始点"）匹配并替换为物理参数（如 "P1"）。
  - **工具集 (Tools)**：
    - `YAML解析`: 读写存储物理参数的 `.yaml` 文件。
    - `语义匹配`: 通过字符串相似度和预设规则进行匹配。
  - **Prompt 核心原则 (Prompt Principles)**：
    - 该节点为确定性节点，不使用 Prompt。其逻辑基于配置文件和匹配算法。

## **4. 动态上下文选取与管理原则**

- **目标**：定义系统如何在不同阶段为智能体提供最相关的上下文信息。

- **原则详述**：
  - **短期记忆（对话历史）管理**：
    - **策略**：采用完整历史记录策略。整个对话历史被完整记录。
    - **实现**：对话历史存储在 `RobotFlowAgentState.messages` 列表中，并作为输入传递给需要理解对话上下文的节点（如 `SAS_USER_INPUT_TO_TASK_LIST`）。
  - **长期记忆（知识库）检索**：
    - **触发条件**：在 `task_list_to_module_steps_node` 节点执行时，根据当前处理任务的 `type` 字段触发。
    - **检索策略**：采用基于规则的直接文件加载。系统不使用向量搜索，而是根据任务类型，从 `/workspace/database/prompt_database/` 和 `/workspace/database/node_database/` 目录中精确查找并加载对应的提示词模板 (`.md`) 和原子操作定义 (`.xml`)。
    - **信息整合**：检索到的提示词模板和原子操作知识被直接格式化并注入到该任务的 LLM Prompt 中，为模型提供执行任务分解所需的全部上下文。
  - **状态间上下文传递 (State-to-State Context)**：
    - **机制**：`RobotFlowAgentState` Pydantic 模型是贯穿整个图执行过程的唯一上下文载体。每个节点通过读取这个中心化状态对象的属性来获取输入，并通过修改该对象来传递其输出。这种机制确保了信息在多智能体节点之间的无缝、可靠流动。

---

# QuickFCPR 项目核心知识库构建方法

## 引言

本文档详细阐述了 `quickfcpr` 项目中核心知识库的构建方法与设计哲学。该知识库是实现从自然语言指令到可执行机器人操作流程（XML 格式）转换的关键。知识库主要由两部分构成：**提示词数据库 (`prompt_database`)** 和 **节点模板数据库 (`node_database`)**。它们共同协作，形成一个高效、精确且可维护的自动化代码生成系统。

---

## 1. 提示词数据库 (`/workspace/database/prompt_database/`)

提示词数据库是整个自然语言理解与代码生成流程的“大脑”，它通过一系列精心设计的提示词模板，引导大型语言模型（LLM）将复杂的任务分解并逐步完成。

### 1.1. 提取与制作过程概述

提示词数据库的创建遵循一个系统化流程，该流程结合了**需求分解、迭代优化和知识参数化**。其核心思想是将复杂的“自然语言到 XML”代码生成任务，分解为一系列由提示词驱动、逻辑独立的子任务链。

### 1.2. 设计哲学

- **任务分解 (Task Decomposition)**: 为了降低复杂性并提升 LLM 执行的准确性，整个代码生成流程被精确地分解为四个主要步骤：

  1.  **理解输入并结构化**: 解析用户输入，输出结构化的 JSON。
  2.  **生成单个节点 XML**: 基于模板生成独立的原子操作 XML 节点。
  3.  **生成节点关系结构**: 定义节点之间的执行顺序和逻辑关系。
  4.  **组合与最终生成**: 将所有部分组合成最终的完整 XML 流程。

- **格式约束与 Schema 驱动 (Schema-Driven Constraint)**: 在任务的中间环节，例如步骤 1 的输出，采用了严格的 Schema 进行约束。这确保了数据在不同处理步骤之间传递的一致性和有效性，构建了一个可靠的处理链条。

- **知识注入与逻辑分离 (Context Injection & Separation of Concerns)**: 系统采用占位符机制（例如 `{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}`）来将核心的指令逻辑与动态变化的外部知识（如节点模板、文件路径等）分离开。一个外部编排器在运行时负责动态地注入这些上下文信息，这使得提示词模板本身具有高度的可维护性和复用性。

### 1.3. 制作流程

1.  **需求分析与任务分解**: 首先，定义高级目标，然后将其拆解为多个逻辑连贯、输入输出明确的子任务阶段。
2.  **接口定义**: 为每个阶段定义清晰的输入和输出格式（例如，JSON 或独立的 XML 片段），这些格式定义构成了连接各个提示词的“契约”。
3.  **初稿撰写与示例构建**: 为每个子任务编写初始的提示词模板，其中包含核心指令和基础的输入输出示例。
4.  **迭代测试与优化**: 使用大量真实和模拟的输入数据对提示词链进行端到端测试。根据 LLM 返回的错误（如格式错误、逻辑不清），针对性地在提示词中增加更强的约束、提供正反示例或添加“重要提醒”，从而持续优化其性能。
5.  **参数化与定稿**: 当模板性能稳定后，将所有动态变化的内容（如知识库的具体路径、机器人型号等）抽象为占位符，并在 `flow_placeholders.md` 文件中进行统一管理，最终完成模板的定稿。

### 1.4. 与 `node_database` 的知识结合机制

- **动态知识清单注入**: 在“理解输入”阶段，系统会从 `node_database` 动态读取所有可用的节点类型列表，并将其作为上下文注入到提示词中。这有效地将 LLM 的解析范围约束在已知的、合法的操作集合内。
- **模板内容注入**: 在“生成节点 XML”阶段，系统会根据上一步解析出的具体操作类型，从 `node_database` 中读取对应 `.xml` 模板的**完整内容**。然后，将这些内容作为字符串注入到提示词中，为 LLM 提供一个必须严格遵循的“样板”，以生成具体的节点实例。

---

## 2. 节点模板数据库 (`/workspace/database/node_database/`)

节点模板数据库是系统中所有原子操作的知识源泉，它通过知识工程的方法构建，是一个**手动编写**的、权威的原子操作知识库。

### 2.1. 提取与制作过程概述

此处的“提取”指的是从技术文档中提炼和总结知识，并将其工程化的过程，而非软件的自动“导出”功能。所有模板均为手动创建，以确保其高质量和与系统的高度兼容性。

### 2.2. 来源与验证

- **手动编写，兼容 Blockly**: 所有模板文件都是为了与 Google Blockly 编辑器兼容而手动创建的。这一点可以从以下几个方面得到证实：
  1.  文件结构遵循 Blockly 的 XML 命名空间和标准规范。
  2.  模板中包含占位符 ID（如 `GENERATED_ID`），这与实际流程中动态生成的 ID 形成对比。
  3.  模板内包含了为开发者和 LLM 准备的、极其详细且结构化的元数据注释，这是自动化导出工具无法实现的。

### 2.3. 提取与创建流程

1.  **知识源识别**: 将机器人技术手册、API 文档（如 `quickfcpr.md`）等官方文档确定为知识的“事实来源”。
2.  **信息提取**: 针对每一个机器人原子操作，系统性地从源文档中提取其操作类型、所有必需参数，以及每个参数的详细元数据（如描述、数据类型、有效值范围、默认值等）。
3.  **模板编写**: 遵循 Blockly XML 规范，为每一个操作手动创建一个对应的 `.xml` 文件。
4.  **知识嵌入**: 将上一步提取出的参数元数据，按照预先定义的注释格式，精确地嵌入到每个 XML 节点的 `<field>` 标签内部。这使得每个模板都成为“自文档化”的知识单元。

### 2.4. 核心作用：原子操作的权威知识库

- **作为权威模板**: 这些 XML 文件为系统中每一个可执行的原子操作提供了权威且唯一的结构模板。下游的 LLM 流程在生成具体节点时，必须加载并严格遵循这些模板。
- **约束代码生成**: 模板为 LLM 的输出提供了强有力的结构性约束。LLM 的核心任务是填充内容（即参数值），而模板则负责保证最终生成代码的格式正确性。
- **连接语言与机器**: 这些模板是连接“自然语言理解”和“机器代码表示”的关键桥梁。它们确保了从用户意图到最终可执行 XML 流程的转换过程既灵活又高度可靠。

---

## 结论

`quickfcpr` 项目的知识库构建方法展示了一个将 LLM 的灵活性与工程的严谨性相结合的先进范例。通过**任务分解**、**Schema 约束**、**知识注入**和**手动知识工程**，系统成功地构建了一个模块化、可维护且高精度的自然语言到代码的生成引擎。
