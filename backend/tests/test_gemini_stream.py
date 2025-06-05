import asyncio
import os
import logging # Added for logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_gemini_stream():
    load_dotenv() # Load environment variables from .env file
    
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file or ensure it's available.")
        return

    # You can change the model name if needed, e.g., "gemini-pro-vision", "gemini-1.5-pro-latest", etc.
    # model_name = "gemini-pro" 
    model_name = os.getenv("GEMINI_MODEL", "gemini-pro") # Use the one from env or default to gemini-pro
    
    logger.info(f"Attempting to initialize ChatGoogleGenerativeAI with model: {model_name}")
    
    try:
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=gemini_api_key)
        logger.info(f"Successfully initialized ChatGoogleGenerativeAI with model: {model_name}")
    except Exception as e:
        logger.error(f"Failed to initialize ChatGoogleGenerativeAI: {e}", exc_info=True)
        return

    prompt_message = "Tell me a very short story about a curious robot."
    logger.info(f"Sending prompt to LLM: \"{prompt_message}\"")
    logger.info("Streaming response:")
    
    full_response_content = ""
    try:
        chunk_count = 0
        async for chunk in llm.astream([HumanMessage(content=prompt_message)]):
            chunk_count += 1
            if hasattr(chunk, 'content') and chunk.content:
                print(chunk.content, end="", flush=True)
                full_response_content += chunk.content
            else:
                # Log if a chunk doesn't have content, to understand the stream better
                logger.debug(f"Received chunk {chunk_count} without 'content' or empty content: {chunk}")
        print() # Add a newline after streaming is complete
        logger.info(f"Stream finished. Received {chunk_count} chunks in total.")
        if not full_response_content:
            logger.warning("Stream finished, but no content was received.")
        else:
            logger.info(f"Full response received: {full_response_content[:200]}...") # Log start of full response for verification

    except Exception as e:
        logger.error(f"An error occurred during streaming: {e}", exc_info=True)
        if full_response_content:
             logger.info(f"Partial response received before error: {full_response_content[:200]}...")


if __name__ == "__main__":
    logger.info("Starting Gemini streaming test...")
    # Ensure GOOGLE_API_KEY is set in your environment (e.g., in a .env file in the workspace root or exported)
    # The script will attempt to load .env
    
    # To run this test, navigate to the /workspace directory in your terminal and execute:
    # python -m backend.tests.test_gemini_stream
    # Make sure your project root (/workspace) is in PYTHONPATH or run with -m.
    
    # If you have a .env file in /workspace, load_dotenv() should pick it up.
    # Example .env content:
    # GOOGLE_API_KEY="your_actual_google_api_key_here"
    # GEMINI_MODEL="gemini-pro" 
    
    asyncio.run(test_gemini_stream())
    logger.info("Gemini streaming test finished.") 