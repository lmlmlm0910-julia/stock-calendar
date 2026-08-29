import os
import json
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")

    prompt = f"""
    당신은 월스트리트 수석 마켓 분석가입니다.
    오늘 기준 날짜 [{today_str}] 마감된 미국 증시 시황 리포트를 작성해 주세요.
    추측성 의견이나 개인적 주관은 완전히 배제하고, 실제 공시된 수치와 사실 뉴스에 근거해서만 작성하세요.

    반드시 아래와 같은 순수한 JSON 구조로만 응답해 주세요 (설명글/마크다운 금지):

    {{
      "updated_at": "{today_str} 미국장 마감 직후",
      "macro_indicators": [
        {{"name": "원/달러 환율", "value": "1,335.50원", "change": "-4.20원", "status": "환율 안정세"}},
        {{"name": "VIX 지수 (공포지수)", "value": "15.40", "change": "-1.10", "status": "시장 변동성 완화"}},
        {{"name": "WTI 유가 (원유)", "value": "$74.80/bbl", "change": "+$0.65", "status": "유가 강보합"}}
      ],
      "indices": [
        {{"name": "S&P 500", "value": "5,648.40", "change": "+0.73%"}},
        {{"name": "다우존스", "value": "41,240.50", "change": "+0.55%"}},
        {{"name": "나스닥", "value": "17,713.00", "change": "+1.13%"}},
        {{"name": "필라델피아 반도체", "value": "5,102.30", "change": "+2.20%"}},
        {{"name": "러셀 2000", "value": "2,210.10", "change": "-0.15%"}}
      ],
      "treasury_yields": [
        {{"tenor": "미국 2년물", "yield_rate": "3.89%", "change": "-0.04%p", "status": "단기 금리 안정"}},
        {{"tenor": "미국 10년물", "yield_rate": "3.85%", "change": "-0.02%p", "status": "기준 금리 하락"}},
        {{"tenor": "미국 30년물", "yield_rate": "4.14%", "change": "-0.01%p", "status": "장기 금리 보합"}}
      ],
      "strong_sectors_analysis": "<b>🔥 반도체 및 대형 테크(M7) 자금 쏠림:</b> 글로벌 AI 서버 증설 수요 지속과 주요 반도체 기업들의 긍정적인 가이던스 발표로 대형 기술주 중심으로 강력한 수급 유입이 나타났습니다.",
      "weak_sectors_analysis": "<b>❄️ 필수소비재 및 유통 섹터 하방 압력:</b> 하반기 경기 둔화에 따른 소비자 지출 위축 우려 공시가 나오면서 관련 유통주들이 상대적 약세를 보였습니다.",
      "fed_speeches_summary": "<b>🎙️ 연준(Fed) 인사 발언 및 금리 이슈:</b> 인플레이션 하향 안정화 신호와 노동 시장 균형에 근거하여 통화정책 재조정 가능성이 시사됨에 따라 시장의 금리 인하 기대감이 유지되었습니다.",
      "overall_market_summary": "금일 미국 증시는 국채 금리 및 VIX 지수의 안정적인 흐름 속에서 반도체 섹터의 강한 주도로 나스닥과 S&P 500 지수가 상승 마감했습니다."
    }}
    """

    print(f"Gemini AI 미국 시황 분석 실행 중 ({today_str})...")
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

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("us_market.json 생성 성공!")

if __name__ == "__main__":
    generate_us_market_report()
