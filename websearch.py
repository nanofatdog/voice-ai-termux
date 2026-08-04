#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
websearch.py — ค้นเว็บ/ข่าว จากเครื่อง (ไม่ต้อง API key, ไม่โดน captcha)

backend:
  - Google News RSS  (ข่าว/เรื่องล่าสุด)  — หลัก
  - Wikipedia API    (ข้อเท็จจริง/แนวคิด) — fallback

Usage:
  python3 websearch.py "AI news"          # ค้นข่าว
  python3 websearch.py --date             # แสดงวันที่วันนี้
"""
import html
import json
import re
import subprocess
import sys
import urllib.parse


def _curl(url, timeout=15):
    try:
        proc = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), "-A",
             "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
             url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        return proc.stdout
    except Exception:
        return ""


def _rss_items(rss):
    """parse RSS → list ของ {title, url, source, desc}"""
    items = re.findall(r"<item>(.*?)</item>", rss, re.S)
    out = []
    for it in items:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
        d = re.search(r"<description>(.*?)</description>", it, re.S)
        title = html.unescape(t.group(1)).strip() if t else ""
        url = html.unescape(l.group(1)).strip() if l else ""
        source = html.unescape(src.group(1)).strip() if src else ""
        desc = re.sub(r"<[^>]+>", "", html.unescape(d.group(1))).strip() if d else ""
        if title and url:
            out.append({"title": title, "url": url, "source": source, "snippet": desc[:200]})
    return out


def search(query, n=5, lang="th"):
    """ค้นข่าว/เว็บ ผ่าน Google News RSS"""
    # ถ้า query ไทย → ค้นไทย, อังกฤษ → ค้นอังกฤษ
    hl, gl, ceid = ("th", "TH", "TH:th") if lang == "th" else ("en-US", "US", "US:en")
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query) +
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    rss = _curl(url)
    items = _rss_items(rss)
    # ตัด item แรกที่เป็นชื่อเรื่องตัวเองออก (Google News ลง title ซ้ำ)
    if items and items[0]["title"].lower().startswith(query.lower()[:15]):
        items = items[1:]
    return items[:n]


def wiki_search(query, n=3):
    """ค้น Wikipedia (ข้อเท็จจริง/แนวคิด)"""
    url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=" +
           urllib.parse.quote(query) + "&srlimit=" + str(n) + "&format=json")
    data = _curl(url)
    try:
        d = json.loads(data)
        out = []
        for r in d.get("query", {}).get("search", []):
            out.append({
                "title": r.get("title", ""),
                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(r.get("title", "").replace(" ", "_")),
                "snippet": re.sub(r"<[^>]+>", "", r.get("snippet", "")).replace("&quot;", "\""),
                "source": "Wikipedia",
            })
        return out
    except Exception:
        return []


def smart_search(query, n=5):
    """ตัดสินใจอัตโนมัติ: ข่าว/เหตุการณ์ล่าสุด → Google News, แนวคิด/ข้อเท็จจริง → Wikipedia"""
    q = query.lower()
    news_words = ("news", "ข่าว", "today", "วันนี้", "ล่าสุด", "latest", "headline",
                  "เกิด", "ราคา", "stock", "weather", "สภาพอากาศ", "election",
                  "trump", "biden", "stock market", "crypto", "bitcoin")
    if any(w in q for w in news_words):
        return search(query, n)
    # ลอง Google News ก่อน, ถ้าไม่ได้ผล → Wikipedia
    res = search(query, n)
    if res:
        return res
    return wiki_search(query, n)


def format_results(results):
    lines = []
    for i, r in enumerate(results, 1):
        src = f" ({r.get('source')})" if r.get("source") else ""
        lines.append(f"{i}. {r['title']}{src}")
        lines.append(f"   {r['url']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:200]}")
    return "\n".join(lines)


def today():
    from datetime import datetime
    return datetime.now().strftime("%A %d %B %Y (%H:%M)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--date":
        print(today())
    else:
        q = sys.argv[1] if len(sys.argv) > 1 else "ข่าววันนี้"
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        print(f"📅 วันนี้: {today()}")
        print(f"🔎 ค้นหา: {q}\n")
        res = smart_search(q, n)
        if res:
            print(format_results(res))
        else:
            print("(ไม่พบผลลัพธ์)")
