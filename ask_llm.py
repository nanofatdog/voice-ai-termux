#!/usr/bin/env python3
# ============================================================
# ask_llm.py — ส่งข้อความไปถาม LLM แล้วพิมพ์คำตอบ
#
# ใช้ API แบบ OpenAI-compatible ที่ http://YOUR_LLM_HOST:PORT/v1 (ตั้ง LLM_BASE env)
# (เครื่อง server ของ Gemma-4-E4B)
#
# วิธีใช้:
#   python3 ask_llm.py "สวัสดี"                  # ถาม 1 คำถาม
#   echo "สวัสดี" | python3 ask_llm.py -          # อ่านจาก stdin
# ============================================================
import json
import sys
import os
import urllib.request

BASE_URL = os.environ.get("LLM_BASE", "http://YOUR_LLM_HOST:PORT/v1")
MODEL = os.environ.get("LLM_MODEL", "/models/your-multimodal-model.gguf")
SYSTEM_PROMPT = (
    "คุณคือผู้ช่วย AI ที่เป็นมิตร พูดภาษาไทย อธิบายให้กระชับ เข้าใจง่าย"
)

def ask_llm(user_text: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }
    last = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            last = data["choices"][0]["message"]["content"].strip()
            if last:
                return last
        except Exception:
            pass  # ลองใหม่
    return last

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        question = " ".join(sys.argv[1:])
    else:
        question = sys.stdin.read().strip()
    if not question:
        print("❌ ใส่คำถามด้วย เช่น: python3 ask_llm.py \"สวัสดี\"")
        sys.exit(1)
    try:
        answer = ask_llm(question)
        if answer:
            print(answer)
        else:
            print("❌ LLM คืนค่าว่าง (ลองใหม่อีกที)", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"❌ เรียก LLM ไม่สำเร็จ: {e}", file=sys.stderr)
        sys.exit(1)
