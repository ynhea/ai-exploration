# Day 1. 온보딩 챗봇 MVP — Backend Engineer 역할

**날짜**: 2026-07-13
**가상 회사**: 컴퍼스랩(CompassLab)
**오늘의 직무**: AI Backend Engineer (LLM API 연동 담당)
**서비스명 (자체 작명)**: 탈주컴퍼니봇 🧭

---

## 1. 오늘 해결한 업무

HR팀이 신입사원 사규 문의 대응 부담을 줄이기 위해 요청한 웹 기반 온보딩 챗봇 MVP를, FastAPI 백엔드 + LLM API + 간단한 웹 UI로 하루 안에 완성했다.

## 2. 완료한 Must 항목

- [x] FastAPI 프로젝트 초기화, `/chat` 엔드포인트 설계
- [x] LLM API 키 발급 및 환경변수 관리 (`.env`, `.gitignore`)
- [x] 사용자 입력 → API 호출 → 응답 반환 흐름 구현
- [x] 간단한 HTML/JS 채팅 UI 연결 (fetch 사용)

## 3. 최종 아키텍처

```
[브라우저: index.html]
     │  fetch POST /chat  { "message": "질문" }
     ▼
[FastAPI 서버: main.py]
     │  client.chat.completions.create(...)
     ▼
[Groq API (llama-3.3-70b-versatile)]
     │  { "reply": "답변" }
     ▼
[브라우저에 답변 렌더링]
```

## 4. 사용 기술 스택

| 항목 | 처음 계획 | 최종 사용 |
|---|---|---|
| 백엔드 | FastAPI | FastAPI |
| LLM API | OpenAI | ~~Gemini~~ → **Groq (llama-3.3-70b-versatile)** |
| 프론트엔드 | HTML/JS (fetch) | HTML/JS (fetch) |
| 키 관리 | `.env` + `python-dotenv` | 동일 |

---

## 5. 겪은 트러블슈팅 (실제 발생 순서)

### ① `.env` 로드 실패 → `None` 반환
- 증상: `os.getenv("GEMINI_API_KEY")`가 계속 `None` 반환
- 원인: 에러 없이 조용히 `None`을 반환하는 것이 함정 포인트 — 나중에야 인증 에러로 터짐
- 해결: `print()`로 직접 로드 값 확인, 서버 재시작(`--reload`는 `.env` 변경은 감지 못함)

### ② API 응답 객체 구조 오해
- 증상: `response.reply`, `response.text.reply` 등 잘못된 속성 접근으로 에러
- 원인: SDK가 반환하는 객체(`response`)와 그 안의 텍스트 필드(`response.text`)를 혼동
- 해결: `response.text` (Gemini) / `completion.choices[0].message.content` (Groq, OpenAI 호환) 구조 확인
- 배운 점: API 제공자마다 응답 객체 구조가 다름 → `print(response)`로 직접 찍어보거나 문서 확인하는 습관 필요

### ③ Gemini API 403 PERMISSION_DENIED (제공자 자체 이슈)
- 증상: `Your project has been denied access. Please contact support.` — 키를 재발급해도 동일하게 발생
- 원인 조사: 웹 검색 결과, 최근 Google AI Developer 포럼에 동일 증상 다수 보고 확인 — 특정 프로젝트 단위로 원인 불명 차단이 걸리는 알려진 이슈로 판단됨 (코드/설정 문제 아님)
- 대응: Gemini 대신 **Groq API**로 전환 결정 → 무료 티어 즉시 발급, SDK 구조는 OpenAI 호환 방식
- 배운 점: 외부 서비스 장애는 원인을 파고들기보다 대안으로 우회하는 판단이 실무에서 더 합리적일 때가 있음

### ④ JS `fetch`/Promise 문법 이해
- 증상: Python 문법(`if (body):`)을 JS에 그대로 섞어 씀
- 해결: `fetch(...).then(response => response.json()).then(data => {...})` 구조와 `data.reply` 형태의 점 표기법 학습

---

## 6. 최종 코드 (완성본)

### `main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
from groq import Groq
import os

load_dotenv()

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

@app.get("/")
def health_check():
    return {"status": "ok"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(request: ChatRequest):
    quiz = str(request.message)

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": quiz}
        ]
    )

    return {"reply": completion.choices[0].message.content}

# 정적 파일 서빙은 반드시 다른 라우트들보다 아래에 위치
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### `static/index.html` (핵심 스크립트 부분)

```javascript
async function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value;
  if (!message) return;

  const chatbox = document.getElementById("chatbox");
  chatbox.innerHTML += `<div class="user">나: ${message}</div>`;
  input.value = "";

  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message })
  })
  .then(response => response.json())
  .then(data => {
    chatbox.innerHTML += `<div class="bot">봇: ${data.reply}</div>`;
  });
}
```

---

## 7. 오늘 배운 AI/개발 개념

- LLM API 호출 구조 (`messages`, `role`, model 파라미터)
- 환경변수(.env)를 통한 시크릿 관리와 그 실패 패턴
- API 제공자별 응답 객체 구조 차이 (Gemini `response.text` vs OpenAI 호환 `choices[0].message.content`)
- FastAPI 자동 문서(`/docs`, Swagger UI)를 이용한 API 테스트
- JS `fetch`와 Promise(`.then()`) 기반 비동기 요청 흐름
- 정적 파일 마운트 순서가 라우팅에 미치는 영향 (가로챔 방지)

---

## 8. 오늘의 회고

> 아래는 본인이 직접 채워 넣는 영역입니다. Day 7 종합 회고에서 활용됩니다.

- **재미있었던 부분**: LLM수업에서 배운 내용을 직접 구현해보고, 인프라와 달리 코드를 만지고 만드는 과정이 신기했다. 아직 노력하면 잘 할 수 있겠다는 감은 첫날이라 안 왔지만, 조금 더 공부를 해봐야겠다.
- **어려웠던/짜증났던 부분**: fetch문법 등과 같이 인공지능 분야에서 사용되는 문법구조가 있는 것같다. LLM수업에서 들은 거지만, 실제로 해보니 느낌이 달리 느껴졌다. 코드 이해 후 작성에 시간이 꽤 걸렸다.

---

## 9. 실무 연결 포인트 (오늘 특히 체감한 것)

계획에 없던 상황이었지만, **외부 API 제공자가 원인 불명으로 막혔을 때 대안 제공자로 전환하는 판단**을 실제로 겪었다. 이는 커리큘럼에 명시된 트러블슈팅(.env 실패, CORS, rate limit)보다 더 실전에 가까운 경험이었으며, 정해진 사양대로만 진행되지 않는 실무의 성격을 미리 체감할 수 있었다.
