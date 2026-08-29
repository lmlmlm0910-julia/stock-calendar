import os
import json
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def generate_stock_data():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. Secrets를 확인해 주세요.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    current_year = now.strftime("%Y")

    prompt = f"""
    당신은 글로벌 금융 시장 최고의 수석 아날리스트입니다.
    오늘 기준 날짜는 [{today_str}] 입니다.
    오늘 이후 다가오는 이번 주 및 다음 주의 한국 증시와 미국 증시 핵심 주요 일정(경제지표 발표, 금리/중앙은행 회의, 기업 이벤트, 실적 발표 등)을 최소 4개 이상 추출하여 매우 심도 있게 분석해 주세요.

    반드시 아래와 같은 순수한 JSON 배열 형식으로만 응답해 주세요. 마크다운 기호(```json 등)나 기타 서론/결론 텍스트는 절대 포함하지 마세요.

    [
      {{
        "year": "{current_year}",
        "date": "8월 31일",
        "day": "월",
        "title": "MSCI 지수 리밸런싱",
        "category": "국내 주식",
        "impact": "상",
        "overview": "MSCI(모건스탠리 캐피털 인터내셔널) 지수의 분기/반기 구성 종목 변경 및 비중 조정 작업입니다.",
        "importance": "글로벌 패시브 자금(지수를 추종하는 펀드 자금)이 종목 변경에 따라 수조 원 단위로 강제 이동하므로 단기 수급 급변동을 유발합니다.",
        "key_points": "종목 편입/편출에 따른 동시호가 종가 자금 집행 규모, 외국인 순매수/순매도 유입량.",
        "korea_impact": "편입 종목에는 대규모 외국인 자금이 유입되어 상승 모멘텀을 형성하는 반면, 편출 종목은 기관/외국인 매물 압박으로 단기 하락 변동성이 커집니다.",
        "us_impact": "글로벌 신흥국(EM) 지수 내 한국 비중 변화에 따라 미국계 자금의 유출입 방향성이 결정됩니다.",
        "stocks": ["LG이노텍", "HLB", "LG디스플레이"],
        "stock_reasons": "LG이노텍: MSCI 지수 편입 확정으로 약 1,500억 원 이상의 외국인 패시브 자금 유입 수혜 예상. HLB/LG디스플레이: 편출에 따른 매도 물량 출회 주의."
      }}
    ]
    """

    print(f"Gemini AI 심층 분석 실행 중 (기준일: {today_str})...")
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

    print("data.json 심도 분석 업데이트 완료!")

if __name__ == "__main__":
    generate_stock_data()
