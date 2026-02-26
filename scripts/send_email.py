#!/usr/bin/env python3
import json, smtplib, os
from email.mime.text import MIMEText
from datetime import datetime

def extract_and_prioritize_news(data, current_source="未知来源", result=None):
    """改进版新闻提取 - 优先提取 Twitter/YouTube 等重要源"""
    if result is None:
        result = []
        
    if isinstance(data, dict):
        if 'title' in data and ('url' in data or 'link' in data):
            # 判断重要性
            importance = 1  # 默认重要性
            source = data.get('source_name', data.get('source', current_source))
            url = data.get('url', data.get('link', '#')).lower()
            
            # Twitter/Youtube 优先级更高
            if any(word in url or word in source.lower() for word in ['twitter', 'nitter', 'rsshub']):
                importance = 5  # Twitter高优先级
            elif any(word in url or word in source.lower() for word in ['youtube', 'youtu.be']):
                importance = 4  # YouTube次优先级
            elif any(word in source.lower() for word in ['openai', 'deepmind', 'meta', 'google']):
                importance = 3  # 重要公司
            
            result.append({
                'title': data.get('title', '无标题'),
                'link': data.get('url', data.get('link', '#')),
                'source': source,
                'importance': importance,
                'published': data.get('published_at', data.get('published', ''))
            })
        else:
            source_guess = current_source
            if 'name' in data: source_guess = data['name']
            elif 'site_name' in data: source_guess = data['site_name']
            
            for k, v in data.items():
                next_source = k if isinstance(v, list) and isinstance(k, str) else source_guess
                extract_and_prioritize_news(v, next_source, result)
                
    elif isinstance(data, list):
        for item in data:
            extract_and_prioritize_news(item, current_source, result)
            
    return result

def send_daily_news_with_expert_content():
    try:
        with open('data/latest-24h.json', 'r', encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception as e:
        print("读取数据失败:", e)
        return

    all_articles = extract_and_prioritize_news(news_data)

    if not all_articles:
        print("没有找到任何新闻")
        return

    # 按重要性+发布时间排序
    all_articles.sort(key=lambda x: (x['importance'], x['published']), reverse=True)
    
    # 添加专家内容统计
    twitter_count = len([a for a in all_articles if 'twitter' in a['source'].lower() or 'nitter' in a['source'].lower()])
    youtube_count = len([a for a in all_articles if 'youtube' in a['source'].lower() or 'youtu.be' in a['link'].lower()])
    
    # 生成邮件内容
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
            .stats { background: #f8f9fa; border-left: 4px solid #0366d6; padding: 15px; margin-bottom: 25px; }
            .article { border-bottom: 1px solid #eee; padding: 15px 0; }
            .article:last-child { border-bottom: none; }
            .title { font-weight: 500; color: #0366d6; text-decoration: none; font-size: 16px; }
            .title:hover { text-decoration: underline; }
            .meta { color: #6a737d; font-size: 14px; margin-top: 8px; }
            .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 8px; }
            .badge-twitter { background: #1da1f2; color: white; }
            .badge-youtube { background: #ff0000; color: white; }
            .badge-important { background: #28a745; color: white; }
            .section { margin-bottom: 30px; }
        </style>
    </head>
    <body>
    '''
    
    # 标题和统计
    html_content += f'''
    <div class="header">
        <h1>🤖 AI 新闻日报</h1>
        <p>每日AI行业动态 + 专家社群更新</p>
    </div>
    
    <div class="stats">
        <strong>📊 今日数据</strong><br>
        共 {len(all_articles)} 条新闻 | Twitter动态: {twitter_count} | YouTube更新: {youtube_count} | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
    '''
    
    # 专家动态部分（前10条）
    expert_articles = [a for a in all_articles if a['importance'] >= 4]
    if expert_articles:
        html_content += '<div class="section">'
        html_content += '<h3>📢 专家动态</h3>'
        for item in expert_articles[:12]:  # 最多12条专家动态
            badge = ''
            if 'twitter' in item['source'].lower() or 'nitter' in item['source'].lower():
                badge = '<span class="badge badge-twitter">Twitter</span>'
            elif 'youtube' in item['source'].lower() or 'youtu.be' in item['link'].lower():
                badge = '<span class="badge badge-youtube">YouTube</span>'
            
            html_content += f'''
            <div class="article">
                <a class="title" href="{item['link']}" target="_blank">{item['title']}</a> {badge}
                <div class="meta">
                    📍 {item['source']} 
                </div>
            </div>
            '''
        html_content += '</div>'
    
    # 其他新闻（最多20条）
    other_articles = [a for a in all_articles if a['importance'] < 4]
    if other_articles:
        html_content += '<div class="section">'
        html_content += '<h3>📰 其他重要新闻</h3>'
        for item in other_articles[:20]:
            html_content += f'''
            <div class="article">
                <a class="title" href="{item['link']}" target="_blank">{item['title']}</a>
                <div class="meta">
                    📍 {item['source']}
                </div>
            </div>
            '''
        html_content += '</div>'
    
    html_content += '''
    <hr style="margin: 30px 0;">
    <p style="color: #888; font-size: 14px;">
        这是自动生成的AI新闻日报。<br>
        查看完整版: <a href="https://lianglingxiao123-coder.github.io/ai-news-radar/">AI News Radar</a><br>
        如需退订或反馈，请回复此邮件。
    </p>
    </body>
    </html>
    '''
    
    # 发送邮件
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = f'【AI日报】{datetime.now().strftime("%m/%d")} - {len(all_articles)}条新闻 + {twitter_count}条专家动态'
    msg['From'] = os.environ.get('SENDER_EMAIL')
    msg['To'] = os.environ.get('RECEIVER_EMAIL')
    
    try:
        server = smtplib.SMTP_SSL(os.environ.get('SMTP_SERVER'), 465)
        server.login(os.environ.get('SENDER_EMAIL'), os.environ.get('SMTP_PASSWORD'))
        server.send_message(msg)
        server.quit()
        print(f"✅ 邮件发送成功！包含 {len(expert_articles)} 条专家动态")
    except Exception as e:
        print("❌ 发送失败:", e)

if __name__ == "__main__":
    send_daily_news_with_expert_content()