import json
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(
    page_title="Daily Slip Processing Agent", page_icon="🧾", layout="wide"
)

st.title("🧾 Daily Slip Processing Agent")
st.subheader("ระบบประมวลผลสลิปและแตกรายการเข้าตารางบัญชีประจำวัน")

# ดึง API Key
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("กรุณาใส่ GEMINI_API_KEY ใน secrets.toml")
    st.stop()

client = genai.Client(api_key=api_key)

# รายชื่อคอลัมน์และ Master Data รถ
KNOWN_COLUMNS = [
    "ยข6872",
    "เด็กท้าย",
    "71-0047",
    "พาเลท",
    "ผห6515",
    "9662",
    "ค่าขับ",
    "9517",
    "ค่าขับ/พาเลท",
    "81-5745",
    "82-8312",
    "p jack",
]

# ช่อง Drag & Drop สลิป
uploaded_files = st.file_uploader(
    "ลากรูปสลิปทั้งหมดของวันนี้มาวางที่นี่ (รองรับหลายรูปพร้อมกัน):",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.info(f"📁 จำนวนสลิปที่เลือก: {len(uploaded_files)} ใบ")

    if st.button("🚀 ประมวลผลสลิปทั้งหมดด้วย AI", type="primary"):
        results = []

        # System Prompt สั่ง AI
        system_instruction = f"""
        คุณคือ AI บัญชีระดับท็อปหน้าที่อ่านสลิปโอนเงินโลจิสติกส์
        จงดึงข้อมูลจากสลิปให้อยู่ในรูปแบบ JSON ตามเงื่อนไขต่อไปนี้:
        1. date: วันที่ในสลิป รูปแบบ YYYY-MM-DD
        2. total_amount: จำนวนเงินรวมในสลิป (float)
        3. ref_no: เลขที่รายการ / Transaction Ref
        4. memo: บันทึกช่วยจำ (ถ้าไม่มีให้ใส่ "")
        5. items: รายการย่อยที่แตกจาก memo
           - ตรวจสอบ memo เช่น "9517 1000 + คนลง" หรือ "ยข6872"
           - แยกยอดเงินค่าน้ำมันตามตัวเลขที่ระบุ ส่วนที่เหลือจาก total_amount ให้เข้าหมวดหมู่ตามข้อความหลังเครื่องหมาย +
           - target_column ต้องตรงกับหนึ่งในคอลัมน์ต่อไปนี้เท่านั้น: {KNOWN_COLUMNS} (ถ้าไม่แน่ใจให้ระบุใกล้เคียงที่สุด)

        ส่งผลลัพธ์กลับมาเป็น JSON ดังนี้:
        {{
            "date": "2026-08-05",
            "total_amount": 2300.0,
            "ref_no": "PPFS260805467861664",
            "memo": "9517 1000 + คนลง",
            "items": [
                {{"target_column": "9517", "category": "ค่าน้ำมัน", "amount": 1000.0}},
                {{"target_column": "ค่าขับ/พาเลท", "category": "ค่าคนลงของ", "amount": 1300.0}}
            ]
        }}
        """

        progress_bar = st.progress(0)

        for idx, file in enumerate(uploaded_files):
            # เรียกใช้ Gemini 2.5 Flash เพื่ออ่านสลิป
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(
                        data=file.read(), mime_type=file.type
                    ),
                    "ดึงข้อมูลสลิปนี้ตามคำสั่ง",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                ),
            )

            try:
                data = json.loads(response.text)
                for item in data.get("items", []):
                    results.append(
                        {
                            "วันที่": data.get("date"),
                            "ยอดรวมสลิป": data.get("total_amount"),
                            "คอลัมน์ลงตาราง": item.get("target_column"),
                            "หมวดหมู่": item.get("category"),
                            "จำนวนเงิน": item.get("amount"),
                            "บันทึกช่วยจำ (Memo)": data.get("memo"),
                            "เลขที่รายการ": data.get("ref_no"),
                            "ชื่อไฟล์": file.name,
                        }
                    )
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

            progress_bar.progress((idx + 1) / len(uploaded_files))

        if results:
            df = pd.DataFrame(results)
            st.success("✅ ประมวลผลสำเร็จครบถ้วน!")

            st.write("### 📊 ตารางตรวจสอบความถูกต้อง (Preview)")
            st.dataframe(df, use_container_width=True)

            # ปุ่มดาวน์โหลดไฟล์ลง Excel
            excel_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลเข้าตาราง Excel (CSV)",
                data=excel_data,
                file_name=f"processed_slips_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )