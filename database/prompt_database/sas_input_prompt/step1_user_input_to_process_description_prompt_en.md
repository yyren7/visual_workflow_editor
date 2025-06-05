# Robot Process Generation Prompt - Stage 1: User Input to Detailed Process Description

## Objective

This Prompt aims to guide you in generating a detailed process plan based on the robot task description provided by the user (usually in natural language Markdown format). This plan should include clear descriptions of a main process and multiple sub-processes, along with textual explanations of their respective process steps and core logic. The goal is to produce a structured, easy-to-understand blueprint for robot task execution, serving as a basis for user review and subsequent refinement steps.

## Input Materials

1.  **Robot Task Description (.md or text)**: Contains natural language descriptions of the overall task the robot is expected to complete, sub-tasks, and objects of operation.

## Generation Guidelines and Requirements

Please follow these guidelines to generate a detailed process description based on the provided task description:

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to available robot control blocks. The available blocks and their capabilities will be provided to you.

- **Block Type Mapping**: For each step you describe, you MUST be able to map it to one or more specific robot control blocks (e.g., `moveP`, `set_motor`, `wait_input`, `procedures_callnoreturn`, etc.).
- **Capability Limitations**: DO NOT describe any functionality that cannot be achieved with the provided robot control blocks.
- **Precaution Compliance**: Pay strict attention to the precautions and limitations mentioned for each block type.
- **Dependency Requirements**: Ensure proper sequence and dependencies (e.g., "select robot" must come before movement commands, "set motor" must come before movement operations).
- **Block Type References**: When describing each step, explicitly mention which block type(s) will be used to implement it.

**Example Step with Block Reference**:

- Description: "Robot moves to initial/safe point (e.g., 'P_Home')"
- Block Type: `moveP` or `moveL`
- Precautions: Must define robot with "select robot" first, and turn ON servo power with "set motor" before using.

### 1. Sub-program/Function Design and Definition (Logical Level)

- **Identify Core Functional Modules**: Extract key operations and logical units from the task description to brainstorm sub-program candidates.
- **Design Sub-program Names and Abbreviations**: Pay special attention to abbreviations in sub-program names (e.g., `BRG`, `PLT`, `CNV`, `RMC`, `LMC`, `BH`, `Clamp`), ensuring they are concise and reflect functionality. Sub-program names should clearly express their purpose.
- **Clarify Sub-program Functions**: Describe in detail the specific tasks each sub-program should perform, the objects of operation, and the expected results. For example: get, put, bearing, pallet, conveyor, machining unit, clamp operation, etc.
- **Clarify Action Types**: Clearly distinguish common actions like `Get` (retrieve/pick) and `Put` (place/put down) in sub-program descriptions.
- **Design Paired Operations**: Pay attention to designing logically paired sub-programs, such as `Open_..._Clamp` and `Close_..._Clamp`, and clarify their functions.
- **Speed Control for Precision and Efficiency**: Plan for speed adjustments within sub-programs. For instance, describe the necessity of reducing speed (e.g., using `set_speed` block) before precise movements like grasping or placing an object, and restoring to a higher speed for an approach, departure, or general travel movements to optimize cycle time while ensuring accuracy and safety.

### 2. Sub-program Modularization and Reuse Strategy Planning (Logical Level)

- **Plan Reuse of Standard Operation Sequences**: Identify and describe the logic of standard operation sequences that can be reused in multiple sub-programs. For example:
  - Material Grasping/Placing Process: Describe the general logic of "approach target -> precise positioning -> execute action (e.g., grasp/release) -> depart target -> return to safe position".
  - Encapsulation of Clamp Operations: Describe how clamp control logic is encapsulated and called in different material handling operations.
- **Modular Design**: Plan whether clamp control, motion control, etc., should be described as independent, reusable logical modules.
- **Parameterization and Configuration Considerations**: Mention in the description whether variables or parameters (such as speed, force) are needed to adjust sub-program behavior for increased flexibility.
- **Nested Call Relationships**: Plan and describe the logical call relationships between sub-programs to reasonably decompose and combine tasks.
- **Symmetrical/Corresponding Operations**: Design the logic for sub-program pairs that are functionally complementary or corresponding.

### 3. Main Program Core Logic Construction (Logical Level)

- **Plan Main Program Initialization Steps**: Describe the initialization logic typically executed when the main program starts (e.g., selecting robot model, starting motors, initializing key variables, etc.).
- **Design Main Program Control Flow**: Describe the macro control flow of the main program, such as the presence of main loops, conditional judgments, etc.
- **Orchestrate Main Program's Sub-program Call Sequence**: Plan and describe how the main program completes the overall task by sequentially calling sub-programs, clearly explaining the timing and purpose of each sub-program call.
- **Consider State Transition and Synchronization Logic**: Describe the logic of how the program synchronizes and interacts with the external environment or other devices by waiting for specific conditions (e.g., sensor signals, external IO) or sending signals.
- **Consider Safety and Transition Logic**: Note whether the robot needs to move to specific safe points or transition points between different task stages.
- **Consider Error Handling and Optional Path Logic**: Think about and describe whether alternative paths or error handling mechanisms are needed. For features that are not enabled temorarily but may be needed in the future, their logic can be described and marked as optional.
- **Define End and Return Logic**: Clearly define the method for ending of loop.

In summary, you need to transform the user's natural language task description into a detailed, structured document that clearly defines the responsibilities, core step logic, and collaborative relationships of the main process and each sub-process. This description will serve as a visual plan for user confirmation and modification.

## Example Fewshot

### Example Task Input (Original User Description)

[Robot Task Description: This automated process aims to collaboratively complete an assembly and handling task involving bearings (BRG), bearing housings (BH), and pallets (PLT). The robot first retrieves a bearing and a bearing housing from a material rack or initial position. Subsequently, these two parts are placed sequentially into the right machining center (RMC), presumably for press-fitting or assembly operations. After assembly, the robot takes the assembled part from the RMC and transfers it to the left machining center (LMC) for temporary storage or subsequent processing. Next, the robot retrieves an empty pallet and places it at a designated station on the conveyor (CNV). Finally, the robot retrieves the previously stored assembled part from the LMC and places it accurately onto the pallet on the conveyor, completing the entire cycle.]

### Example Output (Detailed Process Description Plan)

I. Main Program Process Description

    - Select robot model (e.g., "dobot_mg400"). (Block Type: `select_robot`)
    - Start robot motors. (Block Type: `set_motor`)
    - Initialize necessary process control variables (e.g., `start_condition = 2`). (Block Type: `set_number`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Main Loop start (Block Type: `loop`)
    - Check condition: `start_condition = 2` (or an infinite loop for continuous operation). (Block Type: `controls_if`)
    - **(Optional/Disabled Logic)** Wait for external start signal (e.g., external IO input `Start_Signal_IN`). (Block Type: `wait_external_io_input`)
    - Call sub-program `BRG_Get_BRG` (Get Bearing). (Block Type: `procedures_callnoreturn`)
    - Call sub-program `Get_BH_InitialPos` (Get Bearing Housing from Initial Position). (Block Type: `procedures_callnoreturn`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Wait for signal that machining center (RMC) is ready (`RMC_Ready_IN`). (Block Type: `wait_external_io_input` or `wait_input`)
    - Call sub-program `RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into RMC). (Block Type: `procedures_callnoreturn`)
    - Wait for RMC machining complete signal (`RMC_Done_IN`). (Block Type: `wait_external_io_input` or `wait_input`)
    - Send signal to notify RMC that part has been taken or is ready to be taken (`RMC_PartTaken_OUT`). (Block Type: `set_external_io_output_upon` or `set_output`)
    - Wait for RMC confirmation signal (`RMC_Confirm_IN`). (Block Type: `wait_external_io_input` or `wait_input`)
    - Call sub-program `RMC_Get_BH_Assembled` (Get Assembled Part from RMC). (Block Type: `procedures_callnoreturn`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Call sub-program `LMC_Put_BH_Temp` (Place Part into LMC for Temporary Storage). (Block Type: `procedures_callnoreturn`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Call sub-program `CNV_Get_PLT` (Get Pallet from Conveyor). (Block Type: `procedures_callnoreturn`)
    - Call sub-program `CNV_Put_PLT` (Place Pallet onto Conveyor). (Block Type: `procedures_callnoreturn`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Call sub-program `LMC_Get_BH_Stored` (Get Stored Part from LMC). (Block Type: `procedures_callnoreturn`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Call sub-program `CNV_Put_BH_On_PLT` (Place Part onto Pallet on Conveyor). (Block Type: `procedures_callnoreturn`)
    - **(Optional/Disabled Logic)** Send task complete signal to external system (`Task_Complete_OUT`). (Block Type: `set_external_io_output_upon` or `set_output`)
    - Return to start of loop (Block Type: `return`)

II. Sub-programs and Their Functional Descriptions

1.  **`BRG_Get_BRG` (Get Bearing)**:

    - Function: The robot retrieves a bearing from a specified initial position (e.g., material rack).
    - Clamp Involved: `BRG&PLT_Clamp` (clamp for operating bearings and pallets).
    - Core Logic:
      - Move to bearing pick-up standby point (e.g., "P21") (Block Type: `moveP`)
      - Move above bearing for pick-up (e.g., "P22") (Block Type: `moveP`)
      - Call sub-program Open_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)
      - Descend to bearing precise grasping point (e.g., "P23") (Block Type: `moveP`)
      - Call sub-program Close_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)
      - Ascend with bearing (e.g., "P25") (Block Type: `moveP`)
      - Move to bearing pick-up departure point (e.g., "P26") (Block Type: `moveP`)
      - Return to bearing pick-up standby point (e.g., "P21") (Block Type: `moveP`)

2.  **`Get_BH_InitialPos` (Get Bearing Housing from Initial Position)**: (Corresponds to `CNV_Get_BH` in flow.xml)

    - Function: The robot retrieves a bearing housing from a specified initial position.
    - Clamp Involved: `BH_Clamp` (clamp for operating bearing housings).
    - Core Logic:
      - Move to bearing housing pick-up standby point (e.g., "P31") (Block Type: `moveP`)
      - Move above bearing housing for pick-up (e.g., "P32") (Block Type: `moveP`)
      - Call sub-program Open_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - Descend to bearing housing precise grasping point (e.g., "P33") (Block Type: `moveP`)
      - Call sub-program Close_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - Ascend with bearing housing (e.g., "P32") (Block Type: `moveP`)
      - Return to bearing housing pick-up standby point (e.g., "P31") (Block Type: `moveP`)

3.  **`RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into Right Machining Center)**:

    - Function: The robot sequentially places the previously retrieved bearing housing and bearing into the designated station of the right machining center (RMC).
    - Clamps Involved: `BH_Clamp`, `BRG&PLT_Clamp`.
    - Core Logic:
      - RMC transition/travel point (e.g., "P20") (Block Type: `moveP`)
      - Move to RMC standby point for BH placement (e.g., "P11") (Block Type: `moveP`)
      - RMC intermediate/transfer point (e.g., "P12") (Block Type: `moveP`)
      - RMC BH interaction/access point (e.g., "P14") (Block Type: `moveP`)
      - RMC BH grasp/release point (e.g., "P15") (Block Type: `moveP`)
      - Call sub-program Open_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - Set speed to 10 (Block Type: `set_speed`)
      - RMC BH interaction/access point (e.g., "P14") (Block Type: `moveP`)
      - Set speed to 100 (Block Type: `set_speed`)
      - Move to RMC standby for BRG placement (e.g., "P13") (Block Type: `moveP`)
      - RMC BRG hover/access point (e.g., "P16") (Block Type: `moveP`)
      - Move to RMC BRG precise placement point (e.g., "P17") (Block Type: `moveP`)
      - Call sub-program Open_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)
      - Set speed to 10 (Block Type: `set_speed`)
      - RMC BRG hover/access point (e.g., "P16") (Block Type: `moveP`)
      - Set speed to 100 (Block Type: `set_speed`)
      - RMC intermediate/transfer point (e.g., "P12") (Block Type: `moveP`)
      - Move to RMC departure/standby point (e.g., "P11") (Block Type: `moveP`)

4.  **`RMC_Get_BH_Assembled` (Get Assembled Part from Right Machining Center)**: (Corresponds to `RMC_Get_BH` in flow.xml)

    - Function: The robot retrieves the assembled (or processed) bearing housing from the right machining center (RMC).
    - Clamp Involved: `BH_Clamp`.
    - Core Logic:
      - Move to RMC standby point for assembled part pick-up (e.g., "P11") (Block Type: `moveP`)
      - RMC intermediate/transfer point (e.g., "P12") (Block Type: `moveP`)
      - RMC BH interaction/access point (e.g., "P14") (Block Type: `moveP`)
      - RMC BH grasp/release point (e.g., "P15") (Block Type: `moveP`)
      - Call sub-program Close_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - RMC BH interaction/access point (e.g., "P14") (Block Type: `moveP`)
      - RMC intermediate/transfer point (e.g., "P12") (Block Type: `moveP`)
      - Move to RMC departure point with part (e.g., "P11") (Block Type: `moveP`)
      - RMC transition/travel point (e.g., "P20") (Block Type: `moveP`)

5.  **`LMC_Put_BH_Temp` (Place Part into Left Machining Center for Temporary Storage)**: (Corresponds to `LMC_Put_BH` in flow.xml)

    - Function: The robot places the part retrieved from RMC into the left machining center (LMC) for temporary storage or subsequent processing.
    - Clamp Involved: `BH_Clamp`.
    - Core Logic:
      - LMC transfer/standby point (e.g., "P41") (Block Type: `moveP`)
      - LMC hover/access point (e.g., "P42") (Block Type: `moveP`)
      - LMC grasp/release point (e.g., "P43") (Block Type: `moveP`)
      - Call sub-program Open_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - LMC hover/access point (e.g., "P42") (Block Type: `moveP`)
      - LMC transfer/standby point (e.g., "P41") (Block Type: `moveP`)
      - Return to main safe/initial point (e.g., "P1") (Block Type: `moveP`)

6.  **`CNV_Get_PLT` (Get Pallet from Conveyor)**:

    - Function: The robot retrieves an empty pallet from a specified location (possibly another area of the conveyor).
    - Clamp Involved: `BRG&PLT_Clamp`.
    - Core Logic:
      - Pallet handling standby point (e.g., "P34") (Block Type: `moveP`)
      - Pallet pickup hover/ascent point (e.g., "P35") (Block Type: `moveP`)
      - Set speed to 10 (Block Type: `set_speed`)
      - Descend to pallet precise grasping point (e.g., "P36") (Block Type: `moveP`)
      - Call sub-program Close_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)
      - Pallet pickup hover/ascent point (e.g., "P35") (Block Type: `moveP`)
      - Set speed to 100 (Block Type: `set_speed`)
      - Pallet handling standby point (e.g., "P34") (Block Type: `moveP`)

7.  **`CNV_Put_PLT` (Place Pallet onto Conveyor)**:

    - Function: The robot places the retrieved empty pallet onto the designated station of the conveyor.
    - Clamp Involved: `BRG&PLT_Clamp`.
    - Core Logic:
      - CNV pallet placement hover/ascent point (e.g., "P37") (Block Type: `moveP`)
      - Move to pallet precise placement point on conveyor (e.g., "P38") (Block Type: `moveP`)
      - Call sub-program Open_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)
      - CNV pallet placement hover/ascent point (e.g., "P37") (Block Type: `moveP`)
      - Pallet handling standby point (e.g., "P34") (Block Type: `moveP`)

8.  **`LMC_Get_BH_Stored` (Get Stored Part from Left Machining Center)**: (Corresponds to `LMC_Get_BH` in flow.xml)

    - Function: The robot retrieves the previously stored part from the left machining center (LMC).
    - Clamp Involved: `BH_Clamp`.
    - Core Logic:
      - LMC transfer/standby point (e.g., "P41") (Block Type: `moveP`)
      - LMC hover/access point (e.g., "P42") (Block Type: `moveP`)
      - LMC grasp/release point (e.g., "P43") (Block Type: `moveP`)
      - Call sub-program Close_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - LMC hover/access point (e.g., "P42") (Block Type: `moveP`)
      - LMC transfer/standby point (e.g., "P41") (Block Type: `moveP`)

9.  **`CNV_Put_BH_On_PLT` (Place Part onto Pallet on Conveyor)**: (Corresponds to `CNV_Put_BH` in flow.xml)

    - Function: The robot accurately places the part retrieved from LMC into the pre-placed pallet on the conveyor.
    - Clamp Involved: `BH_Clamp`.
    - Core Logic:
      - CNV part-on-pallet hover/ascent point (e.g., "P39") (Block Type: `moveP`)
      - Move to precise part placement point on pallet (e.g., "P40") (Block Type: `moveP`)
      - Call sub-program Open_BH_Clamp (Block Type: `procedures_callnoreturn`)
      - CNV part-on-pallet hover/ascent point (e.g., "P39") (Block Type: `moveP`)
      - Return to main safe/initial point (e.g., "P1") (Block Type: `moveP`)
      - Return from sub-program (Block Type: `return`)

10. **`Open_BH_Clamp` (Open Bearing Housing Clamp)**:

    - Function: Controls the robot end-effector to open the clamp used for holding the bearing housing.
    - Core Logic:
      - Wait for a predefined delay for clamp operation (e.g., timer "N483") (Block Type: `wait_timer`)
      - Send signal to open bearing housing clamp (e.g., set output pin 1 to on) (Block Type: `set_output`)
      - Wait for feedback confirming bearing housing clamp is open (e.g., wait for input pin 0 to be on) (Block Type: `wait_input`)

11. **`Close_BH_Clamp` (Close Bearing Housing Clamp)**:

    - Function: Controls the robot end-effector to close the clamp used for holding the bearing housing.
    - Core Logic:
      - Wait for a predefined delay for clamp operation (e.g., timer "N482") (Block Type: `wait_timer`)
      - Send signal to close bearing housing clamp (e.g., set output pin 1 to off) (Block Type: `set_output`)
      - Wait for feedback confirming bearing housing clamp is closed (e.g., wait for input pin 1 to be on) (Block Type: `wait_input`)

12. **`Open_BRG&PLT_Clamp` (Open Bearing/Pallet Clamp)**:

    - Function: Controls the robot end-effector to open the clamp used for holding bearings or pallets.
    - Core Logic:
      - Wait for a predefined delay for clamp operation (e.g., timer "N482") (Block Type: `wait_timer`)
      - Send signal to open bearing/pallet clamp (e.g., set output pin 2 to on) (Block Type: `set_output`)
      - Wait for feedback confirming bearing/pallet clamp is open (e.g., wait for input pin 2 to be on) (Block Type: `wait_input`)

13. **`Close_BRG&PLT_Clamp` (Close Bearing/Pallet Clamp)**:
    - Function: Controls the robot end-effector to close the clamp used for holding bearings or pallets.
    - Core Logic:
      - Wait for a predefined delay for clamp operation (e.g., timer "N482") (Block Type: `wait_timer`)
      - Send signal to close bearing/pallet clamp (e.g., set output pin 2 to off) (Block Type: `set_output`)
      - Wait for feedback confirming bearing/pallet clamp is closed (e.g., wait for input pin 3 to be on) (Block Type: `wait_input`)

III. Modularization and Reuse Explanation

- **Clamp Operations**: `Open/Close_BH_Clamp` and `Open/Close_BRG&PLT_Clamp` are designed as independent, reusable sub-programs. They encapsulate the specific control logic for each clamp type and are called by various material handling sub-programs (`BRG_Get_BRG`, `Get_BH_InitialPos`, `RMC_Put_BH&BRG`, etc.). This promotes consistency and simplifies maintenance.
- **Standard Movement Sequences**: Most pick and place sub-programs (`BRG_Get_BRG`, `Get_BH_InitialPos`, `CNV_Get_PLT`, etc.) follow a common "approach target -> precise positioning -> execute action (grasp/release) -> depart target -> return to safe position" movement pattern. This logic can be abstracted and reused, potentially through parameterized functions for different target locations.
- **Speed Control**: For operations requiring high precision or delicate handling (e.g., `RMC_Put_BH&BRG`, `CNV_Get_PLT`), the core logic explicitly mentions the need for reduced speed during critical phases. This can be implemented via a parameter or a dedicated low-speed movement function.
- **External Interaction and Synchronization**: The main process incorporates multiple points for synchronization with external devices (RMC, LMC, conveyor). This is achieved by waiting for specific input signals (`RMC_Ready_IN`, `RMC_Done_IN`) and sending output signals (`RMC_PartTaken_OUT`, `Task_Complete_OUT`). This modular approach ensures robust interaction with the surrounding environment.
- **Optional Logic**: Features like waiting for an external start signal or sending a task complete signal are marked as optional. This allows for flexible deployment, where these features can be enabled or disabled based on the specific system integration requirements without altering the core process flow.
