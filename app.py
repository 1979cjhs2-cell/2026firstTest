import streamlit as st
import google.generativeai as genai
import json
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# CSS 스타일
st.markdown("""
<style>
.api-popup {background-color: #f0f8ff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #2196F3; margin: 1rem 0;}
.progress-list {background-color: #e8f5e8; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;}
.theme-btn {margin: 0.3rem; padding: 0.5rem 1rem; border-radius: 20px;}
</style>
""", unsafe_allow_html=True)

# 세션 초기화
if 'current_step' not in st.session_state: st.session_state.current_step = 0
if 'api_keys' not in st.session_state: st.session_state.api_keys = {}
if 'selected_themes' not in st.session_state: st.session_state.selected_themes = []
if 'selected_period' not in st.session_state: st.session_state.selected_period = '1주'
if 'top_contents' not in st.session_state: st.session_state.top_contents = []
if 'prompts' not in st.session_state:
    st.session_state.prompts = {
        "theme_research": {
            "ko": """다음 테마와 기간에 대해 YouTube 트래픽 분석해줘:
테마: {theme}
기간: {period}

1. TOP 10 인기 콘텐츠 (제목, 채널, 조회수, 업로드일, 링크)
2. 트렌드 분석 (공통점, 인기 시간대)
3. 근거 자료 출처 3개 이상

JSON 형식으로 정확히 출력.""",
            "en": "Analyze YouTube traffic for: {theme} during {period}..."
        }
    }

st.set_page_config(page_title="AI YouTube 자동화", layout="wide")

# ===== 0단계: API 연결 =====
def api_connection():
    st.header("🔑 0단계: API 연결 테스트")

    col1, col2 = st.columns([3,1])
    with col1:
        api_key = st.text_input("Gemini API Key", type="password", help="https://aistudio.google.com/app/apikey")
    with col2:
        if st.button("🔍 연결 테스트", type="primary"):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                response = model.generate_content("테스트")

                st.markdown("""
                <div class="api-popup">
                    <h3>✅ 연결 성공!</h3>
                    <ul>
                        <li>🔥 gemini-2.0-flash-exp (추천)</li>
                        <li>⚡ gemini-1.5-flash</li>
                        <li>🧠 gemini-1.5-pro</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

                if st.button("💾 API 키 저장 & 시작", type="secondary"):
                    st.session_state.api_keys['gemini'] = api_key
                    st.session_state.current_step = 1
                    st.rerun()

            except Exception as e:
                st.error(f"❌ 연결 실패: {str(e)}")
                st.info("API 키를 정확히 입력해주세요")

# ===== 1단계: 테마 선택 =====
def step1_theme_selection():
    st.header("📊 1단계: 테마 선택 & 데이터 조회")

    # TOP 10 테마
    popular_themes = ["인공지능/AI", "크립토/비트코인", "주식 투자", "게임 리뷰",
                     "K-뷰티", "다이어트", "부동산", "영어 공부", "요리", "컴퓨터"]

    st.subheader("🔥 트래픽 TOP 10 테마")
    cols = st.columns(5)
    selected_themes = []
    for i, theme in enumerate(popular_themes):
        with cols[i%5]:
            if st.button(theme, key=f"btn_{i}", help="클릭하여 선택"):
                if theme in st.session_state.get('selected_themes', []):
                    st.session_state.selected_themes.remove(theme)
                else:
                    st.session_state.selected_themes.append(theme)
                st.rerun()

    # 사용자 테마 추가
    st.subheader("➕ 사용자 테마 추가")
    col1, col2 = st.columns([3,1])
    with col1:
        custom_theme = st.text_input("키워드 입력")
    with col2:
        if st.button("추가") and custom_theme:
            st.session_state.selected_themes.append(custom_theme)
            st.rerun()

    # 기간 선택
    st.subheader("📅 조회 기간")
    col1, col2 = st.columns(2)
    with col1:
        period = st.radio("기간", ["1일", "1주", "1달", "1년"], key="period_radio")
    with col2:
        custom_days = st.number_input("사용자 기간(일)", 1, 365, 30)
        if st.button("📋 기간 설정"):
            st.session_state.selected_period = f"{custom_days}일"

    # 프롬프트 편집기
    with st.expander("🔧 조회 프롬프트 편집", expanded=False):
        prompt_key = "theme_research"
        col1, col2 = st.columns(2)
        with col1:
            ko_prompt = st.text_area("한국어",
                                   st.session_state.prompts[prompt_key]["ko"],
                                   height=150, key="ko_prompt")
        with col2:
            en_prompt = st.text_area("영어",
                                   st.session_state.prompts[prompt_key]["en"],
                                   height=150, key="en_prompt")
        col1, col2 = st.columns(2)
        if col1.button("💾 저장"):
            st.session_state.prompts[prompt_key] = {"ko": ko_prompt, "en": en_prompt}
            st.success("저장됨!")

    # 조회 시작
    if st.button("🔍 **테마 조회 시작**", type="primary", use_container_width=True):
        if st.session_state.selected_themes:
            theme = st.session_state.selected_themes[0]
            period = st.session_state.selected_period or period

            # 진행 상황 팝업
            progress_col1, progress_col2 = st.columns([1,3])
            with progress_col1:
                st.markdown("### 📋 AI 작업 진행")
            with progress_col2:
                st.markdown("""
                <div class="progress-list">
                🔍 테마 데이터 수집 중... (0%)<br>
                📊 트래픽 분석 중... (33%)<br>
                📈 TOP 10 콘텐츠 추출... (66%)<br>
                ✅ **분석 완료!** (100%)
                </div>
                """, unsafe_allow_html=True)

            # 시연용 딜레이
            with st.spinner("AI 분석 중..."):
                time.sleep(3)

            # 결과 생성 (더미 - 실제 Gemini 호출로 대체 가능)
            st.session_state.top_contents = [
                {
                    "title": f"{theme} TOP 콘텐츠 #{i+1}",
                    "channel": f"채널{i+1}",
                    "views": f"{800000 + i*50000:,}",
                    "date": "2026-01-15",
                    "link": f"https://youtube.com/watch?v=test{i}"
                } for i in range(10)
            ]

            st.success(f"✅ **{theme}** ({period}) 조회 완료!")

    # 결과 표시
    if st.session_state.top_contents:
        st.markdown(f"""
        ### 📈 **{st.session_state.selected_theme}** ({st.session_state.selected_period}) 분석 결과

        **📊 전체 트래픽:** 평균 조회수 **{sum(int(c['views'].replace(',','')) for c in st.session_state.top_contents)//10:,}**

        **🔗 근거 자료:**
        • [YouTube 트렌드](https://trends.google.com)
        • [SocialBlade 분석](https://socialblade.com)
        • [Google 검색 트렌드](https://trends.google.com/trends)
        """)

        st.subheader("🏆 TOP 10 콘텐츠")
        selected = st.multiselect(
            "✅ 사용할 콘텐츠 선택 (복수 가능)",
            [f"#{i+1} {c['title']} ({c['views']})" for i, c in enumerate(st.session_state.top_contents)],
            key="top_select"
        )

        if st.button("➡️ **2단계로 이동**", type="primary"):
            st.session_state.current_step = 2
            st.rerun()

# ===== 메인 페이지 로직 =====
if st.session_state.current_step == 0:
    api_connection()
elif st.session_state.current_step == 1:
    step1_theme_selection()
else:
    st.header(f"📋 {st.session_state.current_step}단계 진행 중...")
    st.info("2~11단계 세부 사항 대기 중...")

# ===== 네비게이션 바 =====
st.markdown("---")
col1, col2, col3 = st.columns([1,1,1])
if col1.button("🔙 이전 단계"):
    st.session_state.current_step = max(0, st.session_state.current_step-1)
    st.rerun()
if col2.button("🏠 1단계"):
    st.session_state.current_step = 1
    st.rerun()
if col3.button("🔄 새로고침"):
    st.rerun()

# 실행 가이드
with st.expander("📖 실행 방법"):
    st.markdown("""
    1. **pip install streamlit google-generativeai python-dotenv**
    2. **Gemini API 키 발급:** https://aistudio.google.com/app/apikey
    3. **streamlit run app.py**
    4. **localhost:8501** 접속 → 즉시 작동!
    """)
