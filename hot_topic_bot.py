#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每小时从百度热搜挑一条新话题，发到树洞。
- 不限制类别：时政、社会、财经、娱乐、国际等都可以
- 仅过滤：违法、色情、暴力血腥、个人隐私、诈骗、谣言
- 同一话题 24 小时内不重复
- 用 Google News RSS 尝试补一句简述；取不到就只发热搜标题
- 不需要登录：树洞发帖只认 nickname，机器人昵称就是“社会热点”

本地试跑（不会发帖）：
    DRY_RUN=1 python hot_topic_bot.py

正式运行：
    SUPABASE_KEY=你的publishable_key python hot_topic_bot.py
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://njpi-forum-api.pages.dev").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
BOT_NICK = os.getenv("BOT_NICK", "社会热点")
DRY_RUN = os.getenv("DRY_RUN", "0").lower() in ("1", "true", "yes")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 最小安全过滤：只挡违法、色情、暴力血腥、隐私、诈骗、谣言
BLOCK = [
    # 色情 / 性暴力
    "色情", "裸", "强奸", "性侵", "嫖", "约炮", "猥亵", "未成年",
    # 暴力血腥
    "杀人", "尸体", "血腥", "肢解", "枪击", "砍人", "爆炸",
    "恐怖袭击", "恐怖主义", "自杀",
    # 违法犯罪
    "毒品", "赌博", "诈骗", "拐卖", "枪支", "爆恐",
    # 个人隐私
    "身份证", "手机号", "家庭住址", "人肉", "开房记录",
    # 谣言 / 不实
    "谣言", "不实信息", "假消息",
]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def baidu_items():
    raw = fetch("https://top.baidu.com/api/board?platform=wise&tab=realtime")
    data = json.loads(raw.decode("utf-8", "replace"))
    items = []
    for card in data.get("data", {}).get("cards", []) or []:
        for block in card.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            nested = block.get("content")
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict) and item.get("word"):
                        items.append(item)
            elif block.get("word"):
                items.append(block)
    return items


def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def google_items():
    """百度不可用时的备用源：Google News 中文 RSS。"""
    try:
        raw = fetch("https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans", timeout=20)
        root = ET.fromstring(raw)
        out = []
        for item in root.iter("item"):
            title = clean_text(item.findtext("title") or "")
            desc = clean_text(item.findtext("description") or "")
            title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
            if title:
                out.append({
                    "word": title,
                    "summary": desc,
                    "url": item.findtext("link") or "",
                })
        return out
    except Exception as exc:
        print("google fallback failed:", exc)
        return []


def google_summary(word):
    """尝试从 Google News RSS 取一句描述，失败就返回空。"""
    try:
        q = urllib.parse.quote(word)
        url = ("https://news.google.com/rss/search?q=" + q +
               "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
        raw = fetch(url, timeout=15)
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            desc = item.findtext("description") or ""
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) >= 12:
                return desc[:120]
    except Exception as exc:
        print("summary skipped:", exc)
    return ""


def recent_posts():
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY is empty")
    nick = urllib.parse.quote(BOT_NICK)
    url = (SUPABASE_URL + "/rest/v1/shouts?select=content&nickname=eq." + nick +
           "&order=created_at.desc&limit=30")
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def post_to_treehole(content):
    url = SUPABASE_URL + "/rest/v1/shouts"
    body = json.dumps([{"content": content, "nickname": BOT_NICK}],
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("posted:", resp.status)


def blocked(text):
    return any(w in text for w in BLOCK)


def main():
    try:
        items = baidu_items()
        source = "百度热搜"
    except Exception as exc:
        print("baidu failed:", exc)
        items = []
        source = "Google News"
    if not items:
        items = google_items()
        source = "Google News"
    print("fetched hot topics:", len(items), "source:", source)
    if not items:
        print("no topics, exit")
        return 0

    if DRY_RUN:
        recent = []
    else:
        try:
            recent = recent_posts()
        except Exception as exc:
            print("cannot read recent posts, exit to avoid duplicates:", exc)
            return 1

    recent_text = "\n".join(str(x.get("content", "")) for x in recent)
    candidates = []
    for item in items:
        word = (item.get("word") or "").strip()
        if not word or blocked(word):
            continue
        if word in recent_text:
            continue
        candidates.append(item)

    if not candidates:
        print("no new topic this hour, skip")
        return 0

    chosen = candidates[0]
    word = clean_text(chosen["word"]).strip()
    summary = chosen.get("summary") or google_summary(word)
    if blocked(summary):
        summary = ""

    lines = ["【社会热点】" + word]
    if summary and summary != word:
        lines.append(summary)
    lines.append("（自动汇总 · 来源：" + source + "）")
    content = "\n".join(lines)[:400]

    print("chosen:", word)
    print("----")
    print(content)
    print("----")

    if DRY_RUN:
        print("DRY_RUN, not posted")
        return 0

    post_to_treehole(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
