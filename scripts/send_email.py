import json, smtplib, os
from email.mime.text import MIMEText

# 这是一个自动拆“俄罗斯套娃”的超级搜索功能
def extract_news(data, current_source="未知来源", result=None):
    if result is None:
        result = []
        
    if isinstance(data, dict):
        # 如果这个字典里既有标题(title)，又有链接(url或link)，说明我们终于找到了最底层的一篇新闻！
        if 'title' in data and ('url' in data or 'link' in data):
            result.append({
                'title': data.get('title', '无标题'),
                'link': data.get('url', data.get('link', '#')),
                'source': data.get('source_name', data.get('source', current_source))
            })
        else:
            # 如果还不是新闻，就继续往下拆。顺便把外包装上的名字当作来源记下来。
            source_guess = current_source
            if 'name' in data: source_guess = data['name']
            elif 'site_name' in data: source_guess = data['site_name']
            elif 'source' in data and isinstance(data['source'], str): source_guess = data['source']
            
            for k, v in data.items():
                # 如果这一层是个列表，外面的名字很可能就是新闻来源（比如 "TechURLs"）
                next_source = k if isinstance(v, list) and isinstance(k, str) else source_guess
                extract_news(v, next_source, result)
                
    elif isinstance(data, list):
        # 如果是个列表，就把里面的盒子挨个拿出来继续拆
        for item in data:
            extract_news(item, current_source, result)
            
    return result

def send_daily_news():
    try:
        with open('data/latest-24h.json', 'r', encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception as e:
        print("读取数据失败:", e)
        return

    # 使用我们的终极搜索功能，把所有隐藏的新闻全部挖出来
    all_articles = extract_news(news_data)

    if not all_articles:
        print("箱子拆完了，但是没有找到任何带标题的新闻。")
        return

    html_content = "<h2>🤖 你的 AI 资讯每日推送</h2><ul>"
    
    # 抓取前 30 条新闻发送
    for item in all_articles[:30]:
        title = item['title']
        link = item['link']
        source = item['source']
        html_content += f"<li style='margin-bottom: 12px;'><a href='{link}' style='text-decoration: none; color: #0366d6; font-weight: bold;'>{title}</a> <br><span style='color: #888; font-size: 13px;'>来源: {source}</span></li>"
    
    html_content += "</ul><p style='margin-top: 20px;'><a href='https://github.com/'>点击去 GitHub 查看完整版</a></p>"

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = '【AI News Radar】每日最新 AI 资讯速递'
    msg['From'] = os.environ.get('SENDER_EMAIL')
    msg['To'] = os.environ.get('RECEIVER_EMAIL')

    try:
        server = smtplib.SMTP_SSL(os.environ.get('SMTP_SERVER'), 465)
        server.login(os.environ.get('SENDER_EMAIL'), os.environ.get('SMTP_PASSWORD'))
        server.send_message(msg)
        server.quit()
        print("✅ 完美！带有正确标题和来源的邮件发送成功！")
    except Exception as e:
        print("❌ 发送失败:", e)

if __name__ == "__main__":
    send_daily_news()
