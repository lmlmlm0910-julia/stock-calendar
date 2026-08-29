import os
import json
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def generate_stock_data():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    current_year = now.strftime("%Y")

    prompt = f"""
    당신은 글로벌 금융 시장 최고의 수석 아날리스트입니다.
    오늘 기준 날짜는 [{today_str}] 입니다.
    오늘 이후 다가오는 이번 주 및 다음 주의 한국 증시와 미국 증시 핵심 주요 일정을 최소 4개 이상 추출하여 매우 심도 있게 분석해 주세요.

    반드시 아래와 같은 순수한 JSON 배열 형식으로만 응답해 주세요 (설명글/마크다운 금지):

    [
      {{
        "year": "{current_year}",
        "date": "8월 31일",
        "day": "월",
        "title": "MSCI 지수 리밸런싱",
        "category": "국내 주식",
        "impact": "상",
        "overview": "MSCI 지수의 구성 종목 변경 및 비중 조정 작업입니다.",
        "importance": "글로벌 패시브 자금이 종목 변경에 따라 강제 이동하므로 단기 수급 변동성을 유발합니다.",
        "key_points": "종목 편입/편출에 따른 동시호가 수급 유입 및 외국인 순매수 변화.",
        "korea_impact": "편입 종목에는 외국인 패시브 자금이 유입되어 상승 모멘텀을 형성합니다.",
        "us_impact": "신흥국 지수 내 한국 비중 변화에 따라 글로벌 자금 이동이 나타납니다.",
        "stocks": ["LG이노텍"],
        "stock_reasons": "MSCI 지수 편입에 따른 패시브 자금 수혜 기대."
      }}
    ]
    """

    data = None
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        models_to_try = ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-2.0-flash']
        for model_name in models_to_try:
            try:
                print(f"Gemini AI 일정 분석 중 ({model_name})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                text = response.text.strip()
                if "```" in text:
                    lines = text.splitlines()
                    cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
                    text = "\n".join(cleaned_lines).strip()
                data = json.loads(text)
                print(f"[{model_name}] 일정 분석 성공!")
                break
            except Exception as e:
                print(f"[{model_name}] 실패: {e}")
    except Exception as err:
        print(f"API 호출 전체 에러: {err}")

    # API 한도 초과 시 기존 파일 유지 또는 기본 구조 생성하여 워크플로 실패 방지
    if not data:
        if os.path.exists("data.json"):
            print("API 제한으로 인해 기존 data.json을 유지합니다.")
            return
        data = [{
            "year": current_year,
            "date": "8월 31일",
            "day": "월",
            "title": "주요 증시 일정 자동 갱신 대기",
            "category": "증시 일정",
            "impact": "보통",
            "overview": "Gemini API 무료 한도 소진으로 기본 데이터가 표시됩니다. 내일 아침 6시 최신 일정으로 자동 업데이트됩니다.",
            "importance": "매일 아침 6시 자동 갱신",
            "key_points": "API 리셋 후 자동으로 최신 데이터 반영",
            "korea_impact": "정상 연동 대기 중",
            "us_impact": "정상 연동 대기 중",
            "stocks": ["주요 종목"],
            "stock_reasons": "자동 갱신 대기 중"
        }]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json 정상 처리 완료!")

if __name__ == "__main__":
    generate_stock_data()
