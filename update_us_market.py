import os
import json
from datetime import datetime
import yfinance as yf
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_real_market_data():
    """야후 파이낸스에서 실제 시장 종가 데이터를 100% 파이썬으로 직접 수집"""
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 2년물": "2YY=X",   # 미국 2년물 국채 금리
        "미국 10년물": "^TNX",    # 미국 10년물 국채 금리
        "미국 30년물": "^TYX"     # 미국 30년물 국채 금리
    }
    
    results = {}
    print("실제 금융 시장 시세 데이터를 수집 중...")
    
    for name, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                close_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change_pct = ((close_price - prev_price) / prev_price) * 100
                
                # 금리 지수(^TNX, ^TYX 등)는 야후 파이낸스에서 10배 표기되므로 10으로 나눔
                if symbol in ["^TNX", "^TYX", "2YY=X"]:
                    display_price = f"{close_price / 10:.2f}" if symbol != "2YY=X" else f"{close_price:.2f}"
                else:
                    display_price = f"{close_price:,.2f}"

                results[name] = {
                    "price": display_price,
                    "change": f"{change_pct:+.2f}%"
                }
            else:
                results[name] = {"price": "N/A", "change": "0.00%"}
        except Exception as e:
            print(f"데이터 수집 에러 ({name}): {e}")
            results[name] = {"price": "N/A", "change": "0.00%"}
            
    return results

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    # 1. 실제 금융 데이터 수집
    real_data = get_real_market_data()
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    today_str = datetime.now().strftime("%Y년 %m월 %d일")

    # 2. Gemini AI에게는 실제 시세 데이터 기반으로 분석 텍스트만 요청
    prompt = f"""
    당신은 월스트리트 수석 마켓 분석가입니다.
    오늘 [{today_str}] 마감된 미국 증시의 실제 수치 데이터는 다음과 같습니다:
    {json.dumps(real_data, ensure_ascii=False, indent=2)}

    위 실제 시세 데이터(5대 지수, 2Y/10Y/30Y 국채 금리, 환율, VIX, 유가)를 기반으로 
    왜 특정 섹터로 자금이 쏠렸는지, 약세 섹터의 하방 압력 요인은 무엇인지, 연준 위원 발언이나 매크로 이슈는 무엇이었는지 사실에 근거하여 작성해 주세요.

    반드시 아래 JSON 형식으로만 응답해 주세요 (마크다운/설명글 절대 금지):
    {{
      "strong_sectors_analysis": "<b>🔥 강한 자금 쏠림 섹터 분석:</b> 상승 요인 및 자금 유입 이유 상세 설명",
      "weak_sectors_analysis": "<b>❄️ 약세 섹터 분석:</b> 하방 압력 및 약세 요인 상세 설명",
      "fed_speeches_summary": "<b>🎙️ 연준(Fed) 발언 및 매크로 이슈:</b> 금리 및 통화정책 파급 효과 요약",
      "overall_market_summary": "오늘 마감된 미국 증시 전체 종합 시황 요약"
    }}
    """

    print("Gemini AI가 실제 시세 데이터를 바탕으로 시황 리포트를 작성 중...")
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )

    text = response.text.strip()
    if "```" in text:
        lines = text.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(cleaned_lines).strip()

    ai_analysis = json.loads(text)

    # 3. 2년물, 10년물, 30년물 금리를 모두 포함하여 final_json 구성
    final_json = {
      "updated_at": f"{today_str} 미국장 마감 직후",
      "macro_indicators": [
        {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price')}원", "change": real_data.get('원/달러 환율', {}).get('change', '0.00%'), "status": "외환시세"},
        {"name": "VIX 지수 (공포지수)", "value": real_data.get('VIX 지수', {}).get('price', 'N/A'), "change": real_data.get('VIX 지수', {}).get('change', '0.00%'), "status": "변동성 지수"},
        {"name": "WTI 유가 (원유)", "value": f"${real_data.get('WTI 유가', {}).get('price')}", "change": real_data.get('WTI 유가', {}).get('change', '0.00%'), "status": "국제 유가"}
      ],
      "indices": [
        {"name": "S&P 500", "value": real_data.get('S&P 500', {}).get('price', 'N/A'), "change": real_data.get('S&P 500', {}).get('change', '0.00%')},
        {"name": "다우존스", "value": real_data.get('다우존스', {}).get('price', 'N/A'), "change": real_data.get('다우존스', {}).get('change', '0.00%')},
        {"name": "나스닥", "value": real_data.get('나스닥', {}).get('price', 'N/A'), "change": real_data.get('나스닥', {}).get('change', '0.00%')},
        {"name": "필라델피아 반도체", "value": real_data.get('필라델피아 반도체', {}).get('price', 'N/A'), "change": real_data.get('필라델피아 반도체', {}).get('change', '0.00%')},
        {"name": "러셀 2000", "value": real_data.get('러셀 2000', {}).get('price', 'N/A'), "change": real_data.get('러셀 2000', {}).get('change', '0.00%')}
      ],
      "treasury_yields": [
        {"tenor": "미국 2년물", "yield_rate": f"{real_data.get('미국 2년물', {}).get('price')}%", "change": real_data.get('미국 2년물', {}).get('change', '0.00%'), "status": "단기 금리"},
        {"tenor": "미국 10년물", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price')}%", "change": real_data.get('미국 10년물', {}).get('change', '0.00%'), "status": "기준 금리"},
        {"tenor": "미국 30년물", "yield_rate": f"{real_data.get('미국 30년물', {}).get('price')}%", "change": real_data.get('미국 30년물', {}).get('change', '0.00%'), "status": "장기 금리"}
      ],
      "strong_sectors_analysis": ai_analysis.get("strong_sectors_analysis", ""),
      "weak_sectors_analysis": ai_analysis.get("weak_sectors_analysis", ""),
      "fed_speeches_summary": ai_analysis.get("fed_speeches_summary", ""),
      "overall_market_summary": ai_analysis.get("overall_market_summary", "")
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json (2Y/10Y/30Y 포함) 정상 업데이트 완료!")

if __name__ == "__main__":
    generate_us_market_report()
