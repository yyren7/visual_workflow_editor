import logging
from typing import Dict, Any, List, Optional, Tuple

from pydantic import BaseModel
from pydantic import ConfigDict
from sqlalchemy.orm import Session
from langchain_core.runnables import (RunnablePassthrough, RunnableParallel, 
                                      RunnableLambda, RunnableConfig, 
                                      RunnableSerializable)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage, get_buffer_string
from openai.types.chat import ChatCompletionMessageParam

# 导入依赖组件
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM
from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
from backend.langchainchat.memory.db_chat_memory import DbChatMemory
from database.embedding.service import DatabaseEmbeddingService # 需要初始化 Retriever

logger = logging.getLogger(__name__)

# --- RAG Chain 输入模型 ---
class RAGInput(BaseModel):
    user_input: str
    chat_id: str
    db_session: Session
    # 可以添加其他参数，如 user_id 等，如果需要的话

    # Pydantic V2 配置：允许任意类型（如 SQLAlchemy Session）
    model_config = ConfigDict(arbitrary_types_allowed=True)

# --- 辅助函数 ---

def _format_docs(docs: List[Any]) -> str:
    """将检索到的文档格式化为字符串。"""
    # 假设 docs 是包含 source_data 和 metadata 的字典列表
    formatted = []
    for i, doc in enumerate(docs):
        # 尝试从 source_data 中提取文本，如果失败则使用空字符串
        text = str(doc.get('source_data', '')) # 将 source_data 转为字符串
        metadata_info = doc.get('metadata', {})
        score_str = f" (Score: {metadata_info.get('score', 'N/A'):.2f})" if 'score' in metadata_info else ""
        formatted.append(f"<doc id='{i}'{score_str}>\n{text}\n</doc>")
    if not formatted:
         return "No relevant context found."
    return "\n\n".join(formatted)

async def _get_chat_history(input_dict: Dict[str, Any]) -> List[BaseMessage]:
    """从 DbChatMemory 加载聊天历史。"""
    chat_id = input_dict.get("chat_id")
    db_session = input_dict.get("db_session")
    if not chat_id or not db_session:
        logger.warning("Chat ID or DB session missing for history retrieval.")
        return []
    
    memory = DbChatMemory(chat_id=chat_id, db_session=db_session)
    # messages 属性会自动调用 _load_messages
    return memory.messages 

async def _save_chat_history(input_output: Dict[str, Any], config: RunnableConfig):
    """将用户输入和AI输出保存到聊天历史。"""
    chat_id = config.get("configurable", {}).get("chat_id")
    db_session = config.get("configurable", {}).get("db_session")
    user_input = input_output.get("user_input")
    ai_response = input_output.get("ai_response")
    
    if not chat_id or not db_session or user_input is None or ai_response is None:
        logger.warning("Missing data for saving chat history. Skipping save.")
        return # 或者可以返回 input_output
        
    memory = DbChatMemory(chat_id=chat_id, db_session=db_session)
    memory.add_message(HumanMessage(content=user_input))
    memory.add_message(AIMessage(content=ai_response))
    logger.info(f"Saved conversation turn to chat history for chat_id: {chat_id}")
    # 如果需要在链中传递，可以返回原始字典或特定值
    # return input_output # 通常不需要返回，因为这是副作用

# --- RAG Chain 定义 (使用 LCEL) ---

# 新增：异步辅助函数，用于调用 DeepSeekLLM 并处理格式
async def _invoke_llm(llm_instance: DeepSeekLLM, prompt_value: Any) -> str:
    """将 LangChain PromptValue 转换为 DeepSeek 格式并调用 LLM。"""
    # 1. 将 PromptValue 转换为 LangChain BaseMessage 列表
    messages: List[BaseMessage] = prompt_value.to_messages()
    
    # 2. 将 BaseMessage 列表转换为 DeepSeek/OpenAI 格式的字典列表
    formatted_messages: List[ChatCompletionMessageParam] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            # 确保 AIMessage 的 content 是字符串
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            formatted_messages.append({"role": "assistant", "content": content})
        elif isinstance(msg, SystemMessage):
            formatted_messages.append({"role": "system", "content": msg.content})
        else:
            logger.warning(f"Unsupported message type encountered: {type(msg)}. Skipping.")
            
    # 3. 调用 LLM 的 chat_completion
    content, success = await llm_instance.chat_completion(messages=formatted_messages)
    
    # 4. 处理结果
    if not success:
        logger.error("LLM chat_completion failed during RAG chain execution.")
        # 可以返回错误信息或抛出异常，这里返回固定错误消息
        return "抱歉，处理请求时遇到错误。"
    return content

def create_rag_chain(
    llm: DeepSeekLLM, 
    retriever: EmbeddingRetriever
) -> RunnableSerializable[RAGInput, str]:
    """
    创建 RAG 链。

    Args:
        llm: 已初始化的 LLM 客户端。
        retriever: 已初始化的 EmbeddingRetriever。

    Returns:
        一个可运行的 RAG 链实例。
    """
    
    # 1. 定义聊天提示模板
    #    使用 MessagesPlaceholder 来动态插入聊天历史
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", 
         "You are a helpful assistant answering questions based on the provided context and chat history. Respond in Chinese.\n"
         "Context:\n"
         "{context}"
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
    ])
    
    # 2. 定义链的核心逻辑
    #    RunnablePassthrough.assign 会将新的键值对添加到原始输入字典中
    rag_chain_logic = (
        RunnablePassthrough.assign(
            # 并行执行：检索文档和加载历史记录
            context=RunnableLambda(lambda x: x['user_input']) | retriever | RunnableLambda(_format_docs),
            chat_history=RunnableLambda(_get_chat_history)
        )
        | prompt_template
        # 使用 RunnableLambda 包装对自定义 LLM 的调用
        | RunnableLambda(lambda prompt_val: _invoke_llm(llm, prompt_val)) 
        | StrOutputParser()
    )
    
    # 3. 包装链以处理历史记录保存 (使用 config 传递 chat_id 和 db_session)
    #    创建一个处理输入的 Runnable 并行执行 RAG 逻辑和提取输入
    chain_with_history = RunnableParallel(
        # 将 user_input 传递给 RAG 链
        ai_response=rag_chain_logic,
        # 同时保留 user_input 以便后续保存历史
        user_input=RunnableLambda(lambda x: x['user_input'])
    ).with_listeners( # 使用 with_listeners 注册副作用 (保存历史)
        on_end=RunnableLambda(_save_chat_history)
    ) | RunnableLambda(lambda x: x['ai_response']) # 最后只输出 ai_response 字符串
    
    # 4. 使用 .with_types 添加输入类型提示
    final_chain = chain_with_history.with_types(input_type=RAGInput, output_type=str)
    
    logger.info("RAG chain created successfully using LCEL.")
    return final_chain


# --- 使用示例 (假设在 FastAPI 或应用层) ---

# # 1. 初始化依赖 (通常在应用启动时完成)
# db_session = next(get_session()) # 获取 DB Session
# embedding_service = DatabaseEmbeddingService() # 使用默认模型
# retriever = EmbeddingRetriever(db_session=db_session, embedding_service=embedding_service)
# llm = DeepSeekLLM() # 需要配置 API Key 等

# # 2. 创建 RAG 链
# rag_chain = create_rag_chain(llm=llm, retriever=retriever)

# # 3. 调用链 (需要传入 chat_id 和 db_session 到 config)
# async def get_rag_response(user_input: str, chat_id: str):
#     input_data = RAGInput(user_input=user_input, chat_id=chat_id, db_session=db_session)
    
#     # 使用 .ainvoke 并通过 config 传递 chat_id 和 db_session
#     response = await rag_chain.ainvoke(
#         input_data,
#         config={"configurable": {"chat_id": chat_id, "db_session": db_session}}
#     )
#     return response

# # Example usage in an async function:
# # async def main():
# #     chat_id = "your_chat_uuid"
# #     response1 = await get_rag_response("什么是流程图？", chat_id)
# #     print("AI Response 1:", response1)
# #     response2 = await get_rag_response("它包含哪些基本元素？", chat_id)
# #     print("AI Response 2:", response2)

# # # Run the example
# # import asyncio
# # asyncio.run(main())
