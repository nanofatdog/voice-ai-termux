#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
record_until_silence.py — บันทึกเสียงจากไมค์ โดยรอจนพูดจบ (VAD แบบ energy)

พฤติกรรม:
  1. รอจนได้ยินเสียงจริง (RMS > threshold → พูด)
  2. พอพูดจบ (เงียบติดต่อกัน ~2.5 วิ = เผื่อช่วงเว้นคำ) → หยุดบันทึก
  3. ตัดเสียงเงียบหัว/ท้าย แล้วบันทึกเป็นไฟล์ WAV (16k mono)

ใช้วิธีเดียวกับ mic_meter: ถอด opus ที่กำลังเขียน → คำนวณระดับเสียง (dB)
+ noise gate ตัดเสียงรบกวนเล็กน้อย

Usage:
  python3 record_until_silence.py out.wav             # เงียบ 2.5 วิ = จบ
  python3 record_until_silence.py out.wav --pad 3.0   # ปรับช่วงเว้น
  python3 record_until_silence.py out.wav --noise -40 # ปรับ threshold เสียงพูด
"""
import array
import math
import os
import subprocess
import sys
import time

SILENCE_PAD = float(os.environ.get("VAD_PAD", "2.5"))      # เงียบนาน = จบ
SPEECH_DB = float(os.environ.get("VAD_SPEECH", "-40"))     # ระดับที่ถือว่า "พูด"
MIN_SPEECH = float(os.environ.get("VAD_MIN_SPEECH", "1.0"))# ต้องมีเสียงยาวเกินนี้ (วิ) ถึงนับเป็นคำพูดจริง
CHUNK_POLL = 0.3                                           # ความถี่ตรวจ
TAIL_SEC = 0.8                                             # ใช้เสียง 0.8 วิหลังสุด
MAX_RECORD = 90                                            # เซฟตี้ไม่ให้เกินนี้

CACHE = os.path.join(os.path.expanduser("~"), ".cache")
RAW = os.path.join(CACHE, "va_recording.opus")
SAMPLE_RATE = 16000


def rms_db(pcm: bytes) -> float:
    """ระดับเสียงเป็น dB จาก PCM 16-bit mono"""
    if not pcm or len(pcm) < 2:
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


def decode_tail(path, tail_sec=TAIL_SEC) -> bytes:
    """ถอด opus → PCM 16k mono แล้วคืนเฉพาะท้าย tail_sec วินาที"""
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


def trim_audio(raw, out_wav):
    """ตัดเสียงเงียบหัว/ท้าย (0.4 วิ) แล้วแปลงเป็น WAV 16k mono"""
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", raw,
        "-af", f"silencedetect=noise={SPEECH_DB - 5:.0f}dB:d=0.4,areverse,"
               f"silencedetect=noise={SPEECH_DB - 5:.0f}dB:d=0.4,areverse",
        "-ac", "1", "-ar", "16000", out_wav,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return os.path.exists(out_wav) and os.path.getsize(out_wav) > 0


def meter_bar(db, width=32):
    ratio = (db + 70.0) / 60.0
    ratio = max(0.0, min(1.0, ratio))
    n = int(ratio * width)
    return "█" * n + "░" * (width - n)


def _release_mic():
    """เรียก -q เพื่อให้ MicRecorderService ปล่อย mic อย่างถูกต้อง
    (timeout กัน -q ค้างตอนไม่มี recording)"""
    try:
        subprocess.run(["termux-microphone-record", "-q"],
                       capture_output=True, timeout=8)
    except Exception:
        pass


def _has_stale_recorder():
    """ตรวจว่ามี recorder/MicRecorder ค้างถือ mic อยู่หรือไม่ (โดยไม่ฆ่า)"""
    try:
        out = subprocess.run(["ps", "-eo", "args"], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        return False
    return any(k in out for k in ("termux-microphone-record", "MicRecorder"))


def _kill_recorders():
    """kill ตัว termux-api ค้างทั้งหมด (MicRecorder/AudioInfo/termux-microphone-record)
    ปลอดภัย: ระบุ PID จาก ps ไม่ใช้ pkill -f (กันโดน shell ตัวเอง)
    ป้องกัน process ค้างถือ mic/audio ที่ทำให้ mic และ TTS ค้าง"""
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        return
    for line in out.splitlines():
        if any(k in line for k in ("termux-microphone-record",
                                   "MicRecorder", "AudioInfo",
                                   "termux-api TTS", "termux-api Tts")):
            parts = line.split()
            if parts:
                try:
                    os.kill(int(parts[0]), 9)
                except Exception:
                    pass


def record_until_silence(out_wav):
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(RAW):
        os.remove(RAW)

    # ปล่อย mic ค้างจากรอบก่อน เฉพาะเมื่อมี recorder ค้าง (กัน -q หน่วงทุกครั้งที่เปิด)
    if _has_stale_recorder():
        _release_mic()
    _kill_recorders()
    time.sleep(0.5)

    rec = subprocess.Popen(
        ["termux-microphone-record", "-d", "-f", RAW, "-l", "0",
         "-r", "16000", "-c", "1", "-e", "opus"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"🎙️  กำลังฟัง... (รอเสียงจริง พูดได้เลย)  [noise gate {SPEECH_DB:.0f}dB, ต้องพูด ≥{MIN_SPEECH:.0f}วิ]", flush=True)

    heard = False          # เคยได้ยินเสียงจริง (ยาวเกิน MIN_SPEECH) แล้ว
    in_speech = False      # กำลังอยู่ในช่วงเสียง
    burst_start = None     # เวลาเริ่มช่วงเสียงปัจจุบัน
    last_speech = None     # เวลาที่เสียงจริงครั้งล่าสุดจบ
    t0 = time.time()

    try:
        while time.time() - t0 < MAX_RECORD:
            db = rms_db(decode_tail(RAW))
            now = time.time()

            # แสดง live meter
            bar = meter_bar(db)
            state = "🔴พูด" if db >= SPEECH_DB else "…"
            sys.stdout.write(f"\r   dB:[{bar}] {db:6.1f}dB  {state}   ")
            sys.stdout.flush()

            if db >= SPEECH_DB:          # มีเสียง (พูด/เสียงดัง)
                if not in_speech:
                    in_speech = True
                    burst_start = now
                last_speech = now
            else:
                # เงียบ — ช่วงเสียงเพิ่งจบ: นับเป็น "เสียงจริง" ถ้ายาวเกิน MIN_SPEECH
                if in_speech:
                    in_speech = False
                    if (now - burst_start) >= MIN_SPEECH:
                        heard = True
                # ถ้าเคยได้ยินเสียงจริงแล้ว และเงียบนานพอ → จบ
                if heard and last_speech is not None:
                    silent_for = now - last_speech
                    if silent_for >= SILENCE_PAD:
                        print(f"\n   ✅ พูดจบ (เงียบ {silent_for:.1f} วิ) — หยุด", flush=True)
                        break

            time.sleep(CHUNK_POLL)
    finally:
        # ปล่อย mic อย่างถูกต้อง (MicRecorderService) แล้วค่อย kill process
        _release_mic()
        try:
            rec.terminate()
            rec.wait(timeout=5)
        except Exception:
            try:
                rec.kill()
            except Exception:
                pass
        _kill_recorders()
        time.sleep(1.0)      # ให้ mic ปล่อยสนิทก่อนรอบถัดไป
        print("", flush=True)

    if not heard:
        print("   ⚠️  ไม่ได้ยินเสียงจริง ไม่บันทึก", flush=True)
        if os.path.exists(RAW):
            os.remove(RAW)
        return False

    ok = trim_audio(RAW, out_wav)
    if os.path.exists(RAW):
        try:
            os.remove(RAW)
        except OSError:
            pass
    if ok:
        print(f"   💾 บันทึก: {out_wav}", flush=True)
    else:
        print(f"   ❌ บันทึกไม่สำเร็จ", flush=True)
    return ok


def main():
    args = sys.argv[1:]
    global SILENCE_PAD, SPEECH_DB, MIN_SPEECH
    out = "speech.wav"
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--pad":
            SILENCE_PAD = float(args[i + 1]); i += 1
        elif a == "--noise":
            SPEECH_DB = float(args[i + 1]); i += 1
        elif a == "--min-speech":
            MIN_SPEECH = float(args[i + 1]); i += 1
        elif not a.startswith("-"):
            out = a
        i += 1
    record_until_silence(out)


if __name__ == "__main__":
    main()
