{{GENERAL_INSTRUCTION_INTRO}}

**第一步：理解输入**
你会收到描述机器人工作流程的自然语言输入，保证有机器人类型，每一行只对应一个动作或逻辑节点。你的任务是将此自然语言输入转换为结构化的 JSON 对象，该对象遵循下面描述的 Pydantic Schema。

**重要约束：**

1.  **操作类型 (`type`)**: 解析出的每一个操作的 `type` 字段，其值**必须**是以下逗号分隔的已知节点类型之一：
    `{{ KNOWN_NODE_TYPES_LIST_STR }}`
    如果输入中描述的某个操作无法明确映射到这些已知类型，请在最终 JSON 输出的该操作的 `description` 字段中注明此问题，并将该操作的 `type` 字段设置为特殊值 `unknown_operation`。
2.  **操作 ID (`id_suggestion`)**: 为每个操作生成一个简洁且有意义的建议 ID，例如基于类型和序号（如 `set_motor_1`、`moveL_2`）或关键参数（如 `moveL_P1`）。
3.  **参数提取 (`parameters`)**:
    - 对于每个操作，仔细识别并提取其所有相关参数。
    - 将提取的参数构造成一个键值对字典，并填充到对应操作的 `parameters` 字段中。
    - 确保参数的键名与节点模板期望的参数名一致（如果已知），值应为适当的数据类型（字符串、数字、布尔值）。
    - 如果参数是关于轴的启用/禁用，请明确列出所有相关的轴（例如 x, y, z, a, b, c）并使用 `true` / `false`。
    - **重要格式提醒**：`parameters` 字段的值**必须**是一个直接的 JSON 对象（即字典），而不是一个被引号包围的、看起来像 JSON 对象的字符串。
      - 正确示例: `"parameters": {"speed": 100, "target_point": "P1"}`
      - 错误示例: `"parameters": "{\"speed\": 100, \"target_point\": \"P1\"}"`

**输出格式：**
确保您的输出严格遵循所提供的 Pydantic JSON Schema，特别是 `ParsedStep` 中的 `id_suggestion`, `type`, `description`, 和 `parameters` 字段。

**示例：**

假设已知节点类型包含 `set_motor_state`, `move_linear_point`, `loop_sequence`, `return_to_start`。

输入自然语言描述:

```text
机器人: {{ROBOT_NAME_EXAMPLE}}
工作流程：

1. 将电机状态设置为 on。
2. 线性移动到点 {{POINT_NAME_EXAMPLE_1}}。Z 轴启用,其余禁用。速度设为100。
3. 线性移动到点 {{POINT_NAME_EXAMPLE_2}}。X 轴和 Y 轴启用, Z 轴禁用。
4. 循环执行3次下列操作：
   a. 线性移动到点 {{POINT_NAME_EXAMPLE_3}}，加速度50
   b. 返回起点
```

期望的 JSON 输出中 `operations` 列表的一个片段可能如下所示 (注意 `parameters` 的提取):

```json
[
  {
    "id_suggestion": "set_motor_state_1",
    "type": "set_motor_state",
    "description": "将电机状态设置为 on。",
    "parameters": {
      "motor_state": "on"
    },
    "has_sub_steps": false,
    "sub_step_descriptions": []
  },
  {
    "id_suggestion": "move_linear_point_P1_2",
    "type": "move_linear_point",
    "description": "线性移动到点 {{POINT_NAME_EXAMPLE_1}}。Z 轴启用,其余禁用。速度设为100。",
    "parameters": {
      "point_name": "{{POINT_NAME_EXAMPLE_1}}",
      "speed": 100,
      "x_enabled": false,
      "y_enabled": false,
      "z_enabled": true,
      "a_enabled": false,
      "b_enabled": false,
      "c_enabled": false
    },
    "has_sub_steps": false,
    "sub_step_descriptions": []
  },
  {
    "id_suggestion": "move_linear_point_P2_3",
    "type": "move_linear_point",
    "description": "线性移动到点 {{POINT_NAME_EXAMPLE_2}}。X 轴和 Y 轴启用, Z 轴禁用。",
    "parameters": {
      "point_name": "{{POINT_NAME_EXAMPLE_2}}",
      "x_enabled": true,
      "y_enabled": true,
      "z_enabled": false,
      "a_enabled": false,
      "b_enabled": false,
      "c_enabled": false
    },
    "has_sub_steps": false,
    "sub_step_descriptions": []
  },
  {
    "id_suggestion": "loop_sequence_4",
    "type": "loop_sequence",
    "description": "循环执行3次下列操作",
    "parameters": {
      "iterations": 3
    },
    "has_sub_steps": true,
    "sub_step_descriptions": [
      "线性移动到点 {{POINT_NAME_EXAMPLE_3}}，加速度50",
      "返回起点"
    ]
  }
]
```

(请注意：上述 JSON 示例仅为片段，用于演示 `parameters` 的提取思路。实际输出需符合完整的 `UnderstandInputSchema`。)

请严格按照 Pydantic JSON Schema 生成完整的 JSON 输出。
