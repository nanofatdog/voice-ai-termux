#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voice_tune.py — ปรับ/ลองเสียง TTS แล้วบันทึก (เขียน voice.json ให้ assistant.py อ่าน)

วิธีใช้:
  python3 voice_tune.py                      # ฟังค่าที่ตั้งไว้ปัจจุบัน + ดูตัวช่วย
  python3 voice_tune.py --pitch 1.5          # ลอง pitch (0.5 ต่ำ ... 1.5 แหลม)
  python3 voice_tune.py --rate 1.1           # ลองความเร็ว
  python3 voice_tune.py --variant th-th-x-thd-network   # ลอง variant อื่น
  python3 voice_tune.py --save --pitch 1.3   # ลอง + บันทึกลง voice.json

ตัวอย่าง variant ไทยที่ลองได้:
  th-th-x-thd-network (หญิงมาตรฐาน), th-th-x-thd-local, th-th-x-tll-network,
  th-th-x-phi-local, th-th-x-imm-network
"""
import json
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "voice-assistant")
VOICE_FILE = os.path.join(BASE, "voice.json")

DEFAULT = {
    "engine": "com.google.android.tts",
    "lang": "th",
    "variant": "th-th-x-thd-network",
    "pitch": 1.0,
    "rate": 1.0,
}

TEST_PHRASE = "สวัสดีค่ะ ฉันคือผู้ช่วยเสียงผู้หญิงนะคะ ยินดีที่ได้คุยกับคุณ"


def load():
    if os.path.exists(VOICE_FILE):
        with open(VOICE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        cfg = dict(DEFAULT)
        cfg.update(d)
        return cfg
    return dict(DEFAULT)


def save(cfg):
    with open(VOICE_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"✅ บันทึก voice.json แล้ว: {VOICE_FILE}")


def speak(cfg):
    cmd = ["termux-tts-speak",
           "-e", cfg["engine"], "-l", cfg["lang"],
           "-v", cfg["variant"],
           "-p", str(cfg["pitch"]),
           "-r", str(cfg["rate"]),
           TEST_PHRASE]
    print(f"🔊 ฟัง: pitch={cfg['pitch']} rate={cfg['rate']} variant={cfg['variant']}")
    subprocess.run(cmd, timeout=90)


def main():
    cfg = load()
    args = sys.argv[1:]
    save_it = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--pitch":
            cfg["pitch"] = float(args[i + 1]); i += 1
        elif a == "--rate":
            cfg["rate"] = float(args[i + 1]); i += 1
        elif a == "--variant":
            cfg["variant"] = args[i + 1]; i += 1
        elif a == "--lang":
            cfg["lang"] = args[i + 1]; i += 1
        elif a == "--save":
            save_it = True
        i += 1

    speak(cfg)
    print("\n🧭 แนะนำค่า pitch:")
    print("   0.5 = ทุ้ม/ต่ำ   1.0 = ปกติ   1.3 = หญิงชัด   1.6 = แหลม")
    print("\n💾 พอได้เสียงที่ชอบ รัน: python3 voice_tune.py --save --pitch <ค่า> --rate <ค่า> --variant <ชื่อ>")
    if save_it:
        save(cfg)


if __name__ == "__main__":
    main()
