# Robot Process Generation Prompt - Stage 1: User Input to Detailed Process Description

## Objective

This Prompt aims to guide you in generating a detailed process plan based on the robot task description provided by the user (usually in natural language Markdown format). This plan should include clear descriptions of a main process and multiple sub-processes, along with textual explanations of their respective process steps and core logic. The goal is to produce a structured, easy-to-understand blueprint for robot task execution, serving as a basis for user review and subsequent refinement steps.

## Input Materials

1.  **Robot Task Description (.md or text)**: Contains natural language descriptions of the overall task the robot is expected to complete, sub-tasks, and objects of operation.

## Generation Guidelines and Requirements

Please follow these guidelines to generate a detailed process description based on the provided task description:

### 1. Sub-program/Function Design and Definition (Logical Level)

- **Identify Core Functional Modules**: Extract key operations and logical units from the task description to brainstorm sub-program candidates.
- **Design Sub-program Names and Abbreviations**: Pay special attention to abbreviations in sub-program names (e.g., `BRG`, `PLT`, `CNV`, `RMC`, `LMC`, `BH`, `Crump`), ensuring they are concise and reflect functionality. Sub-program names should clearly express their purpose.
- **Clarify Sub-program Functions**: Describe in detail the specific tasks each sub-program should perform, the objects of operation, and the expected results. For example: get, put, bearing, pallet, conveyor, machining unit, clamp operation, etc.
- **Clarify Action Types**: Clearly distinguish common actions like `Get` (retrieve/pick) and `Put` (place/put down) in sub-program descriptions.
- **Design Paired Operations**: Pay attention to designing logically paired sub-programs, such as `Open_..._Clamp` and `Close_..._Clamp`, and clarify their functions.

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
- **Define End and Return Logic**: Clearly define the method and conditions for ending the main program and each sub-program.

In summary, you need to transform the user's natural language task description into a detailed, structured document that clearly defines the responsibilities, core step logic, and collaborative relationships of the main process and each sub-process. This description will serve as a visual plan for user confirmation and modification.

## Example Fewshot

### Example Task Input (Original User Description)

[Robot Task Description: This automated process aims to collaboratively complete an assembly and handling task involving bearings (BRG), bearing housings (BH), and pallets (PLT). The robot first retrieves a bearing and a bearing housing from a material rack or initial position. Subsequently, these two parts are placed sequentially into the right machining center (RMC), presumably for press-fitting or assembly operations. After assembly, the robot takes the assembled part from the RMC and transfers it to the left machining center (LMC) for temporary storage or subsequent processing. Next, the robot retrieves an empty pallet and places it at a designated station on the conveyor (CNV). Finally, the robot retrieves the previously stored assembled part from the LMC and places it accurately onto the pallet on the conveyor, completing the entire cycle.]

### Example Output (Detailed Process Description Plan)

#### I. Sub-programs and Their Functional Descriptions

1.  **`BRG_Get_BRG` (Get Bearing)**:

    - Function: The robot retrieves a bearing from a specified location (e.g., material rack).
    - Core Logic: Move to bearing standby point -> Move above bearing -> Open bearing clamp -> Descend to bearing precise grasping point -> Close bearing clamp -> Ascend -> Move to departure point -> Return to safe/initial point.
    - Clamp Involved: `BRG&PLT_Crump` (clamp for operating bearings and pallets).

2.  **`CNV_Get_BH` (Get Bearing Housing from Conveyor)**:

    - Function: The robot retrieves a bearing housing from a specified location on the conveyor.
    - Core Logic: Move to bearing housing standby point near conveyor -> Move above bearing housing -> Open bearing housing clamp -> Descend to bearing housing precise grasping point -> Close bearing housing clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BH_Crump` (clamp for operating bearing housings).

3.  **`RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into Right Machining Center)**:

    - Function: The robot sequentially places the previously retrieved bearing housing and bearing into the designated station of the right machining center (RMC).
    - Core Logic:
      - Move to RMC standby point.
      - Place Bearing Housing: Move above RMC bearing housing placement point -> Precisely move to placement point -> Open bearing housing clamp -> Ascend.
      - Place Bearing: Move above RMC bearing placement point -> Precisely move to placement point -> Open bearing clamp -> Ascend.
      - Move to RMC departure point.
    - Clamps Involved: `BH_Crump`, `BRG&PLT_Crump`.
    - Note: Speed may need to be reduced during placement to ensure accuracy.

4.  **`RMC_Get_BH` (Get Assembled Part from Right Machining Center)**:

    - Function: The robot retrieves the assembled (or processed) bearing housing from the right machining center (RMC) (at this point, it may already be assembled with the bearing).
    - Core Logic: Move to RMC standby point -> Move above assembled part -> Open bearing housing clamp (if previously open, this step is to prepare for grasping) -> Descend to precise grasping point -> Close bearing housing clamp -> Ascend -> Move to departure point.
    - Clamp Involved: `BH_Crump`.

5.  **`LMC_Put_BH` (Place Part into Left Machining Center)**:

    - Function: The robot places the part retrieved from RMC into the left machining center (LMC) for temporary storage or subsequent processing.
    - Core Logic: Move to LMC standby point -> Move above LMC placement point -> Precisely move to placement point -> Open bearing housing clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BH_Crump`.

6.  **`CNV_Get_PLT` (Get Pallet from Conveyor)**:

    - Function: The robot retrieves an empty pallet from a specified location (possibly another area of the conveyor).
    - Core Logic: Move to pallet standby point -> Move above pallet -> (Possibly low speed) Precisely move to grasping point -> Close pallet clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BRG&PLT_Crump`.

7.  **`CNV_Put_PLT` (Place Pallet onto Conveyor)**:

    - Function: The robot places the retrieved empty pallet onto the designated station of the conveyor.
    - Core Logic: Move above conveyor pallet placement point -> Precisely move to placement point -> Open pallet clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BRG&PLT_Crump`.

8.  **`LMC_Get_BH` (Get Part from Left Machining Center)**:

    - Function: The robot retrieves the previously stored part from the left machining center (LMC).
    - Core Logic: Move to LMC standby point -> Move above part -> Precisely move to grasping point -> Close bearing housing clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BH_Crump`.

9.  **`CNV_Put_BH` (Place Part onto Pallet on Conveyor)**:

    - Function: The robot accurately places the part retrieved from LMC into the pre-placed pallet on the conveyor.
    - Core Logic: Move above conveyor pallet (with loaded part) -> Precisely move to designated placement point within pallet -> Open bearing housing clamp -> Ascend -> Return to safe/initial point.
    - Clamp Involved: `BH_Crump`.

10. **`Open_BH_Crump` (Open Bearing Housing Clamp)**:

    - Function: Controls the robot end-effector to open the clamp used for holding the bearing housing.
    - Core Logic: Send open signal, wait for clamp in-position feedback.

11. **`Close_BH_Crump` (Close Bearing Housing Clamp)**:

    - Function: Controls the robot end-effector to close the clamp used for holding the bearing housing.
    - Core Logic: Send close signal, wait for clamp in-position feedback.

12. **`Open_BRG&PLT_Crump` (Open Bearing/Pallet Clamp)**:

    - Function: Controls the robot end-effector to open the clamp used for holding bearings or pallets.
    - Core Logic: Send open signal, wait for clamp in-position feedback.

13. **`Close_BRG&PLT_Crump` (Close Bearing/Pallet Clamp)**:
    - Function: Controls the robot end-effector to close the clamp used for holding bearings or pallets.
    - Core Logic: Send close signal, wait for clamp in-position feedback.

#### II. Main Program Process Description

Select robot model (e.g., "dobot*mg400").
Start robot motors.
Initialize necessary process control variables (e.g., `N5 = 2`, used for conditional judgment in the example).
Main loop starts.
Loop condition: May be based on a specific condition or an infinite loop (in this example, executes the core process once based on `N5 == 2`).
Robot moves to **initial/safe point (e.g., "P1")**.
*(Optional/Disabled Logic)_ Wait for external start signal (e.g., external IO input).
Call sub-program `BRG_Get_BRG` (Get Bearing).
_(Optional/Disabled Logic)_ Wait for material in-position or station clear signal.
Call sub-program `CNV_Get_BH` (Get Bearing Housing from Conveyor).
Robot moves to **initial/safe point (e.g., "P1")**.
Wait for signal that machining center (RMC) is ready.
Call sub-program `RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into RMC).
Wait for RMC machining complete signal.
Send signal to notify RMC that part has been taken or is ready to be taken.
Wait for RMC confirmation signal.
Call sub-program `RMC_Get_BH` (Get Assembled Part from RMC).
Robot moves to **initial/safe point (e.g., "P1")**.
Call sub-program `LMC_Put_BH` (Place Part into LMC).
Robot moves to **initial/safe point (e.g., "P1")**.
Call sub-program `CNV_Get_PLT` (Get Pallet from Conveyor).
Call sub-program `CNV_Put_PLT` (Place Pallet onto Conveyor).
Robot moves to **initial/safe point (e.g., "P1")**.
Call sub-program `LMC_Get_BH` (Get Part from LMC).
Robot moves to **initial/safe point (e.g., "P1")**.
Call sub-program `CNV_Put_BH` (Place Part onto Pallet on Conveyor).
_(Optional/Disabled Logic)\_ Send task complete signal to external system.
Main loop ends.

#### III. Modularization and Reuse Explanation

- **Clamp Operations**: `Open/Close_BH_Crump` and `Open/Close_BRG&PLT_Crump` are standard clamp control sub-programs that will be called in various material pick and place sub-programs.
- **Movement Sequences**: Most pick/place sub-programs follow the "standby point -> approach point -> precise point -> (execute action) -> lift point -> departure point -> safe point" movement logic.
- **Speed Control**: In precise operations like `RMC_Put_BH&BRG`, `CNV_Get_PLT`, the description should mention planning for a low-speed movement phase.
- **External Interaction**: The main process plans for multiple signal interaction points with external devices (RMC, LMC, conveyor sensors) for process synchronization. Interactions that are uncertain or can be disabled during debugging are marked as optional/disabled.
