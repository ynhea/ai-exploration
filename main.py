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
    # request.message를 가져와서
    quiz = request.message
    
    # Groq의 chat.completions.create() 호출
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": """
                - 너는 탈주컴퍼니에서 회사의 규정을 알려주는 챗봇이다.
                - 모르는 정보는 반드시 모른다고 답한다.
                  절대 그럴 듯한 답변을 하지 않는다.
                - 너는 회사 내부 문서에 접근할 권한이 없다. 사내 규정에 대한 구체적 수치나 조항은 절대 답하지 마라
                - 답변 톤은 질문답변톤을 장착한다.
                - 대부분은 100자 이내로 간결하게 답하며, 최대 200자까지 허용한다.
                - 한자나 외국어, 마크다운 문법은 제거한다
                  한국어로만 답한다.
                - 줄글보단, 읽기 좋게 정리해서 답변한다.
             """},
            {"role": "user", "content": "연차가 며칠이야?"},
            {"role": "assistant", "content": "연차 횟수에 대한 구체적인 정보는 모릅니다. 관련된 사항은 인사팀에 문의하세요."},
            {"role": "user", "content": "점심메뉴 추천해줘"},
            {"role": "assistant", "content": "사내 규정과 무관한 질문입니다."},
            {"role": "user", "content": quiz}
        ]
    )

    return {"reply": completion.choices[0].message.content}     # FastAPI는 딕셔너리 리턴을 자동으로 JSON문자열로 바꿈

from fastapi.staticfiles import StaticFiles     # static 폴더 안에 있는 정적 파일들을 웹 브라우저에 통째로 배포
app.mount("/", StaticFiles(directory="static", html=True), name="static") 