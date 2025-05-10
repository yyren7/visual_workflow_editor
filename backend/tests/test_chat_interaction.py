import pytest
import httpx
import asyncio
import json
import os

# --- 配置 ---
# 您需要将这些替换为实际的值或从环境变量中读取
# 例如: BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000/api/v1")
# AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "your_actual_jwt_token")
# TEST_CHAT_ID = os.getenv("TEST_CHAT_ID", "your_existing_chat_id")

BASE_URL = "http://localhost:8000/api/v1"  # 确保这与您的 FastAPI 应用前缀匹配
AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMiLCJleHAiOjE3NDY4Njg0Njh9.LGez3CuM92Ra3izrioElN0lkdotLT9Kwczw8hmSIbIE"  # 替换为有效的 JWT token
TEST_CHAT_ID = "62b623d2-9cc6-4349-8c46-d1ead4ccffe8" # 替换为有效的 chat_id

# 确保您的后端服务正在运行，并且上述 CHAT_ID 是有效的且与 AUTH_TOKEN 对应的用户相关联。

@pytest.mark.asyncio
async def test_send_message_and_receive_events():
    """
    测试向聊天发送消息并接收 SSE 事件。
    需要手动配置 AUTH_TOKEN 和 TEST_CHAT_ID。
    后端服务必须正在运行。
    """
    if AUTH_TOKEN == "YOUR_AUTH_TOKEN_HERE" or TEST_CHAT_ID == "YOUR_TEST_CHAT_ID_HERE":
        pytest.skip("需要配置 AUTH_TOKEN 和 TEST_CHAT_ID 才能运行此测试")

    user_message_content = "你好，这是一个测试消息！"
    send_message_url = f"{BASE_URL}/chats/{TEST_CHAT_ID}/messages"
    events_url = f"{BASE_URL}/chats/{TEST_CHAT_ID}/events"

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json" # 对于发送消息
    }
    
    event_headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Accept": "text/event-stream" # 对于 SSE
    }

    message_payload = {
        "flow_id": "WILL_BE_IGNORED_BY_CURRENT_ENDPOINT_BUT_SCHEMA_REQUIRES_IT", # chat.py add_message 不直接使用，但 Pydantic 模型可能需要
        "message": {
            "role": "user",
            "content": user_message_content
        }
        # "stream": True # 默认或由路由处理
    }
    
    # 我们需要在两个不同的任务中运行发送和接收
    # 因为接收 SSE 是一个长连接

    async def receive_events():
        received_events_data = []
        print(f"\nAttempting to connect to SSE endpoint: {events_url}")
        try:
            async with httpx.AsyncClient(timeout=30) as client: # 增加超时
                async with client.stream("GET", events_url, headers=event_headers) as response:
                    print(f"SSE Connection Response Status: {response.status_code}")
                    if response.status_code != 200:
                        response_text = await response.aread()
                        print(f"SSE Connection Failed. Response: {response_text.decode()}")
                        assert response.status_code == 200, f"无法连接到事件流: {response_text.decode()}"
                    
                    print("Successfully connected to SSE. Waiting for events...")
                    event_count = 0
                    # 循环读取事件，设置一个最大事件数或超时以防止测试永远运行
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            try:
                                data_str = line[len("data:"):].strip()
                                if data_str:
                                    event_data = json.loads(data_str)
                                    print(f"Received event: {event_data}")
                                    received_events_data.append(event_data)
                                    
                                    # 检查是否是流结束标记
                                    if event_data.get("type") == "stream_end" or event_data.get("event") == "stream_end":
                                        print("Stream end event received.")
                                        break
                                    # 或者检查是否有 AI 的回复内容
                                    if event_data.get("type") == "message" and event_data.get("data", {}).get("role") == "assistant":
                                        print(f"Assistant message received: {event_data['data']['content']}")
                                        # 可以根据需要在此处添加断言
                                        # break # 如果收到预期回复，可以提前结束
                                        
                                    event_count += 1
                                    if event_count >= 10: # 最多接收10个数据事件以防万一
                                        print("Reached max event count for testing.")
                                        break
                            except json.JSONDecodeError:
                                print(f"Error decoding JSON from event line: {line}")
                            except Exception as e:
                                print(f"Error processing event: {e}")
                        elif line.startswith("event:"):
                            print(f"Event type line: {line}")

        except httpx.ConnectError as e:
            print(f"Connection error to SSE endpoint: {e}")
            pytest.fail(f"无法连接到 SSE 端点: {e}")
        except httpx.ReadTimeout:
            print("Read timeout while waiting for SSE events.")
            # 根据是否预期超时来决定是否 fail
            # pytest.fail("SSE 事件读取超时") 
        except Exception as e:
            print(f"An unexpected error occurred while receiving events: {e}")
            pytest.fail(f"接收事件时发生意外错误: {e}")
            
        return received_events_data

    async def send_message():
        print(f"\nAttempting to send message to: {send_message_url}")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(send_message_url, json=message_payload, headers=headers)
            print(f"Send Message Response Status: {response.status_code}")
            if response.status_code != 202: # add_message 应该返回 202 Accepted
                response_text = await response.text()
                print(f"Send Message Failed. Response: {response_text}")
            assert response.status_code == 202, f"发送消息失败: {response.text}"
            print(f"Message sent successfully. Server accepted the request. ({response.status_code})")
            # 这里不直接返回响应体，因为 202 通常没有有意义的响应体
            # result = response.json() 
            # print(f"Send Message Response Data: {result}")


    # 为了确保接收端准备好，我们可以先启动接收事件的协程
    # 然后再发送消息。或者使用 asyncio.gather
    
    # 使用 asyncio.gather 同时运行两个任务
    # receive_task = asyncio.create_task(receive_events())
    # await asyncio.sleep(1) # 给接收端一点时间启动 (可选)
    # await send_message()
    # received_data = await receive_task

    # 更稳妥的方式：先发送，然后尝试接收
    await send_message()
    # 短暂等待，让后端有时间处理消息并开始发送事件
    await asyncio.sleep(2) # 等待2秒，根据您的系统响应时间调整
    received_data = await receive_events()

    assert len(received_data) > 0, "没有从 SSE 端点接收到任何事件数据"
    
    # 您可以在这里添加更多断言来验证接收到的事件内容
    # 例如，检查是否有包含 "你好" 的助手回复
    assistant_replied = False
    for event in received_data:
        if isinstance(event, dict): # 确保 event 是字典
            # 检查原始的 LangGraph 事件结构
            if event.get("event") == "on_chat_model_stream" and event.get("name") == "agent":
                 chunk = event.get("data", {}).get("chunk", {})
                 if isinstance(chunk, dict) and chunk.get("content"): # AIMessageChunk
                     if user_message_content in chunk["content"] or "你好" in chunk["content"]: # 简单检查
                        assistant_replied = True
                        break
            # 检查 chat.py 中格式化后的事件
            elif event.get("type") == "message" and event.get("data", {}).get("role") == "assistant":
                if user_message_content in event["data"]["content"] or "你好" in event["data"]["content"]:
                    assistant_replied = True
                    break
            elif event.get("type") == "final_response": # 假设有这样一个事件类型代表最终回复
                if user_message_content in event.get("data",{}).get("content","") or "你好" in event.get("data",{}).get("content",""):
                    assistant_replied = True
                    break


    # 注意: 上面的检查逻辑可能需要根据您实际的 SSE 事件结构进行调整。
    # 从日志中，事件可能是 'RunLogPatch' 的一部分，需要更复杂的解析。
    # 这里我简化为几种可能的事件结构。

    # 如果没有明确的助手回复事件，至少应收到 stream_end
    has_stream_end = any(evt.get("type") == "stream_end" or evt.get("event") == "stream_end" for evt in received_data if isinstance(evt, dict))
    
    # 如果您期望一定有AI回复，可以取消下面断言的注释
    # assert assistant_replied, f"助手的回复中未包含期望的内容或未收到助手回复。收到的数据: {received_data}"

    assert has_stream_end, f"未收到 stream_end 事件。收到的数据: {received_data}"

    print("\nTest finished.")

# 如果您想直接运行这个文件进行快速测试 (非 pytest 方式)
if __name__ == "__main__":
    # 确保替换 AUTH_TOKEN 和 TEST_CHAT_ID
    if AUTH_TOKEN == "YOUR_AUTH_TOKEN_HERE" or TEST_CHAT_ID == "YOUR_TEST_CHAT_ID_HERE":
        print("测试已跳过：请在脚本中为 AUTH_TOKEN 和 TEST_CHAT_ID 设置实际值以运行此测试。")
        print("例如：")
        print("AUTH_TOKEN = \"your_jwt_token_here\"")
        print("TEST_CHAT_ID = \"actual_chat_id_here\"")
    else:
        print("运行测试...")
        asyncio.run(test_send_message_and_receive_events())
        print("测试完成。请查看上面的输出来验证结果。") 