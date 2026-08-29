import os
import json
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def generate_stock_data():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. Secrets를 확인해 주세요.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """
    당신은 주식 시장 전문가입니다. 
    이번 주 및 다음 주 한국 증시와 미국 증시의 주요 증시 일정과 관련 수혜 종목을 작성해 주세요.
    
    반드시 순수한 JSON 배열 형식으로만 응답해 주세요. 마크다운 기호(```json 등)나 추가 설명글은 모두 제외해 주세요.
    [
      {
        "date": "8월 31일",
        "day": "월",
        "title": "MSCI 지수 리밸런싱",
        "category": "국내 주식",
        "impact": "중",
        "details": "[편입] LG이노텍 | [편출] HLB, LG디스플레이",
        "stocks": ["LG이노텍"],
        "analysis": "MSCI 편입으로 LG이노텍에 외국인 패시브 자금 유입이 기대됩니다."
      }
    ]
    """

    print("Gemini AI 분석 실행 중...")
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )

    text = response.text.strip()

    if "```" in text:
        lines = text.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(cleaned_lines).strip()

    data = json.loads(text)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json 정상 업데이트 완료!")

if __name__ == "__main__":
    generate_stock_data()
