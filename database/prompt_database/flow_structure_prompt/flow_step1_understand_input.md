{{GENERAL_INSTRUCTION_INTRO}}

**第一步：理解输入**
你会收到描述机器人工作流程的自然语言输入，保证每一行只对应一个机器人动作节点，并且该节点所有必要的参数存在且合法。例如，
输入是
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
