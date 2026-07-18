import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
from llm_client import client


FILESYSTEM_DOCS_PATH = r"C:\Users\PC\Workspace\3주\인공지능\documents"

# client가 실행 -> 백그라운드에서 서버 2개 실행
server_params_local = StdioServerParameters(command="python", args=["mcp_server.py"])
server_params_fs = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", FILESYSTEM_DOCS_PATH],
)

# LLM과 연결
async def run_agent_multi_mcp(user_question: str, max_iterations: int = 5):
    # 서버 2개 각각 Sesstion 설정
    async with stdio_client(server_params_local) as (read1, write1), \
               stdio_client(server_params_fs) as (read2, write2):
        async with ClientSession(read1, write1) as session_local, \
                   ClientSession(read2, write2) as session_fs:

            await session_local.initialize()
            await session_fs.initialize()

            tools_local = (await session_local.list_tools()).tools
            
            tools_fs = (await session_fs.list_tools()).tools
            ALLOWED_FS_TOOLS = {"read_text_file", "list_directory"}
            tools_fs = [t for t in tools_fs if t.name in ALLOWED_FS_TOOLS]

            # 두 목록을 합쳐서 groq_tools 만들기 (Step2에서 했던 변환 로직 재사용)
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

            # 어떤 도구 이름이 어느 세션 소속인지 알아야, 나중에 call_tool을 올바른 세션으로 보낼 수 있다.
            tool_to_session = {}
            for tool in tools_local:
                tool_to_session[tool.name] = session_local
            for tool in tools_fs:
                tool_to_session[tool.name] = session_fs

            print("우리 서버 도구:", [t.name for t in tools_local])
            print("filesystem 서버 도구:", [t.name for t in tools_fs])
        

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
                    print(f"[경고] LLM 호출 실패: {e}")
                    # 루프를 빠져나가서 아래의 "지금까지 알아낸 정보로 답하라" 로직으로 넘어감
                    messages.append({"role": "system", "content": "지금까지 알아낸 정보만으로 최종 답을 내라"})
                    fallback_response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
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
                        print(f"[경고] tool call 인자 파싱 실패: {tool_call.function.arguments}")
                        if function_name == "search_company_docs":
                            # 깨진 question 대신 사용자의 원본 질문을 그대로 사용
                            function_args = {"question": user_question}
                        else:
                            # calculate_annual_leave처럼 숫자 인자인 도구는
                            # 대신 채워줄 안전한 기본값이 없으니, 이번 호출은 건너뛴다
                            continue

                    print(f"[Agent 판단] 도구 선택: {function_name}, 인자: {function_args}")

                    # TODO 2: available_functions 딕셔너리 직접 실행 대신
                    #         session.call_tool(function_name, function_args) 사용
                    #   힌트: 결과는 result.content (리스트) 안에 TextContent 객체들이 들어있음
                    #         result.content[0].text 로 실제 문자열 값을 꺼낼 수 있다
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
    result = asyncio.run(run_agent_multi_mcp("입사한지 3년 됐어. 연차랑 리프레시 휴가 각각 며칠씩 받을 수 있는지 알려줘"))
    print(result)