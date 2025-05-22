import http.server
import socketserver
import os
import socket

PORT = 8000
FILENAME = "flow.xml"
FILE_PATH = os.path.abspath(FILENAME)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' + FILENAME:
            try:
                with open(FILE_PATH, 'rb') as f:
                    self.send_response(200)
                    self.send_header("Content-type", "application/xml")
                    self.send_header("Content-Disposition", f'attachment; filename="{FILENAME}"')
                    fs = os.fstat(f.fileno())
                    self.send_header("Content-Length", str(fs.st_size))
                    self.end_headers()
                    self.copyfile(f, self.wfile)
            except FileNotFoundError:
                self.send_error(404, "File not found")
            except Exception as e:
                self.send_error(500, f"Server error: {e}")
        else:
            self.send_error(404, "File not found")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    if not os.path.exists(FILE_PATH):
        print(f"错误: 文件 {FILE_PATH} 未找到。请确保 '{FILENAME}' 文件与脚本在同一目录下。")
    else:
        # 切换到文件所在目录，以便 SimpleHTTPRequestHandler 可以找到它
        os.chdir(os.path.dirname(FILE_PATH) or '.')
        
        httpd = socketserver.TCPServer(("", PORT), Handler)
        
        local_ip = get_local_ip()
        
        print(f"文件 '{FILENAME}' 已准备好，可以通过以下方式从 Windows 电脑下载：")
        print(f"1. 在 Windows 电脑的浏览器中打开: http://{local_ip}:{PORT}/{FILENAME}")
        print(f"2. 或者，在 Windows 电脑的 PowerShell 中运行以下命令 (这将文件下载到桌面):")
        print(f"   Invoke-WebRequest -Uri http://{local_ip}:{PORT}/{FILENAME} -OutFile $HOME\Desktop\{FILENAME}")
        print(f"按 Ctrl+C 停止服务器。")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止。")
        finally:
            httpd.server_close() 