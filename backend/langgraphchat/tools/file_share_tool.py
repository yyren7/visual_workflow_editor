import subprocess
import os
from dotenv import load_dotenv # 引入 dotenv

load_dotenv() # 加载 .env 文件中的变量

# 配置 - 从环境变量加载
smb_host = os.getenv("SMB_HOST")
smb_share_flow = os.getenv("SMB_SHARE_LLM")
smb_share_config = os.getenv("SMB_SHARE_CONFIG")
smb_user_domain = os.getenv("SMB_USER_DOMAIN")
smb_username = os.getenv("SMB_USERNAME")
smb_password = os.getenv("SMB_PASSWORD")

# 检查是否所有必要的环境变量都已设置
if not all([smb_host, smb_share_flow, smb_share_config, smb_user_domain, smb_username, smb_password]):
    print("错误：一个或多个 SMB 配置环境变量未在 .env 文件中设置。")
    print("请确保 SMB_HOST, SMB_SHARE, SMB_USER_DOMAIN, SMB_USERNAME, SMB_PASSWORD 都已定义。")
    exit(1) # 如果配置不完整则退出

local_download_dir = "/workspace/backend/langgraphchat/synced_files"
files_to_download = ["flow.xml"]

# 完整 SMB 用户凭证，格式为 'DOMAIN\\username%password'
# smb_credentials = f"{smb_user_domain}\\\\{smb_username}%{smb_password}" # 旧方式，注释掉
smb_user_pass = f"{smb_username}%{smb_password}" # 新方式：用户名%密码
smb_base_url = f"//{smb_host}/{smb_share_flow}"

def download_files():
    # 创建本地目录（如果不存在）
    try:
        os.makedirs(local_download_dir, exist_ok=True)
        print(f"本地目录 '{local_download_dir}' 已确保存在。")
    except OSError as e:
        print(f"创建目录 '{local_download_dir}' 失败: {e}")
        return

    for file_name in files_to_download:
        remote_file_path = file_name # 文件位于共享的根目录
        local_file_path = os.path.join(local_download_dir, file_name)
        
        # 构建 smbclient 命令
        # 示例: smbclient '//172.30.84.220/llm_test' -U 'JP\\J100052060%frank123' \\
        #         -c 'get auto.py /workspace/backend/tests/share_folder/auto.py'
        smb_get_command = f"get {remote_file_path} {local_file_path}"
        # full_command = [ # 旧命令构建
        #     "smbclient",
        #     smb_base_url,
        #     "-U",
        #     smb_credentials,
        #     "-c",
        #     smb_get_command
        # ]
        full_command = [ # 新命令构建
            "smbclient",
            smb_base_url,
            "-W", # 指定工作组/域
            smb_user_domain,
            "-U", # 指定用户和密码
            smb_user_pass,
            "-c",
            smb_get_command
        ]
        
        print(f"准备下载 '{file_name}' 到 '{local_file_path}'...")
        # 为安全起见，打印命令时可以考虑隐藏或部分隐藏密码
        # print(f"执行命令: {' '.join(full_command)}") # 实际执行时会包含密码

        try:
            # Using subprocess.run for simpler blocking execution and error handling
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=60, check=False)

            if result.returncode == 0:
                print(f"成功下载 '{file_name}'.")
                if result.stdout:
                    print(f"smbclient 输出:\n{result.stdout}")
                # smbclient often uses stderr for status messages even on success
                if result.stderr and "NT_STATUS_OK" not in result.stderr : # Heuristic to filter common success messages on stderr
                     print(f"smbclient (可能的) 消息/警告:\n{result.stderr}")
            else:
                print(f"下载 '{file_name}' 失败。返回码: {result.returncode}")
                if result.stdout:
                    print(f"smbclient 标准输出:\n{result.stdout}")
                if result.stderr:
                    print(f"smbclient 错误输出:\n{result.stderr}")
        
        except subprocess.TimeoutExpired:
            print(f"下载 '{file_name}' 超时。")
        except FileNotFoundError:
            print("错误: 'smbclient' 命令未找到。请确保它已安装并在您的 PATH 中。")
            break # 如果 smbclient 未找到，则停止
        except Exception as e:
            print(f"下载 '{file_name}' 时发生未知错误: {e}")

# 新增：上传文件的函数
def upload_file(local_file_path, remote_file_name):
    print(f"准备上传 '{local_file_path}' 到共享目录下的 '{remote_file_name}'...")

    if not os.path.exists(local_file_path):
        print(f"错误：本地文件 '{local_file_path}' 不存在，无法上传。")
        return False # 新增返回

    # 构建 smbclient 命令
    # 示例: smbclient '//172.30.84.220/llm_test' -W JP -U J100052060%frank123 \\
    #         -c 'put /workspace/backend/tests/conftest.py conftest.py'
    smb_put_command = f"put {local_file_path} {remote_file_name}"
    full_command = [
        "smbclient",
        smb_base_url,
        "-W", 
        smb_user_domain,
        "-U", 
        smb_user_pass,
        "-c",
        smb_put_command
    ]

    try:
        result = subprocess.run(full_command, capture_output=True, text=True, timeout=60, check=False)

        if result.returncode == 0:
            print(f"成功上传 '{local_file_path}' 为 '{remote_file_name}'.")
            if result.stdout:
                print(f"smbclient 输出:\\n{result.stdout}")
            if result.stderr and "NT_STATUS_OK" not in result.stderr:
                 print(f"smbclient (可能的) 消息/警告:\\n{result.stderr}")
            return True # 新增返回
        else:
            print(f"上传 '{local_file_path}' 失败。返回码: {result.returncode}")
            if result.stdout:
                print(f"smbclient 标准输出:\\n{result.stdout}")
            if result.stderr:
                print(f"smbclient 错误输出:\\n{result.stderr}")
            return False # 新增返回
    
    except subprocess.TimeoutExpired:
        print(f"上传 '{local_file_path}' 超时。")
        return False # 新增返回
    except FileNotFoundError:
        print("错误: 'smbclient' 命令未找到。请确保它已安装并在您的 PATH 中。")
        return False # 新增返回
    except Exception as e:
        print(f"上传 '{local_file_path}' 时发生未知错误: {e}")
        return False # 新增返回

if __name__ == "__main__":
    print("开始文件下载过程...")
    download_files()
    print("文件下载过程结束。")

    print("\n开始文件上传过程...")
    upload_file(local_file_to_upload, remote_file_name_for_upload)
    print("文件上传过程结束。") 