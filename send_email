import json, smtplib, os
from email.mime.text import MIMEText

def send_daily_news():
    try:
        with open('data/latest-24h.json', 'r', encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception:
        return

    html_content = "<h2>🤖 你的 AI 资讯每日推送</h2><ul>"
    for item in news_data[:30]:
        title = item.get('title', '无标题')
        link = item.get('url', '#')
        source = item.get('source_name', '未知来源')
        html_content += f"<li style='margin-bottom: 10px;'><a href='{link}'>{title}</a> <span>[{source}]</span></li>"
    html_content += "</ul>"

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = '【AI News Radar】每日最新 AI 资讯速递'
    msg['From'] = os.environ.get('SENDER_EMAIL')
    msg['To'] = os.environ.get('RECEIVER_EMAIL')

    try:
        server = smtplib.SMTP_SSL(os.environ.get('SMTP_SERVER'), 465)
        server.login(os.environ.get('SENDER_EMAIL'), os.environ.get('SMTP_PASSWORD'))
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("发送失败", e)

if __name__ == "__main__":
    send_daily_news()
