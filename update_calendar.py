import os
import json
from datetime import datetime
import yfinance as yf
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_real_market_data():
    """야후 파이낸스에서 실제 시장 종가 데이터를 100% 파이썬으로 수집"""
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 10년물": "^TNX",
        "미국 2년물": "^IRX"
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
                results[name] = {
                    "price": f"{close_price:,.2f}",
                    "change": f"{change_pct:+.2f}%"
                }
            elif len(hist) == 1:
                close_price = hist['Close'].iloc[-1]
                results[name] = {"price": f"{close_price:,.2f}", "change": "0.00%"}
            else:
                results[name] = {"price": "N/A", "change": "0.00%"}
        except Exception as e:
            print(f"데이터 수집 에러 ({name}): {e}")
            results[name] = {"price": "N/A", "change": "0.00%"}
            
    return results

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    # 1. 파이썬이 실제 수치 데이터 직접 수집 (AI가 숫자를 임의로 지어내지 못하도록 방지)
    real_data = get_real_market_data()
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    today_str = datetime.now().strftime("%Y년 %m월 %d일")

    # 2. Gemini AI에게는 수집된 실제 시세를 넘겨주고 '원인 분석 글'만 작성하도록 요청
    prompt = f"""
    당신은 월스트리트 수석 마켓 분석가입니다.
    오늘 [{today_str}] 마감된 미국 증시의 실제 수치 데이터는 다음과 같습니다:
    {json.dumps(real_data, ensure_ascii=False, indent=2)}

    위 실제 시세 데이터(나스닥, S&P500, 환율, VIX 등)의 등락을 바탕으로, 
    왜 해당 섹터로 돈이 쏠렸는지, 하방 압력을 받은 요인은 무엇인지 사실에 기반하여 분석 글만 작성해 주세요.

    반드시 아래 JSON 형식으로만 응답해 주세요 (설명글/마크다운 절대 금지):
    {{
      "strong_sectors_analysis": "<b>🔥 강한 자금 쏠림 섹터 분석:</b> 상승 요인 및 자금 유입 이유 상세 설명",
      "weak_sectors_analysis": "<b>❄️ 약세 섹터 분석:</b> 하방 압력 및 약세 요인 상세 설명",
      "fed_speeches_summary": "<b>🎙️ 연준(Fed) 발언 및 매크로 이슈:</b> 금리 및 통화정책 파급 효과 요약",
      "overall_market_summary": "오늘 마감된 미국 증시 전체 종합 시황 요약"
    }}
    """

    print("Gemini AI가 실제 시세를 바탕으로 분석 리포트를 작성 중...")
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

    # 3. 파이썬이 숫자는 100% 실제 데이터로, 글은 AI 분석글로 합쳐서 최종 JSON 생성
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
        {"tenor": "미국 2년물", "yield_rate": f"{real_data.get('미국 2년물', {}).get('price')}%", "change": real_data.get('미국 2년물', {}).get('change', '0.00%'), "status": "단기 국채"},
        {"tenor": "미국 10년물", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price')}%", "change": real_data.get('미국 10년물', {}).get('change', '0.00%'), "status": "기준 국채"}
      ],
      "strong_sectors_analysis": ai_analysis.get("strong_sectors_analysis", ""),
      "weak_sectors_analysis": ai_analysis.get("weak_sectors_analysis", ""),
      "fed_speeches_summary": ai_analysis.get("fed_speeches_summary", ""),
      "overall_market_summary": ai_analysis.get("overall_market_summary", "")
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 실제 수치 연동 완료!")

if __name__ == "__main__":
    generate_us_market_report()
