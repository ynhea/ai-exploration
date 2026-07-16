# Day 4. RAG 품질 개선 & 비용/성능 최적화 — AI Engineer (Optimization) 역할

**날짜**: 2026-07-16
**가상 회사**: 컴퍼스랩(CompassLab) / 탈주컴퍼니
**오늘의 직무**: AI Engineer (성능/비용 최적화 담당)
**서비스명**: 탈주컴퍼니봇 🧭

---

## 1. 오늘 해결한 업무

Day 3에서 RAG를 붙여 할루시네이션은 줄었지만, 대표가 "답변이 느리다", "비용이 얼마나 나오는지 모르겠다", "가끔 엉뚱한 문서를 참조한다"고 지적했다. 이를 "느낌"이 아니라 **수치**로 측정하고 개선하는 하루였다.

## 2. 완료한 Must 항목

- [x] 질문-정답 테스트케이스 10개 작성 (Employment/Leave/Welfare 문서 기반, `answer_keywords` 포함)
- [x] top-k 값(1, 3, 5, 8)을 바꿔가며 retrieval/generation 정확도 비교
- [x] 동일 질문 캐싱 (완전 일치 기준, `(질문, top_k)` 조합 key, JSON 파일 저장)
- [x] 토큰 사용량 및 예상 비용 로그 기록 (`logs.jsonl`)

## 3. 최종 아키텍처

```
[사용자 질문]
     │
     ▼
get_cache_key(question, top_k=3)
     │
     ├── 캐시 히트 ──────────────────────► 저장된 reply 반환 (Groq 호출 X, 비용 0)
     │
     └── 캐시 미스
            │  build_rag_prompt(question, top_k=3)
            ▼
       [ChromaDB 검색 → chunk 삽입 프롬프트]
            │  client.chat.completions.create(...)
            ▼
       [Groq 응답 + completion.usage]
            │
            ├─► cache[key] = reply → save_cache()
            └─► log_usage(question, prompt_tokens, completion_tokens, cost) → logs.jsonl append
```

## 4. 사용 기술 스택 / 구조 변경

| 항목 | 내용 |
|---|---|
| 평가 스크립트 | `eval.py` — `test_cases`, `eval_retrieval`, `eval_generation` |
| 구조 리팩터링 | `client` 생성 로직을 `llm_client.py`로 분리 (main.py / eval.py 공용) |
| 캐싱 | `cache_utils.py` — `get_cache_key`, `load_cache`, `save_cache` (JSON 파일, 완전 일치 기준) |
| 로깅 | `log_utils.py` — `log_usage` (JSONL 파일, append 방식) |
| 비용 단가 | Input $0.00059 / 1K tokens, Output $0.00079 / 1K tokens |

---

## 5. top-k 실험 결과

| top_k | retrieval | generation | 격차 |
|---|---|---|---|
| 1 | 50.0% | 40.0% | -10%p |
| 3 | 100.0% | 70.0% | -30%p |
| 5 | 100.0% | 80.0% | -20%p |

- top_k=3부터 retrieval은 100%로 포화 → 검색 자체는 top_k=3이면 충분해 보임
- 그러나 retrieval 100%인데도 generation은 70~80%에 머무름 → "검색된 것처럼 보이지만 실제로는 실패"한 케이스 존재

## 6. 겪은 트러블슈팅 (실제 발생 순서)

### ① `eval_retrieval`의 "거짓 성공" 문제
- 증상: retrieval 100%인데 generation 실패 케이스(리프레시 휴가, 퇴사 절차) 발생
- 원인 추적: `build_rag_prompt`의 실제 출력을 직접 찍어본 결과, 정답 chunk가 top-5, 심지어 top-8 안에도 없었음
- 발견: keyword("별도", "30일")가 **엉뚱한 chunk**(간식비 별도 지원 / 자녀 출산 30일)에 우연히 매칭되어 `eval_retrieval`이 성공으로 잘못 판정한 것
- 의미: 짧고 일반적인 keyword 기반 채점은 "우연한 매칭"에 취약함 — 향후 metadata의 `source` 일치 여부로 채점 방식 개선 필요 (Day 5 이월)

### ② 질문-문서 표현 차이로 인한 검색 실패
- "리프레시 휴가는 연차를 **써야되는거야**?" vs chunk "연차와 **별도**" — 의미상 반대 개념이라 임베딩 유사도가 낮게 나와, top_k=8까지 늘려도 정답 chunk를 못 찾음
- top_k를 늘리는 것만으로는 해결되지 않는, 임베딩 검색의 근본적 한계로 확인됨

### ③ chunk_size=100으로 인한 문장 잘림 재발
- "퇴사 희망일 최소 30일 전... 인수인계 문서 작성 필수" 문장이 여전히 chunk 경계에서 잘려, top_k=8에서도 꼬리("필수")만 겨우 걸림
- Day 3에서 예고했던 chunk_size 문제가 그대로 재현됨

---

## 7. 최종 코드 (완성본)

### `llm_client.py`

```python
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
```

### `cache_utils.py`

```python
import json
import os

CACHE_FILE = "cache.json"

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_cache_key(question: str, top_k: int) -> str:
    key = f"질문: {question}, top_k: {top_k}"
    return key
```

### `log_utils.py`

```python
import json
from datetime import datetime

LOG_FILE = "logs.jsonl"

def log_usage(question: str, prompt_tokens: int, completion_tokens: int, cost: float):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 6)
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
```

### `main.py` (`/chat` 엔드포인트, 캐싱 + 로깅 반영)

```python
from fastapi import FastAPI
from pydantic import BaseModel
from rag_utils import build_rag_prompt
from cache_utils import load_cache, save_cache, get_cache_key
from log_utils import log_usage

app = FastAPI()
TOP_K = 3

from llm_client import client

class ChatRequest(BaseModel):
    message: str

conversation_history = []

@app.post("/chat")
def chat(request: ChatRequest):
    quiz = request.message

    key = get_cache_key(quiz, TOP_K)
    cache = load_cache()

    if key in cache:
        print(f"[캐시 히트] key={key}")
        reply = cache[key]
        log_usage(quiz, 0, 0, 0.0)
    else:
        print(f"[캐시 미스] key={key} → Groq 호출")
        context = build_rag_prompt(quiz, TOP_K)

        messages = [
            {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
        ] + conversation_history + [{"role": "user", "content": context}]

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = completion.choices[0].message.content

        cache[key] = reply
        save_cache(cache)

        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        INPUT_PRICE_PER_1K = 0.00059
        OUTPUT_PRICE_PER_1K = 0.00079
        cost = (prompt_tokens / 1000 * INPUT_PRICE_PER_1K) + (completion_tokens / 1000 * OUTPUT_PRICE_PER_1K)

        log_usage(quiz, prompt_tokens, completion_tokens, cost)

    conversation_history.append({"role": "user", "content": quiz})
    conversation_history.append({"role": "assistant", "content": reply})

    return {"reply": reply}

from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### `eval.py`

```python
from rag_utils import search_similar_chunks, build_rag_prompt
from llm_client import client

test_cases = [
    {"question": "건강을 지원해주는 제도가 있어?", "answer_keywords": ["건강검진", "심리상담"]},
    {"question": "성장을 지원해주는 제도가 있어?", "answer_keywords": ["도서구입비", "외부 교육"]},
    {"question": "식대는 얼마야?", "answer_keywords": ["15만원"]},
    {"question": "연차는 며칠이야?", "answer_keywords": ["25일"]},
    {"question": "경조사일 경우에는 얼마나 쉴 수 있어?", "answer_keywords": ["7일"]},
    {"question": "리프레시 휴가는 연차를 써야되는거야?", "answer_keywords": ["별도"]},
    {"question": "반차는 어떻게 사용해야돼?", "answer_keywords": ["4시간", "1일 전"]},
    {"question": "재택근무도 가능해?", "answer_keywords": ["주 2회"]},
    {"question": "수습기간 특이사항이 뭐야?", "answer_keywords": ["3개월", "80%"]},
    {"question": "퇴사는 어떻게 하면 돼?", "answer_keywords": ["30일", "인수인계"]},
]

def eval_retrieval(test_cases: list, top_k: int):
    success = 0
    for case in test_cases:
        results = search_similar_chunks(case["question"], top_k)
        context = "\n\n---\n\n".join(results["documents"][0])
        for keyword in case["answer_keywords"]:
            if keyword in context:
                success += 1
                break
    return (success / len(test_cases)) * 100

def eval_generation(test_cases: list, top_k: int):
    success = 0
    fail_logs = []
    for case in test_cases:
        prompt = build_rag_prompt(case["question"], top_k=top_k)
        messages = [
            {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
        ] + [{"role": "user", "content": prompt}]
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = completion.choices[0].message.content
        matched = any(keyword in reply for keyword in case["answer_keywords"])
        if matched:
            success += 1
        else:
            fail_logs.append({"question": case["question"], "reply": reply, "expected": case["answer_keywords"]})
    rate = (success / len(test_cases)) * 100
    return rate, fail_logs

if __name__ == "__main__":
    for k in [1, 3, 5]:
        r_rate = eval_retrieval(test_cases, k)
        g_rate, fails = eval_generation(test_cases, k)
        print(f"top_k={k} | retrieval: {r_rate}% | generation: {g_rate}%")
```

---

## 8. 오늘 배운 AI/개발 개념

- **평가(Evaluation)의 2단계 분리**: retrieval 평가(검색된 chunk에 정답이 있는가, LLM 호출 불필요)와 generation 평가(최종 답변에 정답이 있는가, LLM 호출 필요)를 나누면, 문제의 원인이 "검색"에 있는지 "생성"에 있는지 구분할 수 있음
- **키워드 기반 채점의 함정**: 짧고 일반적인 keyword는 의도치 않은 chunk에 우연히 매칭되어 "거짓 성공"을 만들 수 있음 — 정확한 평가를 위해서는 출처(metadata) 기반 채점이 더 안전할 수 있음
- **임베딩 검색의 한계**: 질문과 문서의 표현 방식이 다르면(동일 단어라도 반대 의미의 문맥), top_k를 아무리 늘려도 정답 chunk를 못 찾을 수 있음 — chunk_size나 임베딩 모델 자체의 한계
- **캐싱 설계**: 완전 일치 캐싱 vs 의미 기반(유사도) 캐싱의 트레이드오프. 의미 기반은 효율은 높지만 임계값 설계를 잘못하면 다른 질문에 같은 답을 주는 사고로 이어질 수 있음

---

## 9. 오늘의 회고

- **어려웠던/답답했던 부분**: chunk의 크기가 문제인 줄 알았는데, 사이즈를 키워도 벡터화를 진행하는 모델이 안 좋으면 결국 거리가 멀어지게 된다는 것을 알게되었다. 모델의 선택또한 매우 중요한 단계임을 알게되는 시간이었다.

- **내 성향과 잘 맞는 이유**: 보안보다는 어디를 print에서 어디가 문제인지 확인해야겠다는 고민과 결정을 내릴 수 있어서 보안보다는 인공지능이 좀 더 나와 맞는 거 같다.

- **내 성향과 맞지 않는 이유**: 외부 api를 써서 연동되는 경우가 많아서 조금 더 유연하고 포용적이고 적응을 빨리 잘하는 사고를 가질 필요가 있는 거 같다.

---

## 10. 실무 연결 포인트 및 다음 단계 (Day 5 예고)

오늘 발견한 세 가지 이슈는 Day 5(AI Agent)로 넘어가기 전에 반드시 짚고 갈 근본 문제였다:

1. **`eval_retrieval`의 채점 방식 개선** — keyword 매칭이 아니라 chunk의 `metadata["source"]`가 기대 문서와 일치하는지 확인하는 방식으로 전환 필요
2. **chunk_size/overlap 근본 재설계** — 문장/단락 경계를 존중하는 분할 방식 검토
3. **포괄적 질문에 대한 검색 취약점** — query expansion(질문 재구성) 등으로 완화 가능성 검토

이 문제들이 해결되지 않은 채로 Agent에 도구를 얹으면, Agent가 "검색은 했지만 틀린 근거로 판단하는" 상황이 그대로 이어질 가능성이 높다.
