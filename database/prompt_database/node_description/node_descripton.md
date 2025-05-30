connect_external_io: Connects to an external I/O device/unit. Precautions: Use in conjunction with blocks like "set external io output" or "wait external io input".
controls_if: Branch the enclosed operation blocks according to the condition. Precautions: The maximum number of conditional branches is 10. Other blocks cannot be connected below the "if" block. If multiple conditions are met simultaneously, the process described in the first (topmost) met condition is prioritized. (Mapped to "if" block from draft)
create_event: Perform parallel processing of operations according to the set conditions. Precautions: Other blocks cannot be connected below the "start thread" block. (Note: The precaution mentions "start thread" block, which might be an error in the source document. It likely implies that the main flow does not continue directly after this block, and its logic is self-contained or triggered by events.)
external_io: Return the external device I/O status as a logical value. Precautions: Define the I/O device with the "connect external io" block before using.
logic_boolean: Return the set logical value (true/false). Precautions: Use together with blocks like "start thread". (Mapped to "logic flag" block from draft)
logic_compare: Return the result of the set comparison operation (e.g., =, <, >) as a logical value. Precautions: Use together with blocks like "start thread".
logic_custom_flag: Return the logical value of a defined flag variable. Precautions: Use together with blocks like "set flag".
logic_operation: Performs a logical operation (AND/OR) between two logical values and returns the result. Precautions: Use together with blocks like "start thread".
loop: Perform loop processing of the enclosed block operations. Precautions: Nesting "loop" blocks (placing one inside another) may cause unintended behavior. Other blocks cannot be connected below the "loop" block. Use the "return" block to complete the loop iteration and go back to the start of the loop.
math_custom_number: Specify and return the value of a numerical variable. Precautions: Use together with blocks like "set number".
math_number: Return a specified numerical value. Precautions: Use together with blocks like "set number".
moveL: Move the robot in an absolute linear motion along all axes. Precautions: Define the robot with the "select robot" block before using. Use after turning ON the servo power with the "set motor" block. For 4-axis robots, Rz becomes R (=0 rotation) (Ry and Rx are invalid).
moveP: Move the robot in an absolute PTP (Point-to-Point) motion along all axes. Precautions: Define the robot with the "select robot" block before using. Use after turning ON the servo power with the "set motor" block. For 4-axis robots, Rz becomes R (= rotation) (Ry and Rx are invalid).
procedures_callnoreturn: Call a previously defined function. Precautions: Define the function using the "define function" block before using this block to call it. (Mapped to "call function" from draft)
procedures_defnoreturn: Define a function with a given name. Precautions: Use in conjunction with the "call function" block. If the "define function" block is deleted, "call function" blocks with the same name will also be deleted. (Mapped to "define function" from draft)
return: Return to the beginning of the loop process. Precautions: Use together with the "loop" block.
robot_io: Return the robot I/O status as a logical value. Precautions: Define the robot with the "select robot" block before using.
select_robot: Select the robot to which commands will be sent. Precautions: Can only be placed at the beginning of the flow. Placing two or more in the same workspace may cause unintended behavior.
set_external_io_output_during: Operate the output of an external device I/O for a specified time. Precautions: Define the I/O device with the "connect external io" block before using.
set_external_io_output_upon: Operate the output of external device I/O when the set condition is met. Precautions: Define the I/O device with the "connect external io" block before using. Use inside a "create event trigger" block.
set_motor: Operate the robot's servo motor power supply. Precautions: Place it before using "move" blocks.
set_number: Assign a numerical value to a variable. Precautions: Define variables in the variable table before storing values in them.
set_output: Operate the robot I/O output. Precautions: Define the robot with the "select robot" block before using.
set_speed: Sets the robot's operational speed. Precautions: Define the robot with the "select robot" block before using. Ensure motor power is ON if applicable before movement commands that use this speed. The speed value is typically a percentage or a specific unit (e.g., mm/s); check robot documentation for specifics.
start_thread: Start the enclosed block operation according to the condition. Precautions: Other blocks cannot be connected below the "start thread" block.
stop_robot_upon: The robot stops when the set condition is met. Precautions: Use inside a "create event trigger" block.
wait_block: Wait until the operating condition of the connected block is met. Precautions: Only blocks from the "Logic" category can be connected as operating conditions.
wait_external_io_input: Wait until the input of the external device I/O meets the specified condition. Precautions: Define the I/O device with the "connect external io" block before using.
wait_input: Wait until the robot I/O input meets the specified condition. Precautions: Define the robot with the "select robot" block before using.
wait_timer: Wait for a specified amount of time. Precautions: Time can only be set in milliseconds (msec).
