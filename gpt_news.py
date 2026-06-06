"""
뉴스 수집 모듈 — RSS 기반 (API 크레딧 불필요)

국내: 매일경제 RSS
국외: Investing.com / CNBC / Yahoo Finance RSS + 한국어 번역 요약
"""
import json
import re
import html
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from dotenv import load_dotenv

import requests
import feedparser

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=True)

# ---------------------------------------------------------------------------
# RSS 피드 설정
# ---------------------------------------------------------------------------

_DOMESTIC_FEEDS = [
    ("매일경제", "https://www.mk.co.kr/rss/30100041/"),   # 경제
    ("매일경제", "https://www.mk.co.kr/rss/30200030/"),   # 증권·금융
]

_INTL_FEEDS = [
    ("Investing.com", "https://www.investing.com/rss/news_301.rss"),   # 경제 지표
    ("Investing.com", "https://www.investing.com/rss/news_285.rss"),   # 중앙은행
    ("Investing.com", "https://www.investing.com/rss/news_11.rss"),    # 원자재·유가
    ("Investing.com", "https://www.investing.com/rss/news_1.rss"),     # 전체
    ("CNBC",          "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch",   "https://feeds.marketwatch.com/marketwatch/topstories/"),
]

_DOMESTIC_ECON_KW = [
    "금리", "환율", "코스피", "코스닥", "물가", "한국은행", "금통위", "기준금리",
    "cpi", "ppi", "경제", "주가", "원달러", "원화", "수출", "무역", "국채",
    "채권", "증시", "주식", "투자", "ipo", "공모", "etf", "펀드", "통화",
    "fed", "fomc", "ecb", "유가", "wti", "인플레", "gdp", "가계부채",
    "금융위", "금감원", "통계청", "기획재정부", "한은", "외환",
]

_INTL_ECON_KW = [
    "fomc", "federal reserve", "fed rate", "ecb", "boj", "bank of",
    "oil price", "crude oil", "wti", "brent", "opec", "petroleum",
    "inflation", "cpi", "ppi", "interest rate", "rate cut", "rate hike",
    "rate decision", "monetary policy", "gdp", "jobs report", "payroll",
    "nasdaq", "s&p 500", "s&p500", "dow jones", "trade deficit", "tariff",
    "imf", "world bank", "recession", "treasury yield", "bond yield",
    "powell", "lagarde", "gold price", "dollar index", "forex",
    "stock market", "wall street", "earnings", "economic data",
]

_EXCLUDE_KW = [
    "bitcoin", "ethereum", "crypto", "blockchain", "nft", "defi",
    "altcoin", "coinbase", "binance", "ripple", "dogecoin",
]

# ---------------------------------------------------------------------------
# 내부 유틸리티
# ---------------------------------------------------------------------------

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; NewsClipper/1.0)"})


def _fetch_feed(url: str) -> list:
    try:
        resp = _SESSION.get(url, timeout=12, verify=True)
        return feedparser.parse(resp.text).entries
    except Exception:
        try:
            resp = _SESSION.get(url, timeout=12, verify=False)
            return feedparser.parse(resp.text).entries
        except Exception:
            return []


def _parse_date(entry) -> datetime | None:
    raw = entry.get("published") or entry.get("updated") or ""
    if not raw:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw[:19], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    # cp1252로 잘못 해석된 UTF-8 복원 (â€™ → ' 등)
    try:
        text = text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return " ".join(text.split())


def _contains_kw(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def _is_today(entry, target_date: str) -> bool:
    dt = _parse_date(entry)
    if dt is None:
        return True
    kst = timezone(timedelta(hours=9))
    local_date = dt.astimezone(kst).date()
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    return abs((local_date - target).days) <= 1


def _is_old_date(date_str: str) -> bool:
    """선택 날짜가 2일 이상 지난 경우 → RSS 피드에 기사 없을 가능성 높음"""
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now(timezone(timedelta(hours=9))).date()
    return (today - target).days >= 2


def _entry_to_item(entry, source_name: str) -> dict:
    return {
        "title": _clean(entry.get("title", "제목 없음")),
        "summary": _clean(entry.get("summary", entry.get("description", "")))[:300],
        "source": source_name,
        "url": entry.get("link", ""),
    }


def _deduplicate(items: list[dict]) -> list[dict]:
    """URL 일치 및 제목 유사도 기반 중복 제거"""
    seen_urls: set[str] = set()
    seen_title_words: list[set] = []
    unique = []
    for item in items:
        url = item.get("url", "")
        if url and url in seen_urls:
            continue

        title_words = set(re.findall(r'\w+', item["title"].lower()))
        is_dup = False
        for sw in seen_title_words:
            if len(title_words) == 0 or len(sw) == 0:
                continue
            overlap = len(title_words & sw) / len(title_words | sw)
            if overlap >= 0.55:
                is_dup = True
                break

        if not is_dup:
            unique.append(item)
            if url:
                seen_urls.add(url)
            seen_title_words.append(title_words)

    return unique


# ---------------------------------------------------------------------------
# 번역 (국외 기사 → 한국어)
# ---------------------------------------------------------------------------

_FREE_MODELS = [
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
]


def _call_llm(prompt: str, max_tokens: int = 3000, timeout: int = 90) -> str | None:
    """사용 가능한 무료 모델을 순서대로 시도해 응답 텍스트를 반환."""
    import time

    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None

    for model in _FREE_MODELS:
        payload_bytes = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }, ensure_ascii=False).encode("utf-8")

        for attempt in range(2):
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload_bytes,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=timeout,
                )
                data = resp.json()

                if "error" not in data:
                    return data["choices"][0]["message"]["content"]

                code = data["error"].get("code", 0)
                if code == 429 and attempt == 0:
                    wait = int(data["error"].get("metadata", {}).get("retry_after_seconds", 35))
                    time.sleep(min(wait + 3, 60))
                    continue
                break
            except Exception:
                break

    return None


def _translate_batch(items: list[dict]) -> list[dict]:
    """국외 기사를 한국어 제목 + 요약으로 일괄 번역 (OpenRouter 무료 모델)."""
    if not items:
        return items

    numbered = []
    for i, item in enumerate(items, 1):
        line = f"{i}. {item['title']}"
        if item.get("summary"):
            line += f" | {item['summary'][:150]}"
        numbered.append(line)

    prompt = (
        "아래 영어 경제 뉴스 기사들을 한국어로 번역·요약해줘.\n"
        "각 항목마다 ① 한국어 제목(간결하게), "
        "② 제목과 내용을 바탕으로 한 2~3문장 한국어 요약을 작성해.\n"
        "요약이 없으면 제목 맥락으로 배경 설명을 써줘.\n"
        "반드시 JSON 배열만 반환하고 설명 없이:\n"
        '[{"id":1,"title":"...","summary":"..."},{"id":2,...}]\n\n'
        "기사:\n" + "\n".join(numbered)
    )

    try:
        content = _call_llm(prompt, max_tokens=3000, timeout=90)
        if not content:
            return items

        match = re.search(r'\[.*\]', content, re.DOTALL)
        if not match:
            return items

        translations = json.loads(match.group(0))
        for t in translations:
            idx = int(t.get("id", 0)) - 1
            if 0 <= idx < len(items):
                if t.get("title"):
                    items[idx]["title"] = t["title"]
                if t.get("summary"):
                    items[idx]["summary"] = t["summary"]
        return items
    except Exception:
        return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_news(date: str, category: str) -> list[dict]:
    """
    category: "domestic" | "international"
    반환: [{"title", "summary", "source", "url"}, ...]
    """
    if category == "domestic":
        return _get_domestic(date)
    elif category == "international":
        return _get_international(date)
    return []


def _get_domestic(date: str) -> list[dict]:
    def _fetch(date_filter: bool) -> list[dict]:
        items = []
        for source_name, url in _DOMESTIC_FEEDS:
            for entry in _fetch_feed(url):
                if date_filter and not _is_today(entry, date):
                    continue
                title = _clean(entry.get("title", ""))
                if not title or not _contains_kw(title, _DOMESTIC_ECON_KW):
                    continue
                items.append(_entry_to_item(entry, source_name))
        return _deduplicate(items)[:15]

    result = _fetch(date_filter=True)
    if not result and _is_old_date(date):
        result = _fetch(date_filter=False)
        for item in result:
            item["_fallback"] = True
    return result


def _get_international(date: str) -> list[dict]:
    def _fetch(date_filter: bool) -> list[dict]:
        items = []
        for source_name, url in _INTL_FEEDS:
            for entry in _fetch_feed(url):
                if date_filter and not _is_today(entry, date):
                    continue
                title = _clean(entry.get("title", ""))
                if not title:
                    continue
                full_text = (title + " " + _clean(entry.get("summary", ""))).lower()
                if _contains_kw(full_text, _EXCLUDE_KW):
                    continue
                if not _contains_kw(full_text, _INTL_ECON_KW):
                    continue
                items.append(_entry_to_item(entry, source_name))
        return _deduplicate(items)[:12]

    unique = _fetch(date_filter=True)
    if not unique and _is_old_date(date):
        unique = _fetch(date_filter=False)
        for item in unique:
            item["_fallback"] = True
    return _translate_batch(unique)
