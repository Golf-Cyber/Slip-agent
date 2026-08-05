import json
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Daily Slip Processing Agent", page_icon="🧾", layout="wide"
)

st.title("🧾 Daily Slip Processing Agent")
st.subheader("ระบบประมวลผลสลิปและแตกรายการเข้าตารางบัญชีประจำวัน")

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("กรุณาใส่ GEMINI_API_KEY ใน Secrets (Settings ⚙️ -> Secrets)")
    st.stop()

# เรียกใช้ Client จาก SDK ตัวใหม่
client = genai.Client(api_key=api_key)

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
    "70-6325",
    "70-6324",
    "p jack",
]

uploaded_files = st.file_uploader(
    "ลากรูปสลิปทั้งหมดของวันนี้มาวางที่นี่:",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.info(f"📁 จำนวนสลิปที่เลือก: {len(uploaded_files)} ใบ")

    if st.button("🚀 ประมวลผลสลิปทั้งหมดด้วย AI", type="primary"):
        results = []

        system_instruction = f"""
        คุณคือ AI บัญชีสำหรับบริษัทขนส่งที่อ่านสลิปโอนเงิน
        จงอ่านรูปสลิป แล้วตอบกลับเป็น JSON Structure เท่านั้น (ห้ามมีคำเกริ่นหรือข้อความอื่น):
        {{
            "date": "YYYY-MM-DD",
            "total_amount": 2300.0,
            "ref_no": "เลขที่รายการ",
            "memo": "ข้อความบันทึกช่วยจำ",
            "items": [
                {{"target_column": "ชื่อคอลัมน์", "category": "หมวดหมู่", "amount": 1000.0}}
            ]
        }}

        เงื่อนไขสำคัญ:
        1. target_column ต้องเลือกให้ตรงกับรายการต่อไปนี้เท่านั้น: {KNOWN_COLUMNS}
        2. หาก Memo พิมพ์รหัสรถและยอด เช่น "9517 1000 + คนลง" ให้แตกรายการเป็น:
           - รายการที่ 1: target_column="9517", category="ค่าน้ำมัน", amount=1000
           - รายการที่ 2: target_column="ค่าขับ/พาเลท", category="ค่าคนลงของ", amount=ส่วนที่เหลือจากยอดรวมสลิป
        3. หาก Memo มีเฉพาะรหัสรถ เช่น "9517" หรือ "ยข6872" ให้ใส่ยอดเต็มของสลิปเข้าคอลัมน์รถนั้น
        """

        progress_bar = st.progress(0)

        for idx, file in enumerate(uploaded_files):
            try:
                # ใช้โมเดล gemini-2.5-flash ผ่าน SDK ตัวใหม่
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
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
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {file.name}: {e}")

            progress_bar.progress((idx + 1) / len(uploaded_files))

        if results:
            df = pd.DataFrame(results)
            st.success("✅ ประมวลผลสำเร็จเรียบร้อย!")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์นำเข้า Excel (CSV)",
                data=csv,
                file_name=f"slips_summary_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
