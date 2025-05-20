# Turn 3 Execution Error

Error: 'merge_xmls'
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
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/utils/runnable.py", line 678, in ainvoke
    input = await step.ainvoke(input, config)
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/utils/runnable.py", line 440, in ainvoke
    ret = await self.afunc(*args, **kwargs)
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/graph/branch.py", line 197, in _aroute
    return self._finish(writer, input, result, config)
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/graph/branch.py", line 209, in _finish
    destinations: Sequence[Union[Send, str]] = [
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/graph/branch.py", line 210, in <listcomp>
    r if isinstance(r, Send) else self.ends[r] for r in result
KeyError: 'merge_xmls'
