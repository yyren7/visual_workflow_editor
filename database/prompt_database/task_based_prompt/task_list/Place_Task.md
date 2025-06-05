## 3. Place Task (放置任务)

- **Type Description (类型描述)**:
  Defines a sequence of actions for placing an object, currently held by an end-effector, at a target destination. It involves approaching the destination, positioning the object, and then deactivating the end-effector to release the object.

- **Precautions (注意事项)**:

  - Ensure the target location is clear and ready to receive the object.
  - Approach, placement, and retract paths must be clear of obstacles.
  - Precise positioning of the object at the target location is critical before release.
  - Speed (`set_speed`) should often be reduced for the final approach and placement movement.
  - Must include a step to open the clamp (or deactivate effector) to release the object.
  - Verify placement success or effector release if sensors are available.

- **Naming Convention (取名原理)**:

  - Typically includes "Put", "Place", or "Release" along with the object's name and optionally its destination.
  - Abbreviations should be consistent.
  - Examples: `Put_Bearing_In_RMC`, `Place_Assembly_On_Pallet`, `Release_Part_To_Conveyor`.

- **Typical Block Types Used (典型使用的 BlockType)**:

  - Movement: `moveP`, `moveL` (for approach, fine positioning, departure).
  - Effector Control: `procedures_callnoreturn` (to call `Open_Clamp_Task` sub-program).
  - Speed Control: `set_speed`.
  - Waiting/Confirmation (optional): `wait_timer`.

- **Allowed Contained Task Types (允许包含的任务类型)**:
  - OpenClampTask (夹爪开启任务)
  - (Conceptionally, can also include fine-grained movement sub-tasks for complex placements).
