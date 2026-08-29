import os
import json
import urllib.request
import urllib.error

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini(prompt):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
        
    # 구글 표준 모델 경로로 수정 (404 에러 해결)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
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
    당신은 주식 시장 전문가입니다. 
    이번 주 및 다음 주 한국 증시와 미국 증시의 주요 증시 일정과 관련 수혜 종목을 작성해 주세요.
    
    반드시 아래와 같은 JSON 배열 형식으로만 작성하세요 (다른 설명글 절대 금지):
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
    raw_response = ask_gemini(prompt).strip()
    
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
    raw_response = raw_response.strip()

    data = json.loads(raw_response)
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("data.json 정상 업데이트 완료!")

if __name__ == "__main__":
    generate_stock_data()
