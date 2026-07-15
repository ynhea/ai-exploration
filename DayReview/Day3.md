# Day 3. 사내 문서 검색 RAG 구축 — AI Engineer (Search) 역할

**날짜**: 2026-07-15
**가상 회사**: 컴퍼스랩(CompassLab)
**오늘의 직무**: AI Engineer (RAG 담당)
**서비스명**: 탈주컴퍼니봇 🧭

---

## 1. 오늘 해결한 업무

HR팀이 "프롬프트만으로는 봇이 실제 회사 정책을 모른다"는 피드백을 줬다. 취업규칙, 복지제도, 휴가정책 등 실제(더미) 사내 문서를 봇이 검색해서 답변에 활용하도록, 문서 → chunk 분할 → embedding → ChromaDB 저장 → 유사도 검색 → LLM 답변 생성까지 이어지는 RAG 파이프라인을 처음부터 직접 구현했다.

## 2. 완료한 Must 항목

- [x] 더미 사내 문서 3개 작성 (`Employment.md`, `Leave.md`, `Welfare.md`)
- [x] 문서를 chunk 단위로 분할 (`split_into_chunks`)
- [x] 로컬 embedding 모델(`sentence-transformers`, `all-MiniLM-L6-v2`)로 chunk 벡터화
- [x] ChromaDB에 저장 및 유사도 검색 구현 (`add_documents_to_db`, `search_similar_chunks`)
- [x] 검색된 chunk를 프롬프트에 삽입해 답변 생성, Day 1~2 챗봇과 연결 (`build_rag_prompt` → `main.py`)

## 2-1. 추가로 진행한 부분 (Should 영역, 일부 시도)

- [x] 대화 히스토리(멀티턴) 유지 기능 추가 — `conversation_history` 전역 리스트로 질문/답변만 저장
- [ ] chunk 크기 비교 실험 (100 vs 300) — 진행함, 결론은 100으로 되돌림 (아래 트러블슈팅 참고)
- [ ] 출처 표시 — 아직 미적용 (`metadatas`에 `source`는 저장해뒀으나 응답에 노출 안 함)

## 3. 최종 아키텍처

```
[더미 문서 3개: Employment.md, Leave.md, Welfare.md]
     │  split_into_chunks() — chunk_size=100, overlap=50
     ▼
[chunk 리스트]
     │  embedding_model.encode()  (all-MiniLM-L6-v2, 384차원)
     ▼
[벡터] ──▶ collection.add(ids, embeddings, documents, metadatas) ──▶ [ChromaDB: company_docs]

--- 질문이 들어오면 ---

[사용자 질문]
     │  embedding_model.encode()로 동일하게 벡터화
     ▼
[질문 벡터] ──▶ collection.query(query_embeddings, n_results=top_k) ──▶ [유사 chunk top-3]
     │
     ▼
[system 메시지 + conversation_history(질문/답변만) + 이번 턴 user 메시지(참고자료+질문)]
     │  client.chat.completions.create(...)
     ▼
[Groq LLM 답변] ──▶ conversation_history에 (quiz, reply) 추가 ──▶ 사용자에게 반환
```

## 4. 사용 기술 스택

| 항목 | 처음 계획 | 최종 사용 |
|---|---|---|
| Embedding | OpenAI Embedding API | **sentence-transformers (all-MiniLM-L6-v2, 로컬/무료)** |
| Vector DB | ChromaDB | ChromaDB (PersistentClient, 로컬 저장) |
| chunk 분할 | 직접 구현 | 직접 구현 (`split_into_chunks`) |
| LLM | Groq (Day1과 동일) | Groq (`llama-3.3-70b-versatile`) |
| 멀티턴 히스토리 | 미정 | 전역 리스트 `conversation_history` (질문/답변만 저장) |

---

## 5. 겪은 트러블슈팅 (실제 발생 순서)

### ① `text[start, end]` — 슬라이싱 문법 실수
- 증상: chunk 분할 함수에서 콤마와 콜론을 혼동
- 원인: `text[start, end]`는 슬라이싱이 아니라 튜플을 인덱스로 쓰는 것으로 해석됨
- 해결: `text[start:end]`로 수정

### ② chunk 길이와 이동 거리(step)를 혼동
- 증상: overlap이 전혀 반영되지 않음
- 원인: "chunk를 얼마나 자를지"와 "다음 시작점을 얼마나 옮길지"를 같은 변수로 계산
- 해결: `end = start + chunk_size` (자르는 길이) / `start = end - overlap` (다음 시작점)로 분리

### ③ `metadatas`를 f-string으로 잘못 생성
- 증상: `f"{"source": filename}"` 같은 문법 에러 반복
- 원인: 딕셔너리를 만드는 것과 문자열을 만드는 것(f-string)을 혼동
- 해결: `{"source": filename}` — f-string 없이 순수 딕셔너리 리터럴로 작성

### ④ embedding 차원 관련 오해
- 궁금증: "임베딩 차원을 고려 안 해도 되나?", "384차원은 내용이 작아서 그런가?"
- 정리: 차원 수는 텍스트 길이와 무관하며, 모델이 설계 시 정해놓은 "표현력" 값. 저장/검색 시 **같은 embedding 모델을 일관되게 사용**하는 것만 신경 쓰면 됨

### ⑤ chunk_size 실험 (100 vs 300)
- chunk_size=100: 검색된 chunk가 문장 중간에서 잘리는 문제 발생 ("가산"이 "산"으로 잘림)
- chunk_size=300: 검색은 더 큰 문맥을 포함하지만, 상위 1개 외 2·3위 결과의 distance가 급격히 커짐(0.72 → 1.35, 1.41) → 관련 없는 문서(Employment.md, Welfare.md)가 억지로 포함되는 현상 확인
- 결론: 오늘은 일단 chunk_size=100으로 되돌리고 진행, 근본적 개선(적정 chunk_size 탐색, distance 기반 필터링)은 Day 4로 이월

### ⑥ chunk 잘림이 실제 답변 품질에 영향을 줌 (오늘의 핵심 발견)
- 증상: "연차는 며칠이야?" 질문에 봇이 **"산은 최대 25일입니다"**라고 답함
- 원인: chunk_size=100으로 자르면서 원문 "가산(최대 25일)"의 앞부분 "가"가 잘려 "산"만 chunk에 남았고, LLM이 이를 그대로 인용
- 의미: RAG를 붙이면 할루시네이션(지어내기)은 확실히 줄어들지만, **chunk 품질이 나쁘면 "지어내진 않지만 부정확한" 답변**이 나올 수 있음을 직접 체감
- Day 4로 이월: chunk 크기/overlap 재조정, 필요시 문장/단락 경계를 존중하는 분할 방식 고려

### ⑦ 멀티턴 히스토리 설계 — context를 히스토리에 저장할지 여부
- 고민: 검색된 참고자료(context)까지 `conversation_history`에 매번 쌓으면, 턴이 늘어날수록 과거 참고자료가 계속 재전송되어 토큰 비용이 급격히 증가하고 맥락이 오염될 수 있음
- 해결: `conversation_history`에는 **원본 질문(quiz)과 답변(reply)만** 저장하고, 참고자료(context)는 매 턴 새로 검색해서 그 턴의 user 메시지에만 임시로 포함
- 남은 이슈: system 메시지의 지침("모르면 모른다고 답하라")과 `build_rag_prompt`가 만든 프롬프트 내 지침이 일부 중복됨 — 동작에는 문제없으나 유지보수 관점에서 `get_context`(지침 없이 chunk만 반환) 함수로 분리하는 것이 더 깔끔함 (오늘은 시간 관계상 중복 허용한 채로 마무리)

---

## 6. 최종 코드 (완성본)

### `rag_utils.py`

```python
from sentence_transformers import SentenceTransformer
import chromadb

def split_into_chunks(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap은 chunk_size보다 작아야 합니다!")
    start = 0
    chunk_list = []
    while start < len(text):
        end = start + chunk_size
        chunk_list.append(text[start:end])
        start = end - overlap
    return chunk_list

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="company_docs")

def add_documents_to_db(doc_filenames: list[str]):
    for filename in doc_filenames:
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = split_into_chunks(text, chunk_size=100, overlap=50)
        vectors = embedding_model.encode(chunks)
        ids = [f"{filename}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename} for i in range(len(chunks))]
        collection.add(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)
    return

def search_similar_chunks(question: str, top_k: int = 3):
    question_vector = embedding_model.encode([question])
    results = collection.query(query_embeddings=question_vector, n_results=top_k)
    return results

def build_rag_prompt(question: str, top_k: int = 3) -> str:
    results = search_similar_chunks(question, top_k=top_k)
    context = "\n\n---\n\n".join(results["documents"][0])
    prompt = f"""다음은 사내 문서에서 검색된 참고 자료입니다:
---
{context}
---
위 자료를 참고하여 다음 질문에 답하세요. 자료에 없는 내용은 "모르겠습니다"라고 답하세요.
질문: {question}"""
    return prompt

if __name__ == "__main__":
    # add_documents_to_db(["documents/Employment.md","documents/Leave.md","documents/Welfare.md"])
    print(build_rag_prompt("연차는 며칠이야?"))
```

### `main.py`

```python
from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from groq import Groq
import os
from rag_utils import build_rag_prompt

load_dotenv()

app = FastAPI()

GEMINI_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GEMINI_API_KEY)

class ChatRequest(BaseModel):
    message: str

conversation_history = []  # 질문/답변만 저장 (참고자료는 저장하지 않음)

@app.post("/chat")
def chat(request: ChatRequest):
    quiz = request.message

    context = build_rag_prompt(quiz)  # 검색 + 지침 프롬프트까지 포함된 문자열

    messages = [
        {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
    ] + conversation_history + [{"role": "user", "content": context}]

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    reply = completion.choices[0].message.content

    conversation_history.append({"role": "user", "content": quiz})
    conversation_history.append({"role": "assistant", "content": reply})

    return {"reply": reply}

from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

---

## 7. 오늘 배운 AI/개발 개념

- **검색(Search) vs RAG**: 검색은 관련 조각을 그대로 반환하는 것, RAG는 그 조각을 LLM에 넘겨 자연어로 종합·재구성한 답변까지 생성하는 것 (Retrieval + Generation)
- **Embedding**: 텍스트를 "의미가 비슷하면 벡터도 가깝게" 만드는 수치 변환. 차원 수(예: 384)는 텍스트 길이와 무관하며 모델의 표현력 설계값
- **ChromaDB (Vector Database)**: 벡터를 저장하고 "유사도 기반"으로 검색하는 저장소. 일반 DB의 정확 일치 검색과 대조됨
- **Chunking과 chunk_size/overlap의 트레이드오프**: 너무 작으면 문맥이 잘리고(예: "가산"→"산"), 너무 크면 무관한 chunk가 상위 결과에 섞여 들어옴
- **distance 값의 의미**: 작을수록 유사. 상위 결과와 하위 결과 간 distance 격차가 크면, 하위 결과는 사실 "억지로 채워진" 무관한 결과일 가능성이 높음
- **멀티턴 히스토리 설계 원칙**: 히스토리에는 대화 내용(질문/답변)만 유지하고, RAG 참고자료는 매 턴 새로 계산해서 임시로만 사용 — 그렇지 않으면 턴이 쌓일수록 토큰 비용이 누적적으로 증가

## 8. 오늘의 회고

- **재미있었던 부분**: 문서 → chunk → 벡터 → 검색 → 답변으로 이어지는 파이프라인이 실제로 눈앞에서 동작하는 걸 확인하는 과정이 흥미로웠다. 특히 "산은 최대 25일입니다"처럼 예상 못한 결과를 보고 원인을 거꾸로 추적해가는 과정이 꽤 몰입됐다.
- **어려웠던/헷갈렸던 부분**: 딕셔너리 리터럴과 f-string을 계속 혼동했고, 함수의 지역 변수(scope) 개념이 처음에 잘 안 와닿아서 "이미 만든 context를 왜 또 함수로 빼야 하냐"는 부분에서 시간이 좀 걸렸다. RAG 파이프라인 자체보다, 이런 기본 파이썬 문법/개념에서 더 막혔던 것 같다.
- **가장 몰입했던 순간**: chunk_size를 100 → 300으로 바꿔보고 다시 100으로 되돌리며, distance 숫자와 실제 답변 품질이 어떻게 같이 움직이는지 비교하던 구간. "검색이 된다"와 "검색 결과가 쓸모 있다"가 다른 얘기라는 걸 체감한 부분이 인상 깊었다.

## 9. 실무 연결 포인트 및 다음 단계(Day 4 예고)

오늘 발견한 chunk 잘림 문제("가산" → "산")는 RAG의 근본적인 트레이드오프를 보여주는 사례였다. Day 4에서는 이 문제를 다음 방향으로 이어서 다룰 예정:
- chunk_size/overlap을 정량적으로 비교 평가 (질문-정답 테스트케이스 활용)
- distance 임계값 기반으로 "관련 없는 결과 걸러내기(fallback)" 로직 추가
- 검색·생성에 드는 토큰/비용 로그화

멀티턴 히스토리 설계에서 "참고자료는 저장하지 않고 매번 새로 계산"하는 패턴은, 실무에서 비용 최적화와 컨텍스트 오염 방지를 위해 흔히 쓰이는 방식이라는 점도 오늘 자연스럽게 체감했다.
