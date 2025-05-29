import socket
import os
import time

WINDOWS_IP = '172.30.84.220'
PORT = 8001
FILENAME = 'flow.xml'
FILE_PATH = os.path.abspath(FILENAME) # 脚本将在文件所在目录运行
BUFFER_SIZE = 4096

def send_file(sock, filepath, filename_to_send):
    filesize = os.path.getsize(filepath)

    # 1. 发送文件名 (固定长度头部 + 文件名)
    filename_bytes = filename_to_send.encode('utf-8')
    filename_len_bytes = len(filename_bytes).to_bytes(4, 'big')
    sock.sendall(filename_len_bytes)
    sock.sendall(filename_bytes)
    # print(f"Sent filename header: {filename_len_bytes}, filename: {filename_bytes}")

    # 2. 发送文件大小 (固定8字节)
    filesize_bytes = filesize.to_bytes(8, 'big')
    sock.sendall(filesize_bytes)
    # print(f"Sent filesize: {filesize_bytes}")

    # 3. 发送文件内容
    sent_bytes = 0
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            sent_bytes += len(chunk)
            # print(f"Sent {sent_bytes}/{filesize} bytes")
    print(f"文件 '{filename_to_send}' ({filesize} bytes) 发送完成。")

if __name__ == "__main__":
    if not os.path.exists(FILE_PATH):
        print(f"错误: 文件 {FILE_PATH} 未找到。请确保 '{FILENAME}' 文件存在。")
    else:
        # 切换到文件所在目录，确保 FILENAME 能直接被 os.path.abspath(FILENAME) 正确解析
        # 并且 send_file 中的 open(filepath, 'rb') 能找到文件
        # 通常这个脚本会从 test_robot_flow_output_deepseek_interactive 目录运行
        # 而 flow.xml 也在那里
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_to_send_abs_path = os.path.join(script_dir, FILENAME)

        if not os.path.exists(file_to_send_abs_path):
            print(f"错误: 文件 {file_to_send_abs_path} 未找到。")
        else:
            max_retries = 3
            retry_delay = 5 # seconds
            for attempt in range(max_retries):
                try:
                    print(f"尝试连接到 {WINDOWS_IP}:{PORT} ...")
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((WINDOWS_IP, PORT))
                        print(f"已连接到 Windows 接收端 {WINDOWS_IP}:{PORT}")
                        send_file(s, file_to_send_abs_path, FILENAME)
                    break # 成功则跳出循环
                except ConnectionRefusedError:
                    print(f"连接被拒绝。请确保接收脚本已在 {WINDOWS_IP} 上运行并监听端口 {PORT}。")
                    if attempt < max_retries - 1:
                        print(f"将在 {retry_delay} 秒后重试... ({attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        print("达到最大重试次数，发送失败。")
                except Exception as e:
                    print(f"发送文件时发生错误: {e}")
                    if attempt < max_retries - 1:
                        print(f"将在 {retry_delay} 秒后重试... ({attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        print("达到最大重试次数，发送失败。") 