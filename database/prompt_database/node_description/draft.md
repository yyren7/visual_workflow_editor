# Block Descriptions Summary

## Robot Category

### 1. select robot

- **Description**: Select the robot to which commands will be sent. [cite: 1]
- **Precautions for Use**:
  - Can only be placed at the beginning of the flow. [cite: 3]
  - Placing two or more in the same workspace may cause unintended behavior. [cite: 3]

### 2. set motor

- **Description**: Operate the robot's servo motor power supply. [cite: 1]
- **Precautions for Use**:
  - Place it before using "move" blocks. [cite: 6]

### 3. move origin

- **Description**: Return the robot to its origin point.
- **Precautions for Use**:
  - Only necessary for robots equipped with incremental encoders.
  - Not necessary for Dobot MG400, Fairino FR, Hitbot Z ARM.

### 4. moveL

- **Description**: Move the robot in an absolute linear motion along all axes. [cite: 7]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 10]
  - Use after turning ON the servo power with the "set motor" block. [cite: 10]
  - For 4-axis robots, Rz becomes R (=0 rotation) (Ry and Rx are invalid). [cite: 10]

### 5. moveP

- **Description**: Move the robot in an absolute PTP (Point-to-Point) motion along all axes.
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 13]
  - Use after turning ON the servo power with the "set motor" block. [cite: 13]
  - For 4-axis robots, Rz becomes R (= rotation) (Ry and Rx are invalid). [cite: 13]

### 6. wait input

- **Description**: Wait until the robot I/O input meets the specified condition. [cite: 13]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 16]

### 7. set output

- **Description**: Operate the robot I/O output. [cite: 16]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 18]

### 8. set output during

- **Description**: Operate the robot I/O output for a specified time. [cite: 18]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 22]

### 9. set output until

- **Description**: Continue operating the specified pin until the robot I/O input meets the specified condition. [cite: 22]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 25]

### 10. robot io

- **Description**: Return the robot I/O status as a logical value. [cite: 25]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 29]

### 11. robot position

- **Description**: Return the current robot position as a numerical value. [cite: 29]
- **Precautions for Use**:
  - Define the robot with the "select robot" block before using. [cite: 31]

### 12. stop robot upon

- **Description**: The robot stops when the set condition is met. [cite: 31]
- **Precautions for Use**:
  - Use inside a "create event trigger" block. [cite: 38] _(The document refers to "create_event" block, image shows "create event trigger" context)_

## External I/O Category

### 13. connect external io

- **Description**: Connects to an external I/O device/unit. (The provided description "Operate the output of external device I/O" [cite: 14] seems to better fit "set external io output"; this description is inferred from block name and usage context.)
- **Precautions for Use**:
  - Use in conjunction with blocks like "set external io output" or "wait external io input". [cite: 41]

### 14. wait external io input

- **Description**: Wait until the input of the external device I/O meets the specified condition. [cite: 41]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 44]

### 15. set external io output

- **Description**: Operate the output of an external device I/O. [cite: 16]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 48]

### 16. set external io output during

- **Description**: Operate the output of an external device I/O for a specified time. [cite: 48]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 51]

### 17. set external io output until

- **Description**: Continue operating the specified pin until the input of the external device I/O meets the specified condition. [cite: 51]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 53]

### 18. external io

- **Description**: Return the external device I/O status as a logical value. [cite: 53]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 56]

### 19. set external io output upon

- **Description**: Operate the output of external device I/O when the set condition is met. [cite: 57]
- **Precautions for Use**:
  - Define the I/O device with the "connect external io" block before using. [cite: 63]
  - Use inside a "create event trigger" block. [cite: 63] _(The document refers to "create_event" block, image shows "create event trigger" context)_

## Control Category

### 20. loop

- **Description**: Perform loop processing of the enclosed block operations. [cite: 63]
- **Precautions for Use**:
  - Nesting "loop" blocks (placing one inside another) may cause unintended behavior. [cite: 63]
  - Other blocks cannot be connected below the "loop" block. [cite: 63]
  - Use the "return" block to complete the loop iteration and go back to the start of the loop. [cite: 63]

### 21. return

- **Description**: Return to the beginning of the loop process. [cite: 64]
- **Precautions for Use**:
  - Use together with the "loop" block. [cite: 64]

### 22. wait timer

- **Description**: Wait for a specified amount of time. [cite: 64]
- **Precautions for Use**:
  - Time can only be set in milliseconds (msec). [cite: 66]

### 23. wait ready

- **Description**: Wait until the Ready button is pressed. [cite: 67]
- **Precautions for Use**:
  - None. [cite: 67]

### 24. wait run

- **Description**: Wait until the Run button is pressed. [cite: 67]
- **Precautions for Use**:
  - None. [cite: 69]

## Logic Category

### 25. if

- **Description**: Branch the enclosed operation blocks according to the condition. [cite: 69]
- **Precautions for Use**:
  - The maximum number of conditional branches is 10. [cite: 71]
  - Other blocks cannot be connected below the "if" block. [cite: 71]
  - If multiple conditions are met simultaneously, the process described in the first (topmost) met condition is prioritized. [cite: 71]

### 26. start thread

- **Description**: Start the enclosed block operation according to the condition. [cite: 71]
- **Precautions for Use**:
  - Other blocks cannot be connected below the "start thread" block. [cite: 73]

### 27. create event

- **Description**: Perform parallel processing of operations according to the set conditions.
- **Precautions for Use**:
  - Other blocks cannot be connected below the "start thread" block. [cite: 73] _(Note: The precaution mentions "start thread" block, which might be an error in the source document. It likely implies that the main flow does not continue directly after this block, and its logic is self-contained or triggered by events.)_

### 28. wait block

- **Description**: Wait until the operating condition of the connected block is met.
- **Precautions for Use**:
  - Only blocks from the "Logic" category can be connected as operating conditions. [cite: 75]

### 29. set flag

- **Description**: Assign a logical value to a variable. [cite: 75]
- **Precautions for Use**:
  - Define variables in the variable table before storing values in them. [cite: 78]

### 30. logic flag

- **Description**: Return the set logical value (true/false). [cite: 78]
- **Precautions for Use**:
  - Use together with blocks like "start thread". [cite: 80]

### 31. logic custom flag

- **Description**: Return the logical value of a defined flag variable. [cite: 80]
- **Precautions for Use**:
  - Use together with blocks like "set flag". [cite: 82]

### 32. logic block

- **Description**: Return the status (e.g., start/stop) of a set block as a logical value. [cite: 82]
- **Precautions for Use**:
  - Use together with blocks like "wait block". [cite: 85]

### 33. logic negate

- **Description**: Return the negation (NOT) of the set logical value. [cite: 85]
- **Precautions for Use**:
  - None. [cite: 88]

### 34. logic compare

- **Description**: Return the result of the set comparison operation (e.g., =, <, >) as a logical value. [cite: 88]
- **Precautions for Use**:
  - Use together with blocks like "start thread". [cite: 91]

### 35. logic operation

- **Description**: Performs a logical operation (AND/OR) between two logical values and returns the result. (The provided description "Return the result of the set comparison operation as a logical value" [cite: 92] is similar to `logic compare`; this description is based on typical AND/OR block functionality).
- **Precautions for Use**:
  - Use together with blocks like "start thread". [cite: 93]

### 36. set flag upon

- **Description**: Assign a logical value to a variable when the set condition is met. [cite: 93]
- **Precautions for Use**:
  - Define variables in the variable table before storing values in them. [cite: 97]

## Math Category

### 37. set number

- **Description**: Assign a numerical value to a variable. [cite: 97]
- **Precautions for Use**:
  - Define variables in the variable table before storing values in them. [cite: 100]

### 38. math number

- **Description**: Return a specified numerical value. [cite: 100]
- **Precautions for Use**:
  - Use together with blocks like "set number". [cite: 102]

### 39. math custom number

- **Description**: Specify and return the value of a numerical variable. [cite: 102]
- **Precautions for Use**:
  - Use together with blocks like "set number". [cite: 104]

### 40. math arithmetic

- **Description**: Performs an arithmetic operation (+, -, \*, /, ^) between two numerical values and returns the result. (The provided description "Assign a value to a variable" [cite: 105] is for `set number`; this description is based on arithmetic block functionality).
- **Precautions for Use**:
  - Define variables in the variable table before storing values in them (if results are to be stored or variables are used as operands). [cite: 106]

### 41. set number upon

- **Description**: Assign a numerical value to a variable when the set condition is met. [cite: 106]
- **Precautions for Use**:
  - Define variables in the variable table before storing values in them. [cite: 110]

## Error Category

### 42. raise error

- **Description**: The set error occurs immediately. [cite: 110]
- **Precautions for Use**:
  - Only alphabetic characters can be set as error messages. [cite: 114]

### 43. raise error upon

- **Description**: An error occurs when the set condition is met. [cite: 114]
- **Precautions for Use**:
  - Only alphabetic characters can be set as error messages. [cite: 119]
  - Use inside a "create event trigger" block. [cite: 119] _(The document refers to "create_event" block, image shows "create event trigger" context)_

## Pallet Category

### 44. set pallet

- **Description**: Set the pallet's configuration (rows, columns, corner points, usage). [cite: 119]
- **Precautions for Use**:
  - To set the pallet offset in "moveL" or "moveP" blocks, select the pallet No. in those move blocks. [cite: 124]

### 45. move next pallet

- **Description**: Advance the current position on the pallet to the next one according to the defined sequence. [cite: 124]
- **Precautions for Use**:
  - Use in conjunction with the "set pallet" block. [cite: 127]

### 46. reset pallet

- **Description**: Return the current position of the pallet to the starting point (Point A). [cite: 127]
- **Precautions for Use**:
  - Use in conjunction with the "set pallet" block. [cite: 131]

## Camera Category

### 47. connect camera

- **Description**: Connect to the camera PC using IP address and port number. [cite: 131]
- **Precautions for Use**:
  - Use in conjunction with blocks like "run camera wait" or "run camera". [cite: 135]

### 48. run camera wait

- **Description**: Send an execution command to the camera PC and wait until the result is obtained. [cite: 135]
- **Precautions for Use**:
  - Use in conjunction with "connect camera" block. [cite: 139]
  - Integration with vision systems such as Facilea, Vision Master, VAST Vision is possible. [cite: 139]
  - For details, please check the documentation of the vision system you are using. [cite: 139]
  - Camera operation command is sent via TCP as a string: "Identification header, program number, config number, model number, position number CRLF". Example: TR1,1,0,0,0\r\n. Only the program number can be changed from the block. [cite: 139]
  - Camera result is received via TCP as a string: "Identification header, judgment result (OK:1, NG:2, ERR:3), x-coordinate [mm], y-coordinate, z-coordinate, judgment content (text) CRLF". Example: TR1,1,0,0,0,0,no work,\r\n. [cite: 139, 140]

### 49. run camera

- **Description**: Send an execution command to the camera PC (does not wait for completion). [cite: 140]
- **Precautions for Use**:
  - Use in conjunction with "connect camera" block. [cite: 144]
  - Integration with vision systems such as Facilea, Vision Master, VAST Vision is possible. [cite: 144]
  - For details, please check the documentation of the vision system you are using. [cite: 144]
  - Camera operation command is sent via TCP as a string: "Identification header, program number, config number, model number, position number CRLF". Example: TR1,1,0,0,0\r\n. Only the program number can be changed from the block. [cite: 144]

### 50. wait camera

- **Description**: Wait until the result is obtained from the camera PC (used after a "run camera" block). [cite: 145]
- **Precautions for Use**:
  - Use in conjunction with blocks like "run camera". [cite: 147]

## PLC Category

### 51. connect plc

- **Description**: Connect to a PLC using maker, IP address, and port number. [cite: 147]
- **Precautions for Use**:
  - Use in conjunction with blocks like "plc bit" or "set plc bit". [cite: 150]

### 52. plc bit

- **Description**: Return the status (ON/OFF) of a PLC's bit device as a logical value. [cite: 150]
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 153]

### 53. plc word

- **Description**: Return the value of a PLC's word device as a numerical value. [cite: 153]
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 156]

### 54. set plc bit

- **Description**: Set the value (ON/OFF) of a PLC's bit device. [cite: 156]
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 158]

### 55. set plc bit during

- **Description**: Set the value (ON/OFF) of a PLC's bit device for a specified duration. [cite: 158]
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 161]

### 56. set plc bit until

- **Description**: Set the value of a PLC's output bit device (ON/OFF) until a specified PLC input bit device meets a certain condition. [cite: 161]
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 164]

### 57. set plc word

- **Description**: Set the numerical value of a PLC's word device. (The provided description "Operate the value of the PLC's bit device" [cite: 164] is incorrect; this is for word devices based on example and context).
- **Precautions for Use**:
  - Use in conjunction with the "connect plc" block. [cite: 167]

## Function Category

### 58. define function

- **Description**: Define a function with a given name. [cite: 167]
- **Precautions for Use**:
  - Use in conjunction with the "call function" block. [cite: 170]
  - If the "define function" block is deleted, "call function" blocks with the same name will also be deleted. [cite: 170]

### 59. call function

- **Description**: Call a previously defined function. [cite: 170]
- **Precautions for Use**:
  - Define the function using the "define function" block before using this block to call it. [cite: 171]
