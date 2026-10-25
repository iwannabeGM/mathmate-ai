
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="중학교 3학년 수준의 이차방정식 문제를 하나 만들어줘. 정답과 풀이도 알려줘."
)

print(response.text)
