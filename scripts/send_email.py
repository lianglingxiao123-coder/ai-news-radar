#!/usr/bin/env python3
import json, smtplib, os, ssl
from email.mime.text import MIMEText
from datetime import datetime

def send_email_compatible():
    """兼容性更强的邮件发送函数"""
    
    # 邮件配置（从环境变量读取）
    smtp_server = os.environ.get('SMTP_SERVER', '')
    sender_email = os.environ.get('SENDER_EMAIL', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    receiver_email = os.environ.get('RECEIVER_EMAIL', '')
    
    # 最简单的邮件内容测试
    test_content = '''
    <h2>🤖 AI新闻雷达邮件测试</h2>
    <p>这只是测试邮件，恭喜！邮箱配置正常工作。</p>
    <p>🚀 GitHub Actions已完成所有更新和工作流配置。</p>
    '''
    
    msg = MIMEText(test_content, 'html', 'utf-8')
    msg['Subject'] = '[测试]AI新闻雷达邮件连通性验证'
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    print(f"🧪 SMTP邮件连接测试:")
    print(f"- 服务器: {smtp_server}")
    print(f"- 端口: {str([587, 465, 25])}")
    print(f"- 发件人: {sender_email[:10]}...@...")
    print(f"- 收件人: {receiver_email}")
    
    # 尝试多种连接方式
    success = False
    
    # 尝试 1: STARTTLS + 端口 587（最便携）
    try:
        print(f"\n📧 尝试方法1: STARTTLS + 端口587")
        server = smtplib.SMTP(smtp_server, 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, smtp_password)
        server.send_message(msg)
        server.quit()
        print("✅ 方法1成功！邮件发送")
        success = True
    except Exception as e:
        print(f"⚠️ 方法1失败: {str(e)[:80]}")
    
    # 尝试 2: SSL + 端口465（传统）
    if not success:
        try:
            print(f"\n📧 尝试方法2: SSL + 端口465")
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_server, 465, context=context)
            server.login(sender_email, smtp_password)
            server.send_message(msg)
            server.quit()
            print("✅ 方法2成功！邮件发送")
            success = True
        except Exception as e:
            print(f"⚠️ 方法2失败: {str(e)[:80]}")
    
    # 尝试 3: SMTPLib 默认（自动检测）
    if not success:
        try:
            print(f"\n📧 尝试方法3: SMTPLib 自动协议")
            server = smtplib.SMTP(smtp_server)
            server.ehlo()
            
            # 如果有STARTTLS能力就启用
            if server.has_extn('STARTTLS'):
                server.starttls()
                server.ehlo()
            
            server.login(sender_email, smtp_password)
            server.send_message(msg)
            server.quit()
            print("✅ 方法3成功！邮件发送")
            success = True
        except Exception as e:
            print(f"⚠️ 方法3失败: {str(e)[:80]}")
    
    # 尝试 4: POST 端口 587 无 SSL/TLS（最宽松）
    if not success:
        try:
            print(f"\n📧 尝试方法4: SMTP明文连接 (不安全)")
            server = smtplib.SMTP(smtp_server, 587)
            server.ehlo()
            
            # 尝试直接明文登录，启用容忍模式
            server.login(sender_email, smtp_password)
            server.send_message(msg)
            server.quit()
            print("✅ 方法4成功！（警告：不使用加密）")
            success = True
        except Exception as e:
            print(f"⚠️ 方法4失败: {str(e)[:80]}")
    
    if success:
        print("\n✅ 祝贺！电子邮件测试成功完成！")
        
        print("\n🎯 GitHub Actions Secrets 配置:")
        secrets_list = '''
echo "::: GitHub Secrets Checklist :::"
echo ""
echo "[待添加] SMTP_SERVER=smtp.gmail.com"
echo "[待添加] SENDER_EMAIL=your_email@gmail.com"
echo "[待添加] SMTP_PASSWORD=生成的专用密码"
echo "[待添加] RECEIVER_EMAIL=your_email@gmail.com"
echo ""
echo "[可选] FOLLOW_OPML_B64=<your-base64-data>"
        '''
        print(secrets_list)
        print("\n🔗 请你立刻去 GitHub Secrets 页面添加这些配置！")
    else:
        print("\n❌ 所有邮件发送尝试均失败")
        print("可能是:")
        print("1. 🌐 GitHub Actions 网络限制访问外部SMTP")
        print("2. 🔒 防火墙/代理拦截")
        print("3. 💼 需要使用自建邮件服务器或转发服务")

if __name__ == "__main__":
    send_email_compatible()