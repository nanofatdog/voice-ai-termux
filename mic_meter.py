#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mic_meter.py — แสดงระดับเสียงจากไมค์แบบ real-time (VU meter) + noise gate

วิธีใช้ (รันบนเครื่องเอง):
  python3 mic_meter.py              # แสดงระดับเสียงสด กด Ctrl-C เพื่อจบ
  python3 mic_meter.py 10           # แสดง 10 วินาทีแล้วจบ
  python3 mic_meter.py --noise -45  # ตั้งระดับ noise gate (dB) ยิ่งติดลบ = ตัดน้อย
  python3 mic_meter.py --out x.wav  # บันทึกเสียงไปด้วย

เมื่อพี่พูด บาร์จะพุ่งขึ้น (สีเขียว) / เงียบจะหดลง (สีเทา)
เสียงรบกวนเล็กน้อยถูกตัด (noise gate) — ไม่แสดงเป็น "เสียง"
"""
import array
import math
import os
import subprocess
import sys
import time

SAMPLE_RATE = 16000
CHUNK = 0.25          # อัปเดตทุก 0.25 วิ
TAIL = 0.5            # ใช้เสียง 0.5 วิหลังสุดในการคำนวณระดับ
NOISE_DB = float(os.environ.get("NOISE_GATE", "-45"))   # noise gate

REC = os.path.join(os.path.expanduser("~"), ".cache", "meter_rec.aac")
os.makedirs(os.path.dirname(REC), exist_ok=True)


def rms_db(pcm: bytes):
    """ระดับเสียงเป็น dB จาก PCM 16-bit"""
    if len(pcm) < 2:
        return -99.0
    a = array.array("h", pcm)
    n = len(a)
    if n == 0:
        return -99.0
    ss = 0
    for s in a:
        ss += s * s
    rms = math.sqrt(ss / n)
    if rms == 0:
        return -99.0
    return 20.0 * math.log10(rms / 32768.0)


def meter_bar(db, width=40):
    """แปลง dB → บาร์กราฟ"""
    # แมปช่วง -70..-10 dB → 0..width
    ratio = (db + 70.0) / 60.0
    ratio = max(0.0, min(1.0, ratio))
    n = int(ratio * width)
    return "█" * n + "░" * (width - n)


def decode_tail(path, tail_sec=TAIL):
    """ถอดเสียงเป็น PCM 16k mono แล้วคืนเฉพาะท้าย (tail_sec วินาที)"""
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        return b""
    cmd = ["ffmpeg", "-v", "error", "-i", path,
           "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=10).stdout
    except Exception:
        return b""
    nbytes = int(SAMPLE_RATE * 2 * tail_sec)
    return out[-nbytes:] if len(out) >= nbytes else out


def main():
    duration = None
    out_wav = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--noise":
            global NOISE_DB
            NOISE_DB = float(args[i + 1]); i += 1
        elif a == "--out":
            out_wav = args[i + 1]; i += 1
        elif a.isdigit():
            duration = int(a)
        i += 1

    if os.path.exists(REC):
        os.remove(REC)

    rec = subprocess.Popen(
        ["termux-microphone-record", "-d", "-f", REC, "-l", "0",
         "-r", str(SAMPLE_RATE), "-c", "1", "-e", "opus"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    print("🎙️  ระดับเสียงสด (noise gate = %.0f dB) — พูดเลย! Ctrl-C = จบ" % NOISE_DB)
    print("    (เงียบ/เสียงรบกวน = ░  |  พูด = █  |  เสียงดัง = 🔴)\n")
    print(f"   dB: {'   ' * 9} [-70 .. -10]")
    print("=" * 60, flush=True)

    start = time.time()
    try:
        while duration is None or (time.time() - start) < duration:
            pcm = decode_tail(REC)
            db = rms_db(pcm)

            if db < NOISE_DB:
                # noise gate: ไม่ใช่เสียงพูด
                label = "เงียบ/รบกวน"
                color = "\033[90m"   # เทา
            elif db < -30:
                label = "พูดเบา"
                color = "\033[32m"   # เขียว
            elif db < -15:
                label = "พูด"
                color = "\033[33m"   # เหลือง
            else:
                label = "เสียงดัง!"
                color = "\033[31m"   # แดง

            bar = meter_bar(db)
            reset = "\033[0m"
            sys.stdout.write(f"\r  {color}{bar}{reset}  {db:6.1f} dB  {label}   ")
            sys.stdout.flush()
            time.sleep(CHUNK)
    except KeyboardInterrupt:
        pass
    finally:
        rec.terminate()
        try:
            rec.wait(timeout=5)
        except Exception:
            rec.kill()
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)

    # บันทึกเสียง (ถ้าต้องการ)
    if out_wav:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", REC,
                        "-ar", "16000", "-ac", "1", out_wav],
                       capture_output=True, timeout=30)
        print(f"\n✅ บันทึก: {out_wav}")

    if os.path.exists(REC):
        try:
            os.remove(REC)
        except OSError:
            pass
    print("\nจบการทดสอบ")


if __name__ == "__main__":
    main()
