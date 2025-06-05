## 1. Main Task (主任务)

- **Type Description (类型描述)**:
  Represents the overall robotic process or a major, high-level phase of an operation. It orchestrates calls to various sub-tasks (like Grasp, Place, or other specialized sub-programs) to achieve a larger, composite goal. The Main Task defines the primary sequence, control flow (loops, conditionals), and initialization/shutdown procedures for the entire operation.

- **Precautions (注意事项)**:

  - Must include essential initialization steps at the beginning, such as robot model selection (`select_robot`) and starting robot motors (`set_motor`).
  - Should clearly define the primary control flow, including any main loops (`loop`) or conditional logic (`controls_if`) that governs the process execution.
  - Ensure all orchestrated sub-tasks are called in a logically correct sequence.
  - Consider overall safety: for instance, moving to a "Home" or safe position at the start, end, and between major segments.
  - May require initialization of process-critical variables (e.g., using `set_number`).

- **Naming Convention (取名原理)**:

  - Names should be `Main_Task`.

- **Typical Block Types Used (典型使用的 BlockType)**:

  - Initialization: `select_robot`, `set_motor`, `set_number`.
  - Control Flow: `loop`, `controls_if`, `return` (for loop control).
  - Sub-task Orchestration: `procedures_callnoreturn` (to call other defined sub-tasks/sub-programs).
  - Movement: `moveP`, `moveL` (for moving to safe/initial positions).
  - Waiting/Synchronization: `wait_external_io_input`, `wait_input`, `wait_timer`, `set_external_io_output_upon`, `set_output` (for interaction with external systems or signals).

- **Allowed Contained Task Types (允许包含的任务类型)**:
  - GraspTask (拿取任务)
  - PlaceTask (放置任务)
  - OpenClampTask (夹爪开启任务) - usually called within Grasp/Place tasks.
  - CloseClampTask (夹爪关闭任务) - usually called within Grasp tasks.
  - Other custom SubTask types representing specific sequences or logic.
