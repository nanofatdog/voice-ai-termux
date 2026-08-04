#!/data/data/com.termux/files/usr/bin/bash
# stt.sh — แปลงเสียงพูดเป็นข้อความ (Android speech recognizer)
# วิธีใช้: ./stt.sh
echo "🎙️ ฟังอยู่... พูดได้เลย"
termux-speech-to-text
echo ""
echo "✅ จบการฟัง"
