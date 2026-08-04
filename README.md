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

## 🧠 Model (LLM) ที่ใช้จริง

โปรเจกต์นี้ใช้ **Gemma 4 E4B** (multimodal) — เป็น model ที่ **อ่านเสียง/ฟังเสียงได้โดยตรง** + รองรับ **function calling** (web search)

- **Model:** `gemma-4-E4B-it-heretic-IQ4_NL-imatrix.gguf`
  - Gemma 4 E4B (Multimodal, instruct) — ฟังเสียง + ดูภาพ + อ่านข้อความ
  - quantized `IQ4_NL` (ไฟล์ GGUF) + imatrix
- **รันด้วย:** llama.cpp server (ต้องโหลดด้วย mmproj เพื่อรองรับ multimodal/เสียง)
- **รองรับ:** `input_audio` (รับไฟล์ WAV ตรงๆ) + `tools` (function calling)

> ตั้งค่า env:
> ```bash
> export LLM_MODEL="/models/gemma-4-E4B-it-heretic-IQ4_NL-imatrix.gguf"
> ```

> 💡 ถ้าจะใช้ model อื่น — ต้องเป็น multimodal ที่รองรับทั้ง **เสียง (audio input)** และ **function calling (tools)** จึงจะทำงานครบ (ฟังเสียง + web search)

---

## 🚀 สิ่งที่ต้องมี

| อย่าง | รายละเอียด |
|-------|-----------|
| โทรศัพท์ Android | ตัวที่ใช้คุย (ทดสอบบน Android 11) |
| **Termux** | terminal emulator (ติดตั้งจาก F-Droid) |
| **Termux:API** | แอพ companion ที่ให้ Termux ใช้ hardware ของเครื่อง (ไมค์, ลำโพง ฯลฯ) |
| **Server LLM** | เครื่องที่รัน model multimodal (OpenAI-compatible API) — อยู่บน LAN เดียวกับโทรศัพท์ |
| เน็ต | สำหรับ web search + (optional) ดาวน์โหลด dependencies |

---

## 📱 การตั้งค่า Android (สำคัญมาก!)

โปรเจกต์นี้ต้องใช้ **ไมโครโฟน** และ **ลำโพง** ของเครื่อง ดังนั้นต้องติดตั้งแอพ + เปิด permission ให้ถูกต้อง ตามขั้นตอนด้านล่าง

### 1. ติดตั้ง Termux

- ไปที่ **F-Droid** → ค้นหา **"Termux"** → ติดตั้ง
  - F-Droid: https://f-droid.org/packages/com.termux/
  - ⚠️ **อย่าติดตั้ง Termux จาก Google Play** (เวอร์ชันเก่า/ถูกยกเลิก) — ใช้ F-Droid เท่านั้น

### 2. ติดตั้ง Termux:API

- ไปที่ **F-Droid** → ค้นหา **"Termux:API"** → ติดตั้ง
  - F-Droid: https://f-droid.org/packages/com.termux.api/
- ติดตั้งเสร็จ เปิด Termux แล้วติดตั้งตัวเชื่อม:
  ```bash
  pkg update
  pkg install termux-api ffmpeg python git
  ```

### 3. เปิด Permission ไมโครโฟน (จำเป็น!)

ต้องเปิด **ไมโครโฟน** ให้ทั้ง **Termux** และ **Termux:API**:

```
การตั้งค่า (Settings) → แอป (Apps)
  → Termux → สิทธิ์ (Permissions) → ไมโครโฟน (Microphone) → เปิดอนุญาต (Allow)
  → Termux:API → สิทธิ์ (Permissions) → ไมโครโฟน (Microphone) → เปิดอนุญาต (Allow)
```

> 💡 ทางลัด: รัน `termux-microphone-record -d -f test.opus -l 3` ใน Termux ครั้งแรก
> มันจะเด้งป๊อปอัปขออนุญาตไมค์ขึ้นมา — แตะ **"อนุญาต/Allow"**

### 4. (แนะนำ) เปิด permission/ตั้งค่าเสริมเพื่อให้ทำงานลื่น

| อย่าง | ทำไม | วิธี |
|-------|------|-----|
| **ละเว้นการปรับแบตเตอรี่ให้เหมาะสม** (Ignore battery optimization) | กันระบบฆ่า Termux ตอนรอฟังเสียง | การตั้งค่า → แบตเตอรี่ → ตั้งค่า Termux → "ไม่จำกัด" / ละเว้น |
| **เปิดใช้งานพื้นหลัง** (Allow background activity) | ให้ Termux ฟังเสียงต่อได้แม้หน้าจอปิด | แอป Termux → สิทธิ์/การใช้งานพื้นหลัง |
| **การแจ้งเตือน** (Notification) | เห็นสถานะ/ข้อความ error | แอป Termux/Termux:API → การแจ้งเตือน → อนุญาต |
| **เริ่มอัตโนมัติ** (Autostart — บางยี่ห้อ) | กันระบบไม่ให้ปิด Termux | ขึ้นอยู่กับยี่ห้อ (Xiaomi/OPPO ต้องเปิด "Autostart") |

### 5. ติดตั้ง server LLM (ฝั่ง server)

- รัน model multimodal บนเครื่อง server (เช่น llama.cpp ที่โหลด `gemma-4-E4B` + mmproj)
- เปิด port ให้โทรศัพท์เข้าถึงได้ (อยู่บน LAN เดียวกัน)
- ตั้งค่า `LLM_BASE` / `LLM_MODEL` (ดูหัวข้อ "ตั้งค่า LLM server")

---

## 🛠️ ขั้นตอนติดตั้ง (หลังตั้งค่า Android เสร็จ)

### 1. ดาวน์โหลดโปรเจกต์

```bash
git clone https://github.com/nanofatdog/voice-ai-termux.git ~/voice-assistant
cd ~/voice-assistant
chmod +x *.sh
```

### 2. ตั้งค่า LLM server

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

### 3. ตั้งค่าเสียง (TTS) — optional

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
