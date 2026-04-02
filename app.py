import streamlit as st
import google.generativeai as genai
import json
import base64
from utils.pdf_processor import extract_text_with_pages
from utils.casp_logic import CASP_SYSTEM_PROMPT, AUDITOR_SYSTEM_PROMPT
from utils.export_helper import create_casp_word_report

st.set_page_config(layout="wide", page_title="CASP SRMA 評讀 AI")
st.title("🛡️ 實證醫學 CASP 自動評讀系統 (雙重覆核版)")

# API 設定
api_key = st.secrets.get("GOOGLE_API_KEY", "")
if not api_key:
    st.warning("請在設定中輸入 GOOGLE_API_KEY")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-pro-flash", generation_config={"response_mime_type": "application/json", "temperature": 0})

st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ 系統診斷")
if st.sidebar.button("測試 API 連線與可用模型"):
    try:
        # 嘗試向 Google 請求列出這把 Key 可以用的所有模型
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        st.sidebar.success("連線成功！您的 API Key 支援以下模型：")
        st.sidebar.write(available_models)
    except Exception as e:
        st.sidebar.error(f"連線失敗，詳細錯誤：{e}")

# 在地情境設定檔
SAVED_PROFILE = {
    "setting": "東部醫學中心急診部",
    "epidemiology": "高齡族群比例高、地理狹長導致到院前時間較長、外傷與急重症多。",
    "resources": "由醫師與專科護理師共同執行處置，需高度考量急診擁擠度與檢傷動線。"
}

with st.sidebar:
    st.header("⚙️ 臨床情境設定")
    base_setting = st.text_input("執業場域", value=SAVED_PROFILE["setting"])
    base_epi = st.text_area("流行病學", value=SAVED_PROFILE["epidemiology"])
    base_res = st.text_area("醫療資源", value=SAVED_PROFILE["resources"])
    additional_context = st.text_area("本次特殊考量 (選填)", placeholder="例如：我們單位啟動 BORP（備援手術室計畫）時的特殊動線考量...")
    
    local_context = f"場域:{base_setting}\n特徵:{base_epi}\n資源:{base_res}\n補充:{additional_context}"

uploaded_file = st.file_uploader("上傳 SRMA 文獻 (PDF)", type="pdf")

if uploaded_file:
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📄 原始文獻")
        base64_pdf = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
        st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
        
    with col_right:
        st.subheader("🤖 評讀結果")
        if st.button("🚀 開始初次評讀"):
            with st.spinner("解析文獻與生成 CASP 報告中..."):
                paper_text = extract_text_with_pages(uploaded_file)
                st.session_state["paper_text"] = paper_text
                prompt = f"{CASP_SYSTEM_PROMPT}\n\n在地情境：{local_context}\n\n文獻內容：{paper_text}"
                resp = model.generate_content(prompt)
                st.session_state["appraisal_result"] = json.loads(resp.text)
                st.rerun()

        if "appraisal_result" in st.session_state:
            result = st.session_state.get("audited_result", st.session_state["appraisal_result"])
            
            for key, val in result.items():
                icon = "✅" if val.get('Verdict') == 'Yes' else "⚠️"
                with st.expander(f"{key}: {val.get('Question', '')} 【{val.get('Verdict')}】 {icon}"):
                    st.write(f"**💡 解析：** {val.get('Reasoning_TW', '')}")
                    if 'Auditor_Note' in val:
                        st.info(f"**🛡️ 稽核：** {val['Auditor_Note']}")
            
            if "audited_result" not in st.session_state:
                if st.button("🕵️ 啟動深度覆核 (Re-assessment)"):
                    with st.spinner("資深稽核員交叉比對中..."):
                        prompt = f"{AUDITOR_SYSTEM_PROMPT}\n\n原文：{st.session_state['paper_text']}\n\n初判：{json.dumps(st.session_state['appraisal_result'])}"
                        resp = model.generate_content(prompt)
                        st.session_state["audited_result"] = json.loads(resp.text)
                        st.rerun()
            else:
                word_file = create_casp_word_report(st.session_state["audited_result"], local_context, uploaded_file.name)
                st.download_button("📄 一鍵下載 Word 報告", data=word_file, file_name="CASP_Report.docx")
