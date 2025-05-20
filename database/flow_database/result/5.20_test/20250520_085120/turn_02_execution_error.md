# Turn 2 Execution Error

Error: "RobotFlowAgentState" object has no field "final_flow_xml_content"
Traceback: Traceback (most recent call last):
  File "/workspace/backend/tests/run_robot_flow_agent.py", line 117, in main
    final_state_output = await robot_flow_app.ainvoke(current_state, {"recursion_limit": 25})
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/__init__.py", line 2892, in ainvoke
    async for chunk in self.astream(
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/__init__.py", line 2759, in astream
    async for _ in runner.atick(
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/runner.py", line 283, in atick
    await arun_with_retry(
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/retry.py", line 128, in arun_with_retry
    return await task.proc.ainvoke(task.input, config)
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/utils/runnable.py", line 676, in ainvoke
    input = await step.ainvoke(input, config, **kwargs)
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/utils/runnable.py", line 440, in ainvoke
    ret = await self.afunc(*args, **kwargs)
  File "/workspace/backend/langgraphchat/graph/nodes/robot_flow_planner/graph_builder.py", line 247, in generate_final_flow_xml_node
    state.final_flow_xml_content = final_xml_string_output
  File "/home/vscode/.local/lib/python3.10/site-packages/pydantic/main.py", line 995, in __setattr__
    elif (setattr_handler := self._setattr_handler(name, value)) is not None:
  File "/home/vscode/.local/lib/python3.10/site-packages/pydantic/main.py", line 1042, in _setattr_handler
    raise ValueError(f'"{cls.__name__}" object has no field "{name}"')
ValueError: "RobotFlowAgentState" object has no field "final_flow_xml_content"
