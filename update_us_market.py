import os
import json
import urllib.request
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def fetch_yahoo_quote(symbol):
    """차단 방지 헤더를 사용하여 야후 파이낸스 실시간 시세를 직접 수집"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            result = data['chart']['result'][0]
            meta = result['meta']
            
            price = meta.get('regularMarketPrice')
            prev_close = meta.get('chartPreviousClose') or meta.get('previousClose')
            
            if price is not None and prev_close is not None and prev_close != 0:
                change_pct = ((price - prev_close) / prev_close) * 100
                return price, change_pct
    except Exception as e:
        print(f"[{symbol}] 시세 수집 실패: {e}")
        
    return None, None

def get_real_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 2년물": "2YY=X",
        "미국 10년물": "^TNX",
        "미국 30년물": "^TYX"
    }
    
    results = {}
    print("야후 파이낸스 API에서 차단 우회하여 시세 수집 중...")
    
    for name, symbol in tickers.items():
        price, change_pct = fetch_yahoo_quote(symbol)
        
        if price is not None and change_pct is not None:
            # 국채 금리 지수 단위 조정 (10년물, 30년물)
            if symbol in ["^TNX", "^TYX"] and price > 10:
                price = price / 10.0
                
            formatted_price = f"{price:,.2f}" if price >= 1 else f"{price:.4f}"
            formatted_change = f"{change_pct:+.2f}%"
        else:
            formatted_price = "N/A"
            formatted_change = "0.00%"
            
        results[name] = {
            "price": formatted_price,
            "change": formatted_change
        }
        
    return results

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    real_data = get_real_market_data()
    client = genai.Client(api_key=GEMINI_API_KEY)
    today_str = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""
    당신은 월스트리트 수석 마켓 분석가입니다.
    오늘 [{today_str}] 마감된 미국 증시의 실제 시세 데이터는 다음과 같습니다:
    {json.dumps(real_data, ensure_ascii=False, indent=2)}

    위 시세 데이터(5대 지수, 2Y/10Y/30Y 국채 금리, 환율, VIX, 유가)의 실황을 기반으로 
    강세 섹터의 수급 유입 요인, 약세 섹터의 하방 압력 악재, 연준 위원 발언을 사실에 근거하여 작성해 주세요.

    반드시 아래 JSON 형식으로만 응답해 주세요 (설명글/마크다운 금지):
    {{
      "strong_sectors_analysis": "<b>🔥 강한 자금 쏠림 섹터 분석:</b> 자금 유입 이유 상세 설명",
      "weak_sectors_analysis": "<b>❄️ 약세 섹터 분석:</b> 하방 압력 요인 상세 설명",
      "fed_speeches_summary": "<b>🎙️ 연준(Fed) 발언 및 매크로 이슈:</b> 통화정책 파급 효과 요약",
      "overall_market_summary": "오늘 마감된 미국 증시 전체 종합 시황 요약"
    }}
    """

    print("Gemini AI가 리포트 생성 중...")
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
        {"tenor": "미국 10년물", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price')}%", "change": real_data.get('미국 10년물', {}).get('change', '0.00%'), "status": "기준 국채"},
        {"tenor": "미국 30년물", "yield_rate": f"{real_data.get('미국 30년물', {}).get('price')}%", "change": real_data.get('미국 30년물', {}).get('change', '0.00%'), "status": "장기 국채"}
      ],
      "strong_sectors_analysis": ai_analysis.get("strong_sectors_analysis", ""),
      "weak_sectors_analysis": ai_analysis.get("weak_sectors_analysis", ""),
      "fed_speeches_summary": ai_analysis.get("fed_speeches_summary", ""),
      "overall_market_summary": ai_analysis.get("overall_market_summary", "")
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 정상 업데이트 완료!")

if __name__ == "__main__":
    generate_us_market_report()
