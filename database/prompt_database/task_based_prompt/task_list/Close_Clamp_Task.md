## 5. Close Clamp Task (夹爪关闭任务)

- **Type Description (类型描述)**:
  A specific, often atomic, action to close a designated clamp, gripper, or other end-effector, typically to secure an object. This task is usually called as a sub-step within a Grasp Task.

- **Precautions (注意事项)**:

  - Ensure this task is called only after the robot/clamp is correctly positioned over/around the object to be grasped.
  - Verify the correct clamp/effector.
  - Consider necessary delays (`wait_timer`) for the mechanical action of closing.
  - If available, wait for sensor feedback (`wait_input`) to confirm the clamp is closed and/or the object is securely held (e.g., pressure sensor, proximity sensor).
  - Avoid applying excessive force that could damage the object or the clamp, unless force control is explicitly part of the block's capability.

- **Naming Convention (取名原理)**:

  - Usually `Close_` followed by the specific clamp or effector name.
  - Abbreviations should be consistent.
  - Examples: `Close_BH_Clamp`, `Close_BRG&PLT_Clamp`, `Close_Gripper_A`.

- **Typical Block Types Used (典型使用的 BlockType)**:

  - Signal Output: `set_output` (to send the electrical signal to close the clamp).
  - Timing: `wait_timer` (to allow time for the clamp to close).
  - Sensor Feedback: `wait_input` (to confirm the clamp is closed or part is present).

- **Allowed Contained Task Types (允许包含的任务类型)**:
  - Typically none. These are usually considered atomic operations at the task planning level.
