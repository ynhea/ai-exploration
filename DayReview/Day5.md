# Day 5. AI Agent 제작 — AI Agent Engineer 역할

**날짜**: 2026-07-17
**가상 회사**: 컴퍼스랩(CompassLab) / 탈주컴퍼니
**오늘의 직무**: AI Agent Engineer
**서비스명**: 탈주컴퍼니봇 🧭

---

## 1. 오늘 해결한 업무

HR팀에서 "연차가 며칠 남았는지 계산해달라", "리프레시 휴가 대상자인지 확인해달라" 같은, 단순 문서 검색만으로는 답할 수 없는 요청이 들어왔다. 지금까지의 봇은 "문서를 찾아서 그대로 전달"만 가능했는데, 이런 질문에 답하려면 **계산**이 필요하다. LLM이 상황에 따라 "검색이 필요한지 / 계산이 필요한지 / 둘 다 필요한지"를 스스로 판단해서 도구를 선택 실행하는 Agent를 Tool Calling으로 직접 구현했다.

## 2. 완료한 Must 항목

- [x] 휴가일수 계산 도구 함수 작성 (`calculate_annual_leave` — 근속연수 기반, `Leave.md` 규정 반영)
- [x] 기존 RAG 검색을 tool 형태로 감싸기 (`search_company_docs`)
- [x] Groq API에 `tools` 파라미터로 두 도구의 JSON Schema 전달
- [x] tool_call 수신 → 실제 함수 실행 → 결과를 `role: "tool"` 메시지로 재전달 → 최종 답변 생성 (왕복 로직)
- [x] 어떤 도구가 어떤 인자로 선택됐는지 콘솔 로그로 확인 (`[Agent 판단] 도구 선택: ...`)

## 2-1. 추가로 진행한 부분 (Should 영역)

- [x] 가드레일 추가 — 검색 결과가 빈 값일 때 "관련 문서를 찾지 못했습니다"로 명시적 치환, system 프롬프트에 "지어내지 마라 + 찾지 못한 건 그대로 알려라 + 한국어로만" 지침 강화
- [x] (Could) 멀티스텝 추론 테스트 — 도구 2개를 순차/동시 사용해야 하는 질문으로 검증, 발견된 구조적 한계(2턴 고정 → 이후 while 루프로 리팩터링)까지 해결

---

## 3. 최종 아키텍처

```
[사용자 질문]
     │
     ▼
messages = [system, user] 구성
     │
     ▼
┌─────────────── while (max_iterations만큼 반복) ───────────────┐
│  client.chat.completions.create(messages, tools=tools)         │
│       │                                                        │
│       ├─ tool_calls 없음 → 최종 답변으로 판단, 루프 종료 & 반환   │
│       │                                                        │
│       └─ tool_calls 있음                                       │
│              │ messages에 assistant(tool_calls 포함) 메시지 추가 │
│              ▼                                                 │
│         [calculate_annual_leave] 또는 [search_company_docs]     │
│         또는 둘 다 (parallel tool calls) 실행                    │
│              │ 실행 결과를 role:"tool" 메시지로 messages에 추가   │
│              ▼                                                 │
│         (루프 처음으로 돌아가 다시 LLM 호출)                      │
└──────────────────────────────────────────────────────────────┘
     │
     ▼ (max_iterations 초과 시)
"지금까지 알아낸 정보만으로 답하라" system 메시지 강제 추가 → tools 없이 1회 호출 → 반환
```

## 4. 사용 기술 스택

| 항목 | 내용 |
|---|---|
| Tool Calling | Groq API `tools` 파라미터 (OpenAI 호환 스펙) |
| 계산 도구 | `calculate_annual_leave` (근속연수 → 연차일수, `Leave.md` 규정 기반) |
| 검색 도구 | `search_company_docs` (Day3~4의 `search_similar_chunks` 재사용, top_k=5) |
| 반복 제어 | `for i in range(max_iterations)` + `tool_calls` 유무로 종료 판단 |
| 신규 파일 | `agent.py` (Agent 로직), `tool_utils.py` (도구 함수 모음) |

---

## 5. 겪은 트러블슈팅 (실제 발생 순서)

### ① `messages.append(response_message)` 직렬화 에러
- 증상: `groq.BadRequestError: ... property 'annotations' is unsupported`
- 원인: SDK가 반환하는 `response_message` 객체를 그대로 messages에 넣으면, Groq가 처리 못 하는 부가 필드(`annotations` 등)까지 그대로 재전송됨
- 해결: `role`, `content`, `tool_calls`만 골라 새 dict로 재구성해서 append

### ② 컬렉션이 완전히 빈 상태(`collection.count() == 0`)
- 증상: `search_company_docs("리프레시 휴가는 언제...")` → `{'context': ''}`, 빈 결과인데도 LLM이 "6개월 이상 근무", "연차 소진 시 사용" 등 문서에 없는 조건을 지어냄
- 원인: `chroma_db/`가 `.gitignore`에 포함되는 로컬 파일 기반 DB라, 이 워크스페이스에는 애초에 색인된 적이 없었음 (Day3~4의 색인 데이터가 이 환경에 없었음)
- 해결: `add_documents_to_db([...])` 재실행으로 3개 문서 재색인
- 배운 점: "코드는 멀쩡한데 서비스가 이상하게 동작"하는 문제의 원인이 로직이 아니라 **비어있는 데이터/상태**인 경우가 실무에서 흔함. 특히 `.gitignore`로 제외되는 로컬 저장소는 "내 컴퓨터에선 되는데 다른 환경에선 안 된다"의 단골 원인 → Day7 배포 설계 시 재색인 스크립트를 앱 시작 흐름에 포함하거나 DB를 외부화할 필요를 미리 확인함

### ③ 재색인 후에도 검색 실패 — "의미 희석" 문제 (chunk가 너무 큰 경우)
- 증상: 재색인 성공(`count=5`) 후에도 "리프레시 휴가" 검색 시 top-3에 정답 chunk가 안 잡힘
- 원인 추적: `Leave.md`가 290자로 짧아 chunk_size=300 하나에 연차/리프레시/경조사/반차 **4개 주제가 통째로** 담김 → 임베딩 벡터가 어느 한 주제에도 뚜렷하게 정렬되지 못해, "리프레시 휴가"라는 단어가 문장에 그대로 있는데도 무관한 단일 주제 chunk(반차)보다 유사도 순위가 밀림 (distance 1.5462로 최하위)
- 의미: Day3~4에서 겪은 "chunk가 작아서 잘리는" 문제의 **정반대 함정** — chunk가 크면 여러 주제가 섞여 검색 신호가 흐려짐. RAG의 chunk_size 트레이드오프를 양쪽 다 실전에서 확인
- 오늘의 대응: 근본적인 chunk 재설계(섹션 단위 분할 등) 대신 `top_k`를 3→5로 늘려 우회, 근본 수정은 Day4 이월 목록에 계속 남겨둠

### ④ 부분 완료 후 조기 종료 — 멀티스텝 질문에서 도구 하나만 쓰고 나머지는 지어냄
- 증상: "연차랑 리프레시 휴가 각각 며칠이야?" 질문에 `calculate_annual_leave`만 호출하고 `search_company_docs`는 안 부른 채, 리프레시 휴가 숫자(11일, 12일 등 매번 다른 값)를 지어내 답함
- 1차 시도: system 프롬프트에 "각 하위 항목마다 필요한 도구를 빠짐없이 호출하라" 지침 추가 → **효과 없음** (여전히 한 도구만 호출)
- 2차 시도(원인 좁히기): 질문 내 하위 항목 순서를 바꿔서 재현 → 순서와 무관하게 동일 패턴 재현, "먼저 언급된 것부터 처리" 가설 기각
- 근본 원인: `calculate_annual_leave`의 tool description이 "연차일수를 계산한다"로만 되어 있어, LLM이 "휴가"라는 큰 범주 전체를 이 도구 하나가 커버한다고 오판
- 해결: description을 "이 도구는 연차휴가만 계산하며, 리프레시/경조사 등 다른 휴가는 계산 못 한다. 다른 휴가는 `search_company_docs`를 쓰라"는 식으로 도구의 한계를 명시 → 이후 두 도구가 parallel tool calls로 한 번에 호출되며 정확한 답변(16일 / 5일) 생성
- 배운 점: tool calling에서는 문제 해결의 무게중심이 system 프롬프트보다 **tool description**에 더 크게 실릴 수 있음 — "무엇을 하라"보다 "무엇을 못 하는지"를 명시하는 게 더 효과적이었음

### ⑤ (구조적 개선) 2턴 고정 구조의 한계 → while 루프 + max_iterations 리팩터링
- 배경: 트러블슈팅 ④를 겪으며 애초에 `run_agent`가 "1턴 도구 호출 → 2턴 최종 답변"으로 고정된 구조라, 순차적으로 여러 번 도구가 필요한 질문 자체를 처리할 수 없었음 (2턴째 호출에 `tools`가 안 넘어감)
- 해결: `for i in range(max_iterations)` 반복문으로 변경, 매 반복마다 `tools`를 넘기고 `tool_calls`가 없을 때만 종료
- 안전장치: 무한/과도 반복 방지를 위해 `max_iterations` 도달 시, "지금까지 알아낸 정보만으로 답하라"는 system 메시지를 강제로 추가하고 `tools` 없이 1회 더 호출해 강제 마무리

---

## 6. 최종 코드 (완성본)

### `tool_utils.py`

```python
from rag_utils import search_similar_chunks

# 계산 Tool
def calculate_annual_leave(years_of_service: float) -> dict:
    """
    근속연수(년)를 받아서 연차일수를 계산한다.
    - 1년 미만: 개근 가정 시 근속 개월 수만큼 1일씩 (최대 11일)
    - 1년 이상: 15일 + (2년마다 1일 가산), 최대 25일
    """
    days = 0
    if years_of_service < 1:
        days = min(int(years_of_service * 12), 11)
    else:
        add = (years_of_service - 1) // 2
        days = min(int(15 + add), 25)
    return {"years_of_service": years_of_service, "annual_leave_days": days}

# 검색 Tool
def search_company_docs(question: str) -> dict:
    """
    사내 문서(취업규칙, 복지제도, 휴가정책)에서 질문과 관련된 내용을 검색한다.
    """
    results = search_similar_chunks(question, top_k=5)
    context = "\n\n---\n\n".join(results["documents"][0])

    if not context:
        context = "관련 문서를 찾지 못했습니다"

    return {"context": context}
```

### `agent.py`

```python
import json
from llm_client import client
from tool_utils import calculate_annual_leave, search_company_docs

# 1) LLM에게 알려줄 도구 스펙
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_annual_leave",
            "description": (
                "근속연수(년)를 입력받아 연차휴가 일수만 계산한다. "
                "리프레시 휴가, 경조사 휴가 등 연차 이외의 다른 휴가 종류는 이 도구로 계산할 수 없으며, "
                "그런 정보가 필요하면 search_company_docs를 사용해야 한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "years_of_service": {
                        "type": "number",
                        "description": "근속연수 (년 단위, 예: 1.5)"
                    }
                },
                "required": ["years_of_service"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_docs",
            "description": "사용자 질문을 입력받아, 사내 문서(취업규칙/복지제도/휴가정책)를 검색한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "사용자 질문"
                    }
                },
                "required": ["question"]
            }
        }
    }
]

# 2) 실제 파이썬 함수와 이름을 매핑
available_functions = {
    "calculate_annual_leave": calculate_annual_leave,
    "search_company_docs": search_company_docs
}

def run_agent(user_question: str, max_iterations: int = 5):
    messages = [
        {"role": "system", "content": """너는 사내 챗봇이다. 필요하면 도구를 사용해서 정확하게 답하라.
            도구 실행 결과에 없는 내용은 절대 지어내지 말고, 모르면 모른다고 답하라.
            도구 실행 결과에 '찾지 못했습니다'라고 나오면, 그 사실을 그대로 사용자에게 알려라.
            한자나 외국어는 사용하지 않고 한국어로만 답한다.
            각 하위 항목마다 필요한 도구를 빠짐없이 호출한 뒤에만 최종 답변을 작성하라.
        """},
        {"role": "user", "content": user_question}
    ]

    for i in range(max_iterations):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if not tool_calls:
            return response_message.content

        messages.append({
            "role": "assistant",
            "content": response_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ]
        })

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            print(f"[Agent 판단] (iteration {i+1}) 도구 선택: {function_name}, 인자: {function_args}")

            function_to_call = available_functions[function_name]
            function_response = function_to_call(**function_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(function_response)
            })

    # max_iterations를 다 돌았는데도 종료 못 한 경우 → 강제 마무리
    messages.append({"role": "system", "content": "지금까지 알아낸 정보만으로 최종 답을 내라"})
    second_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    return second_response.choices[0].message.content


if __name__ == "__main__":
    print(run_agent("입사한지 3년 됐는데 연차 며칠이야?"))
    print(run_agent("리프레시 휴가는 언제 받을 수 있어?"))
    print(run_agent("입사한지 3년 됐어. 연차랑 리프레시 휴가 각각 며칠씩 받을 수 있는지 알려줘"))
```

---

## 7. main.py 미연동 관련 메모

오늘 만든 `run_agent()`는 `agent.py`에서 `__main__`으로만 실행되는 상태이며, `main.py`의 `/chat` 엔드포인트는 여전히 Day4의 RAG-only(`build_rag_prompt`) 흐름을 그대로 사용 중이다. 즉 웹 UI(`static/index.html`)에는 아직 Agent가 연결되지 않았다.

`main.py` 통합 시 추가로 다뤄야 할 것 (다음 단계로 이월):
- `run_agent()`가 매번 `messages`를 새로 만드는 구조 → 기존 `conversation_history`(멀티턴 유지) 로직과 합치는 방법 설계 필요
- Day4에서 붙인 캐싱(`cache_utils`), 로깅(`log_utils`)이 Agent 구조에는 아직 없음 — tool 호출이 늘어난 만큼 토큰/비용 로그의 중요성이 오히려 커짐
- system 프롬프트가 Agent 전용으로 새로 작성된 상태라, 기존 `main.py`의 프롬프트와 통합/정리 필요

---

## 8. 오늘 배운 AI/개발 개념

- **Tool Calling(Function Calling)의 왕복 구조**: LLM에게 도구 스펙(JSON Schema)만 알려주고, 실제 실행 여부/인자는 LLM이 판단 → 우리 코드가 실행 → 결과를 `role: "tool"` 메시지로 다시 전달 → LLM이 최종 답변 생성
- **parallel tool calls**: 한 번의 응답에 여러 개의 `tool_calls`가 동시에 담겨 올 수 있음 (오늘 최종적으로 두 도구가 한 iteration에서 동시에 호출된 사례로 확인)
- **tool description의 중요성**: "무엇을 하라"는 system 프롬프트 지침보다, "이 도구는 무엇을 할 수 있고 무엇은 할 수 없는지"를 tool description에 명시하는 것이 도구 선택 정확도에 더 직접적인 영향을 줌
- **반복 제어(max_iterations)와 안전장치**: 순차적 다단계 도구 사용을 지원하려면 while/for 루프 구조가 필요하지만, 무한/과도 반복을 막기 위한 상한과 강제 종료 로직이 함께 필요
- **RAG chunk_size의 양방향 트레이드오프**: 너무 작으면 문장이 잘리고(Day3~4), 너무 크면 여러 주제가 섞여 임베딩 신호가 흐려짐(오늘) — 정답은 상황에 따라 다르며 무조건 크게/작게가 능사가 아님
- **빈 상태(empty state) 디버깅**: "코드는 정상인데 서비스가 이상하다"의 원인이 로직이 아니라 데이터/상태 자체가 비어있는 경우가 흔하다는 것을 직접 겪음

---

## 9. 오늘의 회고

- **재미있었던 부분**:
- **어려웠던/헷갈렸던 부분**:
- **가장 몰입했던 순간**:
- **이 업무를 하루 종일 하는 모습을 상상할 수 있는가**:
- **내 성향과 잘 맞는 이유**:
- **내 성향과 맞지 않는 이유**:

---

## 10. 실무 연결 포인트 및 다음 단계 (Day 6 예고)

오늘의 트러블슈팅은 Day 6(MCP 연동)로 넘어가기 전에 짚고 갈 지점을 명확히 남겼다:

1. **도구가 늘어날수록 description 설계의 중요성이 커짐** — MCP로 외부 도구(캘린더, 위키 등)까지 연결되면, 도구 간 역할 구분이 오늘보다 훨씬 복잡해질 것. description을 모호하게 두면 오늘 겪은 "부분 완료 후 조기 종료" 문제가 더 큰 규모로 재발할 가능성
2. **while 루프 + max_iterations 구조는 MCP 연동에도 그대로 재사용 가능** — Day 6에서 MCP 서버를 통해 도구가 추가되어도, 지금 짜놓은 반복 제어 로직 위에 도구만 얹으면 되는 구조
3. **main.py 통합은 여전히 미완** — Agent 검증이 끝났으니, 조만간 히스토리/캐싱/로깅과 함께 실제 서비스에 연결하는 작업이 필요
