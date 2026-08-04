#!/data/data/com.termux/files/usr/bin/bash
# speak.sh — พูดข้อความออกลำโพง (TTS)
# วิธีใช้: ./speak.sh "สวัสดีครับ"  /  ./speak.sh "Hello" en
TEXT="$1"
LANG="${2:-th}"
if [ -z "$TEXT" ]; then
    echo "ต้องระบุข้อความ: ./speak.sh \"สวัสดี\""
    exit 1
fi
echo "🔊 พูดว่า: $TEXT"
termux-tts-speak -l "$LANG" "$TEXT"
echo "✅ พูดเสร็จ"
