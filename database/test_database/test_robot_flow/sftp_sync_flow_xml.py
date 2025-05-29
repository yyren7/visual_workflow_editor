import pysftp
import os
import paramiko

WINDOWS_HOST = '172.30.84.220'
WINDOWS_USERNAME = 'J100052060'  # <-- 重要: 替换为您的 Windows 用户名
WINDOWS_PASSWORD = 'frank123'  # <-- 重要: 替换为您的 Windows 密码 (或使用 SSH 密钥)
SSH_PORT = 22 # SSH 默认端口

LOCAL_FILE_NAME = 'flow.xml'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE_PATH = os.path.join(SCRIPT_DIR, LOCAL_FILE_NAME)

# Windows 桌面路径 (SFTP 格式)。您可能需要根据您的 SSH 服务器配置调整此路径。
# 示例:
# - 'Desktop/flow.xml' (如果 SSH 服务器默认进入用户主目录)
# - '/C/Users/YourUsername/Desktop/flow.xml' (如果使用类似 MobaXterm 的 SSH 服务器且映射了驱动器)
# - 'C:/Users/YourUsername/Desktop/flow.xml' (某些配置可能直接接受 Windows 路径)
REMOTE_DESKTOP_PATH_SFTP = f'Desktop/{LOCAL_FILE_NAME}' # <-- 重要: 根据实际情况调整此路径

# (可选) 如果您使用 SSH 密钥而不是密码，请取消注释以下行并设置密钥路径
# PRIVATE_KEY_PATH = '~/.ssh/id_rsa' # 替换为您的私钥路径
# PRIVATE_KEY_PASSWORD = None # 如果您的私钥有密码，请设置

# pysftp 使用 cnopts (Connection Options) 来忽略主机密钥检查 (不推荐用于生产环境)
# 在首次连接或主机密钥更改时，这可以避免 HostKeysException。
# 更安全的方式是预先接受主机密钥。
cnopts = pysftp.CnOpts()
cnopts.hostkeys = None # 禁用主机密钥检查，仅用于测试或受信任的网络

if __name__ == "__main__":
    if not os.path.exists(LOCAL_FILE_PATH):
        print(f"错误: 本地文件 {LOCAL_FILE_PATH} 未找到。")
    else:
        print(f"准备通过 SFTP 将 '{LOCAL_FILE_NAME}' 上传到 {WINDOWS_HOST}:{REMOTE_DESKTOP_PATH_SFTP}")
        try:
            # 如果使用密码登录:
            with pysftp.Connection(host=WINDOWS_HOST,
                                   username=WINDOWS_USERNAME,
                                   password=WINDOWS_PASSWORD,
                                   port=SSH_PORT,
                                   cnopts=cnopts) as sftp:
                print(f"已连接到 {WINDOWS_HOST} 作为用户 {WINDOWS_USERNAME}。")
                
                # 确保远程目录的父目录存在 (如果适用)
                # remote_dir = os.path.dirname(REMOTE_DESKTOP_PATH_SFTP)
                # if remote_dir and remote_dir != '.':
                #     try:
                #         sftp.makedirs(remote_dir) # 创建远程目录 (如果不存在)
                #         print(f"确保远程目录 '{remote_dir}' 存在或已创建。")
                #     except Exception as e:
                #         print(f"警告: 创建远程目录 '{remote_dir}' 失败: {e}. 假设它已存在或不需要。")

                sftp.put(LOCAL_FILE_PATH, REMOTE_DESKTOP_PATH_SFTP)
                print(f"文件 '{LOCAL_FILE_NAME}' 已成功上传到 '{REMOTE_DESKTOP_PATH_SFTP}'")

            # # 如果使用 SSH 密钥登录 (取消注释并注释掉上面的密码登录部分):
            # with pysftp.Connection(host=WINDOWS_HOST, 
            #                        username=WINDOWS_USERNAME, 
            #                        private_key=PRIVATE_KEY_PATH,
            #                        private_key_pass=PRIVATE_KEY_PASSWORD, # 如果私钥有密码
            #                        port=SSH_PORT,
            #                        cnopts=cnopts) as sftp:
            #     print(f"已连接到 {WINDOWS_HOST} 作为用户 {WINDOWS_USERNAME} 使用 SSH 密钥。")
            #     sftp.put(LOCAL_FILE_PATH, REMOTE_DESKTOP_PATH_SFTP)
            #     print(f"文件 '{LOCAL_FILE_NAME}' 已成功上传到 '{REMOTE_DESKTOP_PATH_SFTP}'")

        except pysftp.exceptions.ConnectionException as e: # 这个通常是 pysftp 对 paramiko.SSHException 的封装
            print(f"连接错误 (pysftp.exceptions.ConnectionException): {e}")
            print(f"""请检查:
            1. Windows 主机 ({WINDOWS_HOST}) 是否可达并且 SSH 服务器正在运行。
            2. 防火墙是否允许端口 {SSH_PORT} 的连接。
            3. 用户名 ({WINDOWS_USERNAME}) 是否正确。""")
        except paramiko.ssh_exception.SSHException as e: # 捕获更底层的 paramiko 连接/SSH 错误
            print(f"SSH 连接错误 (paramiko.ssh_exception.SSHException): {e}")
            print(f"这通常意味着无法连接到服务器 ({WINDOWS_HOST}:{SSH_PORT})，或者在SSH协议级别出现问题。请检查服务器状态和网络防火墙。")
        except paramiko.ssh_exception.AuthenticationException as e: # 正确的认证异常
            print(f"身份验证失败 (paramiko.ssh_exception.AuthenticationException): {e}")
            print(f"请检查您的用户名 ({WINDOWS_USERNAME}) 和密码 (或 SSH 密钥) 是否正确。")
        except pysftp.exceptions.HostKeysException as e: # pysftp 的主机密钥异常
            print(f"主机密钥错误 (pysftp.exceptions.HostKeysException): {e}.")
            print(f"如果这是第一次连接或主机密钥已更改，并且您信任此主机，可以暂时设置 cnopts.hostkeys = None (已在脚本中)。")
        except FileNotFoundError as e: # 本地文件未找到或 SFTP 远程文件/目录问题
            print(f"文件未找到错误: {e}")
            print(f"请检查本地文件路径 '{LOCAL_FILE_PATH}' 是否正确。")
            print(f"或者，对于SFTP操作，远程路径 '{REMOTE_DESKTOP_PATH_SFTP}' 可能无效或目标目录不存在。")
        except IOError as e: # 通用 I/O 错误，有时 SFTP 操作因权限或路径问题会触发
            print(f"I/O 或权限错误: {e}")
            print(f"这可能与本地文件权限、远程文件权限或无效的远程路径有关。")
        except Exception as e:
            print(f"发生未知错误: {e} (类型: {type(e).__name__})") 