# 机器人流程生成 - 占位符定义

本文档定义了在机器人流程生成步骤的 Markdown 模板 (`flow_step0_*.md` 到 `flow_step4_*.md`) 中使用的占位符及其示例值。

- `{{GENERAL_INSTRUCTION_INTRO}}`: 智能体通用指令介绍文本。

  - _示例值_: `作为机器人流程文件创建智能体，根据上下文和用户的最新自然语言输入，你需要执行以下多步骤流程来生成机器人控制的 XML 文件：`

- `{{ROBOT_NAME_EXAMPLE}}`: 自然语言输入中使用的机器人名称示例。

  - _示例值_: `dobot_mg400`

- `{{POINT_NAME_EXAMPLE_1}}`: 自然语言输入中使用的示例点位名称 1。

  - _示例值_: `P3`

- `{{POINT_NAME_EXAMPLE_2}}`: 自然语言输入中使用的示例点位名称 2。

  - _示例值_: `P1`

- `{{POINT_NAME_EXAMPLE_3}}`: 自然语言输入中使用的示例点位名称 3。

  - _示例值_: `P2`

- `{{NODE_TEMPLATE_DIR_PATH}}`: 存放 XML 节点模板的目录路径。

  - _示例值_: `/workspace/database/node_database/quick-fcpr`

- `{{OUTPUT_DIR_PATH}}`: 存放所有生成文件的目标输出目录路径。

  - _示例值_: `/workspace/database/flow_database/result/example_run/`

- `{{EXAMPLE_FLOW_STRUCTURE_DOC_PATH}}`: 展示节点连接方法和 XML 结构的示例流程文件路径。

  - _示例值_: `/workspace/database/document_database/flow.xml`

- `{{BLOCK_ID_PREFIX_EXAMPLE}}`: 生成 XML 块 ID 时使用的前缀示例。

  - _示例值_: `block_uuid`

- `{{RELATION_FILE_NAME_ACTUAL}}`: 节点关系结构文件的标准名称。

  - _示例值_: `relation.xml`

- `{{FINAL_FLOW_FILE_NAME_ACTUAL}}`: 最终完整流程 XML 文件的标准名称。
  - _示例值_: `flow.xml`
