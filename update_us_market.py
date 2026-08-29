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
    """야후 파이낸스에서 실제 시세 및 정확한 등락률 직접 계산"""
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
    """구글 뉴스 RSS에서 미국 증시 최신 기사 제목 직접 수집"""
    url = "https://news.google.com/rss/search?q=US+stock+market+fed+inflation&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    news_titles = []
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            for item in root.findall('.//item')[:10]:
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
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    market_date_str = get_market_date_string()

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

    print(f"Gemini AI가 {market_date_str} 리포트 작성 중...")
    
    # 503 일시적 서버 과부하 대응: 최대 5회 자동 재시도 로직
    max_retries = 5
    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            break
        except Exception as e:
            print(f"Gemini API 호출 중 일시적 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("5초 후 다시 시도합니다...")
                time.sleep(5)
            else:
                raise e

    text = response.text.strip()
    if "```" in text:
        lines = text.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(cleaned_lines).strip()

    ai_analysis = json.loads(text)

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

    print("us_market.json 정상 업데이트 완료!")

if __name__ == "__main__":
    generate_us_market_report()
