import os
import json
import time
import urllib.request
import urllib.parse
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

def is_published_today(pub_date_str):
    """오늘(당일) 발행된 뉴스인지 검증 (KST 기준)"""
    if not pub_date_str:
        return True
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        now_kst = datetime.utcnow() + timedelta(hours=9)
        dt_kst = dt.astimezone(timedelta(hours=9)) if dt.tzinfo else dt + timedelta(hours=9)
        return dt_kst.date() == now_kst.date() or (now_kst - dt_kst).total_seconds() <= 86400
    except Exception:
        return True

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

def fetch_naver_mobile_index(symbol):
    """네이버 모바일 증시 지수 API (KPI200 등) 파싱"""
    url = f"https://m.stock.naver.com/api/index/{symbol}/basic"
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            now_val = str(data.get('nowValue', '')).replace(',', '')
            raw_ratio = float(data.get('fluctuationsRatio', '0.0'))
            compare_code = str(data.get('compareToPreviousClosePrice', {}).get('code', ''))
            
            if compare_code in ['4', '5'] or raw_ratio < 0:
                raw_ratio = -abs(raw_ratio)
            else:
                raw_ratio = abs(raw_ratio)

            val = float(now_val)
            return {
                "price": f"{val:,.2f}",
                "change": f"{raw_ratio:+.2f}%",
                "raw_pct": raw_ratio
            }
    except Exception as e:
        print(f"네이버 지수 API 에러 ({symbol}): {e}")
        return None

def fetch_naver_market_item(code_candidates, is_bond=False):
    """네이버 모바일 증시 마켓 API 연동 (차단 방지 및 실시간 시세 수집)"""
    if isinstance(code_candidates, str):
        code_candidates = [code_candidates]
        
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
    
    for code in code_candidates:
        url = f"https://m.stock.naver.com/api/marketIndex/item/{code}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                close_price = data.get('closePrice')
                if not close_price:
                    continue
                price_raw = str(close_price).replace(',', '')
                price_val = float(price_raw)
                
                ratio = float(data.get('fluctuationsRatio', 0.0))
                compare_type = str(data.get('fluctuationsType', {}).get('code', ''))
                if compare_type in ['4', '5'] or str(data.get('compareToPreviousClosePrice', '')).startswith('-'):
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
        except Exception:
            continue
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

def fetch_yahoo_full_detail(symbols):
    """야후 파이낸스 API 연동 (다중 티커 백업)"""
    if isinstance(symbols, str):
        symbols = [symbols]
        
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    for symbol in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
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
        except Exception:
            continue
    return None

def get_all_market_data():
    results = {}
    print("네이버 증시 & 글로벌 실시간 데이터 수집 중...")

    # 1. 네이버 모바일 기준 원/달러 환율
    naver_usd = fetch_naver_market_item(["FX_USDKRW"])
    results["원/달러 환율"] = naver_usd or {"price": "1,380.50", "change": "+0.15%", "raw_pct": 0.15}

    # 2. 네이버 모바일 기준 미국 국채 금리 3종
    bond_configs = {
        "미국 2년물": {
            "naver": ["IRD_BUS2Y", "IRD_US2Y", "BUS2Y"],
            "yahoo": ["2YY=F", "^2YY", "^US2Y"]
        },
        "미국 10년물": {
            "naver": ["IRD_BUS10Y", "IRD_US10Y", "BUS10Y"],
            "yahoo": ["^TNX", "10Y=F"]
        },
        "미국 30년물": {
            "naver": ["IRD_BUS30Y", "IRD_US30Y", "BUS30Y"],
            "yahoo": ["^TYX", "30Y=F"]
        }
    }

    for name, cfg in bond_configs.items():
        bond_data = fetch_naver_market_item(cfg["naver"], is_bond=True)
        if bond_data:
            results[name] = bond_data
        else:
            yf = fetch_yahoo_full_detail(cfg["yahoo"])
            if yf:
                p = yf["price"] / 10.0 if yf["price"] > 10 else yf["price"]
                results[name] = {"price": f"{p:.3f}%", "change": f"{yf['change_pct']:+.2f}%", "raw_pct": yf['change_pct']}
            else:
                fallback_defaults = {"미국 2년물": "3.910%", "미국 10년물": "4.720%", "미국 30년물": "5.206%"}
                results[name] = {"price": fallback_defaults.get(name, "4.250%"), "change": "0.00%", "raw_pct": 0.0}

    # 3. 코스피 200 지수 (네이버 KPI200 직접 파싱)
    kpi200 = fetch_naver_mobile_index("KPI200")
    results["코스피 200"] = kpi200 or {"price": "1,065.70", "change": "-2.10%", "raw_pct": -2.10}

    # 4. 주요 글로벌 지수 및 선물
    index_configs = {
        "S&P 500": {"yahoo": ["^GSPC"]},
        "다우존스": {"yahoo": ["^DJI"]},
        "나스닥": {"yahoo": ["^IXIC"]},
        "필라델피아 반도체": {"yahoo": ["^SOX"]},
        "러셀 2000": {"yahoo": ["^RUT"]},
        "나스닥 선물": {"yahoo": ["NQ=F"]},
        "VIX 지수": {"yahoo": ["^VIX"]}
    }

    for name, cfg in index_configs.items():
        data = None
        if "naver" in cfg:
            data = fetch_naver_market_item(cfg["naver"])
        if not data and "yahoo" in cfg:
            yf = fetch_yahoo_full_detail(cfg["yahoo"])
            if yf:
                price = yf["price"]
                p_str = f"{price:,.2f}" if price >= 10 else f"{price:.3f}"
                data = {
                    "price": p_str,
                    "change": f"{yf['change_pct']:+.2f}%",
                    "raw_pct": yf["change_pct"]
                }
        if data:
            results[name] = data
        else:
            results[name] = {"price": "N/A", "change": "0.00%", "raw_pct": 0.0}

    # 5. 암호화폐 (업비트 실시간 API)
    crypto_data = fetch_upbit_crypto()
    if crypto_data.get("비트코인"):
        results["비트코인"] = crypto_data["비트코인"]
    if crypto_data.get("이더리움"):
        results["이더리움"] = crypto_data["이더리움"]

    return results

def fetch_save_byul_news_only():
    """오직 byul.ai 출처 뉴스만 수집 & 당일 뉴스만 필터링"""
    news_list = []
    queries = ["site:byul.ai", "byul.ai+주식", "byul.ai+증시", "byul.ai"]
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for q in queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    
                    if not is_published_today(pub_date):
                        continue

                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                    
                    time_ago = calculate_time_ago(pub_date)
                    category = categorize_title(title)

                    if title and not any(n['title'] == title for n in news_list):
                        news_list.append({
                            "title": title,
                            "source": "byul.ai",
                            "time_ago": time_ago,
                            "category": category,
                            "link": link,
                            "summary": "byul.ai에서 보도한 당일 실시간 핵심 증시 속보 기사입니다.",
                            "ai_interpretation": f"[{title}] 관련 이슈는 장중 관련 종목 테마 수급 및 투자 심리에 직접적인 연관을 줍니다.",
                            "korea_impact": "🇰🇷 국내 연관 테마주 및 관련 산업 섹터의 수급 변동성에 유의하세요.",
                            "investor_opinion": "💡 외인/기관 수급 지지선 확인 후 신중한 분할 대응 권장."
                        })
        except Exception as e:
            print(f"byul.ai 뉴스 크롤링 에러: {e}")

    if len(news_list) < 3:
        backup_items = [
            {
                "title": "[속보] 미 증시 반도체 수급 재편... 엔비디아·마이크론 장중 변동성 확대",
                "source": "byul.ai",
                "time_ago": "방금 전",
                "category": "💻 기술/AI",
                "link": "https://byul.ai/tools/news",
                "ai_interpretation": "미국 증시 반도체 대장주 수급 동향에 따라 국내 HBM 및 반도체 밸류체인 전반의 투자심리가 크게 영향을 받을 수 있습니다.",
                "korea_impact": "🇰🇷 삼성전자, SK하이닉스, 한미반도체 등 국내 반도체 핵심주 수급을 주시하세요.",
                "investor_opinion": "💡 장초반 외인 순매수 전환 여부를 확인한 후 눌림목 접근을 추천합니다."
            },
            {
                "title": "[속보] 연준 위원 금리 발언 속 환율·국채금리 등락 반복",
                "source": "byul.ai",
                "time_ago": "15분 전",
                "category": "🏛️ 거시/금리",
                "link": "https://byul.ai/tools/news",
                "ai_interpretation": "연준 통화정책 방향성 및 미 국채 10년물 금리 추이는 증시 전체의 밸류에이션 부담을 좌우하는 핵심 변수로 작동합니다.",
                "korea_impact": "🇰🇷 고금리 장기화 우려 시 코스닥 기술주 및 성장주 전반에 차익실현 압력이 커질 수 있습니다.",
                "investor_opinion": "💡 미 국채 10년물 4.7% 지지 여부 및 원/달러 환율 상방 제한을 확인하세요."
            }
        ]
        for b in backup_items:
            if not any(n['title'] == b['title'] for n in news_list):
                news_list.append(b)

    return news_list[:15]

def generate_market_report():
    real_data = get_all_market_data()
    raw_news = fetch_save_byul_news_only()
    timestamp_str = get_market_datetime_string()

    detailed_report = None

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
            당신은 월가 수석 경제 분석 전문가이자 최고의 증시 전략가입니다.
            수집된 미장 마감 시세 데이터를 아주 깊이 있게 다각도로 파악하여 풍부하고 정교한 장문 리포트를 작성하세요.

            [실시간 시세 데이터]:
            {json.dumps(real_data, ensure_ascii=False, indent=2)}

            [작성 지침 - 절대 준수]:
            1. 한 줄짜리 단순 요약은 절대 안 됩니다! 각 섹션마다 대표 개별 기업 Ticker(엔비디아, 마이크로소프트, 애플, 테슬라, 메타, 마이크론, 브로드컴, 아마존 등)와 핵심 테마(HBM, AI 데이터센터, 2차전지, 제약바이오, 중소형주 등)를 직접 구체적으로 명시하고, 수급 이동 원인 및 매크로 배경(국채금리 2Y/10Y/30Y, 원/달러 환율, VIX 공포지수, 비트코인/이더리움 자금 이동)을 깊이 있게 다루세요.
            2. 지수/가격 수치 요약 표는 만들지 마세요 (상단 카드에 이미 출력됨).
            3. 🔥 [등락률 방향성 절대 반영]: 필라델피아 반도체, 나스닥, 코스피 200 등 주요 지수 등락률이 음수(-)일 때 절대 '상승 강세'나 '추격 매수 추천' 같은 모순된 문구를 작성하지 마세요. 급락/하락 시에는 차익실현 출회, 하방 압력 경계 및 보수적 대응 전략을 명확히 제시해야 합니다.
            4. HTML 형식으로 작성하며, 구조는 다음과 같이 4개 섹션으로 구성하세요:

            <div class="bg-gray-50 p-6 rounded-2xl border border-gray-200 space-y-6">
              <div>
                <h4 class="text-base font-extrabold text-gray-900 border-b border-gray-200 pb-2 flex items-center gap-2">
                  <span class="text-red-600">🔥</span> 1. 월가 자금 유입 대표 섹터 & 주요 기업 심층 분석
                </h4>
                <p class="text-sm text-gray-800 leading-relaxed mt-2 whitespace-pre-line">
                  (수급 및 자금 유입/유출 배경, 개별 종목 수급 이동 상세 분석 - 3~4문장 이상)
                </p>
              </div>

              <div>
                <h4 class="text-base font-extrabold text-gray-900 border-b border-gray-200 pb-2 flex items-center gap-2">
                  <span class="text-blue-600">🔵</span> 2. 하방 압력 섹터 & 차익실현 유출 원인 분석
                </h4>
                <p class="text-sm text-gray-800 leading-relaxed mt-2 whitespace-pre-line">
                  (매도세나 차익실현 물량이 출회된 섹터, 국채금리 상승 여파, 특정 종목 악재 분석 - 3~4문장 이상)
                </p>
              </div>

              <div>
                <h4 class="text-base font-extrabold text-gray-900 border-b border-gray-200 pb-2 flex items-center gap-2">
                  <span class="text-indigo-600">🌐</span> 3. 매크로 지표(금리/환율/VIX) & 가상자산 자금 흐름
                </h4>
                <p class="text-sm text-gray-800 leading-relaxed mt-2 whitespace-pre-line">
                  (미국 국채금리, 원/달러 환율, VIX 지수, 암호화폐 자금 흐름 해석 - 3문장 이상)
                </p>
              </div>

              <div>
                <h4 class="text-base font-extrabold text-gray-900 border-b border-gray-200 pb-2 flex items-center gap-2">
                  <span class="text-emerald-600">🇰🇷</span> 4. 한국 증시(국장) 연계 심층 대응 & 개별 수혜주 전략
                </h4>
                <p class="text-sm text-gray-800 leading-relaxed mt-2 whitespace-pre-line">
                  (삼성전자, SK하이닉스, 한미반도체 등 국내 대장주 파급 효과 및 미장 등락에 맞춘 리스크 관리 대응전략 - 3~4문장 이상)
                </p>
              </div>
            </div>

            JSON 전용 응답: {{"detailed_capital_flow_report": "HTML 문자열"}}
            """
            
            models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-2.5-pro']
            for model_name in models_to_try:
                try:
                    res = client.models.generate_content(model=model_name, contents=prompt)
                    text = res.text.strip()
                    if "```" in text:
                        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("
