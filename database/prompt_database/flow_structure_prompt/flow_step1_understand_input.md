{{GENERAL_INSTRUCTION_INTRO}}

**第一步：理解输入**
你会收到描述机器人工作流程的自然语言输入，保证有机器人类型，每一行只对应一个动作或逻辑节点，并且节点所有必要的参数存在且合法。此外，如果用户提到了循环或重复序列 (例如 "以点 231231 的顺序循环")，请将其作为以循环步骤开始，其他步骤作为 tab 空行+字母开头的子步骤直到返回子步骤的集合。例如：

```
text
4.循环：顺序执行下列线性移动，启用全部六轴控制：
   a. 移动到点 {{POINT_NAME_EXAMPLE_2}}
   b. 移动到点 {{POINT_NAME_EXAMPLE_3}}
   c. 移动到点 {{POINT_NAME_EXAMPLE_1}}
   d. 返回
```

完整的例子，比如输入是：
'''text
用 mg400 机器人先移动到点 1，再以 231231 的顺序循环。
'''
处理成以下输入：

'''text
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
   '''
