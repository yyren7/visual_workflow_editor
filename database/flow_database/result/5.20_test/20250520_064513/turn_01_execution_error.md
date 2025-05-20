# Turn 1 Execution Error

Error: 'RobotFlowAgentState' object has no attribute 'get'
Traceback: Traceback (most recent call last):
  File "/workspace/backend/tests/run_robot_flow_agent.py", line 114, in main
    final_state_dict = await robot_flow_app.ainvoke(current_state, {"recursion_limit": 25})
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
  File "/home/vscode/.local/lib/python3.10/site-packages/langchain_core/runnables/config.py", line 616, in run_in_executor
    return await asyncio.get_running_loop().run_in_executor(
  File "/usr/lib/python3.10/concurrent/futures/thread.py", line 58, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/home/vscode/.local/lib/python3.10/site-packages/langchain_core/runnables/config.py", line 607, in wrapper
    return func(*args, **kwargs)
  File "/workspace/backend/langgraphchat/graph/nodes/robot_flow_planner/graph_builder.py", line 40, in initialize_state_node
    current_config = state.get("config", {})
  File "/home/vscode/.local/lib/python3.10/site-packages/pydantic/main.py", line 989, in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
AttributeError: 'RobotFlowAgentState' object has no attribute 'get'
