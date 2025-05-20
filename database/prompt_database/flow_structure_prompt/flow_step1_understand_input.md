{{GENERAL_INSTRUCTION_INTRO}}

**第一步：理解输入**
你会收到描述机器人工作流程的自然语言输入，保证有机器人类型，每一行只对应一个动作或逻辑节点。

**重要约束：**
解析出的每一个操作的 `type` 字段，其值**必须**是以下逗号分隔的已知节点类型之一：
`{{ KNOWN_NODE_TYPES_LIST_STR }}`
如果输入中描述的某个操作无法明确映射到这些已知类型，请在最终 JSON 输出的该操作的 `description` 字段中注明此问题，并将该操作的 `type` 字段设置为特殊值 `unknown_operation`。

节点所有必要的参数应尽可能从文本中提取。

完整的例子，比如输入是（假设已知节点类型包含 moveL, set_motor, loop, return）：

```text
机器人: {{ROBOT_NAME_EXAMPLE}}
工作流程：

1. 将电机状态设置为 on。
2. 线性移动到点 {{POINT_NAME_EXAMPLE_1}}。Z 轴启用,其余禁用。
3. 线性移动到点 {{POINT_NAME_EXAMPLE_1}}。Z 轴禁用,其余启用。
4. 循环：顺序执行下列线性移动，启用全部六轴控制：
   a. 移动到点 {{POINT_NAME_EXAMPLE_2}}
   b. 移动到点 {{POINT_NAME_EXAMPLE_3}}
   c. 移动到点 {{POINT_NAME_EXAMPLE_1}}
   d. 移动到点 {{POINT_NAME_EXAMPLE_2}}
   e. 移动到点 {{POINT_NAME_EXAMPLE_3}}
   f. 移动到点 {{POINT_NAME_EXAMPLE_1}}
   g. 返回
```

确保您的输出严格遵循所提供的 Pydantic JSON Schema。
