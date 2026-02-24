import json, smtplib, os
from email.mime.text import MIMEText

def send_daily_news():
    try:
        with open('data/latest-24h.json', 'r', encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception as e:
        print("读取数据失败:", e)
        return

    # --- 这里是我们新增的“智能整理”逻辑 ---
    items = []
    # 如果它本来就是一字排开的，直接用
    if isinstance(news_data, list):
        items = news_data
    # 如果它里面有分门别类的小盒子，把小盒子里的新闻都倒出来汇总
    elif isinstance(news_data, dict):
        for key, value in news_data.items():
            if isinstance(value, list):
                items.extend(value)

    # 如果连新闻都没有，就停止发送
    if not items:
        print("箱子是空的，没有找到新闻。")
        return

    html_content = "<h2>🤖 你的 AI 资讯每日推送</h2><ul>"
    
    # 现在我们可以安全地去抓前 30 条了
    for item in items[:30]:
        # 兼容一下格式，防止抓到不是新闻的东西
        if not isinstance(item, dict): 
            continue
            
        title = item.get('title', '无标题')
        link = item.get('url', item.get('link', '#'))
        source = item.get('source_name', item.get('source', '未知来源'))
        
        html_content += f"<li style='margin-bottom: 10px;'><a href='{link}' style='text-decoration: none; color: #0366d6;'>{title}</a> <span style='color: #666; font-size: 12px;'>[{source}]</span></li>"
    
    html_content += "</ul><p><a href='https://github.com/'>点击去 GitHub 查看完整版</a></p>"

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = '【AI News Radar】每日最新 AI 资讯速递'
    msg['From'] = os.environ.get('SENDER_EMAIL')
    msg['To'] = os.environ.get('RECEIVER_EMAIL')

    try:
        server = smtplib.SMTP_SSL(os.environ.get('SMTP_SERVER'), 465)
        server.login(os.environ.get('SENDER_EMAIL'), os.environ.get('SMTP_PASSWORD'))
        server.send_message(msg)
        server.quit()
        print("✅ 邮件发送成功！去邮箱查收吧！")
    except Exception as e:
        print("❌ 发送失败:", e)

if __name__ == "__main__":
    send_daily_news()
