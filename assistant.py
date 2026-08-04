#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant.py — AI คุยได้ด้วยเสียง ตัวเดียวทำได้หมด (ทั้งหมดรวมในสคริปต์เดียว)

ความสามารถ:
  🎙️  ฟังเสียง (VAD รอจนพูดจบ, ใช้ Opus) + แสดง live level meter
  🧠  ส่ง WAV ตรงให้ model multimodal — ไม่ต้อง STT
  🔎  Web Search (tool calling) — ถามข่าว/ข้อมูลล่าสุด model จะค้นให้
  💾  Session (--new / -c) เก็บ jsonl เหมือน session agent
  📉  Context >70% → compress เหลือ ~30-40% (สรุปด้วย LLM)
  🔊  TTS เสียงผู้หญิงไทยคนเดียวตลอด (ล็อก variant + pitch)

Usage:
  python3 assistant.py --new          # เริ่ม session ใหม่
  python3 assistant.py -c             # ต่อ session ล่าสุด
  python3 assistant.py                # ต่อ session ล่าสุด (เหมือน -c)
  python3 assistant.py --text \"...\"   # โหมดพิมพ์ (ไม่ใช้ไมค์)
  python3 assistant.py --no-web       # ปิด web search (คุยธรรมดา)
  python3 assistant.py --ctx 8192     # ตั้ง context window
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

import websearch

HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "voice-assistant")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
LLM_BASE = os.environ.get("LLM_BASE", "http://YOUR_LLM_HOST:PORT/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "/models/gemma-4-E4B-it-heretic-IQ4_NL-imatrix.gguf")
CONTEXT_WINDOW = int(os.environ.get("LLM_CTX", "8192"))
COMPRESS_AT = 0.70
COMPRESS_TARGET = 0.35
RECENT_KEEP = 6
WAV_PATH = os.path.join(BASE_DIR, "speech.wav")

TODAY_STR = websearch.today()

# ---- เสียง TTS: ล็อกเป็นผู้หญิงไทยคนเดียวตลอด (อ่านจาก voice.json ถ้ามี) ----
TTS_ENGINE = "com.google.android.tts"
TTS_VARIANT = "th-th-x-thd-network"   # เสียงผู้หญิงไทย (Google)
TTS_PITCH = "1.3"                     # pitch สูง = เสียงหญิงชัด
TTS_RATE = "1.0"


def _load_voice():
    """โหลดค่าสียงจาก voice.json (ถ้ามี) มาแทนค่า default"""
    global TTS_ENGINE, TTS_VARIANT, TTS_PITCH, TTS_RATE
    vf = os.path.join(BASE_DIR, "voice.json")
    if os.path.exists(vf):
        try:
            with open(vf, encoding="utf-8") as f:
                d = json.load(f)
            TTS_ENGINE = d.get("engine", TTS_ENGINE)
            TTS_VARIANT = d.get("variant", TTS_VARIANT)
            TTS_PITCH = str(d.get("pitch", float(TTS_PITCH)))
            TTS_RATE = str(d.get("rate", float(TTS_RATE)))
        except Exception:
            pass

SYSTEM_PROMPT = (
    "คุณคือผู้ช่วย AI ผู้หญิง พูดภาษาไทย กระชับ สั้น เหมาะกับเสียง "
    f"วันนี้คือ {TODAY_STR} "
    "ถ้าผู้ใช้ถามข่าว/ข้อมูลล่าสุด/เหตุการณ์ปัจจุบัน ให้เรียก web_search "
    "แล้วสรุปจากผลลัพธ์เป็นภาษาไทย กระชับ ระบุแหล่งที่มา"
)

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "ค้นหาข้อมูลล่าสุด/ข่าว/เหตุการณ์ปัจจุบันจากอินเทอร์เน็ต ใช้เมื่อผู้ใช้ถามข่าววันนี้ ข้อมูลล่าสุด หรือสิ่งที่เกินความรู้",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "คำค้นหา (ภาษาเดียวกับคำถาม)"}
            },
            "required": ["query"],
        },
    },
}

EXIT_WORDS = {"exit", "ออก", "ลาก่อน", "bye", "จบ", "พอแล้ว"}


# ==================== LLM (tool calling + audio) ====================
def _post(payload, timeout=300):
    req = urllib.request.Request(
        f"{LLM_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _audio_content(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return [{"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}]


def agent_chat(messages, user_text=None, audio_path=None, use_web=True,
               max_tokens=900, max_rounds=4, temperature=0.5):
    """agent loop: ส่ง → ถ้า model เรียก web_search → ค้น → เอาผลกลับ → จนได้คำตอบ"""
    cur = list(messages)
    if audio_path:
        cur.append({"role": "user", "content": _audio_content(audio_path)})
    elif user_text:
        cur.append({"role": "user", "content": user_text})

    payload_base = {
        "model": LLM_MODEL,
        "max_tokens": max_tokens, "temperature": temperature,
        "reasoning_effort": "none",
    }
    if use_web:
        payload_base["tools"] = [WEB_SEARCH_TOOL]

    last_answer = ""
    for rnd in range(max_rounds):
        payload = dict(payload_base)
        payload["messages"] = cur
        try:
            d = _post(payload)
        except Exception as e:
            print(f"   ⚠️  LLM error ({e}) — ลองใหม่...", file=sys.stderr)
            time.sleep(1)
            continue
        msg = d["choices"][0]["message"]
        tcs = msg.get("tool_calls") if use_web else None

        if tcs:
            cur.append({
                "role": "assistant", "content": msg.get("content") or "",
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["function"]["name"],
                                  "arguments": tc["function"]["arguments"]}}
                    for tc in tcs
                ],
            })
            for tc in tcs:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"   🔎 [tool] {fn}({args.get('query','')})", file=sys.stderr, flush=True)
                if fn == "web_search":
                    results = websearch.smart_search(args.get("query", ""), 5)
                    result_text = websearch.format_results(results) or "(ไม่พบผลลัพธ์)"
                else:
                    result_text = f"(unknown tool {fn})"
                cur.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})
            continue

        last_answer = (msg.get("content") or "").strip()
        if last_answer:
            return last_answer
    return last_answer


def ask_summary(prompt, max_tokens=400):
    try:
        d = _post({"model": LLM_MODEL,
                   "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": max_tokens, "temperature": 0.3,
                   "reasoning_effort": "none"})
        return d["choices"][0]["message"].get("content", "").strip()
    except Exception:
        return ""


# ==================== รับเสียง (VAD) ====================
def record_wav():
    import record_until_silence as vad
    print("   🎙️  (ฟัง) พูดได้เลย... พูดจบรอ 2-3 วิ = ตัด", file=sys.stderr, flush=True)
    return vad.record_until_silence(WAV_PATH)


def check_mic(duration=2):
    """ตรวจสอบไมค์ก่อนเริ่ม — บันทึกสั้นๆ (limit → ปล่อย mic สะอาด) แล้วตรวจว่าได้เสียง
    คืน True ถ้าไมค์ใช้ได้, พิมพ์คำแนะนำถ้าไม่ได้"""
    import record_until_silence as vad
    print("🎙️  ตรวจสอบไมโครโฟน...", flush=True)
    vad._kill_recorders()
    time.sleep(0.5)

    test_file = os.path.join(vad.CACHE, "mic_check.opus")
    try:
        os.remove(test_file)
    except OSError:
        pass

    # บันทึก 2 วิ — ใช้ limit (completes naturally → ปล่อย mic สะอาด ไม่ค้าง)
    try:
        subprocess.run(
            ["termux-microphone-record", "-d", "-f", test_file,
             "-l", str(duration), "-r", "16000", "-c", "1", "-e", "opus"],
            capture_output=True, timeout=duration + 10,
        )
    except Exception:
        pass
    time.sleep(1)

    # ตรวจว่าได้เสียงจริงไหม (ไม่เงียบสนิท)
    ok = os.path.exists(test_file) and os.path.getsize(test_file) > 0
    if ok:
        db = vad.rms_db(vad.decode_tail(test_file, 0.5))
        if db <= -90:
            print("   ⚠️  ไมค์เปิดได้ แต่ไม่มีสัญญาณเสียง (ตรวจระดับเสียง/ไมค์)")
        else:
            print(f"   ✅ ไมค์พร้อมใช้งาน (ระดับเสียง {db:.0f}dB — ถ้าตรวจเจอ -70 ถึง -90 ถือปกติเพราะห้องเงียบ)")
    else:
        print("   ❌ ไมค์ไม่ทำงาน")
        print("      ตรวจ: 1) ติดตั้ง Termux:API  2) เปิด permission ไมโครโฟน  3) รีสตาร์ท Termux/เครื่อง")

    vad._kill_recorders()
    try:
        os.remove(test_file)
    except OSError:
        pass
    return ok


# ==================== TTS (เสียงผู้หญิงไทยคนเดียว) ====================
def clean_tts_text(text):
    """ลบ markdown/สัญลักษณ์ที่จะถูกอ่านเป็นเสียง (**, #, `, _, ~, []() ฯลฯ)"""
    if not text:
        return text
    # ตัวหนา/เอียง/โค้ด
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    # หัวข้อ (##, ###)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    # bullet / หมายเลข
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+[\.\)]\s+", "", text, flags=re.M)
    # ลิงก์ [ข้อความ](url) → ข้อความ
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # เอาเครื่องหมายที่เหลือออก (แทนด้วยช่องว่าง)
    for ch in ("*", "#", "`", "_", "~", ">", "|"):
        text = text.replace(ch, " ")
    # ลบช่องว่างซ้ำ
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tts(text, lang="th"):
    """พูดด้วยเสียงผู้หญิงไทยตัวเดียวตลอด (ฟิก engine + variant + pitch + rate)
    และลบ markdown (เช่น *) ออกก่อนพูด"""
    text = clean_tts_text(text)
    if not text:
        return
    cmd = ["termux-tts-speak",
           "-e", TTS_ENGINE, "-l", lang,
           "-v", TTS_VARIANT, "-p", TTS_PITCH, "-r", TTS_RATE,
           text]
    try:
        subprocess.run(cmd, timeout=90)
    except Exception:
        # fallback: ถ้า variant นั้นใช้ไม่ได้ → default
        try:
            subprocess.run(["termux-tts-speak", "-l", lang, text], timeout=90)
        except Exception:
            pass


# ==================== session (jsonl) ====================
def _write_jsonl(path, entries, mode="a"):
    with open(path, mode, encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return out


def find_latest_session():
    if not os.path.isdir(SESSIONS_DIR):
        return None
    for d in reversed(sorted(os.listdir(SESSIONS_DIR))):
        f = os.path.join(SESSIONS_DIR, d, "conversation.jsonl")
        if os.path.exists(f):
            return os.path.join(SESSIONS_DIR, d)
    return None


def new_session():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sdir = os.path.join(SESSIONS_DIR, ts)
    os.makedirs(sdir, exist_ok=True)
    return sdir


def build_messages(entries):
    messages = []
    for e in entries:
        if e.get("type") in ("system", "user", "assistant"):
            messages.append({"role": e.get("role", e.get("type")),
                             "content": e.get("content", "")})
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    return messages


def load_messages(sdir):
    return build_messages(_read_jsonl(os.path.join(sdir, "conversation.jsonl")))


def append_entry(sdir, entry):
    _write_jsonl(os.path.join(sdir, "conversation.jsonl"), [entry], mode="a")


def est_tokens(t):
    return max(1, len(t or "") // 2)


def msgs_tokens(ms):
    return sum(est_tokens(m.get("content", "")) + 4 for m in ms)


def compress_context(sdir, messages):
    total = msgs_tokens(messages)
    if total <= COMPRESS_AT * CONTEXT_WINDOW:
        return messages, False
    old = messages[1:-RECENT_KEEP]
    recent = messages[-RECENT_KEEP:]
    if not old:
        return messages, False
    print(f"   📉 Context {total}/{CONTEXT_WINDOW} (>70%) — compress...", file=sys.stderr)
    budget = int(COMPRESS_TARGET * 0.5 * CONTEXT_WINDOW)
    prompt = ("สรุปบทสนทนาก่อนหน้าเป็นภาษาไทย เก็บสาระสำคัญ: หัวข้อ, ข้อมูลผู้ใช้, "
              f"สิ่งที่ตกลง/ค้างไว้ ให้สั้นประมาณ {budget} ตัวอักษร\n\n" +
              "\n".join(f"{'ผู้ใช้' if m['role']=='user' else 'ผู้ช่วย'}: {m['content']}"
                        for m in old))
    summary = ask_summary(prompt, max_tokens=budget).strip()
    if not summary:
        summary = " ".join(m["content"] for m in old)[:max(budget * 2, 500)]
    summary_msg = {"role": "system", "content": "[สรุปบทสนทนาก่อนหน้า]\n" + summary}
    new_messages = [messages[0], summary_msg] + recent
    after = msgs_tokens(new_messages)
    f = os.path.join(sdir, "conversation.jsonl")
    if os.path.exists(f) and os.path.getsize(f) > 0:
        shutil.copy(f, f + ".bak" + datetime.now().strftime("%H%M%S"))
    entries = [{"type": m["role"], "role": m["role"], "content": m["content"]}
               for m in new_messages]
    entries.append({"type": "summary", "content": summary,
                    "tokens_before": total, "tokens_after": after,
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    _write_jsonl(f, entries, mode="w")
    print(f"   ✅ Compress: {total} → {after} tokens", file=sys.stderr)
    return new_messages, True


# ==================== main ====================
def run(sdir, use_mic=True, text_input=None, use_web=True):
    messages = load_messages(sdir)
    print(f"   📁 Session: {sdir}")
    print(f"   📅 วันนี้: {TODAY_STR}")
    print(f"   🧠 Context: {CONTEXT_WINDOW} (compress >{int(COMPRESS_AT*100)}% → {int(COMPRESS_TARGET*100)}%)")
    print(f"   🔎 Web Search: {'พร้อม' if use_web else 'ปิด'}")
    print(f"   🔊 เสียง: ผู้หญิงไทย (ล็อก)\n")
    append_entry(sdir, {"type": "session", "action": "start",
                        "session_id": os.path.basename(sdir), "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

    turn = 0
    used_first = False
    while True:
        turn += 1
        print(f"🎙️  [รอบ {turn}] ฟังอยู่... พูดได้เลย!", flush=True)

        if not use_mic:
            if text_input and not used_first:
                user_text = text_input
                used_first = True
            else:
                try:
                    user_text = input("คุณ: ").strip()
                except EOFError:
                    print("\n👋 (จบ input)", flush=True)
                    break
            if user_text.strip().lower() in EXIT_WORDS:
                print("👋 ลาก่อน!", flush=True)
                break
            print("🤖  กำลังคิด...", flush=True)
            reply = agent_chat(messages, user_text=user_text, use_web=use_web)
            if not reply:
                print("   (model ไม่ตอบ)", flush=True)
                continue
            print(f"🤖  AI: {reply}", flush=True)
            append_entry(sdir, {"type": "user", "role": "user", "content": user_text, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            append_entry(sdir, {"type": "assistant", "role": "assistant", "content": reply, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            messages.append({"role": "user", "content": user_text})
            messages.append({"role": "assistant", "content": reply})
            messages, _ = compress_context(sdir, messages)
            print("", flush=True)
            time.sleep(1)
            continue

        # โหมดเสียง
        if not record_wav():
            print("   (ไม่ได้ยิน/ไม่มีเสียง ลองใหม่)", flush=True)
            continue
        print("🤖  กำลังฟัง/คิด...", flush=True)
        reply = agent_chat(messages, audio_path=WAV_PATH, use_web=use_web)
        if os.path.exists(WAV_PATH):
            try:
                os.remove(WAV_PATH)
            except OSError:
                pass
        if not reply:
            print("   (model ไม่ตอบ ลองใหม่)", flush=True)
            continue
        print(f"🤖  AI: {reply}", flush=True)
        append_entry(sdir, {"type": "user", "role": "user", "content": f"[เสียงรอบ {turn}]", "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        append_entry(sdir, {"type": "assistant", "role": "assistant", "content": reply, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        messages.append({"role": "user", "content": f"[เสียงรอบ {turn}]"})
        messages.append({"role": "assistant", "content": reply})
        messages, _ = compress_context(sdir, messages)

        tts(reply)
        print("", flush=True)
        time.sleep(1)


def main():
    global TTS_PITCH, TTS_RATE, TTS_VARIANT
    _load_voice()

    # เช็คว่า LLM_BASE เป็น placeholder (ยังไม่ได้ตั้งค่า) → error ชัดเจน
    if "YOUR_LLM_HOST" in LLM_BASE or "your-multimodal" in LLM_MODEL or "your-model" in LLM_MODEL:
        print("❌ ยังไม่ได้ตั้งค่า LLM server")
        print("")
        print("   ตั้งค่า env ก่อนรัน:")
        print("     export LLM_BASE=\"http://<IP>:<PORT>/v1\"")
        print("     export LLM_MODEL=\"/path/to/your-model.gguf\"")
        print("")
        print("   หรือดู README.md หัวข้อ 'ตั้งค่า LLM server'")
        print("   (ตัวอย่าง: สร้าง run.sh ตั้งค่า env แล้วรัน)")
        return

    args = sys.argv[1:]
    use_mic = True
    text_input = None
    use_web = True
    new = False
    do_voice_test = False
    do_mic_check = False
    skip_mic_check = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--new":
            new = True
        elif a in ("-c", "--continue"):
            new = False
        elif a == "--text":
            use_mic = False
            text_input = args[i + 1] if i + 1 < len(args) else ""
            i += 1
        elif a == "--no-web":
            use_web = False
        elif a == "--ctx":
            global CONTEXT_WINDOW
            CONTEXT_WINDOW = int(args[i + 1])
            i += 1
        elif a == "--pitch":
            TTS_PITCH = args[i + 1]; i += 1
        elif a == "--rate":
            TTS_RATE = args[i + 1]; i += 1
        elif a == "--variant":
            TTS_VARIANT = args[i + 1]; i += 1
        elif a == "--voice-test":
            do_voice_test = True
        elif a == "--check-mic":
            do_mic_check = True
        elif a == "--no-mic-check":
            skip_mic_check = True
        i += 1

    if do_voice_test:
        print(f"🔊 ทดสอบเสียง: pitch={TTS_PITCH} rate={TTS_RATE} variant={TTS_VARIANT}")
        tts("สวัสดีค่ะ ฉันคือผู้ช่วยเสียงผู้หญิงนะคะ")
        return

    if do_mic_check:
        ok = check_mic()
        print("\n(รัน `python3 assistant.py` เพื่อเริ่มคุย)")
        return

    # ตรวจไมค์ก่อนเริ่ม (เฉพาะโหมดเสียง, เว้นแต่ข้าม) — เจอปัญหาเร็ว
    if use_mic and not skip_mic_check:
        mic_ok = check_mic()
        if not mic_ok:
            print("\n⚠️  ไมค์ยังใช้ไม่ได้ — ตรวจตามคำแนะนำด้านบน แล้วลองใหม่")
            print("   (ใช้ `python3 assistant.py --check-mic` ตรวจซ้ำ หรือ --no-mic-check ข้าม)\n")

    if new:
        sdir = new_session()
        print(f"🆕 สร้าง session ใหม่: {sdir}")
    else:
        sdir = find_latest_session() or new_session()
        print(f"🔁 ต่อ session: {sdir}")

    try:
        run(sdir, use_mic=use_mic, text_input=text_input, use_web=use_web)
    except KeyboardInterrupt:
        # Ctrl+C → ปล่อย mic ให้สะอาด (กัน recorder ค้างถือ mic)
        print("\n👋 ปิดโปรแกรม — กำลังปล่อย mic...", flush=True)
        try:
            import record_until_silence as _vad
            if _vad._has_stale_recorder():
                _vad._release_mic()
            _vad._kill_recorders()
        except Exception:
            pass
        print("✅ ปล่อย mic เรียบร้อยแล้ว — เปิดใหม่ได้เลย")


if __name__ == "__main__":
    main()
