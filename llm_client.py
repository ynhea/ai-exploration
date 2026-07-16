from groq import Groq   # Groq API 라이브러리
import os
from dotenv import load_dotenv      

load_dotenv()       # .env 파일의 환경 변수를 시스템에 로드

# os.getenv()로 GEMINI_API_KEY를 읽어오기
GEMINI_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GEMINI_API_KEY)