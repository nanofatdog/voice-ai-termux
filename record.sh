#!/data/data/com.termux/files/usr/bin/bash
# record.sh — บันทึกเสียงจากไมค์ (กำหนดเวลา)
# วิธีใช้: ./record.sh out.wav 5
OUT="${1:-recording.wav}"
DUR="${2:-5}"
mkdir -p "$(dirname "$OUT")"
echo "🎙️ บันทึก ${DUR} วินาที ... (พูดได้เลย!)"
termux-microphone-record -d -f "$OUT" -l "$DUR"
if [ -f "$OUT" ] && [ -s "$OUT" ]; then
    echo "✅ บันทึกสำเร็จ: $OUT"
else
    echo "❌ บันทึกไม่สำเร็จ (ตรวจ permission ไมค์)"
fi
