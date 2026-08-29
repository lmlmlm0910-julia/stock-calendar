import os
import json
import urllib.request
import urllib.error

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def ask_gemini(prompt):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. GitHub Secrets를 확인해 주세요.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['candidates'][0]['content']['parts'][0]['text']
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[API HTTP 에러 발생] 코드: {e.code}, 상세내용: {error_body}")
        raise RuntimeError(f"HTTP Error {e.code}: {error_body}")
    except Exception as e:
        print(f"[일반 에러 발생] {str(e)}")
        raise

def generate_stock_data():
    prompt = """
    당신은 주식 시장 전문가입니다. 
    이번 주 및 다음 주 한국 증시와 미국 증시의 주요 증시 일정과 관련 수혜 종목을 작성해 주세요.
    
    반드시 순수한 JSON 배열 형식으로만 응답해 주세요. 마크다운 기호나 설명글은 완전히 제외해 주세요.
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
    
    print("Gemini AI 분석 요청 중...")
    text = ask_gemini(prompt).strip()
    
    # 마크다운 래핑 제거
    if "```" in text:
        lines = text.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(cleaned_lines).strip()
        
    print("수신된 응답 처리 중...")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[JSON 파싱 에러] 수신 원문:\n{text}")
        raise e
        
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("data.json 정상 업데이트 성공!")

if __name__ == "__main__":
    generate_stock_data()
