from fastapi import FastAPI         # 웹서버 구축
from pydantic import BaseModel      # 요청 데이터 포맷 정의             
from rag_utils import build_rag_prompt
from cache_utils import load_cache, save_cache, get_cache_key
from log_utils import log_usage

# FastAPI 객체 생성
app = FastAPI()
TOP_K = 3

from llm_client import client

# # get요청 시, 경로 지정
# @app.get("/")
# def health_check():
#     return {"status": "ok"}

# 사용자 요청 body 형태를 정의
class ChatRequest(BaseModel):
    message: str  # 사용자가 입력한 질문

# 히스토리
conversation_history = []

@app.post("/chat")
def chat(request: ChatRequest):
    # request.message를 가져와서
    quiz = request.message
    
    # 캐시 key 생성
    key = get_cache_key(quiz, TOP_K)
    # 캐시 불러오기
    cache  = load_cache()
    
    # key가 캐시에 있으면 -> 바로 반환
    if key in cache:
        print(f"[캐시 히트] key={key}")
        reply = cache[key]
        log_usage(quiz, 0, 0, 0.0)
        
    # 없으면 -> 기존 로직(RAG + Groq 호출) 실행
    else:
        print(f"[캐시 미스] key={key} → Groq 호출")
        # RAG 컨텍스트만 따로 만들기
        context = build_rag_prompt(quiz, TOP_K)

        # system 메시지 + 히스토리 + user_message 합쳐서 messages 구성
        messages = [
        {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
        ] + conversation_history + [{"role": "user", "content": context}]
        
        # Groq의 chat.completions.create() 호출
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        print(completion.usage)
        reply = completion.choices[0].message.content
        
        # 캐시에 저장
        cache[key] = reply
        save_cache(cache)
        
        # 로그에 누적
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        INPUT_PRICE_PER_1K = 0.00059   # USD, 1000 input 토큰당
        OUTPUT_PRICE_PER_1K = 0.00079  # USD, 1000 output 토큰당  
        cost = (prompt_tokens / 1000 * INPUT_PRICE_PER_1K) + (completion_tokens / 1000 * OUTPUT_PRICE_PER_1K)  
        
        log_usage(quiz, prompt_tokens, completion_tokens, cost)
        

    # 히스토리 업데이트
    conversation_history.append({"role": "user", "content": quiz})
    conversation_history.append({"role": "assistant", "content": reply})

    return {"reply": reply}

from fastapi.staticfiles import StaticFiles     # static 폴더 안에 있는 정적 파일들을 웹 브라우저에 통째로 배포
app.mount("/", StaticFiles(directory="static", html=True), name="static") 