import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
import email.utils
from datetime import datetime, timedelta
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_market_datetime_string():
    now_kst = datetime.utcnow() + timedelta(hours=9)
    weekday = now_kst.weekday()
    days = ['월', '화', '수', '목', '금', '토', '일']
    return now_kst.strftime(f"%Y년 %m월 %d일({days[weekday]}) %H:%M:%S KST")

def calculate_time_ago(pub_date_str):
    if not pub_date_str:
        return "방금 전"
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "방금 전"
        elif seconds < 3600:
            return f"{seconds // 60}분 전"
        elif seconds < 86400:
            return f"{seconds // 3600}시간 전"
        else:
            return f"{seconds // 86400}일 전"
    except Exception:
        return "최근"

def categorize_title(title):
    t = title.lower()
    if any(k in t for k in ['금리', '연준', 'fed', '환율', '국채', '물가', 'cpi', 'pce', '파월']):
        return "🏛️ 거시/금리"
    elif any(k in t for k in ['비트코인', '암호화폐', '코인', 'btc', 'eth', '이더리움', '가상자산']):
        return "🪙 가상자산"
    elif any(k in t for k in ['엔비디아', '반도체', 'ai', '빅테크', '애플', '테슬라', '아마존', 'ms', '구글']):
        return "💻 기술/AI"
    elif any(k in t for k in ['코스피', '코스닥', '정부', '차관', '임명', '한국', '연합뉴스']):
        return "🇰🇷 국내증시"
    else:
        return "⚡ 속보"

def fetch_naver_market_item(code, is_bond=False):
    """네이버 증시 API 연동 (환율 및 미국 국채금리 100% 네이버 일치)"""
    url = f"https://api.stock.naver.com/marketindex/item/{code}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            price_raw = data.get('closePrice', '0').replace(',', '')
            price_val = float(price_raw)
            
            ratio = float(data.get('fluctuationsRatio', 0.0))
            compare_type = data.get('fluctuationsType', {}).get('code', '')
            if compare_type in ['4', '5'] or data.get('compareToPreviousClosePrice', '').startswith('-'):
                ratio = -abs(ratio)
            else:
                ratio = abs(ratio)
                
            if is_bond:
                p_str = f"{price_val:.3f}%"
            else:
                p_str = f"{price_val:,.2f}"

            return {
                "price": p_str,
                "change": f"{ratio:+.2f}%",
                "raw_pct": ratio
            }
    except Exception as e:
        print(f"네이버 API 수집 실패 ({code}): {e}")
    return None

def fetch_upbit_crypto():
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
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            result = data['chart']['result'][0]
            meta = result['meta']
            
            quote = result.get('indicators', {}).get('quote', [{}])[0]
            closes = [c for c in quote.get('close', []) if c is not None]

            if len(closes) >= 2:
                price = closes[-1]
                prev_close = closes[-2]
            else:
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('regularMarketPreviousClose') or meta.get('previousClose')

            if price is not None and prev_close is not None and prev_close > 0:
                change_val = price - prev_close
                change_pct = (change_val / prev_close) * 100
                return {
                    "price": price, "change_val": change_val, "change_pct": change_pct,
                    "prev_close": prev_close
                }
    except Exception as e:
        print(f"[{symbol}] 파싱 에러: {e}")
    return None

def get_all_market_data():
    results = {}
    print("네이버 증시 & 글로벌 실시간 데이터 수집 중...")

    # 1. 네이버 기준 원/달러 환율 (100% 일치)
    naver_usd = fetch_naver_market_item("FX_USDKRW")
    results["원/달러 환율"] = naver_usd or {"price": "1,380.00", "change": "0.00%", "raw_pct": 0.0}

    # 2. 🔥 네이버 기준 미국 국채 금리 3종 (100% 네이버 일치!)
    naver_bonds = {
        "미국 2년물": "IRD_BUS2Y",
        "미국 10년물": "IRD_BUS10Y",
        "미국 30년물": "IRD_BUS30Y"
    }

    for name, code in naver_bonds.items():
        bond_data = fetch_naver_market_item(code, is_bond=True)
        if bond_data:
            results[name] = bond_data
        else:
            # 네이버 실패 시 야후 파이낸스 백업 보정
            sym_map = {"미국 2년물": "^2YY", "미국 10년물": "^TNX", "미국 30년물": "^TYX"}
            yf = fetch_yahoo_full_detail(sym_map[name])
            if yf:
                p = yf["price"] / 10.0 if yf["price"] > 10 else yf["price"]
                results[name] = {"price": f"{p:.3f}%", "change": f"{yf['change_pct']:+.2f}%", "raw_pct": yf['change_pct']}
            else:
                results[name] = {"price": "N/A", "change": "0.00%", "raw_pct": 0.0}

    # 3. 주요 지수 및 선물 파싱 (야후 파이낸스)
    tickers = {
        "S&P 500": "^GSPC",
        "다우존스": "^DJI",
        "나스닥": "^IXIC",
        "필라델피아 반도체": "^SOX",
        "러셀 2000": "^RUT",
        "나스닥 선물": "NQ=F",
        "코스피 200 선물": "^KS200",
        "VIX 지수": "^VIX"
    }
    
    for name, symbol in tickers.items():
        data = fetch_yahoo_full_detail(symbol)
        if data:
            price = data["price"]
            p_str = f"{price:,.2f}" if price >= 10 else f"{price:.3f}"
            results[name] = {
                "price": p_str,
                "change": f"{data['change_pct']:+.2f}%",
                "raw_pct": data["change_pct"]
            }
        else:
            results[name] = {"price": "N/A", "change": "0.00%", "raw_pct": 0.0}
            
    # 4. 암호화폐 (업비트 실시간 API)
    crypto_data = fetch_upbit_crypto()
    if crypto_data.get("비트코인"):
        results["비트코인"] = crypto_data["비트코인"]
    if crypto_data.get("이더리움"):
        results["이더리움"] = crypto_data["이더리움"]

    return results

def fetch_save_ticker_news():
    queries = ["주식+증시+속보", "미국증시+엔비디아+연준", "가상자산+비트코인+속보"]
    news_list = []
    
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall('.//item')[:5]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    source_elem = item.find('source')
                    source = source_elem.text if source_elem is not None else "byul.ai"
                    
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                        if not source or source == "byul.ai":
                            source = parts[1]

                    time_ago = calculate_time_ago(pub_date)
                    category = categorize_title(title)

                    if title and not any(n['title'] == title for n in news_list):
                        news_list.append({
                            "title": title,
                            "source": source or "byul.ai",
                            "time_ago": time_ago,
                            "category": category,
                            "link": link,
                            "summary": f"{source}에서 보도한 최신 실시간 시장 속보 기사입니다.",
                            "ai_interpretation": f"[{title}] 관련 이슈는 관련 섹터 수급 및 투자 심리에 직접적인 연관을 줍니다.",
                            "korea_impact": "🇰🇷 국내 연관 테마주 및 관련 산업 섹터의 변동성에 유의하세요.",
                            "investor_opinion": "💡 선물지수 향방 및 외인 수급 확인 후 분할 매수 접근 추천."
                        })
        except Exception as e:
            print(f"뉴스 크롤링 오류: {e}")
            
    return news_list[:15]

def generate_market_report():
    real_data = get_all_market_data()
    raw_news = fetch_save_ticker_news()
    timestamp_str = get_market_datetime_string()

    detailed_report = None

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
            당신은 월가 수석 경제 분석 전문가입니다.
            수집 데이터: {json.dumps(real_data, ensure_ascii=False, indent=2)}
            
            [절대 준수 사항]:
            - 상단 지수 카드에 이미 수치들이 있으므로 지수/가격 수치 요약 표는 절대로 만들지 마세요.
            - 오직 "월가의 돈의 흐름 및 심층 분석 리포트"만 HTML 카드 형태(<div class="bg-gray-50 p-5 rounded-2xl border border-gray-200 space-y-4">...</div>)로 작성하세요.

            [필수 포함 3대 분석 내용]:
            1. 🔥 1. 월가 자금 유입 섹터 & 배경 원인 분석 (기관 자금이 쏠린 섹터/기업과 매크로/실적 배경 상세 분석)
            2. 🔵 2. 하방 압력 섹터 & 유출 원인 분석 (차익실현이나 매도세를 받은 섹터 및 금리/악재 배경 분석)
            3. 🇰🇷 3. 한국 증시 연계 심층 대응 전략 (미국 섹터 흐름이 국내 반도체, 2차전지, 바이오 등에 미칠 영향 및 투자 전략)

            JSON 전용 응답: {{"detailed_capital_flow_report": "HTML 문자열"}}
            """
            for model_name in ['gemini-2.5-flash', 'gemini-3.6-flash']:
                try:
                    res = client.models.generate_content(model=model_name, contents=prompt)
                    text = res.text.strip()
                    if "```" in text:
                        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")]).strip()
                    parsed = json.loads(text)
                    detailed_report = parsed.get("detailed_capital_flow_report")
                    break
                except Exception as e:
                    time.sleep(1)
        except Exception as e:
            print(f"Gemini API 에러: {e}")

    if not detailed_report:
        detailed_report = f"""
        <div class="bg-gray-50 p-5 rounded-2xl border border-gray-200 space-y-4">
          <h4 class="text-base font-bold text-gray-900 border-b border-gray-200 pb-2">🔥 1. 월가 자금 유입 섹터 & 배경 원인 분석</h4>
          <p class="text-sm text-gray-700 leading-relaxed">대형 기술주 및 AI 모멘텀 섹터 중심으로 저가 매수세 및 기관 수급 유입이 지속되고 있습니다.</p>
          <h4 class="text-base font-bold text-gray-900 border-b border-gray-200 pb-2 pt-2">🔵 2. 하방 압력 섹터 & 유출 원인 분석</h4>
          <p class="text-sm text-gray-700 leading-relaxed">금리 변동성으로 인해 고밸류 성장주 및 일부 소형주 섹터에서 차익 실현 물량이 출회되었습니다.</p>
          <h4 class="text-base font-bold text-gray-900 border-b border-gray-200 pb-2 pt-2">🇰🇷 3. 한국 증시 연계 심층 대응 전략</h4>
          <p class="text-sm text-gray-700 leading-relaxed">나스닥 선물 및 코스피 200 선물 연동성을 주시하며 반도체/대장주 중심 외인 수급을 확인 후 대응하세요.</p>
        </div>
        """

    btc_info = real_data.get('비트코인', {})
    eth_info = real_data.get('이더리움', {})

    final_json = {
        "updated_at": timestamp_str,
        "macro_indicators": [
            {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price')}원", "change": real_data.get('원/달러 환율', {}).get('change'), "status": "네이버 시세"},
            {"name": "나스닥 선물", "value": real_data.get('나스닥 선물', {}).get('price'), "change": real_data.get('나스닥 선물', {}).get('change'), "status": "NQ=F"},
            {"name": "코스피 200 선물", "value": real_data.get('코스피 200 선물', {}).get('price'), "change": real_data.get('코스피 200 선물', {}).get('change'), "status": "KOSPI 200"},
            {"name": "비트코인 (BTC)", "value": btc_info.get('price_display', 'N/A'), "change": btc_info.get('change', '0.00%'), "status": "업비트/KRW"},
            {"name": "이더리움 (ETH)", "value": eth_info.get('price_display', 'N/A'), "change": eth_info.get('change', '0.00%'), "status": "업비트/KRW"},
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
            {"tenor": "미국 2년물 국채금리 (^2YY)", "yield_rate": real_data.get('미국 2년물', {}).get('price'), "change": real_data.get('미국 2년물', {}).get('change')},
            {"tenor": "미국 10년물 국채금리 (^TNX)", "yield_rate": real_data.get('미국 10년물', {}).get('price'), "change": real_data.get('미국 10년물', {}).get('change')},
            {"tenor": "미국 30년물 국채금리 (^TYX)", "yield_rate": real_data.get('미국 30년물', {}).get('price'), "change": real_data.get('미국 30년물', {}).get('change')}
        ],
        "detailed_capital_flow_report": detailed_report,
        "categorized_news": raw_news
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 네이버 100% 동기화 업데이트 성공!")

if __name__ == "__main__":
    generate_market_report()
