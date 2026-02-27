#!/usr/bin/env python3
"""
AI News Radar - 完整邮件发送系统
整合 RSS新闻 + Twitter + YouTube 内容
"""

import json
import smtplib
import os
import ssl
import re
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ───────────────────────────────────────────────
# 1. 读取新闻数据
# ───────────────────────────────────────────────

def load_news_data(data_dir: str = "data") -> dict:
    """尝试读取 update_news.py 产出的 JSON 文件"""
    candidates = [
        Path(data_dir) / "latest-24h.json",
        Path(data_dir) / "latest.json",
        Path(data_dir) / "snapshot.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                print(f"✅ 读取新闻数据: {path} ({data.get('total_items', '?')} 条)")
                return data
            except Exception as e:
                print(f"⚠️ 读取 {path} 失败: {e}")
    print("⚠️ 未找到新闻数据文件，使用空数据")
    return {"items": [], "total_items": 0}


# ───────────────────────────────────────────────
# 2. 读取 Twitter/YouTube 动态
# ───────────────────────────────────────────────

def load_social_data(data_dir: str = "data") -> dict:
    """读取社交媒体数据（Twitter/YouTube）"""
    social = {"twitter": [], "youtube": []}

    # Twitter 数据
    twitter_files = [
        Path(data_dir) / "twitter.json",
        Path(data_dir) / "twitter-latest.json",
        Path(data_dir) / "social.json",
    ]
    for path in twitter_files:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    tw_data = json.load(f)
                if isinstance(tw_data, list):
                    social["twitter"] = tw_data
                elif isinstance(tw_data, dict):
                    social["twitter"] = tw_data.get("twitter", tw_data.get("items", []))
                print(f"✅ 读取 Twitter 数据: {len(social['twitter'])} 条")
                break
            except Exception as e:
                print(f"⚠️ 读取 Twitter 数据失败: {e}")

    # YouTube 数据
    youtube_files = [
        Path(data_dir) / "youtube.json",
        Path(data_dir) / "youtube-latest.json",
    ]
    for path in youtube_files:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    yt_data = json.load(f)
                if isinstance(yt_data, list):
                    social["youtube"] = yt_data
                elif isinstance(yt_data, dict):
                    social["youtube"] = yt_data.get("youtube", yt_data.get("items", []))
                print(f"✅ 读取 YouTube 数据: {len(social['youtube'])} 条")
                break
            except Exception as e:
                print(f"⚠️ 读取 YouTube 数据失败: {e}")

    # 如果没有社交数据文件，尝试从 news data 中提取
    if not social["twitter"] and not social["youtube"]:
        news_data = load_news_data(data_dir)
        items = news_data.get("items", [])
        for item in items:
            source = str(item.get("source", "")).lower()
            url = str(item.get("url", item.get("link", ""))).lower()
            if "twitter" in source or "twitter.com" in url or "x.com" in url:
                social["twitter"].append(item)
            elif "youtube" in source or "youtube.com" in url or "youtu.be" in url:
                social["youtube"].append(item)
        if social["twitter"]:
            print(f"  从新闻数据中提取到 {len(social['twitter'])} 条 Twitter 内容")
        if social["youtube"]:
            print(f"  从新闻数据中提取到 {len(social['youtube'])} 条 YouTube 内容")

    return social


# ───────────────────────────────────────────────
# 3. 渲染 HTML 邮件
# ───────────────────────────────────────────────

def _clean(text: str, max_len: int = 200) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def build_html_email(news_data: dict, social_data: dict) -> tuple[str, str]:
    """生成 HTML + 纯文本邮件，返回 (html, plain)"""

    tz_cn = timezone(timedelta(hours=8))
    now = datetime.now(tz_cn)
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    items = news_data.get("items", [])
    tw_items = social_data.get("twitter", [])[:10]
    yt_items = social_data.get("youtube", [])[:5]

    # ── RSS 新闻部分 ──────────────────────────────
    rss_html = ""
    rss_plain = ""
    if items:
        for i, item in enumerate(items[:15], 1):
            title = _clean(item.get("title", "无标题"), 100)
            summary = _clean(item.get("summary", item.get("description", "")), 180)
            url = item.get("url", item.get("link", "#"))
            source = _clean(item.get("source", item.get("feed_title", "未知来源")), 50)

            rss_html += f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
                <a href="{url}" style="color:#1a73e8;text-decoration:none;font-weight:600;font-size:14px;">{i}. {title}</a>
                <div style="color:#888;font-size:12px;margin:4px 0 0 12px;">📰 {source}</div>
                {"<div style='color:#555;font-size:13px;margin:6px 0 0 12px;'>" + summary + "</div>" if summary else ""}
              </td>
            </tr>"""
            rss_plain += f"{i}. {title}\n   来源: {source}\n"
            if summary:
                rss_plain += f"   {summary}\n"
            rss_plain += f"   🔗 {url}\n\n"
    else:
        rss_html = "<tr><td style='color:#888;padding:10px 0;'>今日暂无 RSS 新闻数据。</td></tr>"
        rss_plain = "今日暂无 RSS 新闻数据。\n"

    # ── Twitter 部分 ──────────────────────────────
    tw_html = ""
    tw_plain = ""
    if tw_items:
        for item in tw_items:
            author = _clean(item.get("author", item.get("username", item.get("name", ""))), 40)
            text = _clean(item.get("text", item.get("content", item.get("summary", ""))), 200)
            url = item.get("url", item.get("link", "#"))
            tw_html += f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
                <span style="color:#1da1f2;font-weight:bold;">🐦 @{author}</span>
                <div style="color:#333;font-size:13px;margin:6px 0 0 8px;">{text}</div>
                {"<div style='margin:4px 0 0 8px;'><a href='" + url + "' style='color:#1a73e8;font-size:12px;'>查看原文</a></div>" if url != "#" else ""}
              </td>
            </tr>"""
            tw_plain += f"🐦 @{author}: {text}\n"
            if url != "#":
                tw_plain += f"   {url}\n"
            tw_plain += "\n"
    else:
        tw_html = "<tr><td style='color:#888;padding:10px 0;'>今日暂无 Twitter 动态数据。<br><small>（如需接入请在 secrets 中配置 TWITTER_BEARER_TOKEN）</small></td></tr>"
        tw_plain = "今日暂无 Twitter 动态数据。\n"

    # ── YouTube 部分 ──────────────────────────────
    yt_html = ""
    yt_plain = ""
    if yt_items:
        for item in yt_items:
            title = _clean(item.get("title", ""), 100)
            channel = _clean(item.get("channel", item.get("author", "")), 50)
            url = item.get("url", item.get("link", "#"))
            summary = _clean(item.get("summary", item.get("description", "")), 150)
            yt_html += f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
                <a href="{url}" style="color:#ff0000;text-decoration:none;font-weight:600;font-size:14px;">▶ {title}</a>
                {"<div style='color:#888;font-size:12px;margin:4px 0 0 12px;'>📺 " + channel + "</div>" if channel else ""}
                {"<div style='color:#555;font-size:13px;margin:6px 0 0 12px;'>" + summary + "</div>" if summary else ""}
              </td>
            </tr>"""
            yt_plain += f"▶ {title}\n"
            if channel:
                yt_plain += f"   频道: {channel}\n"
            yt_plain += f"   {url}\n\n"
    else:
        yt_html = "<tr><td style='color:#888;padding:10px 0;'>今日暂无 YouTube 视频数据。<br><small>（如需接入请配置 YOUTUBE_API_KEY）</small></td></tr>"
        yt_plain = "今日暂无 YouTube 视频数据。\n"

    # ── 完整 HTML ──────────────────────────────────
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
<div style="max-width:680px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">

  <!-- 头部 -->
  <div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:28px 32px;text-align:center;">
    <div style="color:#fff;font-size:28px;font-weight:700;letter-spacing:1px;">🤖 AI 新闻雷达</div>
    <div style="color:rgba(255,255,255,.8);font-size:14px;margin-top:6px;">{date_str} · {time_str} · 每日精选</div>
  </div>

  <!-- RSS 新闻 -->
  <div style="padding:24px 32px;">
    <div style="font-size:18px;font-weight:700;color:#333;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #1a73e8;">
      📰 今日 AI 新闻 ({len(items)} 条)
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {rss_html}
    </table>
  </div>

  <!-- Twitter -->
  <div style="padding:24px 32px;background:#f9fdff;">
    <div style="font-size:18px;font-weight:700;color:#333;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #1da1f2;">
      🐦 AI 专家 Twitter 动态 ({len(tw_items)} 条)
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {tw_html}
    </table>
  </div>

  <!-- YouTube -->
  <div style="padding:24px 32px;">
    <div style="font-size:18px;font-weight:700;color:#333;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #ff0000;">
      ▶ AI 相关 YouTube 视频 ({len(yt_items)} 条)
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {yt_html}
    </table>
  </div>

  <!-- 底部 -->
  <div style="background:#f5f5f5;padding:16px 32px;text-align:center;color:#999;font-size:12px;">
    由 AI News Radar 自动生成 · GitHub Actions · 每日 07:30 (北京时间)
  </div>

</div>
</body>
</html>"""

    plain = f"""AI 新闻雷达 - {date_str}
{"="*50}

【今日 AI 新闻】
{rss_plain}

【AI 专家 Twitter 动态】
{tw_plain}

【AI 相关 YouTube 视频】
{yt_plain}

--
由 AI News Radar 自动生成 | 每日 07:30 北京时间
"""

    return html, plain


# ───────────────────────────────────────────────
# 4. 发送邮件
# ───────────────────────────────────────────────

def send_email(html: str, plain: str) -> bool:
    smtp_server  = os.environ.get("SMTP_SERVER", "")
    smtp_port    = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ.get("SENDER_EMAIL", "")
    smtp_password= os.environ.get("SMTP_PASSWORD", "")
    receiver_email = os.environ.get("RECEIVER_EMAIL", "")

    if not all([smtp_server, sender_email, smtp_password, receiver_email]):
        print("❌ 缺少 SMTP 环境变量配置")
        print(f"   SMTP_SERVER   : {'✓' if smtp_server else '✗'}")
        print(f"   SENDER_EMAIL  : {'✓' if sender_email else '✗'}")
        print(f"   SMTP_PASSWORD : {'✓' if smtp_password else '✗'}")
        print(f"   RECEIVER_EMAIL: {'✓' if receiver_email else '✗'}")
        return False

    tz_cn = timezone(timedelta(hours=8))
    today = datetime.now(tz_cn).strftime("%Y-%m-%d")
    subject = f"🤖 AI 新闻雷达日报 · {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"AI News Radar <{sender_email}>"
    msg["To"]      = receiver_email
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    errors = []

    # 方案1: STARTTLS 587
    try:
        print(f"📤 尝试 STARTTLS:{smtp_port} ...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(sender_email, smtp_password)
            s.send_message(msg)
        print(f"✅ 邮件已发送 → {receiver_email}")
        return True
    except Exception as e:
        errors.append(f"STARTTLS:{smtp_port} → {e}")

    # 方案2: SSL 465
    try:
        print("📤 尝试 SSL:465 ...")
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, 465, context=ctx, timeout=30) as s:
            s.login(sender_email, smtp_password)
            s.send_message(msg)
        print(f"✅ 邮件已发送 (SSL:465) → {receiver_email}")
        return True
    except Exception as e:
        errors.append(f"SSL:465 → {e}")

    print("❌ 所有 SMTP 方案均失败：")
    for err in errors:
        print(f"   {err}")
    return False


# ───────────────────────────────────────────────
# 5. 入口
# ───────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 AI News Radar — 邮件发送系统")
    print("=" * 50)

    data_dir = os.environ.get("DATA_DIR", "data")

    news_data   = load_news_data(data_dir)
    social_data = load_social_data(data_dir)

    html_body, plain_body = build_html_email(news_data, social_data)

    ok = send_email(html_body, plain_body)
    sys.exit(0 if ok else 1)
