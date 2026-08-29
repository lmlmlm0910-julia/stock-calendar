import os
import json
import urllib.request

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result['candidates'][0]['content']['parts'][0]['text']

def generate_stock_data():
    prompt = """
    당신은 최고 수준의 주식 시장 분석가입니다.
    다가오는 이번 주 및 다음 주의 한국 증시와 미국 증시 주요 일정을 분석해 주세요.
    
    반드시 아래와 같은 JSON 배열 형식으로만 응답해 주세요 (다른 설명글 절대 금지):
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
    최소 4개 이상의 주요 경제 지표 발표, 기업 이벤트, 실적 발표 일정을 구성해 주세요.
    """
    
    print("Gemini AI가 최신 증시 일정 및 수혜주를 분석 중입니다...")
    response_json_text = ask_gemini(prompt)
    data = json.loads(response_json_text)
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("data.json 업데이트 완료!")

if __name__ == "__main__":
    generate_stock_data()
