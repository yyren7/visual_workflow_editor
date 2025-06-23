import psycopg2
import json

# --- 请根据您的实际情况修改以下变量 ---
DB_HOST = "db"  # 或者 "localhost" / 数据库服务器IP (如果不在Docker网络中)
DB_PORT = "5432"
DB_NAME = "flow_editor_db"
DB_USER = "yyren"
DB_PASSWORD = "yyren123123"
TARGET_CHAT_ID = "7c64e3a2-7bb6-4c89-a7d0-4cf36677c6ba" # This is the chat_id (same as flow_id in logs)
# --- 修改结束 ---

def query_chat_data_config():
    conn = None
    try:
        conn_string = f"host='{DB_HOST}' port='{DB_PORT}' dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}'"
        print(f"Connecting to database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        print(f"Executing query for chat_id: {TARGET_CHAT_ID}")
        cur.execute("SELECT chat_data FROM chats WHERE id = %s", (TARGET_CHAT_ID,))
        row = cur.fetchone()
        
        if row:
            chat_data = row[0]
            print("\n--- Full chat_data ---")
            print(json.dumps(chat_data, indent=2, ensure_ascii=False))
            
            if chat_data and isinstance(chat_data, dict):
                persisted_sas_state = chat_data.get("persisted_sas_graph_state")
                if persisted_sas_state and isinstance(persisted_sas_state, dict):
                    print("\n--- persisted_sas_graph_state --- ")
                    print(json.dumps(persisted_sas_state, indent=2, ensure_ascii=False))
                    
                    config = persisted_sas_state.get("config")
                    print("\n--- config within persisted_sas_graph_state ---")
                    if config and isinstance(config, dict):
                        print(json.dumps(config, indent=2, ensure_ascii=False))
                        auto_accept_tasks = config.get("auto_accept_tasks")
                        print(f"\nValue of 'auto_accept_tasks' in persisted_sas_graph_state.config: {auto_accept_tasks}")
                        if auto_accept_tasks is True:
                            print("\n>>> !!! auto_accept_tasks is True in persisted chat state !!! <<<")
                        elif auto_accept_tasks is False:
                            print("\n>>> auto_accept_tasks is False in persisted chat state.")
                        else:
                            print("\n>>> auto_accept_tasks key not found or has unexpected value in persisted chat state config.")
                    else:
                        print("No 'config' dictionary found in persisted_sas_graph_state, or it's not a dictionary.")
                else:
                    print("No 'persisted_sas_graph_state' found in chat_data, or it's not a dictionary.")
            else:
                print("chat_data is empty, None, or not a dictionary.")
        else:
            print(f"No chat found with chat_id: {TARGET_CHAT_ID}")
            
        cur.close()
    except (Exception, psycopg2.Error) as error:
        print(f"Error: {error}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    query_chat_data_config() 