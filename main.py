from fastapi import FastAPI         # 웹서버 구축
from dotenv import load_dotenv
from pydantic import BaseModel      # 요청 데이터 포맷 정의
from groq import Groq               # Groq API 라이브러리
import os
from rag_utils import build_rag_prompt

# .env 파일의 환경 변수를 시스템에 로드
load_dotenv()

# FastAPI 객체 생성
app = FastAPI()

# os.getenv()로 GEMINI_API_KEY를 읽어오기
GEMINI_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GEMINI_API_KEY)

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
    
    # TODO 1: RAG 컨텍스트만 따로 만들기
    context = build_rag_prompt(quiz)

    # TODO 2: system 메시지 + 히스토리 + user_message 합쳐서 messages 구성
    messages = [
    {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
    ] + conversation_history + [{"role": "user", "content": context}]
    
    # Groq의 chat.completions.create() 호출
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    reply = completion.choices[0].message.content

    # TODO 3: 히스토리 업데이트
    conversation_history.append({"role": "user", "content": quiz})
    conversation_history.append({"role": "assistant", "content": reply})

    return {"reply": reply}

from fastapi.staticfiles import StaticFiles     # static 폴더 안에 있는 정적 파일들을 웹 브라우저에 통째로 배포
app.mount("/", StaticFiles(directory="static", html=True), name="static") 