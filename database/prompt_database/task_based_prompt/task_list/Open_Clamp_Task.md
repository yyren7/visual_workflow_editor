## 4. Open Clamp Task (夹爪开启任务)

- **Type Description (类型描述)**:
  A specific, often atomic, action to open a designated clamp, gripper, or other end-effector. This task is usually called as a sub-step within a Grasp Task (before approaching an object) or a Place Task (to release an object).

- **Precautions (注意事项)**:

  - Ensure this task is called at the correct point in a sequence.
  - Verify that the correct clamp/effector is being addressed if the robot has multiple effectors.
  - Consider any necessary delays (`wait_timer`) to allow for the mechanical action of opening.
  - If available, wait for sensor feedback (`wait_input`) to confirm the clamp is fully open.

- **Naming Convention (取名原理)**:

  - Usually `Open_` followed by the specific clamp or effector name.
  - Abbreviations should be consistent.
  - Examples: `Open_BH_Clamp`, `Open_BRG&PLT_Clamp`, `Open_Gripper_A`.

- **Typical Block Types Used (典型使用的 BlockType)**:

  - Signal Output: `set_output` (to send the electrical signal to open the clamp).
  - Timing: `wait_timer` (to allow time for the clamp to open).
  - Sensor Feedback: `wait_input` (to confirm the clamp is open via a sensor).

- **Allowed Contained Task Types (允许包含的任务类型)**:
  - Typically none. These are usually considered atomic operations at the task planning level, though their block implementation might have a sequence.
