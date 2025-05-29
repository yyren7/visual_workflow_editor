# Turn 1 Execution Error

Error: Recursion limit of 20 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key.
For troubleshooting, visit: https://python.langchain.com/docs/troubleshooting/errors/GRAPH_RECURSION_LIMIT
Traceback: Traceback (most recent call last):
  File "/workspace/backend/tests/run_robot_flow_agent.py", line 156, in main
    final_state_output = await robot_flow_app.ainvoke(current_state, {"recursion_limit": 20})
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/__init__.py", line 2963, in ainvoke
    async for chunk in self.astream(
  File "/home/vscode/.local/lib/python3.10/site-packages/langgraph/pregel/__init__.py", line 2852, in astream
    raise GraphRecursionError(msg)
langgraph.errors.GraphRecursionError: Recursion limit of 20 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key.
For troubleshooting, visit: https://python.langchain.com/docs/troubleshooting/errors/GRAPH_RECURSION_LIMIT
