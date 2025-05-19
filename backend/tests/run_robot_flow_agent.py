# /workspace/backend/tests/run_robot_flow_agent.py

import logging
import json
import os
import asyncio

from dotenv import load_dotenv # Import dotenv
load_dotenv() # Load environment variables from .env file at the start

# Import DeepSeek LLM client
from langchain_deepseek import ChatDeepSeek 

from backend.langgraphchat.graph.nodes.robot_flow_planner.graph_builder import create_robot_flow_graph 
from backend.langgraphchat.graph.nodes.robot_flow_planner.state import RobotFlowAgentState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
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
            temperature=0
        )
        logging.info(f"Successfully instantiated ChatDeepSeek with model '{deepseek_model}' and base URL '{deepseek_base_url}'.")
    except Exception as e:
        logging.error(f"Failed to instantiate ChatDeepSeek: {e}", exc_info=True)
        logging.error("Please ensure 'langchain-deepseek' is installed and DEEPSEEK_API_KEY (and optionally DEEPSEEK_BASE_URL, DEEPSEEK_MODEL) are correctly set in .env.")
        return

    # Create the graph
    robot_flow_app = create_robot_flow_graph(llm=llm)

    # Initial user request that might require clarification
    initial_user_input = "让机器人以 点231231 的顺序循环。" 
    # initial_user_input = "机器人: mg400\n工作流程：\n1. 打开夹爪.\n2. 移动到 P10 点 (快速模式).\n3. 关闭夹爪.\n4. 移动到 P20 点 (慢速精定位模式)." # For testing direct processing

    current_state: RobotFlowAgentState = {
        "messages": [],
        "user_input": initial_user_input,
        "config": {
            "OUTPUT_DIR_PATH": "/workspace/test_robot_flow_output_deepseek_interactive",
        },
        # Explicitly initialize other relevant state fields for the first call
        "robot_model": None,
        "raw_user_request": None,
        "dialog_state": "initial", # Start with initial dialog state
        "clarification_question": None,
        "enriched_structured_text": None,
        "parsed_flow_steps": None,
        "parsed_robot_name": None,
        "is_error": False,
        "error_message": None,
        "current_step_description": None
    }

    logging.info(f"Starting interactive agent. Initial request: '{initial_user_input}'")

    max_turns = 5 # Limit interactions to prevent infinite loops
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        logging.info(f"\n--- Agent Turn {turn_count} ---")
        logging.info(f"Invoking graph with current state (user_input: '{current_state.get('user_input')}', dialog_state: '{current_state.get('dialog_state')}')")
        
        try:
            # Ensure recursion_limit is high enough for potential internal retries or complex paths
            final_state_dict = await robot_flow_app.ainvoke(current_state, {"recursion_limit": 25})
            final_state: RobotFlowAgentState = final_state_dict

            logging.info(f"Graph turn completed. Dialog state: {final_state.get('dialog_state')}")
            # logging.debug(f"Full state after invoke: {json.dumps(final_state, indent=2, ensure_ascii=False)}")

            current_state = final_state # Update current_state with the full result for the next iteration

            if final_state.get('is_error'):
                logging.error(f"Flow encountered an error: {final_state.get('error_message')}")
                break

            if final_state.get('clarification_question'):
                logging.info(f"Agent asks: {final_state['clarification_question']}")
                try:
                    user_response = await asyncio.to_thread(input, "Your response: ")
                except RuntimeError: # Fallback for environments where asyncio.to_thread(input, ...) might not work (e.g. some test runners)
                    print("Your response (fallback input): ", end="")
                    user_response = input()

                current_state['user_input'] = user_response
                # dialog_state will be handled by the graph based on 'awaiting_robot_model'
                # messages list is managed by the nodes themselves and accumulates
                logging.info(f"Received user response: '{user_response}'")
                continue # Go to next turn of the loop
            
            # Check for successful completion (e.g., input understood and no more questions)
            # This condition might need to be more specific based on when the flow is truly "done"
            if final_state.get('dialog_state') == 'input_understood':
                logging.info("Agent has understood the input and no further clarifications are needed.")
                if final_state.get('parsed_flow_steps'):
                    logging.info(f"Parsed flow steps: {json.dumps(final_state.get('parsed_flow_steps'), indent=2, ensure_ascii=False)}")
                    logging.info("Further XML generation steps would follow here.")
                else:
                    logging.warning("Input understood, but no parsed_flow_steps found. This might be an issue.")
                break # Exit loop as this phase is complete
            
            # Fallback break if dialog state is not one we explicitly handle for continuing interaction
            if final_state.get('dialog_state') not in ['initial', 'awaiting_robot_model', 'processing_enriched_input']:
                logging.warning(f"Exiting loop due to unhandled dialog state: {final_state.get('dialog_state')}")
                break

        except Exception as e:
            logging.error(f"An error occurred during graph execution: {e}", exc_info=True)
            break
        
    if turn_count >= max_turns:
        logging.warning(f"Max interaction turns ({max_turns}) reached.")

    logging.info(f"\n--- Final Agent State After Interaction ---")
    # Convert messages to a serializable format before printing
    serializable_state = current_state.copy()
    if "messages" in serializable_state and serializable_state["messages"] is not None:
        serializable_state["messages"] = [
            message.dict() # Using .dict() method of Pydantic models (BaseMessage inherits from Pydantic) or a custom representation
            # Alternatively, if .dict() is not available or suitable:
            # { "type": message.type, "content": message.content } 
            for message in serializable_state["messages"]
        ]
    logging.info(json.dumps(serializable_state, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main()) 