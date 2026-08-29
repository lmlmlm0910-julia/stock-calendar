import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_market_date_string():
    """토/일요일 실행 시 금요일 마감일자 계산"""
    now = datetime.now()
    weekday = now.weekday()
    if weekday == 5:
        market_date = now - timedelta(days=1)
    elif weekday == 6:
        market_date = now - timedelta(days=2)
    else:
        market_date = now
    days = ['월', '화', '수', '목', '금', '토', '일']
    return market_date.strftime(f"%Y년 %m월 %d일({days[market_date.weekday()]})")

def fetch_real_quotes():
    """야후 파이낸스에서 실제 시세 및 등락률 수집"""
    symbols = ["^GSPC", "^DJI", "^IXIC", "^SOX", "^RUT", "KRW=X", "^VIX", "CL=F", "^IRX", "^TNX", "^TYX"]
    symbols_str = ",".join(symbols)
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols_str}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    name_map = {
        "^GSPC": "S&P 500", "^DJI": "다우존스", "^IXIC": "나스닥", "^SOX": "필라델피아 반도체",
        "^RUT": "러셀 2000", "KRW=X": "원/달러 환율", "^VIX": "VIX 지수", "CL=F": "WTI 유가",
        "^IRX": "미국 2년물", "^TNX": "미국 10년물", "^TYX": "미국 30년물"
    }
    
    results = {}
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            quote_list = data.get('quoteResponse', {}).get('result', [])
            for item in quote_list:
                sym = item.get('symbol')
                name = name_map.get(sym)
                if not name: continue
                
                price = item.get('regularMarketPrice')
                change_pct = item.get('regularMarketChangePercent')
                
                if price is not None and change_pct is not None:
                    if sym in ["^TNX", "^TYX", "^IRX"] and price > 15:
                        price /= 10.0
                    price_str = f"{price:,.2f}" if price >= 1 else f"{price:.4f}"
                    results[name] = {"price": price_str, "change": f"{change_pct:+.2f}%"}
    except Exception as e:
        print(f"시세 수집 에러: {e}")
        
    return results

def fetch_google_news():
    """구글 뉴스 RSS에서 최신 외신 헤드라인 수집"""
    url = "https://news.google.com/rss/search?q=US+stock+market+fed+inflation&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    news_titles = []
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            for item in root.findall('.//item')[:8]:
                title = item.find('title').text
                news_titles.append(f"- {title}")
    except Exception as e:
        print(f"뉴스 수집 에러: {e}")
        
    return "\n".join(news_titles) if news_titles else "최신 외신 뉴스 수집 중..."

def generate_us_market_report():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    real_data = fetch_real_quotes()
    real_news = fetch_google_news()
    market_date_str = get_market_date_string()

    ai_analysis = None

    # 1. AI 호출 시도 (한도 초과/오류 발생 시 자동 에러 잡기)
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        당신은 월스트리트 수석 투자 전략가입니다.
        
        1. [{market_date_str}] 실제 증시 시세 수치:
        {json.dumps(real_data, ensure_ascii=False, indent=2)}

        2. [{market_date_str}] 실제 발생한 주요 미국 뉴스 기사 헤드라인:
        {real_news}

        [작성 규칙]
        위 제공된 실제 수치와 구글 뉴스 기사를 기반으로, 
        어떤 테마/섹터(엔비디아, 마이크로소프트, 테슬라, 애플, 반도체, 금융 등 주요 종목명 포함)에 자금이 쏠렸고 어떤 섹터가 하방 압력을 받았는지, 
        연준 위원 발언이나 매크로 악재/호재 원인을 정밀 분석하여 작성해 주세요.

        HTML 태그(<b>, <br>, <ul>, <li>)를 써서 깔끔하게 출력해 주세요.

        반드시 아래 JSON 구조로만 응답하세요 (설명글/마크다운 금지):
        {{
          "strong_sectors_analysis": "HTML 포함 강세 섹터 & 대표 종목 수급 분석",
          "weak_sectors_analysis": "HTML 포함 약세 섹터 & 악재 원인 분석",
          "fed_speeches_summary": "HTML 포함 연준 발언 & 매크로 분석",
          "overall_market_summary": "HTML 포함 오늘 증시 종합 총평"
        }}
        """

        models_to_try = ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-2.0-flash']
        for model_name in models_to_try:
            try:
                print(f"Gemini API ({model_name}) 호출 중...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                text = response.text.strip()
                if "```" in text:
                    lines = text.splitlines()
                    cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
                    text = "\n".join(cleaned_lines).strip()
                ai_analysis = json.loads(text)
                print(f"[{model_name}] 성공!")
                break
            except Exception as err:
                print(f"[{model_name}] 호출 실패: {err}")
                time.sleep(2)

    except Exception as outer_err:
        print(f"Gemini API 호출 중 전체 예외: {outer_err}")

    # 2. 일일 API 한도 초과(429) 시 안전 대체 생성 (워크플로 에러 방지)
    if not ai_analysis:
        print("⚠️ API 한도 초과로 실제 수집된 데이터 기반 대체 리포트를 안전하게 리턴합니다.")
        news_items = "".join([f"<li>{n.replace('- ', '')}</li>" for n in real_news.split("\n") if n.strip()])
        ai_analysis = {
            "strong_sectors_analysis": f"<b>🔥 실시간 증시 종가 현황:</b><br>나스닥 {real_data.get('나스닥', {}).get('price')} ({real_data.get('나스닥', {}).get('change')}), S&P 500 {real_data.get('S&P 500', {}).get('price')} ({real_data.get('S&P 500', {}).get('change')})<br>실시간 시장 주가 지수 흐름을 반영합니다.",
            "weak_sectors_analysis": f"<b>❄️ 실시간 매크로 지표 현황:</b><br>VIX 지수: {real_data.get('VIX 지수', {}).get('price')} ({real_data.get('VIX 지수', {}).get('change')}), WTI 원유: ${real_data.get('WTI 유가', {}).get('price')} ({real_data.get('WTI 유가', {}).get('change')})",
            "fed_speeches_summary": f"<b>🎙️ 실시간 주요 외신 헤드라인:</b><ul>{news_items}</ul>",
            "overall_market_summary": f"<b>📊 {market_date_str} 증시 요약:</b><br>원/달러 환율 {real_data.get('원/달러 환율', {}).get('price')}원 ({real_data.get('원/달러 환율', {}).get('change')}), 미국 10년물 금리 {real_data.get('미국 10년물', {}).get('price')}% ({real_data.get('미국 10년물', {}).get('change')})로 집계되었습니다."
        }

    final_json = {
      "updated_at": f"{market_date_str} 미국장 마감 시황",
      "macro_indicators": [
        {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price', 'N/A')}원", "change": real_data.get('원/달러 환율', {}).get('change', '0.00%'), "status": "외환시세"},
        {"name": "VIX 지수 (공포지수)", "value": real_data.get('VIX 지수', {}).get('price', 'N/A'), "change": real_data.get('VIX 지수', {}).get('change', '0.00%'), "status": "변동성 지수"},
        {"name": "WTI 유가 (원유)", "value": f"${real_data.get('WTI 유가', {}).get('price', 'N/A')}", "change": real_data.get('WTI 유가', {}).get('change', '0.00%'), "status": "국제 유가"}
      ],
      "indices": [
        {"name": "S&P 500", "value": real_data.get('S&P 500', {}).get('price', 'N/A'), "change": real_data.get('S&P 500', {}).get('change', '0.00%')},
        {"name": "다우존스", "value": real_data.get('다우존스', {}).get('price', 'N/A'), "change": real_data.get('다우존스', {}).get('change', '0.00%')},
        {"name": "나스닥", "value": real_data.get('나스닥', {}).get('price', 'N/A'), "change": real_data.get('나스닥', {}).get('change', '0.00%')},
        {"name": "필라델피아 반도체", "value": real_data.get('필라델피아 반도체', {}).get('price', 'N/A'), "change": real_data.get('필라델피아 반도체', {}).get('change', '0.00%')},
        {"name": "러셀 2000", "value": real_data.get('러셀 2000', {}).get('price', 'N/A'), "change": real_data.get('러셀 2000', {}).get('change', '0.00%')}
      ],
      "treasury_yields": [
        {"tenor": "미국 2년물", "yield_rate": f"{real_data.get('미국 2년물', {}).get('price', 'N/A')}%", "change": real_data.get('미국 2년물', {}).get('change', '0.00%'), "status": "단기 국채"},
        {"tenor": "미국 10년물", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price', 'N/A')}%", "change": real_data.get('미국 10년물', {}).get('change', '0.00%'), "status": "기준 국채"},
        {"tenor": "미국 30년물", "yield_rate": f"{real_data.get('미국 30년물', {}).get('price', 'N/A')}%", "change": real_data.get('미국 30년물', {}).get('change', '0.00%'), "status": "장기 국채"}
      ],
      "strong_sectors_analysis": ai_analysis.get("strong_sectors_analysis", ""),
      "weak_sectors_analysis": ai_analysis.get("weak_sectors_analysis", ""),
      "fed_speeches_summary": ai_analysis.get("fed_speeches_summary", ""),
      "overall_market_summary": ai_analysis.get("overall_market_summary", "")
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 정상 수집 완료!")

if __name__ == "__main__":
    generate_us_market_report()
