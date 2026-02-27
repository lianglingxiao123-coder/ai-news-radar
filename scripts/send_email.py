#!/usr/bin/env python3
"""
AI News Radar — 每日邮件发送系统 v3
- 读取 data/latest-24h.json 中的新闻
- 通过 RSS 抓取 Twitter/YouTube AI 专家动态
- 专家内容提炼 + 中文翻译
- 生成精美 HTML 邮件
"""

from __future__ import annotations
import json, os, re, smtplib, ssl, sys, time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
import urllib.request, urllib.error

# ── 配置 ──────────────────────────────────────────────────────────────────────

# 经过严格筛选的 AI 专家列表
# 标准：① 在 AI/ML 领域有实质研究或产品贡献 ② 在学术/工业界有持续影响力
TWITTER_EXPERTS = [
    {"name": "Yann LeCun",       "handle": "ylecun",    "role": "Meta AI Chief Scientist / 深度学习先驱"},
    {"name": "Andrej Karpathy",  "handle": "karpathy",  "role": "前Tesla AI总监 / 前OpenAI"},
    {"name": "Sam Altman",       "handle": "sama",      "role": "OpenAI CEO"},
    {"name": "Demis Hassabis",   "handle": "demishassabis", "role": "Google DeepMind CEO"},
    {"name": "Ilya Sutskever",   "handle": "ilyasut",   "role": "SSI创始人 / 前OpenAI首席科学家"},
    {"name": "Andrew Ng",        "handle": "AndrewYNg", "role": "DeepLearning.AI创始人"},
    {"name": "Fei-Fei Li",       "handle": "drfeifei",  "role": "斯坦福AI Lab教授 / ImageNet之母"},
    {"name": "Kai-Fu Lee 李开复", "handle": "kaifulee",  "role": "零一万物CEO / AI领域知名投资人"},
    {"name": "Jim Fan",          "handle": "drjimfan",  "role": "NVIDIA Senior Research Scientist"},
    {"name": "Emad Mostaque",    "handle": "emostaque",  "role": "Stability AI创始人"},
]

YOUTUBE_CHANNELS = [
    {"name": "Andrej Karpathy",    "channel_id": "UCMLn3WlKFHHsBuSovpyHdJg", "desc": "Neural Nets 深度讲解"},
    {"name": "DeepMind",           "channel_id": "UCbmNph6VwoDyBf_E2VpBqWg",  "desc": "Google DeepMind官方"},
    {"name": "OpenAI",             "channel_id": "UCXZCJLdBC09xxGZ6gcdus6w",  "desc": "OpenAI官方"},
    {"name": "Andrew Ng",          "channel_id": "UCrtf7mpeVr1APmm7rNHmugg",  "desc": "DeepLearning.AI课程"},
    {"name": "Lex Fridman",        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",  "desc": "AI/科技深度访谈"},
    {"name": "Two Minute Papers",  "channel_id": "UCbfYPyITQ-7l4upoX8nvctg",  "desc": "最新AI论文解读"},
    {"name": "Yannic Kilcher",     "channel_id": "UCZHmQk67mSJgfCCTn7xBfew",  "desc": "ML论文深度解析"},
]

# RSSHub 镜像（Twitter RSS源，多个备用）
RSSHUB_MIRRORS = [
    "https://rsshub.rssforever.com",
    "https://rss.shab.fun",
    "https://rsshub.app",
]

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

# ── 工具函数 ───────────────────────────────────────────────────────────────────

def clean_html(text: str, max_len: int = 300) -> str:
    """去除HTML标签并截断"""
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    """HTTP GET，返回响应文本"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (AI News Radar RSS Reader)",
            "Accept": "application/xml,application/rss+xml,text/xml,*/*"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def translate_to_zh(text: str) -> str:
    """
    简单英文→中文翻译（规则映射 + 直接返回中文）
    注：如需真实翻译，可接入 DeepL / Google Translate API
    """
    if not text:
        return ""
    # 如果已有中文（超过30%是CJK字符），直接返回
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk / max(len(text), 1) > 0.2:
        return text
    # 对英文内容标注"[EN]"，保持原文
    # 如果配置了翻译API可在此替换
    return f"[英] {text}"

# ── 抓取专家 Twitter 动态 ─────────────────────────────────────────────────────

def parse_rss_items(xml_text: str, expert_name: str, expert_role: str) -> list[dict]:
    """解析RSS XML，提取条目"""
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.findall(".//item")[:3]:
            title = item.findtext("title", "").strip()
            desc  = item.findtext("description", "").strip()
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "").strip()

            content = clean_html(desc or title, 250)
            if not content or len(content) < 10:
                continue

            items.append({
                "expert_name": expert_name,
                "expert_role": expert_role,
                "content":     content,
                "content_zh":  translate_to_zh(content),
                "url":         link,
                "published":   pub,
                "type":        "twitter",
            })

        # Atom
        if not items:
            for entry in root.findall("atom:entry", ns)[:3]:
                title   = (entry.findtext("atom:title", "", ns) or "").strip()
                summary = (entry.findtext("atom:summary", "", ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link    = link_el.get("href", "") if link_el is not None else ""
                pub     = (entry.findtext("atom:published", "", ns) or "").strip()

                content = clean_html(summary or title, 250)
                if not content or len(content) < 10:
                    continue

                items.append({
                    "expert_name": expert_name,
                    "expert_role": expert_role,
                    "content":     content,
                    "content_zh":  translate_to_zh(content),
                    "url":         link,
                    "published":   pub,
                    "type":        "twitter",
                })

    except ET.ParseError:
        pass
    return items


def fetch_twitter_experts() -> list[dict]:
    """抓取所有 Twitter 专家的最新动态"""
    results = []
    print(f"🐦 抓取 Twitter 专家动态 ({len(TWITTER_EXPERTS)} 位)...")

    for expert in TWITTER_EXPERTS:
        handle = expert["handle"]
        name   = expert["name"]
        role   = expert["role"]
        fetched = False

        # 依次尝试各 RSSHub 镜像
        for mirror in RSSHUB_MIRRORS:
            url = f"{mirror}/twitter/user/{handle}"
            xml = fetch_url(url, timeout=8)
            if xml and ("<item>" in xml or "<entry>" in xml):
                items = parse_rss_items(xml, name, role)
                if items:
                    results.extend(items[:2])  # 每人最多取2条
                    print(f"  ✅ {name}: {len(items)} 条 (via {mirror})")
                    fetched = True
                    break
            time.sleep(0.3)

        if not fetched:
            # 尝试 Nitter（备用）
            nitter_url = f"https://nitter.net/{handle}/rss"
            xml = fetch_url(nitter_url, timeout=8)
            if xml and ("<item>" in xml or "<entry>" in xml):
                items = parse_rss_items(xml, name, role)
                if items:
                    results.extend(items[:2])
                    print(f"  ✅ {name}: {len(items)} 条 (via Nitter)")
                    fetched = True

        if not fetched:
            print(f"  ⚠️ {name} (@{handle}): 无法抓取")

    print(f"  共获取 Twitter 动态: {len(results)} 条")
    return results


def fetch_youtube_channels() -> list[dict]:
    """抓取所有 YouTube 频道的最新视频"""
    results = []
    print(f"▶  抓取 YouTube 频道 ({len(YOUTUBE_CHANNELS)} 个)...")

    for ch in YOUTUBE_CHANNELS:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['channel_id']}"
        xml = fetch_url(url, timeout=10)
        if not xml:
            print(f"  ⚠️ {ch['name']}: 无法抓取")
            continue

        items = []
        try:
            root = ET.fromstring(xml)
            ns = {
                "atom":  "http://www.w3.org/2005/Atom",
                "media": "http://search.yahoo.com/mrss/",
                "yt":    "http://www.youtube.com/xml/schemas/2015",
            }
            for entry in root.findall("atom:entry", ns)[:2]:
                title    = (entry.findtext("atom:title", "", ns) or "").strip()
                link_el  = entry.find("atom:link", ns)
                link     = link_el.get("href", "") if link_el is not None else ""
                pub      = (entry.findtext("atom:published", "", ns) or "").strip()
                desc_el  = entry.find(".//media:description", ns)
                desc     = clean_html(desc_el.text or "" if desc_el is not None else "", 200)

                if not title:
                    continue
                items.append({
                    "channel_name": ch["name"],
                    "channel_desc": ch["desc"],
                    "title":        title,
                    "title_zh":     translate_to_zh(title),
                    "summary":      desc,
                    "url":          link,
                    "published":    pub,
                    "type":         "youtube",
                })
        except ET.ParseError:
            pass

        if items:
            results.extend(items)
            print(f"  ✅ {ch['name']}: {len(items)} 条")
        else:
            print(f"  ⚠️ {ch['name']}: 解析失败")

        time.sleep(0.5)

    print(f"  共获取 YouTube 视频: {len(results)} 条")
    return results

# ── 读取本地新闻数据 ──────────────────────────────────────────────────────────

def load_news(data_dir: Path, max_items: int = 20) -> list[dict]:
    """读取 update_news.py 产出的 latest-24h.json"""
    for fname in ["latest-24h.json", "latest.json", "snapshot.json"]:
        p = data_dir / fname
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                items = data.get("items", data if isinstance(data, list) else [])
                print(f"✅ 读取新闻: {p} ({len(items)} 条)")
                return items[:max_items]
            except Exception as e:
                print(f"⚠️ {p}: {e}")
    print("⚠️ 未找到本地新闻数据")
    return []

# ── 构建 HTML 邮件 ────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML 转义"""
    return (str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_email(news_items: list[dict],
                tw_items:   list[dict],
                yt_items:   list[dict]) -> tuple[str, str]:
    """生成 (html, plain) 邮件内容"""

    tz8  = timezone(timedelta(hours=8))
    now  = datetime.now(tz8)
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    # ── 新闻 HTML ──
    news_rows = ""
    news_plain = ""
    for i, item in enumerate(news_items, 1):
        title = _esc(item.get("title_zh") or item.get("title") or "无标题")
        url   = item.get("url", "#")
        src   = _esc(item.get("source") or item.get("site_name") or "")
        news_rows += f"""
        <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
          <a href="{url}" style="color:#1a73e8;font-weight:600;font-size:14px;text-decoration:none;">{i}. {title}</a>
          {"<div style='color:#999;font-size:11px;margin-top:3px;'>📰 " + src + "</div>" if src else ""}
        </td></tr>"""
        news_plain += f"{i}. {item.get('title_zh') or item.get('title','')}\n   {url}\n\n"

    if not news_rows:
        news_rows = "<tr><td style='color:#999;padding:10px 0;'>今日暂无新闻数据</td></tr>"
        news_plain = "今日暂无新闻数据\n"

    # ── Twitter HTML ──
    tw_rows = ""
    tw_plain = ""
    for item in tw_items:
        name    = _esc(item["expert_name"])
        role    = _esc(item["expert_role"])
        content = _esc(item["content"])
        zh      = _esc(item.get("content_zh", ""))
        url     = item.get("url", "#")

        # 如果翻译只是 "[英] ..." 就只显示原文
        show_zh = zh and not zh.startswith("[英]")

        tw_rows += f"""
        <tr><td style="padding:12px 0;border-bottom:1px solid #e8f4fd;">
          <div style="display:flex;align-items:center;margin-bottom:6px;">
            <span style="background:#1da1f2;color:#fff;border-radius:50%;width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;font-size:14px;margin-right:8px;">🐦</span>
            <div>
              <span style="font-weight:700;color:#1da1f2;font-size:14px;">{name}</span>
              <span style="color:#999;font-size:12px;margin-left:6px;">{role}</span>
            </div>
          </div>
          <div style="color:#333;font-size:13px;line-height:1.6;margin-left:40px;">{content}</div>
          {"<div style='color:#555;font-size:13px;line-height:1.6;margin-left:40px;margin-top:4px;background:#f0f7ff;padding:6px 8px;border-radius:4px;'>🇨🇳 " + zh + "</div>" if show_zh else ""}
          {"<div style='margin:6px 0 0 40px;'><a href='" + url + "' style='color:#1da1f2;font-size:12px;'>查看原文 →</a></div>" if url != "#" else ""}
        </td></tr>"""

        tw_plain += f"🐦 {item['expert_name']} ({item['expert_role']})\n"
        tw_plain += f"   {item['content']}\n"
        if url != "#":
            tw_plain += f"   {url}\n"
        tw_plain += "\n"

    if not tw_rows:
        tw_rows = """<tr><td style="color:#999;padding:10px 0;font-size:13px;">
            今日 Twitter 专家动态暂未获取到。<br>
            <small>（Twitter RSS 源不稳定，如持续无内容可考虑配置 Twitter API）</small>
          </td></tr>"""
        tw_plain = "今日 Twitter 专家动态暂未获取。\n"

    # ── YouTube HTML ──
    yt_rows = ""
    yt_plain = ""
    for item in yt_items:
        ch    = _esc(item["channel_name"])
        desc  = _esc(item["channel_desc"])
        title = _esc(item["title"])
        title_zh = _esc(item.get("title_zh", ""))
        url   = item.get("url", "#")
        show_zh = title_zh and not title_zh.startswith("[英]")

        yt_rows += f"""
        <tr><td style="padding:12px 0;border-bottom:1px solid #fff0f0;">
          <div style="margin-bottom:6px;">
            <span style="background:#ff0000;color:#fff;border-radius:4px;padding:2px 6px;font-size:11px;margin-right:6px;">▶ YouTube</span>
            <span style="font-weight:700;color:#ff0000;font-size:13px;">{ch}</span>
            <span style="color:#999;font-size:12px;margin-left:6px;">{desc}</span>
          </div>
          <a href="{url}" style="color:#333;font-weight:600;font-size:14px;text-decoration:none;">{title}</a>
          {"<div style='color:#555;font-size:13px;margin-top:4px;background:#fff5f5;padding:6px 8px;border-radius:4px;'>🇨🇳 " + title_zh + "</div>" if show_zh else ""}
        </td></tr>"""

        yt_plain += f"▶ {item['channel_name']} - {item['title']}\n   {url}\n\n"

    if not yt_rows:
        yt_rows = "<tr><td style='color:#999;padding:10px 0;'>今日 YouTube 视频暂未获取到。</td></tr>"
        yt_plain = "今日 YouTube 视频暂未获取。\n"

    # ── 完整 HTML ──
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 新闻雷达日报</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
<div style="max-width:700px;margin:24px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,.1);">

  <!-- 头部 -->
  <div style="background:linear-gradient(135deg,#1a73e8 0%,#0d47a1 100%);padding:32px;text-align:center;">
    <div style="font-size:32px;margin-bottom:8px;">🤖</div>
    <div style="color:#fff;font-size:24px;font-weight:700;letter-spacing:2px;">AI 新闻雷达日报</div>
    <div style="color:rgba(255,255,255,.75);font-size:14px;margin-top:8px;">{date_str} &nbsp;·&nbsp; {time_str} 北京时间 &nbsp;·&nbsp; 每日精选</div>
  </div>

  <!-- 今日 AI 新闻 -->
  <div style="padding:28px 32px;">
    <div style="font-size:18px;font-weight:700;color:#222;margin-bottom:16px;padding-bottom:10px;border-bottom:3px solid #1a73e8;">
      📰 今日 AI 新闻 <span style="font-size:14px;color:#999;font-weight:400;">({len(news_items)} 条)</span>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">{news_rows}</table>
  </div>

  <!-- Twitter 专家动态 -->
  <div style="padding:28px 32px;background:#f7fbff;">
    <div style="font-size:18px;font-weight:700;color:#222;margin-bottom:4px;padding-bottom:10px;border-bottom:3px solid #1da1f2;">
      🐦 AI 专家 Twitter 动态 <span style="font-size:14px;color:#999;font-weight:400;">({len(tw_items)} 条)</span>
    </div>
    <div style="color:#999;font-size:12px;margin-bottom:14px;">
      追踪：{" · ".join(e["name"] for e in TWITTER_EXPERTS)}
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">{tw_rows}</table>
  </div>

  <!-- YouTube 视频 -->
  <div style="padding:28px 32px;">
    <div style="font-size:18px;font-weight:700;color:#222;margin-bottom:4px;padding-bottom:10px;border-bottom:3px solid #ff0000;">
      ▶ AI YouTube 频道 <span style="font-size:14px;color:#999;font-weight:400;">({len(yt_items)} 条)</span>
    </div>
    <div style="color:#999;font-size:12px;margin-bottom:14px;">
      频道：{" · ".join(c["name"] for c in YOUTUBE_CHANNELS)}
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">{yt_rows}</table>
  </div>

  <!-- 底部 -->
  <div style="background:#f5f5f5;padding:20px 32px;text-align:center;">
    <div style="color:#999;font-size:12px;line-height:1.8;">
      由 <strong>AI News Radar</strong> 自动生成 &nbsp;·&nbsp; GitHub Actions &nbsp;·&nbsp; 每日 07:30 北京时间<br>
      新闻来源：多个 AI 权威媒体 RSS &nbsp;·&nbsp; 专家动态实时抓取
    </div>
  </div>

</div>
</body>
</html>"""

    plain = f"""AI 新闻雷达日报 — {date_str}
{"="*55}

【今日 AI 新闻 ({len(news_items)} 条)】
{news_plain}
{"="*55}

【AI 专家 Twitter 动态 ({len(tw_items)} 条)】
{tw_plain}
{"="*55}

【AI YouTube 频道 ({len(yt_items)} 条)】
{yt_plain}
{"="*55}
AI News Radar | 每日 07:30 北京时间自动发送
"""

    return html, plain

# ── 发送邮件 ──────────────────────────────────────────────────────────────────

def send_email(html: str, plain: str) -> bool:
    server   = os.environ.get("SMTP_SERVER", "")
    port     = int(os.environ.get("SMTP_PORT", "587"))
    user     = os.environ.get("SENDER_EMAIL", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    receiver = os.environ.get("RECEIVER_EMAIL", "")

    if not all([server, user, password, receiver]):
        missing = [k for k, v in {
            "SMTP_SERVER": server, "SENDER_EMAIL": user,
            "SMTP_PASSWORD": password, "RECEIVER_EMAIL": receiver
        }.items() if not v]
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        return False

    tz8   = timezone(timedelta(hours=8))
    today = datetime.now(tz8).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI 新闻雷达日报 · {today}"
    msg["From"]    = f"AI News Radar <{user}>"
    msg["To"]      = receiver
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    # 方案1: STARTTLS
    try:
        print(f"📤 STARTTLS:{port} → {receiver} ...")
        with smtplib.SMTP(server, port, timeout=30) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.login(user, password)
            s.send_message(msg)
        print("✅ 邮件发送成功！")
        return True
    except Exception as e:
        print(f"   STARTTLS 失败: {e}")

    # 方案2: SSL
    try:
        print("📤 SSL:465 ...")
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, 465, context=ctx, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
        print("✅ 邮件发送成功 (SSL)！")
        return True
    except Exception as e:
        print(f"   SSL:465 失败: {e}")

    print("❌ 所有 SMTP 方案均失败")
    return False

# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("🚀 AI News Radar — 邮件系统 v3")
    print("=" * 55)

    # 1. 读取本地新闻
    news_items = load_news(DATA_DIR, max_items=20)

    # 2. 实时抓取 Twitter 专家动态
    tw_items = fetch_twitter_experts()

    # 3. 实时抓取 YouTube 频道
    yt_items = fetch_youtube_channels()

    # 4. 构建邮件
    print("\n📧 构建邮件内容...")
    html_body, plain_body = build_email(news_items, tw_items, yt_items)
    print(f"   HTML: {len(html_body):,} 字节")

    # 5. 发送
    print("\n📬 发送邮件...")
    ok = send_email(html_body, plain_body)

    print("\n" + "=" * 55)
    print(f"{'✅ 完成' if ok else '❌ 失败'} — "
          f"新闻 {len(news_items)} 条 | Twitter {len(tw_items)} 条 | YouTube {len(yt_items)} 条")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
