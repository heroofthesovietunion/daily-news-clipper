from datetime import date, datetime, timedelta

import streamlit as st

from gpt_news import get_news

st.set_page_config(
    page_title="Daily News Clipper",
    page_icon="📰",
    layout="wide",
)

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def render_news_card(item: dict) -> None:
    title = item.get("title", "제목 없음")
    summary = item.get("summary", "")
    source = item.get("source", "")
    url = item.get("url", "")

    st.markdown(f"**{title}**")
    if summary:
        st.write(summary)
    if url:
        st.markdown(f"출처: [{source or '원문 보기'}]({url})")
    else:
        st.caption(f"출처: {source}")
    st.divider()


def render_news_list(news_list: list[dict]) -> None:
    if not news_list:
        st.info("해당 날짜의 뉴스를 찾을 수 없습니다. 날짜 범위를 조정해보세요.")
        return
    for item in news_list:
        render_news_card(item)


# ---------------------------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------------------------
st.title("📰 Daily News Clipper")

with st.sidebar:
    st.header("📅 조회 날짜 설정")
    selected_date = st.date_input(
        "날짜를 선택하세요",
        value=date.today() - timedelta(days=1),
        min_value=date.today() - timedelta(days=31),
        max_value=date.today(),
    )
    wd = WEEKDAYS[selected_date.weekday()]
    st.success(f"**{selected_date.year}년 {selected_date.month}월 {selected_date.day}일 ({wd})**")
    st.caption("최대 31일 전까지 조회 가능합니다.")
    st.divider()
    st.caption("📡 출처: 매일경제 · Investing.com · CNBC · Yahoo Finance")

date_str = selected_date.strftime("%Y-%m-%d")
wd = WEEKDAYS[selected_date.weekday()]
st.subheader(f"📌 {selected_date.year}년 {selected_date.month}월 {selected_date.day}일 ({wd}) 경제 뉴스")

tab_domestic, tab_intl = st.tabs(["🇰🇷 국내 경제", "🌐 국외 경제"])

def _show_fallback_warning():
    st.warning("RSS 피드는 최신 기사만 보관합니다. 선택한 날짜의 기사가 없어 **현재 최신 뉴스**를 표시합니다.")


with tab_domestic:
    cache_key = f"{date_str}_domestic"
    if cache_key not in st.session_state:
        with st.spinner("국내 뉴스를 수집하는 중..."):
            st.session_state[cache_key] = get_news(date_str, "domestic")
    news_dom = st.session_state[cache_key]
    if news_dom and news_dom[0].get("_fallback"):
        _show_fallback_warning()
    render_news_list(news_dom)

with tab_intl:
    cache_key_intl = f"{date_str}_international"
    if cache_key_intl not in st.session_state:
        with st.spinner("국외 뉴스 수집 및 번역 중... (30~60초 소요)"):
            st.session_state[cache_key_intl] = get_news(date_str, "international")
    news_intl = st.session_state[cache_key_intl]
    if news_intl and news_intl[0].get("_fallback"):
        _show_fallback_warning()
    render_news_list(news_intl)

st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
