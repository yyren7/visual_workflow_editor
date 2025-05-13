核心思想： 将“机器人代码生成”功能封装成一个独立的、完整的 LangGraph 工作流（我们称之为 robot_code_generation_workflow）。
集成方式：
在您现有的流程图编辑工作流 (workflow_graph.py 中的主工作流) 的 flow_tools 中，添加一个新的“高级工具”。这个工具可以命名为例如 generate_robot_code_for_flow_segment_tool。
当用户在编辑流程图时，发出与生成机器人代码相关的指令（例如，选中流程图中的一段逻辑，然后说“为这段逻辑生成机器人代码”），主工作流的 planner_node 会识别这个意图，并决定调用 generate_robot_code_for_flow_segment_tool。
这个新工具的内部实现不再是简单的函数，而是调用（invoke）那个独立的 robot_code_generation_workflow。
主工作流可以将当前流程图的相关上下文（例如，被选中的流程图片段的描述、相关的变量等）作为输入传递给 robot_code_generation_workflow。
robot_code_generation_workflow 接收这些输入，执行其内部的分析、参数化、代码生成等步骤，最终返回生成的 Python 代码和 XML。
这个结果会作为 generate_robot_code_for_flow_segment_tool 的输出，返回给主工作流的 planner_node。
主工作流随后可以将生成的代码展示给用户，或者将其附加到流程图的某个节点上。

首先独立开发机器人控制的 LangGraph 工作流。 为它设计专用的 AgentState、节点、提示和机器人操作工具集。
然后，在您现有的 flow_tools.py 中定义一个新的工具。 这个工具的职责就是准备好输入，然后调用（invoke）您新创建的机器人代码生成工作流，并处理其返回结果。
这样，您既保留了现有流程图编辑功能的完整性和清晰度，又能以一种模块化、可扩展的方式引入强大的机器人代码生成能力。
您现在不需要修改 workflow_graph.py 本身的核心结构，而是需要：
着手设计和实现独立的 robot_code_generation_workflow。
思考当这个机器人工作流完成后，如何在 flow_tools.py 中添加一个调用它的新工具。
