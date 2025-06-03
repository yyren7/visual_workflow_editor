# /workspace/backend/tests/run_robot_flow_agent.py

import logging
import json
import os
import asyncio
from datetime import datetime # Added datetime
from typing import Optional

from dotenv import load_dotenv # Import dotenv
load_dotenv() # Load environment variables from .env file at the start

# Import DeepSeek LLM client
from langchain_deepseek import ChatDeepSeek
# Import Google Gemini LLM client
from langchain_google_genai import ChatGoogleGenerativeAI
# Import message types
from langchain_core.messages import HumanMessage, AIMessageChunk # Added AIMessageChunk

from backend.langgraphchat.graph.nodes.robot_flow_planner.graph_builder import create_robot_flow_graph 
from backend.langgraphchat.graph.nodes.robot_flow_planner.state import RobotFlowAgentState # Import the state model

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Helper function to save content to a file
def save_to_md(filepath: str, content: str, title: Optional[str] = None):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            if title:
                f.write(f"# {title}\n\n")
            f.write(content)
        logging.info(f"Saved content to {filepath}")
    except Exception as e:
        logging.error(f"Failed to save to {filepath}: {e}")

async def main():
    # Determine active LLM provider
    active_llm_provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower() # Default to deepseek
    active_llm_provider = "gemini"
    llm = None
    if active_llm_provider == "gemini":
        google_api_key = os.getenv("GOOGLE_API_KEY")
        gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20") # Default Gemini model

        if not google_api_key:
            logging.error("CRITICAL: GOOGLE_API_KEY not found in environment variables for Gemini.")
            logging.error("Exiting application. LLM calls will fail without a valid API key.")
            return
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-preview-05-20",
                google_api_key=google_api_key,
                temperature=0,
                # convert_system_message_to_human=True # Depending on Langchain version and specific needs
            )
            logging.info(f"Successfully instantiated ChatGoogleGenerativeAI with model '{gemini_model_name}'.")
        except Exception as e:
            logging.error(f"Failed to instantiate ChatGoogleGenerativeAI: {e}", exc_info=True)
            logging.error("Please ensure 'langchain-google-genai' is installed and GOOGLE_API_KEY is correctly set.")
            return

    elif active_llm_provider == "deepseek":
        # Configure DeepSeek LLM using environment variables loaded from .env
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com") # Default if not in .env
        deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat") # Default if not in .env

        if not deepseek_api_key:
            logging.error("CRITICAL: DEEPSEEK_API_KEY not found in environment variables (expected from .env file or set manually).")
            logging.error("Exiting application. LLM calls will fail without a valid API key.")
            return

        try:
            llm = ChatDeepSeek(
                model=deepseek_model,
                api_key=deepseek_api_key,
                base_url=deepseek_base_url, # Pass base_url if your .env has it
                temperature=0,
                streaming=True # Enable streaming
            )
            logging.info(f"Successfully instantiated ChatDeepSeek with model '{deepseek_model}' and base URL '{deepseek_base_url}'.")
        except Exception as e:
            logging.error(f"Failed to instantiate ChatDeepSeek: {e}", exc_info=True)
            logging.error("Please ensure 'langchain-deepseek' is installed and DEEPSEEK_API_KEY (and optionally DEEPSEEK_BASE_URL, DEEPSEEK_MODEL) are correctly set in .env.")
            return
    else:
        logging.error(f"CRITICAL: Unsupported ACTIVE_LLM_PROVIDER: '{active_llm_provider}'. Supported values are 'gemini' or 'deepseek'.")
        logging.error("Exiting application.")
        return
    
    if llm is None: # Should not happen if logic above is correct, but as a safeguard
        logging.error("CRITICAL: LLM could not be initialized. Please check provider configuration and API keys.")
        return

    # Create the graph
    robot_flow_app = create_robot_flow_graph(llm=llm)

    # Create a unique directory for this session based on the current time
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_log_dir = "/workspace/database/test_database/test_robot_flow"
    session_log_dir = os.path.join(base_log_dir, session_timestamp)
    try:
        os.makedirs(session_log_dir, exist_ok=True)
        logging.info(f"Session logs will be saved in: {session_log_dir}")
    except Exception as e:
        logging.error(f"Could not create session log directory {session_log_dir}: {e}")
        # Optionally, decide if you want to proceed without saving logs or exit
        # For now, we'll proceed but log saving might fail

    # Initial user request that might require clarification
    initial_user_input_simple = "mg400に点b、c、aの順で運動させ、その後、点a、b、cの順で循環運動させてください。"
    initial_user_input = """We need to generate a task flow for a robot or automation system. This flow is primarily implemented using specific Blockly XML block types, covering the following aspects:

Initialization and Event Handling:
Use the `start_thread` block to initiate a parallel thread (typically, the condition is set to always true, e.g., using a `logic_boolean` block set to TRUE).
Within the `DO` statement of this thread, first use the `connect_external_io` block to connect to an external I/O device named "DIO000" (e.g., io_no: 1).
Next, use multiple `create_event` blocks to define event-driven logic:

- For external output control (e.g., controlling the on/off state of pins 13, 14): Within the `EVENT` statement of the `create_event` block, use the `set_external_io_output_upon` block. Its condition is typically provided by a `logic_custom_flag` block (e.g., F481, F482), specifying `io_no`, `output_pin_name`, `out_state`, and `trigger_condition`.
- For robot stop: Within the `EVENT` statement of the `create_event` block, use the `stop_robot_upon` block. Its condition can be formed by a `logic_compare` block (comparing the state of a pin read by `external_io` with a `logic_boolean` value).

Subroutine Definition:
Use the `procedures_defnoreturn` block to define a series of reusable subroutines (e.g., specifying the name via the `NAME` field). The `STACK` statement within the subroutine contains a series of operation blocks:

- `BRG_Get_BRG`: Get bearing from the bearing supply. May internally contain multiple `moveP` blocks for robot movement, and call gripper control subroutines via `procedures_callnoreturn`.
- `CNV_Get_BH`: Get bushing from the conveyor belt. Similarly, includes `moveP` movements and gripper operation calls.
- `Open_BH_Crump` / `Close_BH_Crump`: Open/close bushing gripper. Such subroutines typically use the robot's own I/O for control, for example, by using the `set_output` block (specifying `output_pin_name` and `out_state`) to operate the gripper, in conjunction with the `wait_input` block to wait for gripper sensor signals, and may also use the `wait_timer` block for delays. **Note: `set_output` should be used to operate robot I/O, not `set_external_io_output_during` or `set_external_io_output_upon`.**
- `Open_BRG&PLT_Crump` / `Close_BRG&PLT_Crump`: Open/close bearing and pallet gripper. Implementation is similar to the bushing gripper, using `set_output`, `wait_input`, `wait_timer`.
- `RMC_Put_BH&BRG`: Place bushing and bearing onto the rotary machining center. Includes `moveP` movements and gripper operation calls.
- `RMC_Get_BH`: Get bushing from the rotary machining center. Includes `moveP` movements and gripper operation calls.
- `LMC_Put_BH`: Place bushing onto the linear machining center. Includes `moveP` movements and gripper operation calls.
- `CNV_Get_PLT`: Get pallet from the conveyor belt. Includes `moveP` movements and gripper operation calls.
- `CNV_Put_PLT`: Place pallet onto the conveyor belt. Includes `moveP` movements and gripper operation calls.
- `LMC_Get_BH`: Get bushing from the linear machining center. Includes `moveP` movements and gripper operation calls.
- `CNV_Put_BH`: Place bushing onto the conveyor belt. Includes `moveP` movements and gripper operation calls.

Main Control Flow:
First, use the `select_robot` block to select the robot named "fairino_FR".
Then, use the `set_motor` block to set the servo motor state to "on".
Use the `set_number` block (in conjunction with a `math_number` block to provide the value) to set the initial value of variable N5 to 2.
Use the `loop` block to construct the main loop. Within the `DO` statement of the loop:

- The `controls_if` block can be used for conditional judgment, with conditions potentially formed by `logic_compare` (e.g., comparing a `math_custom_number` type variable N5 with a `math_number` constant).
- Robot Movement: The `moveP` block must be used (not `moveL`) for point-to-point movement to preset positions (P1, P11-P17, P20-P26, P31-P43, etc.), ensuring all necessary motion control parameters (such as `point_name_list`, `control_x`, etc.) are provided.
- Call Subroutine: Use the `procedures_callnoreturn` block to call defined subroutines to complete tasks such as pick and place operations.
- Wait Conditions:
  - Use the `wait_external_io_input` block to wait for external I/O signals.
  - Use the `wait_input` block to wait for robot I/O signals.
  - Use the `wait_block` block (whose condition is typically formed by logic blocks like `logic_operation` or `logic_compare`) to wait for internal conditions to be met.
- Robot Gripper Control: Use the `set_output` block (specifying `output_pin_name` and `out_state`) to control the opening and closing of the robot gripper.
- Speed Setting: The `set_speed` block can be used to set the robot's operating speed.
  This flow involves transporting bearings (BRG), bushings (BH), and pallets (PLT) between different workstations (such as bearing supply, conveyor belt, Rotary Machining Center RMC, Linear Machining Center LMC) using `moveP`.
  The continuation of the loop is managed by the `loop` block itself. The end of a subroutine or a specific logic segment might use a `return` block (e.g., at the end of the `CNV_Put_BH` subroutine, returning to the main flow or the calling loop level).

In summary, this file describes a complex automated assembly or material handling task where the robot, through precise `moveP` movements and I/O control based on specific Blockly blocks (such as `set_output`, `wait_input`, `set_external_io_output_upon`, etc.), coordinates a series of pick-and-place operations between multiple workstations."""
    # initial_user_input = "机器人: mg400\n工作流程：\n1. 打开夹爪.\n2. 移动到 P10 点 (快速模式).\n3. 关闭夹爪.\n4. 移动到 P20 点 (慢速精定位模式)." # For testing direct processing

    # Initialize current_state as a RobotFlowAgentState Pydantic model instance
    current_state = RobotFlowAgentState(
        messages=[],
        user_input=initial_user_input,
        config={
            "OUTPUT_DIR_PATH": session_log_dir,
            "NODE_TEMPLATE_DIR_PATH": "/workspace/database/node_database/quick-fcpr-new",
        },
        # Initialize other fields as per RobotFlowAgentState definition or let them use defaults
        robot_model=None,
        raw_user_request=initial_user_input, # Set raw_user_request initially
        dialog_state="initial", 
        clarification_question=None,
        enriched_structured_text=None,
        parsed_flow_steps=None,
        parsed_robot_name=None,
        is_error=False,
        error_message=None,
        current_step_description=None
        # Add other fields from RobotFlowAgentState if they need non-default initial values
    )

    logging.info(f"Starting interactive agent. Initial request: '{initial_user_input}'")
    save_to_md(os.path.join(session_log_dir, "turn_00_initial_request.md"), initial_user_input, "Initial User Request")

    max_turns = 10 # Limit interactions to prevent infinite loops
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        logging.info(f"\n--- Agent Turn {turn_count} ---")
        current_user_input_for_log = current_state.user_input # Access attribute directly
        # logging.info(f"Invoking graph with current state (user_input: '{current_user_input_for_log}', dialog_state: '{current_state.dialog_state}')") # Old log
        
        # Save user input for this turn (if not the initial one, which is saved before loop)
        if turn_count > 1 or (turn_count == 1 and current_user_input_for_log != initial_user_input): # handle cases where initial input might be directly processed or re-fed
             save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_user_input.md"), str(current_user_input_for_log), f"Turn {turn_count} User Input")

        try:
            final_state_output_dict = None
            logging.info(f"Invoking graph with current state (user_input: '{current_user_input_for_log[:100]}...', dialog_state: '{current_state.dialog_state}') using astream_events")

            async for event in robot_flow_app.astream_events(current_state, {"recursion_limit": 20}, version="v2"):
                event_type = event["event"]
                
                if event_type == "on_chain_stream":
                    # This event contains chunks from streaming runnables within the subgraph.
                    # The chunk is in event["data"]["chunk"].
                    # Based on robot_flow_invoker_node.py, this chunk is expected to be a dict like:
                    # {"node_name_in_subgraph": {"messages": [AIMessageChunk(...)]}}
                    chunk_from_event_data = event.get("data", {}).get("chunk")
                    if isinstance(chunk_from_event_data, dict):
                        for internal_node_name, internal_node_output_dict in chunk_from_event_data.items():
                            if isinstance(internal_node_output_dict, dict) and "messages" in internal_node_output_dict:
                                messages_in_chunk = internal_node_output_dict["messages"]
                                if messages_in_chunk and isinstance(messages_in_chunk[-1], AIMessageChunk):
                                    logging.info(f"Streaming AIMessageChunk from internal node '{internal_node_name}': {messages_in_chunk[-1].content[:100]}...")
                                    # Test script logs the chunk; invoker_node would yield it.
            
                elif event_type == "on_chain_end" and event.get("name") == "LangGraph": 
                    # This event signifies the end of the graph's execution.
                    # The final output of the graph is in event["data"]["output"].
                    if isinstance(event.get("data"), dict) and "output" in event["data"]:
                        final_state_output_dict = event["data"]["output"]
                        logging.info(f"Subgraph astream_events ended. Final state output captured from 'LangGraph' event.")
                    else:
                        logging.warning(f"Subgraph astream_events 'LangGraph' ended but final output format is unexpected or missing: {event.get('data')}")
                    break # Crucial: Exit the event loop once the graph execution is complete.

            if final_state_output_dict is None:
                logging.error("Graph astream_events completed, but final_state_output_dict was not captured.")
                # Set error state or raise an exception
                current_state.is_error = True
                current_state.error_message = "Failed to capture final state from robot_flow_subgraph astream_events."
                # Break from the while loop for turns if this happens
                save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_system_error.md"), "Failed to capture final state from astream_events.", f"Turn {turn_count} System Error")
                break 
            
            # Process the final state output to update current_state
            if isinstance(final_state_output_dict, dict):
                current_state = RobotFlowAgentState(**final_state_output_dict)
            elif isinstance(final_state_output_dict, RobotFlowAgentState): # Should be dict from astream_events 'output'
                current_state = final_state_output_dict 
            else:
                logging.warning(f"Unexpected type for final_state_output_dict: {type(final_state_output_dict)}. Attempting to process as dict.")
                try:
                    current_state = RobotFlowAgentState(**final_state_output_dict) # This might fail if not a dict
                except Exception as e_conv:
                    logging.error(f"Could not convert final_state_output_dict to RobotFlowAgentState: {e_conv}", exc_info=True)
                    current_state.is_error = True
                    current_state.error_message = f"Failed to convert final state from astream_events: {e_conv}"
                    save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_system_error.md"), f"Failed to convert final state: {e_conv}", f"Turn {turn_count} System Error")
                    break # Break from the while loop for turns

            logging.info(f"Graph turn completed via astream_events. Dialog state: {current_state.dialog_state}")

            assistant_response_for_log = ""
            if current_state.clarification_question:
                assistant_response_for_log = current_state.clarification_question
            elif current_state.messages and isinstance(current_state.messages, list) and len(current_state.messages) > 0:
                last_message = current_state.messages[-1]
                if hasattr(last_message, 'type') and getattr(last_message, 'type') == 'ai':
                    assistant_response_for_log = str(getattr(last_message, 'content', ""))
            
            if assistant_response_for_log:
                save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_assistant_output.md"), assistant_response_for_log, f"Turn {turn_count} Assistant Output")
            elif current_state.is_error:
                 error_log_content = f"Error: {current_state.error_message}\nDialog State: {current_state.dialog_state}"
                 save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_assistant_error.md"), error_log_content, f"Turn {turn_count} Assistant Error")
            elif current_state.dialog_state == 'input_understood' or current_state.dialog_state == 'flow_completed':
                 final_summary = f"Flow state: {current_state.dialog_state}.\n"
                 if current_state.parsed_flow_steps:
                     final_summary += f"Parsed flow steps: {json.dumps(current_state.parsed_flow_steps, indent=2, ensure_ascii=False)}" # parsed_flow_steps is List[Dict]
                 elif current_state.final_flow_xml_path:
                     final_summary += f"Final flow XML path: {current_state.final_flow_xml_path}"
                 save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_assistant_final_summary.md"), final_summary, f"Turn {turn_count} Assistant Final Summary")

            if current_state.is_error:
                logging.error(f"Flow encountered an error: {current_state.error_message}")
                break

            if current_state.clarification_question:
                logging.info(f"Agent asks: {current_state.clarification_question}")
                try:
                    user_response = await asyncio.to_thread(input, "Your response: ")
                except RuntimeError: 
                    print("Your response (fallback input): ", end="")
                    user_response = input()

                current_state.user_input = user_response
                # Add the user's new response as a HumanMessage to the messages list
                from langchain_core.messages import HumanMessage # Ensure import
                if not current_state.messages: current_state.messages = [] # Initialize if None for safety
                current_state.messages.append(HumanMessage(content=user_response))
                
                logging.info(f"Received user response: '{user_response}', added to messages.")
                current_state.clarification_question = None # Clear the question as it's (presumably) answered
                continue 
            
            if current_state.dialog_state in ['input_understood', 'flow_completed', 'final_xml_generated_success']: # Added final_xml_generated_success
                logging.info(f"Agent has reached a terminal state: {current_state.dialog_state}.")
                break 
            
            unhandled_states_for_continuation = ['initial', 'awaiting_robot_model', 'awaiting_enrichment_confirmation', 'processing_enriched_input'] 
            if current_state.dialog_state not in unhandled_states_for_continuation:
                logging.warning(f"Exiting loop due to unhandled dialog state for continuation: {current_state.dialog_state}")
                break

        except Exception as e:
            logging.error(f"An error occurred during graph execution: {e}", exc_info=True)
            # Import traceback if not already done at the top for this specific usage
            import traceback
            save_to_md(os.path.join(session_log_dir, f"turn_{turn_count:02d}_execution_error.md"), f"Error: {e}\nTraceback: {traceback.format_exc()}", f"Turn {turn_count} Execution Error")
            break
        
    if turn_count >= max_turns:
        logging.warning(f"Max interaction turns ({max_turns}) reached.")

    logging.info(f"\n--- Final Agent State After Interaction ---")
    # current_state is a RobotFlowAgentState Pydantic model instance here
    # Use model_dump() for proper serialization of Pydantic models to dict for JSON
    try:
        final_state_dict_for_json = current_state.model_dump(exclude_none=True) # Removed mode='json' as it might not be standard/needed if output is dict
        # json.dumps is still needed if model_dump(mode='json') returns a string already, 
        # but typically it returns a dict for mode='python' (default) or 'json' (which aims for json-compatible dict)
        # If model_dump(mode='json') itself produces the final JSON string, then logging.info(final_state_dict_for_json) would be enough.
        # However, the standard pattern is model_dump -> dict, then json.dumps(dict)
        final_state_str = json.dumps(final_state_dict_for_json, indent=2, ensure_ascii=False) # No change here if final_state_dict_for_json is already dict
        logging.info(final_state_str)
        save_to_md(os.path.join(session_log_dir, "final_agent_state.md"), f"```json\n{final_state_str}\n```", "Final Agent State")
    except Exception as e:
        logging.error(f"Error serializing final agent state: {e}", exc_info=True)
        # Fallback: try to log current_state directly if model_dump fails, though it might be partial
        logging.info(f"Fallback raw current_state: {current_state}")

if __name__ == '__main__':
    import traceback # Import traceback for the new error logging
    asyncio.run(main()) 