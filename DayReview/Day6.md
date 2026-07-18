# Day 6. 외부 도구 연동(MCP) & 통합 트러블슈팅 — Platform/Integration Engineer 역할

**날짜**: 2026-07-18
**가상 회사**: 컴퍼스랩(CompassLab) / 탈주컴퍼니
**오늘의 직무**: AI Platform Engineer
**서비스명**: 탈주컴퍼니봇 🧭

---

## 1. 오늘 해결한 업무

Day 5까지 만든 Agent(`agent.py`)는 `tool_utils.py`의 함수를 직접 import해서 쓰는 구조였다. 오늘은 이걸 MCP(Model Context Protocol) 표준으로 감싸서, ①직접 MCP 서버를 만들어보고 ②그 서버를 Agent가 클라이언트로서 호출하도록 연결하고 ③공개 MCP 서버(filesystem)까지 동시에 붙여, 여러 서버를 연결할 때 실제로 어떤 문제가 생기는지 직접 겪어보는 하루였다.

## 2. 완료한 Must 항목

- [x] MCP가 해결하는 문제(N×M 조합 문제) 개념적으로 이해
- [x] 직접 MCP 서버 구현 (`mcp_server.py`, `tool_utils.py`의 기존 도구를 그대로 재사용)
- [x] Day5의 Agent를 MCP 클라이언트로 재구성 (`agent_mcp.py`) — 도구 스펙을 손으로 안 적고 서버로부터 자동으로 받아옴
- [x] Agent-MCP 서버 간 통신 성공/실패를 로그로 직접 추적

## 2-1. 추가로 진행한 부분 (Should 영역)

- [x] 공개 MCP 서버(`@modelcontextprotocol/server-filesystem`) 연결
- [x] 여러 MCP 서버 동시 연결 (`stdio_client`, `ClientSession` 두 세트) 및 `tool_to_session` 매핑으로 도구별 세션 라우팅 구현
- [x] 여러 서버 연결 시 발생한 충돌 문제(도구 역할 중복, 도구 폭증) 직접 겪고 화이트리스트 필터링으로 완화

---

## 3. 최종 아키텍처

```
[mcp_server.py]  ─┐  (우리 서버: calculate_annual_leave, search_company_docs)
                   │  stdio
[filesystem MCP]  ─┤  (공개 서버: read_text_file, list_directory — 화이트리스트 필터링 후)
                   │  stdio
                   ▼
        [agent_mcp.py = MCP 클라이언트]
             │
             ├─ session.list_tools() × 2 → 도구 스펙 자동 수집 → groq_tools 병합
             ├─ tool_to_session = {도구명: 소속 세션}  (라우팅 테이블)
             │
             ▼
   client.chat.completions.create(messages, tools=groq_tools)
             │
             ├─ tool_calls 없음 → 최종 답변 반환
             └─ tool_calls 있음
                    │ try: json.loads(arguments) → 실패 시 폴백(원본 질문 재사용 / skip)
                    ▼
             tool_to_session[도구명].call_tool(도구명, 인자)
                    │
                    ▼
             결과를 role:"tool" 메시지로 추가 → 반복
```

## 4. 사용 기술 스택 / 구조 변경

| 항목 | 내용 |
|---|---|
| MCP 서버 SDK | `mcp` (Python), `FastMCP` |
| 우리 서버 | `mcp_server.py` — `mcp.tool()(기존 함수)` 방식으로 `tool_utils.py` 재사용 (로직 복붙 없이 단일 진실 공급원 유지) |
| MCP 클라이언트 | `agent_mcp.py` — `stdio_client` + `ClientSession`, `async/await` 최초 도입 |
| 공개 서버 | `@modelcontextprotocol/server-filesystem` (npx 실행) |
| 다중 서버 연결 | `stdio_client`/`ClientSession` 두 세트 동시 오픈, `tool_to_session` 딕셔너리로 호출 라우팅 |
| 안전장치 | tool call 인자 JSON 파싱 실패 시 폴백, LLM 호출(400 등) 실패 시 폴백 |

---

## 5. 겪은 트러블슈팅 (실제 발생 순서)

### ① Tool call 인자가 간헐적으로 깨져서 옴 (모델 자체의 불안정성)
- 증상: 도구 2개를 연속 호출(계산 → 검색)할 때, `search_company_docs`의 `question` 인자가 이중 이스케이프된 깨진 유니코드 문자열로 오는 경우가 간헐적으로 발생 (`\\ubd83` 형태)
- 원인 조사: `repr()`로 raw `tool_call.function.arguments`를 직접 찍어본 결과, 우리 코드의 디코딩 문제가 아니라 **LLM(Groq `llama-3.3-70b-versatile`)이 함수 호출 인자를 생성하는 단계에서 이미 깨진 문자열을 출력**하고 있음을 확인
- 재현성 확인: 도구 1개만 필요한 단독 질문("반차는 어떻게 써?")은 5회 연속 모두 정상. 도구 2개를 연속 호출해야 하는 질문에서만 간헐적으로 재발 → "이전 tool 실행 결과가 대화에 낀 상태에서 한글 인자를 새로 생성"하는 조건이 불안정성과 관련 있는 것으로 추정(모델 내부 동작이라 100% 확정은 어려움)
- 대응: 근본 수정이 불가능한 영역이므로, `json.loads()`를 `try/except`로 감싸 파싱 실패 시 `search_company_docs`는 원본 사용자 질문으로 대체, 그 외 도구는 해당 호출을 skip하는 가드레일 적용

### ② 다중 MCP 서버 연결 시 도구 폭증 → Groq API 400 에러
- 증상: 우리 서버(도구 2개) + filesystem 서버(도구 14개) = 총 16개 도구를 한 번에 넘기자, `groq.BadRequestError: tool_use_failed`가 발생. `failed_generation` 필드를 보면 함수 호출 문법 자체를 완성하지 못한 채 깨진 한글로 끊겨 있었음
- 원인 분석: (1) `search_company_docs`(우리 서버)와 `search_files`(filesystem 서버)가 의도상 경쟁 관계에 놓여 모델의 도구 선택 판단을 어렵게 만듦 (2) 도구 후보가 2개→16개로 8배 늘면서, 이미 간헐적으로 불안정했던 한글 인자 생성(트러블슈팅 ④)이 API 레벨 실패로까지 악화된 것으로 추정
- 대응: filesystem 서버의 도구 14개 중 실제로 필요한 것만 화이트리스트로 필터링(`read_text_file`, `list_directory`만 허용) → 도구 후보를 4개로 축소 → 이후 반복 실행에서 400 에러 재현되지 않고 답변도 정확(16일/5일)하게 안정화됨
- 의미: Day6 커리큘럼이 예고했던 "여러 MCP 서버 연결 시 충돌/우선순위 문제"를 실증적으로 겪고 완화한 사례. 도구가 늘어날수록 역할 중복 제거와 후보 축소가 안정성에 직접적인 영향을 준다는 것을 확인


---

## 6. 최종 코드 (핵심 부분)

### `mcp_server.py`

```python
from mcp.server.fastmcp import FastMCP
from tool_utils import calculate_annual_leave, search_company_docs

mcp = FastMCP("compasslab-tools")

# tool_utils.py를 유일한 진실 공급원으로 유지 (로직 복붙 없이 감싸기만 함)
mcp.tool()(calculate_annual_leave)
mcp.tool()(search_company_docs)

if __name__ == "__main__":
    mcp.run()  # stdio transport
```

### `agent_mcp.py` (다중 서버 연결 + 가드레일 반영 최종본)

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from llm_client import client

FILESYSTEM_DOCS_PATH = r"C:\Users\PC\Workspace\3주\인공지능\documents"

server_params_local = StdioServerParameters(command="python", args=["mcp_server.py"])
server_params_fs = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", FILESYSTEM_DOCS_PATH],
)

async def run_agent_multi_mcp(user_question: str, max_iterations: int = 5):
    async with stdio_client(server_params_local) as (read1, write1), \
               stdio_client(server_params_fs) as (read2, write2):
        async with ClientSession(read1, write1) as session_local, \
                   ClientSession(read2, write2) as session_fs:

            await session_local.initialize()
            await session_fs.initialize()

            tools_local = (await session_local.list_tools()).tools
            tools_fs = (await session_fs.list_tools()).tools

            # 트러블슈팅 ⑥ 대응: 도구 후보 축소 (역할 중복 도구 배제)
            ALLOWED_FS_TOOLS = {"read_text_file", "list_directory"}
            tools_fs = [t for t in tools_fs if t.name in ALLOWED_FS_TOOLS]

            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                }
                for tool in tools_local + tools_fs
            ]

            tool_to_session = {}
            for tool in tools_local:
                tool_to_session[tool.name] = session_local
            for tool in tools_fs:
                tool_to_session[tool.name] = session_fs

            messages = [
                {"role": "system", "content": """너는 사내 챗봇이다. 필요하면 도구를 사용해서 정확하게 답하라.
                    도구 실행 결과에 없는 내용은 절대 지어내지 말고, 모르면 모른다고 답하라.
                    한자나 외국어는 사용하지 않고 한국어로만 답한다.
                """},
                {"role": "user", "content": user_question}
            ]

            for i in range(max_iterations):
                try:
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        tools=groq_tools
                    )
                except Exception as e:
                    # 트러블슈팅 ⑥: LLM 호출 자체가 실패해도 서비스가 죽지 않도록 폴백
                    print(f"[경고] LLM 호출 실패: {e}")
                    messages.append({"role": "system", "content": "지금까지 알아낸 정보만으로 최종 답을 내라"})
                    fallback_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile", messages=messages
                    )
                    return fallback_response.choices[0].message.content

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
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        }
                        for tc in tool_calls
                    ]
                })

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        # 트러블슈팅 ④: 간헐적으로 깨지는 인자에 대한 가드레일
                        print(f"[경고] tool call 인자 파싱 실패: {tool_call.function.arguments}")
                        if function_name == "search_company_docs":
                            function_args = {"question": user_question}
                        else:
                            continue

                    print(f"[Agent 판단] 도구 선택: {function_name}, 인자: {function_args}")

                    result = await tool_to_session[function_name].call_tool(function_name, function_args)
                    function_response = result.content[0].text

                    messages.append({
                        "role": "tool", "tool_call_id": tool_call.id,
                        "name": function_name, "content": str(function_response)
                    })

            messages.append({"role": "system", "content": "지금까지 알아낸 정보만으로 최종 답을 내라"})
            second_response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
            return second_response.choices[0].message.content


if __name__ == "__main__":
    result = asyncio.run(run_agent_multi_mcp(
        "입사한지 3년 됐어. 연차랑 리프레시 휴가 각각 며칠씩 받을 수 있는지 알려줘"
    ))
    print(result)
```

### `tool_utils.py` — 오늘 수정된 부분 (description 강화)

```python
def search_company_docs(question: str) -> dict:
    """
    사내 문서(취업규칙, 복지제도, 휴가정책)에서 질문과 관련된 내용을 검색한다.
    연차휴가 일수 계산 이외의 모든 정책성 질문(리프레시 휴가, 경조사 휴가, 복지제도, 근무시간,
    수습기간, 퇴사절차 등)은 반드시 이 도구로 확인해야 하며, 다른 도구로는 알 수 없다.
    """
    ...
```

---

## 7. 오늘 배운 AI/개발 개념

- **MCP(Model Context Protocol)의 목적**: 도구를 표준화된 형태(서버)로 노출하면, Agent(클라이언트)는 그 서버에 "무슨 도구 있어?"라고 물어 스펙을 자동으로 받아올 수 있음 — N개 Agent × M개 도구를 일일이 연결하던 문제를 N+M 구조로 줄임
- **MCP 클라이언트-서버 아키텍처**: `stdio_client`로 서버 프로세스와 read/write 채널을 열고, `ClientSession`으로 `list_tools()`(스펙 조회) / `call_tool()`(실행 위임) 왕복을 수행
- **여러 MCP 서버 동시 연결의 실전 트레이드오프**: 서버를 더 붙일수록 기능은 늘지만, 도구 후보 공간이 커질수록 모델의 함수 호출 정확도가 떨어짐 — "도구는 많을수록 좋다"가 아니라, 실제 필요한 도구만 선별해서 노출하는 것이 안정성에 직결됨

---

## 8. 오늘의 회고

- **재미있었던 부분**: 점차 근거 기반으로 효과적인 AI Agent를 만들어가고 있다는 느낌을 받은 게 좋았다.
- **어려웠던/헷갈렸던 부분**: 아직은 스스로 print를 찍어서 원인을 찾아내고 다음 행동을 판단하는 능력이 부족하다고 느꼈다. 코드의 빈칸을 채우는 감각과, 왜 이 구조가 필요한지를 스스로 설계하는 감각 사이에 아직 거리가 있다는 걸 오늘 여러 번 체감했다

---

## 9. 실무 연결 포인트 및 다음 단계 (Day 7 예고)

오늘의 트러블슈팅은 Day 7(배포/QA)로 넘어가기 전에 짚고 갈 지점을 남겼다:

1. **도구 화이트리스트가 하드코딩된 상태** — 새 MCP 서버를 붙일 때마다 코드를 직접 고쳐야 하는 구조. 설정 파일이나 환경변수로 분리하면 유지보수가 쉬워짐
2. **LLM 호출 실패 시 폴백 답변이 근거 없이 지어내질 수 있음이 확인됨** — "일시적 오류로 정확한 답변을 드릴 수 없습니다" 같은 안전한 실패 문구로 교체 필요
3. **`agent_mcp.py`도 아직 `main.py`(웹 서비스)에는 연결되지 않은 상태** — Day5의 `agent.py`와 마찬가지로, 실제 서비스 통합은 미완
4. **Day 7 배포 시 고려할 것**: MCP 서버들을 Docker로 함께 패키징할지, 각 서버의 콜드 스타트 비용(트러블슈팅 ②)을 어떻게 흡수할지 미리 설계 필요
