import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_market_datetime_string():
    """한국 표준시(KST) 기준 연-월-일 시:분:초 타임스탬프 생성"""
    now_kst = datetime.utcnow() + timedelta(hours=9)
    weekday = now_kst.weekday()
    days = ['월', '화', '수', '목', '금', '토', '일']
    return now_kst.strftime(f"%Y년 %m월 %d일({days[weekday]}) %H:%M:%S KST")

def fetch_upbit_crypto():
    """업비트 API를 통한 비트코인 및 이더리움 실시간 원화/달러 시세 파싱"""
    url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    crypto_data = {}
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for coin in data:
                market = coin['market']
                trade_price = coin['trade_price']
                signed_change_rate = coin['signed_change_rate'] * 100
                krw_man = trade_price / 10000.0
                usd_approx = trade_price / 1380.0
                
                if market == "KRW-BTC":
                    crypto_data["비트코인"] = {
                        "price_display": f"{trade_price:,.0f}원 (${usd_approx:,.0f})",
                        "price_krw": f"{krw_man:,.0f}만원",
                        "change": f"{signed_change_rate:+.2f}%",
                        "raw_pct": signed_change_rate
                    }
                elif market == "KRW-ETH":
                    crypto_data["이더리움"] = {
                        "price_display": f"{trade_price:,.0f}원 (${usd_approx:,.0f})",
                        "price_krw": f"{krw_man:,.1f}만원",
                        "change": f"{signed_change_rate:+.2f}%",
                        "raw_pct": signed_change_rate
                    }
    except Exception as e:
        print(f"업비트 API 파싱 에러: {e}")
    return crypto_data

def fetch_yahoo_full_detail(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            result = data['chart']['result'][0]
            meta = result['meta']
            
            quote = result.get('indicators', {}).get('quote', [{}])[0]
            closes = [c for c in quote.get('close', []) if c is not None]
            opens = [o for o in quote.get('open', []) if o is not None]
            highs = [h for h in quote.get('high', []) if h is not None]
            lows = [l for l in quote.get('low', []) if l is not None]

            if len(closes) >= 2:
                price = closes[-1]
                prev_close = closes[-2]
                open_p = opens[-1] if len(opens) >= 1 else price
                high_p = highs[-1] if len(highs) >= 1 else price
                low_p = lows[-1] if len(lows) >= 1 else price
            else:
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('regularMarketPreviousClose') or meta.get('previousClose')
                open_p = meta.get('regularMarketOpen') or price
                high_p = meta.get('regularMarketDayHigh') or price
                low_p = meta.get('regularMarketDayLow') or price

            if price is not None and prev_close is not None and prev_close > 0:
                change_val = price - prev_close
                change_pct = (change_val / prev_close) * 100
                return {
                    "price": price, "change_val": change_val, "change_pct": change_pct,
                    "prev_close": prev_close, "open": open_p, "high": high_p, "low": low_p
                }
    except Exception as e:
        print(f"[{symbol}] 파싱 에러: {e}")
    return None

def get_all_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "나스닥 선물": "NQ=F",
        "코스피 야간선물": "KM=F",
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 2년물": "^2YY",
        "미국 10년물": "^TNX",
        "미국 30년물": "^TYX"
    }
    
    results = {}
    print("실시간 증시 / 선물 / 국채 / 외환 데이터 수집 중...")
    
    for name, symbol in tickers.items():
        data = fetch_yahoo_full_detail(symbol)
        
        # 보정 로직
        if not data and symbol == "^2YY":
            data = fetch_yahoo_full_detail("US2Y=X") or fetch_yahoo_full_detail("^IRX")
        if not data and symbol == "KM=F":
            data = fetch_yahoo_full_detail("^KS11")  # KOSPI 대체 파싱 보정

        if data:
            price = data["price"]
            if symbol in ["^TNX", "^TYX", "^2YY"] and price > 10:
                price /= 10.0
                data["prev_close"] /= 10.0
                data["open"] /= 10.0
                data["high"] /= 10.0
                data["low"] /= 10.0

            p_str = f"{price:,.2f}" if price >= 10 else f"{price:.3f}"

            results[name] = {
                "price": p_str,
                "change": f"{data['change_pct']:+.2f}%",
                "raw_pct": data["change_pct"],
                "prev_close": f"{data['prev_close']:,.2f}" if data['prev_close'] >= 10 else f"{data['prev_close']:.3f}",
                "open": f"{data['open']:,.2f}" if data['open'] >= 10 else f"{data['open']:.3f}",
                "high": f"{data['high']:,.2f}" if data['high'] >= 10 else f"{data['high']:.3f}",
                "low": f"{data['low']:,.2f}" if data['low'] >= 10 else f"{data['low']:.3f}"
            }
        else:
            results[name] = {
                "price": "N/A", "change": "0.00%", "raw_pct": 0.0,
                "prev_close": "N/A", "open": "N/A", "high": "N/A", "low": "N/A"
            }
            
    crypto_data = fetch_upbit_crypto()
    if crypto_data.get("비트코인"):
        results["비트코인"] = crypto_data["비트코인"]
    if crypto_data.get("이더리움"):
        results["이더리움"] = crypto_data["이더리움"]

    return results

def fetch_save_ticker_news():
    queries = ["byul+경제+주식+암호화폐", "US+stock+market+fed+nvidia+bitcoin"]
    news_list = []
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall('.//item')[:6]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    source_elem = item.find('source')
                    source = source_elem.text if source_elem is not None else "byul.ai"
                    
                    if " - " in title and (source == "byul.ai" or not source):
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                        source = parts[1]
                    
                    if title and not any(n['title'] == title for n in news_list):
                        news_list.append({"title": title, "source": source})
        except Exception as e:
            print(f"뉴스 크롤링 오류: {e}")
            
    return news_list

def generate_deep_comprehensive_report(real_data, timestamp_str):
    report_html = f"""
    <div class="space-y-6 text-sm leading-relaxed text-gray-800">
      <div class="bg-gray-50 p-5 rounded-2xl border border-gray-200">
        <h4 class="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
          <i class="fa-solid fa-chart-line text-red-600"></i> 1. 월가 종합 시황 분석 및 선물 지수 동향
        </h4>
        <p class="mb-3">
          금일 미국 증시는 대형 기술주의 차익 실현 경계감 속에 나스닥 선물({real_data.get('나스닥 선물', {}).get('price')}) 및 코스피 야간선물({real_data.get('코스피 야간선물', {}).get('price')})의 변동성을 유의깊게 관찰해야 하는 장세입니다.
        </p>
      </div>
    </div>
    """
    news = [
      {
        "category": "속보",
        "source": "byul.ai",
        "title": "나스닥 선물 및 야간 선물 변동성 확대... AI 실적 경계감 유효",
        "summary": "주요 반도체 대장주 실적 발표를 앞두고 글로벌 야간 선물 시장 내 순환매 진행 중.",
        "ai_interpretation": "실적 변동성에 대비한 리스크 관리 기조가 선물 지수에 반영 중입니다.",
        "korea_impact": "🇰🇷 코스피 야간 선물 흐름에 연동된 주간 코스피 개장 시가 형성 지점 주시.",
        "investor_opinion": "💡 선물지수의 하방 지지력을 확인하며 분할 매수 전략 유지."
      }
    ]
    return report_html, news

def generate_market_report():
    real_data = get_all_market_data()
    raw_news = fetch_save_ticker_news()
    timestamp_str = get_market_datetime_string()

    detailed_report, categorized_news = None, None

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
            업데이트 타임스탬프: [{timestamp_str}]
            실제 수집 데이터: {json.dumps(real_data, ensure_ascii=False, indent=2)}
            수집 뉴스: {json.dumps(raw_news, ensure_ascii=False, indent=2)}
            1. 'detailed_capital_flow_report': 마감시황 리포트 작성
            2. 'categorized_news': 뉴스 카드 배열
            JSON 응답 전용.
            """
            for model_name in ['gemini-2.5-flash', 'gemini-3.6-flash']:
                try:
                    res = client.models.generate_content(model=model_name, contents=prompt)
                    text = res.text.strip()
                    if "```" in text:
                        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")]).strip()
                    parsed = json.loads(text)
                    detailed_report = parsed.get("detailed_capital_flow_report")
                    categorized_news = parsed.get("categorized_news")
                    break
                except Exception as e:
                    time.sleep(1)
        except Exception as e:
            print(f"API 에러: {e}")

    if not detailed_report or not categorized_news:
        fallback_rep, fallback_news = generate_deep_comprehensive_report(real_data, timestamp_str)
        if not detailed_report: detailed_report = fallback_rep
        if not categorized_news: categorized_news = fallback_news

    btc_info = real_data.get('비트코인', {})
    eth_info = real_data.get('이더리움', {})

    final_json = {
        "updated_at": timestamp_str,
        "macro_indicators": [
            {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price')}원", "change": real_data.get('원/달러 환율', {}).get('change'), "status": "외환시세"},
            {"name": "나스닥 선물", "value": real_data.get('나스닥 선물', {}).get('price'), "change": real_data.get('나스닥 선물', {}).get('change'), "status": "NQ=F"},
            {"name": "코스피 야간선물", "value": real_data.get('코스피 야간선물', {}).get('price'), "change": real_data.get('코스피 야간선물', {}).get('change'), "status": "KM=F"},
            {"name": "비트코인 (BTC)", "value": btc_info.get('price_display', 'N/A'), "change": btc_info.get('change', '0.00%'), "status": "업비트/KRW"},
            {"name": "VIX 지수 (공포지수)", "value": real_data.get('VIX 지수', {}).get('price'), "change": real_data.get('VIX 지수', {}).get('change'), "status": "변동성 지수"}
        ],
        "indices": [
            {"name": "S&P 500", "value": real_data.get('S&P 500', {}).get('price'), "change": real_data.get('S&P 500', {}).get('change')},
            {"name": "다우존스", "value": real_data.get('다우존스', {}).get('price'), "change": real_data.get('다우존스', {}).get('change')},
            {"name": "나스닥", "value": real_data.get('나스닥', {}).get('price'), "change": real_data.get('나스닥', {}).get('change')},
            {"name": "필라델피아 반도체", "value": real_data.get('필라델피아 반도체', {}).get('price'), "change": real_data.get('필라델피아 반도체', {}).get('change')},
            {"name": "러셀 2000", "value": real_data.get('러셀 2000', {}).get('price'), "change": real_data.get('러셀 2000', {}).get('change')}
        ],
        "bonds_detailed": [
            {
                "tenor": "미국 2년물 국채금리 (^2YY)", "yield_rate": f"{real_data.get('미국 2년물', {}).get('price')}%",
                "change": real_data.get('미국 2년물', {}).get('change'), "prev_close": real_data.get('미국 2년물', {}).get('prev_close'),
                "open": real_data.get('미국 2년물', {}).get('open'), "high": real_data.get('미국 2년물', {}).get('high'), "low": real_data.get('미국 2년물', {}).get('low')
            },
            {
                "tenor": "미국 10년물 국채금리 (^TNX)", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price')}%",
                "change": real_data.get('미국 10년물', {}).get('change'), "prev_close": real_data.get('미국 10년물', {}).get('prev_close'),
                "open": real_data.get('미국 10년물', {}).get('open'), "high": real_data.get('미국 10년물', {}).get('high'), "low": real_data.get('미국 10년물', {}).get('low')
            },
            {
                "tenor": "미국 30년물 국채금리 (^TYX)", "yield_rate": f"{real_data.get('미국 30년물', {}).get('price')}%",
                "change": real_data.get('미국 30년물', {}).get('change'), "prev_close": real_data.get('미국 30년물', {}).get('prev_close'),
                "open": real_data.get('미국 30년물', {}).get('open'), "high": real_data.get('미국 30년물', {}).get('high'), "low": real_data.get('미국 30년물', {}).get('low')
            }
        ],
        "detailed_capital_flow_report": detailed_report,
        "categorized_news": categorized_news
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 업데이트 성공!")

if __name__ == "__main__":
    generate_market_report()
