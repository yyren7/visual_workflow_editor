import psycopg2
import json

# --- 请根据您的实际情况修改以下变量 ---
DB_HOST = "db"  # 或者 "localhost" / 数据库服务器IP (如果不在Docker网络中)
DB_PORT = "5432"
DB_NAME = "flow_editor_db"
DB_USER = "yyren"
DB_PASSWORD = "yyren123123"
TARGET_FLOW_ID = "7c64e3a2-7bb6-4c89-a7d0-4cf36677c6ba"
# --- 修改结束 ---

def query_agent_state():
    conn = None
    try:
        # 构建连接字符串
        conn_string = f"host='{DB_HOST}' port='{DB_PORT}' dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}'"
        
        # 连接到 PostgreSQL 服务器
        print(f"Connecting to database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(conn_string)
        
        # 创建一个 cursor 对象
        cur = conn.cursor()
        
        print(f"Executing query for flow_id: {TARGET_FLOW_ID}")
        # 执行查询
        cur.execute("SELECT agent_state FROM flows WHERE id = %s", (TARGET_FLOW_ID,))
        
        # 获取查询结果
        row = cur.fetchone()
        
        if row:
            agent_state = row[0]
            print("\n--- Full agent_state ---")
            # 使用 ensure_ascii=False 来正确处理可能的非ASCII字符（例如中文）
            print(json.dumps(agent_state, indent=2, ensure_ascii=False)) 
            
            if agent_state and isinstance(agent_state, dict):
                config = agent_state.get("config")
                print("\n--- config ---")
                if config and isinstance(config, dict):
                    print(json.dumps(config, indent=2, ensure_ascii=False))
                else:
                    print("No 'config' dictionary found in agent_state, or it's not a dictionary.")
            else:
                print("agent_state is empty, None, or not a dictionary.")
        else:
            print(f"No flow found with flow_id: {TARGET_FLOW_ID}")
            
        # 关闭 cursor 和连接
        cur.close()
    except (Exception, psycopg2.Error) as error:
        print(f"Error while connecting to PostgreSQL or executing query: {error}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    query_agent_state() 