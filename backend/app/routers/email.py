import smtplib
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException
from backend.app.config import Config # 导入 Config

router = APIRouter()

@router.post("/email/send")
async def send_email(to: str, subject: str, body: str):
    """
    发送邮件到指定邮箱。
    """
    if not to or not subject or not body:
        raise HTTPException(status_code=400, detail="Missing email parameters")

    # 邮件配置
    mail_host = Config.MAIL_HOST  # 从配置中获取 SMTP 服务器地址
    mail_user = Config.MAIL_USER  # 从配置中获取发件人邮箱用户名
    mail_pass = Config.MAIL_PASS  # 从配置中获取发件人邮箱密码或授权码
    sender = mail_user  # 发件人邮箱
    receivers = [to]  # 接收邮件，可设置为你的邮箱或者配置项中的目标邮箱

    message = MIMEText(body, 'plain', 'utf-8')
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = to  # 直接使用传入的 to 参数作为收件人

    try:
        smtp_obj = smtplib.SMTP()
        smtp_obj.connect(mail_host, 25)  # 25 为 SMTP 端口号
        smtp_obj.login(mail_user, mail_pass)
        smtp_obj.sendmail(sender, receivers, message.as_string())
        print("Email sent successfully")
        return {"message": "Email sent successfully", "to": to, "subject": subject}
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")