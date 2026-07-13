from fastapi import FastAPI         # 웹서버 구축
from dotenv import load_dotenv
from pydantic import BaseModel      # 요청 데이터 포맷 정의
from groq import Groq               # Groq API 라이브러리
import os

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

@app.post("/chat")
def chat(request: ChatRequest):
    # TODO 1: request.message를 가져와서
    quiz = request.message
    
    # TODO: Groq의 chat.completions.create()를 호출해보세요.
    # 힌트: OpenAI 스타일이라 messages=[{"role": "user", "content": ...}] 형태
    # model 이름은 "llama-3.3-70b-versatile"
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": quiz}
        ]
    )

    return {"reply": completion.choices[0].message.content}     # FastAPI는 딕셔너리 리턴을 자동으로 JSON문자열로 바꿈

from fastapi.staticfiles import StaticFiles     # static 폴더 안에 있는 정적 파일들을 웹 브라우저에 통째로 배포
app.mount("/", StaticFiles(directory="static", html=True), name="static") 