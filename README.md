# Daily News Clipper

매크로 경제 및 FDS(이상금융거래탐지) 관련 뉴스를 자동 수집·요약하는 Streamlit 웹 앱.

OpenAI GPT-4o의 web_search 기능을 활용하여 지정한 날짜의 주요 뉴스를 실시간으로 검색하고 한국어로 요약합니다.

## 주요 기능

- 날짜 선택 (기본값: 전날 D-1, 최대 31일 전까지)
- 매크로 경제 뉴스 탭 (금리, 환율, 증시, 물가 등)
- FDS/금융보안 뉴스 탭 (금융사기, 보이스피싱, 규제 동향 등)
- 동일 날짜 재조회 시 캐시 사용 (불필요한 API 호출 방지)

## 로컬 실행 방법

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일 생성:

```
OPENROUTER_API_KEY=sk-or-v1-여기에_실제_키_입력
```

### 3. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

## Streamlit Cloud 배포 방법

1. GitHub 레포 생성 후 코드 push (`.env` 파일은 push하지 말 것)
2. [streamlit.io](https://streamlit.io) → **New app** → GitHub 레포 연결
3. **Settings > Secrets**에 아래 내용 추가:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-여기에_실제_키_입력"
   ```
4. **Deploy** 클릭 → 배포 완료 후 URL 확인

## 환경변수 설정

| 변수명 | 설명 | 필수 여부 |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API 인증 키 (perplexity/sonar 모델 사용) | 필수 |

> **주의**: `.env` 파일은 절대 GitHub에 push하지 마세요. `.gitignore`에 이미 포함되어 있습니다.

## 파일 구조

```
├── app.py                    # Streamlit 메인 UI
├── gpt_news.py               # OpenAI API 호출 및 뉴스 파싱
├── requirements.txt          # 패키지 목록
├── .env                      # 로컬 API 키 (gitignore 대상)
├── .gitignore                # .env 등 민감 파일 제외
├── test_gpt_news.py          # 백엔드 테스트
└── .streamlit/
    └── secrets.toml          # Streamlit Secrets 샘플
```
