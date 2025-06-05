## 2. Grasp Task (拿取任务)

- **Type Description (类型描述)**:
  Defines a sequence of actions specifically for picking up an object from a source location using an end-effector (e.g., gripper, multi-finger clamp, suction cup). It typically involves approaching the object, positioning the end-effector, activating it to secure the object, and then retracting.

- **Precautions (注意事项)**:

  - Ensure the correct end-effector/clamp sub-program (e.g., `Open_XYZ_Clamp`, `Close_XYZ_Clamp`) is specified and called.
  - Approach, grasp, and retract paths must be carefully planned to be clear of obstacles.
  - Precise positioning of the end-effector relative to the object is critical before attempting to grasp.
  - Speed (`set_speed`) should often be reduced for the final approach and grasp movement to ensure accuracy and prevent damage.
  - Must include a step to open the clamp _before_ final approach to the object.
  - Must include a step to close the clamp to secure the object.
  - Verify grasp success if sensors are available (e.g., `wait_input`).

- **Naming Convention (取名原理)**:

  - Typically includes "Get", "Grasp", or "Pick" along with the object's name and optionally its source.
  - Abbreviations for objects (e.g., BRG for Bearing, BH for Bearing Housing) should be used if defined.
  - Examples: `Get_Bearing_BRG`, `Grasp_Part_From_Feeder`, `Pick_Component_A_From_Tray1`.

- **Typical Block Types Used (典型使用的 BlockType)**:

  - Movement: `moveP`, `moveL` (for approach, fine positioning, departure).
  - Effector Control: `procedures_callnoreturn` (to call `Open_Clamp_Task` and `Close_Clamp_Task` sub-programs).
  - Speed Control: `set_speed`.
  - Waiting/Confirmation (optional): `wait_timer`, `wait_input`.

- **Allowed Contained Task Types (允许包含的任务类型)**:
  - OpenClampTask (夹爪开启任务)
  - CloseClampTask (夹爪关闭任务)
  - (Conceptionally, can also include fine-grained movement sub-tasks if the grasp is very complex, but usually involves direct motion commands).
