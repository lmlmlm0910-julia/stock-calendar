import os
import json
from datetime import datetime
import yfinance as yf
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_real_market_data():
    """야후 파이낸스에서 실제 금요일 마감 지수/금리/환율/유가/VIX 데이터 긁어오기"""
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 10년물 금리": "^TNX",
        "미국 2년물 금리": "^IRX"
    }
    
    fetched_data = {}
    print("야후 파이낸스에서 실제 시장 종가 데이터를 수집 중...")
    for name, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change_pct = ((close - prev) / prev) * 100
                fetched_data[name] = {
                    "price": round(close, 2),
                    "change_pct": f"{change_pct:+.2f}%"
                }
            else:
                fetched_data[name] = {"price": "N/A", "change_pct": "0.00%"}
        except Exception as e:
            print(f"데이터 수집 예외 ({name}): {e}")
            fetched_data[name] = {"price": "N/A", "change_pct": "0.00%"}
            
    return fetched_data

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    # 1. 실제 시장 수치 수집
    market_facts = get_real_market_data()
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    today_str = datetime.now().strftime("%Y년 %m월 %d일")

    # 2. 실제 수치를 Gemini AI에게 전달하여 깊이 있는 원인 분석만 요청
    prompt = f"""
    당신은 월스트리트 수석 마켓 분석가입니다.
    오늘 기준 날짜 [{today_str}] 마감된 미국 증시의 실제 수치 데이터는 다음과 같습니다:
    {json.dumps(market_facts, ensure_ascii=False, indent=2)}

    위의 [실제 시장 데이터]를 바탕으로, 지수 및 금리/매크로 변화의 근거 있는 원인 분석 리포트를 작성해 주세요.
    추측성 소설이나 왜곡 없이, 왜 해당 섹터로 돈이 쏠렸는지, 하방 압력을 받은 섹터의 악재 원인은 무엇인지, 연준 발언 영향을 사실 기반으로 정리해 주세요.

    반드시 아래와 같은 순수한 JSON 구조로만 응답해 주세요 (설명글/마크다운 절대 금지):

    {{
      "updated_at": "{today_str} 미국장 마감 직후",
      "macro_indicators": [
        {{"name": "원/달러 환율", "value": "{market_facts.get('원/달러 환율', {}).get('price')}원", "change": "{market_facts.get('원/달러 환율', {}).get('change_pct')}", "status": "외환시장 종가"}},
        {{"name": "VIX 지수 (공포지수)", "value": "{market_facts.get('VIX 지수', {}).get('price')}", "change": "{market_facts.get('VIX 지수', {}).get('change_pct')}", "status": "변동성 지수"}},
        {{"name": "WTI 유가 (원유)", "value": "${market_facts.get('WTI 유가', {}).get('price')}", "change": "{market_facts.get('WTI 유가', {}).get('change_pct')}", "status": "국제 유가"}}
      ],
      "indices": [
        {{"name": "S&P 500", "value": "{market_facts.get('S&P 500', {}).get('price')}", "change": "{market_facts.get('S&P 500', {}).get('change_pct')}"}},
        {{"name": "다우존스", "value": "{market_facts.get('다우존스', {}).get('price')}", "change": "{market_facts.get('다우존스', {}).get('change_pct')}"}},
        {{"name": "나스닥", "value": "{market_facts.get('나스닥', {}).get('price')}", "change": "{market_facts.get('나스닥', {}).get('change_pct')}"}},
        {{"name": "필라델피아 반도체", "value": "{market_facts.get('필라델피아 반도체', {}).get('price')}", "change": "{market_facts.get('필라델피아 반도체', {}).get('change_pct')}"}},
        {{"name": "러셀 2000", "value": "{market_facts.get('러셀 2000', {}).get('price')}", "change": "{market_facts.get('러셀 2000', {}).get('change_pct')}"}}
      ],
      "treasury_yields": [
        {{"tenor": "미국 2년물", "yield_rate": "{market_facts.get('미국 2년물 금리', {}).get('price')}%", "change": "{market_facts.get('미국 2년물 금리', {}).get('change_pct')}", "status": "단기 국채"}},
        {{"tenor": "미국 10년물", "yield_rate": "{market_facts.get('미국 10년물 금리', {}).get('price')}%", "change": "{market_facts.get('미국 10년물 금리', {}).get('change_pct')}", "status": "기준 국채"}}
      ],
      "strong_sectors_analysis": "<b>🔥 자금 쏠림 섹터 분석:</b> 실제 수치 상승을 이끈 반도체 및 대형 테크 종목으로의 수급 유입 배경과 호재 요인 설명.",
      "weak_sectors_analysis": "<b>❄️ 약세 섹터 분석:</b> 매도세가 집중되어 하방 압력을 받은 섹터의 기업 실적, 악재 뉴스 및 하락 이유 설명.",
      "fed_speeches_summary": "<b>🎙️ 연준(Fed) 발언 및 매크로 이슈:</b> 채권 금리 변동을 유발한 연준 위원들의 발언 및 경제지표 여파 요약.",
      "overall_market_summary": "오늘 마감된 미국 증시 전체 종합 시황 요약."
    }}
    """

    print("Gemini AI가 실시간 금융 데이터를 바탕으로 시황 리포트를 생성 중...")
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

    print("us_market.json 실시간 분석 업데이트 성공!")

if __name__ == "__main__":
    generate_us_market_report()
