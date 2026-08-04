# 🎙️ Voice AI Assistant on Termux/Android

AI ที่พูดคุยได้ด้วยเสียง รันบนโทรศัพท์ Android ผ่าน **Termux** —
รับเสียง → ส่งตรงให้ **LLM multimodal** ฟัง → คิด → ตอบเป็นเสียงผู้หญิง
โดย **ไม่ต้อง STT แยก** และรองรับ **Web Search** (ถามข่าว/ข้อมูลล่าสุดได้)

> ตัว model (`gemma-4-E4B` หรือ multimodal ใดก็ได้) รันอยู่บน **เครื่อง server แยก** ใน LAN
> โทรศัพท์แค่จับเสียง/เล่นเสียง แล้วส่ง WAV ผ่าน HTTP ไปให้ model ฟังเอง

---

## ✨ ความสามารถ

- 🎙️ ฟังเสียง (VAD รอจนพูดจบ ~2.5 วิ, ใช้ **Opus** — อ่านไฟล์ที่กำลังเขียนได้)
- 📊 แสดง **live level meter** (เห็นระดับเสียง/บาร์ตอนพูด) + **noise gate** ตัดเสียงรบกวน
- 🧠 ส่ง WAV ตรงให้ **LLM multimodal** — model ฟังเสียงได้เอง ไม่ต้อง STT แยก
- 🔎 **Web Search** (tool calling) — ถาม "ข่าววันนี้" model จะค้นให้เอง (Google News RSS + Wikipedia)
- 🔊 **TTS เสียงผู้หญิงไทย** ล็อก variant + pitch ให้คงที่ (ปรับได้)
- 💾 **Session** — `--new` / `-c` เก็บเป็น JSONL เหมือน session ของ agent
- 📉 **Context management** — ถ้าเกิน 70% ของ ctx → compress เหลือ ~30-40% (คุยได้ไม่รู้จบ)

---

## 🚀 สิ่งที่ต้องมี

| อย่าง | รายละเอียด |
|-------|-----------|
| โทรศัพท์ Android | ตัวที่ใช้คุย (ทดสอบบน Android 11) |
| **Termux** | ติดตั้งจาก F-Droid: `pkg install termux-api` + ติดตั้งแอพ **Termux:API** (จาก F-Droid) |
| **Server LLM** | เครื่องที่รัน model multimodal (OpenAI-compatible API) — อยู่บน LAN เดียวกับโทรศัพท์ |
| เน็ต | สำหรับ web search + (optional) ดาวน์โหลด dependencies |

---

## 🛠️ ขั้นตอนติดตั้ง

### 1. ติดตั้ง Termux + Termux:API

```bash
# ใน Termux
pkg update && pkg install termux-api ffmpeg python git
```

ติดตั้งแอพ **Termux:API** จาก F-Droid (package: `com.termux.api`)
จากนั้น grant permission **ไมโครโฟน (RECORD_AUDIO)** ให้ทั้ง Termux และ Termux:API
(การตั้งค่า → แอป → Termux/Termux:API → สิทธิ์ → ไมโครโฟน)

### 2. ดาวน์โหลดโปรเจกต์

```bash
git clone https://github.com/nanofatdog/voice-ai-termux.git ~/voice-assistant
cd ~/voice-assistant
chmod +x *.sh
```

### 3. ตั้งค่า LLM server

เปิดไฟล์ `assistant.py` แล้วแก้ 2 ค่า (หรือตั้ง env var):

```bash
# วิธีที่ 1: แก้ใน assistant.py
export LLM_BASE="http://YOUR_LLM_SERVER_IP:PORT/v1"   # ← ใส่ IP/port จริงของ server
export LLM_MODEL="/path/to/your-model.gguf"           # ← ชื่อ model บน server
```

หรือตั้งก่อนรัน:
```bash
export LLM_BASE="http://192.168.x.x:8080/v1"
export LLM_MODEL="/models/your-model.gguf"
```

> ⚠️ server ต้องรองรับ **multimodal** (รับไฟล์เสียง) และ **function calling** (tools)
> เช่น llama.cpp ที่โหลด model multimodal + mmproj

### 4. ตั้งค่าเสียง (TTS) — optional

```bash
# ลองฟังเสียงแบบต่างๆ แล้วบันทึกค่าที่ชอบ
python3 voice_tune.py --pitch 1.1 --variant th-th-x-thd-local --rate 1.1
python3 voice_tune.py --save --pitch 1.1 --variant th-th-x-thd-local --rate 1.1
```

(จะเขียน `voice.json` — `assistant.py` อ่านอัตโนมัติ)
ใช้ variant `-local` = ใช้ได้แบบ **offline** ไม่ต้องเน็ต

---

## ▶️ วิธีใช้

```bash
# คุยด้วยเสียง (เริ่ม session ใหม่)
python3 assistant.py --new

# คุยต่อ session ล่าสุด (จำความจำก่อนหน้า)
python3 assistant.py -c

# โหมดพิมพ์ (ทดสอบ ไม่ใช้ไมค์)
python3 assistant.py --text "สวัสดี"

# ปิด web search
python3 assistant.py --no-web

# ทดสอบเสียง TTS
python3 assistant.py --voice-test --pitch 1.3
```

พูด **"exit"** / **"ออก"** เพื่อจบ

**ตัวอย่าง:** พูดว่า *"ข่าว AI วันนี้มีอะไรบ้าง"* → model เรียก `web_search` → ค้นจริง → สรุปเป็นไทยพร้อมแหล่งที่มา → พูดกลับ

---

## 🧪 เครื่องมืออื่น

| ไฟล์ | หน้าที่ |
|------|--------|
| `mic_meter.py` | วัดระดับเสียงสด (noise gate) — ตรวจว่าไมค์รับเสียง |
| `record_until_silence.py` | VAD บันทึกจนพูดจบ + live meter |
| `voice_tune.py` | ลอง/ปรับเสียง TTS แล้วบันทึก |
| `websearch.py` | ค้นเว็บ (Google News RSS + Wikipedia) |
| `ask_llm.py` | ถาม LLM แบบข้อความ (สำหรับ script อื่น) |
| `speak.sh` / `record.sh` | 🔊🎙️ หน่วยเสียงเดี่ยว |

---

## 🔧 แก้ปัญหา

| ปัญหา | วิธีแก้ |
|-------|--------|
| ไมค์ไม่รับเสียง | เช็ค permission ไมค์ของ Termux:API (การตั้งค่า → สิทธิ์ → ไมโครโฟน) |
| ฟังแล้วไม่ต่อ | รัน `python3 mic_meter.py` ดูว่าเห็นระดับเสียงไหม; ตรวจไม่มี process `termux-api` ค้าง |
| ครั้งแรกได้ ครั้งที่ 2 ไม่ได้ | เป็น bug ของ recorder ค้างถือ mic — script มี `_release_mic()` (เรียก `-q`) จัดการให้แล้ว |
| เสียงเปลี่ยน | ใช้ `voice_tune.py` ล็อก variant + pitch (ควรใช้ `-local` เพื่อ offline) |
| ไม่มีเสียงออก | ตรวจ TTS engine (Google TTS) ทำงาน + ระดับเสียง media ไม่เป็น 0 |
| web search ไม่ตอบ | ต้องต่อเน็ต; ถามคำถามที่เกี่ยวกับข่าว/ข้อมูลล่าสุด |

---

## 📁 โครงสร้างไฟล์

```
voice-assistant/
├── assistant.py               # 🔄 ตัวหลัก (เสียง + web search + session)
├── websearch.py               # 🔎 ค้นเว็บ
├── record_until_silence.py    # 🎙️ VAD + live meter
├── mic_meter.py               # 📊 วัดระดับเสียง
├── voice_tune.py              # 🔊 ปรับเสียง TTS
├── ask_llm.py                 # 🤖 ถาม LLM
├── speak.sh / record.sh / stt.sh
├── voice.json                 # (สร้างอัตโนมัติ) ค่าตั้งเสียง
└── sessions/                  # (สร้างอัตโนมัติ) session เก็บ JSONL
```

---

## 📄 License

MIT — ใช้ได้ฟรี ปรับปรุง/แจกจ่ายได้

---

> 🔒 **หมายเหตุความปลอดภัย:** โปรเจกต์นี้ไม่รวมข้อมูลลับใดๆ (IP/port/password)
> ให้ตั้งค่า `LLM_BASE`/`LLM_MODEL` เองตาม environment ของคุณ
