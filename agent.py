import json
from llm_client import client
from tool_utils import calculate_annual_leave, search_company_docs
from tool_utils import search_company_docs
from rag_utils import search_similar_chunks, collection

# 1) LLM에게 알려줄 도구 스펙
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_annual_leave",
            "description": "이 도구는 연차휴가 일수만 계산하며, 리프레시/경조사 등 다른 휴가 종류는 계산하지 못한다. 다른 휴가 정보는 search_company_docs를 사용하라",
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
        # TODO: search_company_docs용 스펙 작성
        # 힌트: 파라미터는 question 하나뿐, type은 "string"
        "type": "function",
        "function": {
            "name": "search_company_docs",
            "description": "사용자 질문을 입력받아, 사내 문서를 검색한다.",
            "parameters": {
                "type": "object",   # dict으로 내보냄
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

# 2) 실제 파이썬 함수와 이름을 매핑 (tool_calls의 name으로 실제 함수를 찾기 위함)
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
        각 하위 항목마다 필요한 도구를 빠짐없이 호출한 뒤에만 최종 답변을 작성하라
    """},
    {"role": "user", "content": user_question}
    ]

    for i in range(max_iterations):
        print(f"===== iteration {i+1} 시작 =====")
        # client.chat.completions.create(...) 호출 (매번 tools=tools를 넘김)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # tool_calls가 없으면 (LLM이 도구 없이 바로 답한 경우) → 최종 답변이 나온 것이므로 그대로 반환하고 함수 종료
        if not tool_calls:
            print(f"===== iteration {i+1}에서 종료 (tool_calls 없음) =====")
            return response_message.content

        # tool_calls가 있는 경우
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
                for tc in tool_calls        # 리스트 컴프리헨션
            ]
        })
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            print(f"[Agent 판단] 도구 선택: {function_name}, 인자: {function_args}")

            # available_functions에서 function_name에 해당하는 실제 함수를 찾아서 function_args를 넣어 실행
            function_to_call = available_functions[function_name]
            function_response = function_to_call(**function_args)   # 딕셔너리 언패킹

            # 실행 결과를 role: "tool" 메시지로 messages에 추가
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": function_name, "content": str(function_response)})
    # 여기서 루프가 다시 돌면서, 방금 추가된 tool 결과를 포함해 다시 LLM 호출됨

    # TODO: for 루프가 max_iterations만큼 다 돌았는데도 break를 못 만난 경우
    #   (도구를 계속 요청하기만 하고 최종 답변을 안 낸 상황) → 어떻게 처리할지 생각해보기
    #   힌트: "지금까지 알아낸 정보만으로 최종 답을 내라"는 메시지를 강제로 붙여서 tools 없이 한 번 더 호출
    messages.append({"role": "system", "content": "지금까지 알아낸 정보만으로 최종 답을 내라"})
    second_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    return second_response.choices[0].message.content


if __name__ == "__main__":
    print(run_agent("입사한지 3년 됐어. 리프레시 휴가랑 연차 각각 며칠씩 받을 수 있는지 알려줘"))