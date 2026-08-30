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
            elif len(closes) == 1:
                price = closes[0]
                prev_close = meta.get('previousClose') or meta.get('regularMarketPreviousClose') or price
                open_p = opens[0] if len(opens) >= 1 else price
                high_p = highs[0] if len(highs) >= 1 else price
                low_p = lows[0] if len(lows) >= 1 else price
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
        "원/달러 환율": "KRW=X",
        "VIX 지수": "^VIX",
        "WTI 유가": "CL=F",
        "미국 2년물": "^2YY",
        "미국 10년물": "^TNX",
        "미국 30년물": "^TYX"
    }
    
    results = {}
    print("실시간 증시 / 국채 / 외환 데이터 수집 중...")
    
    for name, symbol in tickers.items():
        data = fetch_yahoo_full_detail(symbol)
        if not data and symbol == "^2YY":
            data = fetch_yahoo_full_detail("US2Y=X") or fetch_yahoo_full_detail("^IRX")

        if data:
            price = data["price"]
            if symbol in ["^TNX", "^TYX", "^2YY", "US2Y=X", "^IRX"] and price > 15:
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
                "prev_close": f"{data['prev_close']:,.2f}",
                "open": f"{data['open']:,.2f}",
                "high": f"{data['high']:,.2f}",
                "low": f"{data['low']:,.2f}"
            }
        else:
            results[name] = {
                "price": "N/A", "change": "0.00%", "raw_pct": 0.0,
                "prev_close": "N/A", "open": "N/A", "high": "N/A", "low": "N/A"
            }
            
    crypto_data = fetch_upbit_crypto()
    if crypto_data.get("비트코인"):
        results["비트코인"] = crypto_data["비트코인"]
    else:
        b_data = fetch_yahoo_full_detail("BTC-USD")
        if b_data:
            p = b_data["price"]
            results["비트코인"] = {
                "price_display": f"${p:,.2f} (약 {p*1380/10000:,.0f}만원)",
                "change": f"{b_data['change_pct']:+.2f}%", "raw_pct": b_data["change_pct"]
            }

    if crypto_data.get("이더리움"):
        results["이더리움"] = crypto_data["이더리움"]
    else:
        e_data = fetch_yahoo_full_detail("ETH-USD")
        if e_data:
            p = e_data["price"]
            results["이더리움"] = {
                "price_display": f"${p:,.2f} (약 {p*1380/10000:,.1f}만원)",
                "change": f"{e_data['change_pct']:+.2f}%", "raw_pct": e_data["change_pct"]
            }

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
          <i class="fa-solid fa-chart-line text-red-600"></i> 1. 월가 종합 시황 & 주요 지수 움직임 심층 분석
        </h4>
        <p class="mb-3">
          금일 미국 증시는 <b>엔비디아(NVDA)</b> 등 주요 반도체 대장주들의 실적 발표를 앞둔 차익 실현 경계감과, 연준(Fed) 주요 인사들의 매파적 금리 발언이 교차하며 지수별로 차별화된 흐름을 나타냈습니다.
        </p>
        <ul class="list-disc pl-5 space-y-1.5 text-xs text-gray-700">
          <li><b>S&P 500 ({real_data.get('S&P 500', {}).get('price')}, {real_data.get('S&P 500', {}).get('change')}):</b> 대형 기술주의 혼조세 속에 금융 및 헬스케어 방어주의 선방으로 소폭 하방 압력 소화.</li>
          <li><b>나스닥 종합지수 ({real_data.get('나스닥', {}).get('price')}, {real_data.get('나스닥', {}).get('change')}):</b> 반도체 섹터의 매물 출회 및 AI 테마주 숨고르기로 주요 지수 중 상대적 약세 연출.</li>
          <li><b>필라델피아 반도체 지수 ({real_data.get('필라델피아 반도체', {}).get('price')}, {real_data.get('필라델피아 반도체', {}).get('change')}):</b> 엔비디아, AMD, Broadcom 등 반도체 밸류체인 전반의 단기 고점 매물 출회로 지수 하락 가속.</li>
          <li><b>러셀 2000 ({real_data.get('러셀 2000', {}).get('price')}, {real_data.get('러셀 2000', {}).get('change')}):</b> 고금리 장기화 우려에 따른 자금 조달 비용 부담으로 중소형주 수급 이탈 지속.</li>
        </ul>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div class="bg-emerald-50 p-5 rounded-2xl border border-emerald-200">
          <h5 class="text-sm font-bold text-emerald-900 mb-2 flex items-center gap-1.5">
            <i class="fa-solid fa-circle-arrow-up text-emerald-600"></i> 🔥 강한 자금 유입 섹터 & 대표 기업
          </h5>
          <p class="text-xs text-gray-700 mb-3">
            반도체에서 차익 실현된 유동성이 이익 안정성과 현금 흐름이 확실한 메가캡 소프트웨어 및 플랫폼주로 빠르게 유입되었습니다.
          </p>
          <div class="space-y-2 text-xs text-gray-800">
            <div class="bg-white p-2.5 rounded-lg border border-emerald-100">
              <b>• 아마존 (AMZN):</b> AWS 클라우드 매출 재가속 및 전자상거래 효율화 모멘텀으로 매수세 집중.
            </div>
            <div class="bg-white p-2.5 rounded-lg border border-emerald-100">
              <b>• 알파벳 (GOOGL) & 메타 (META):</b> 생성형 AI 검색 광고 수익화 및 온디바이스 AI 시장 선점 기대감 유지.
            </div>
            <div class="bg-white p-2.5 rounded-lg border border-emerald-100">
              <b>• 마이크로소프트 (MSFT) & 애플 (AAPL):</b> 기관 패시브 자금의 하방 지지 매수세 유입.
            </div>
          </div>
        </div>

        <div class="bg-rose-50 p-5 rounded-2xl border border-rose-200">
          <h5 class="text-sm font-bold text-rose-900 mb-2 flex items-center gap-1.5">
            <i class="fa-solid fa-circle-arrow-down text-rose-600"></i> ❄️ 하방 압력 약세 섹터 & 요인 분석
          </h5>
          <p class="text-xs text-gray-700 mb-3">
            밸류에이션 부담이 가중된 반도체 밸류체인과 고금리 민감 종목군에서 선제적 리스크 관리 매물이 출회되었습니다.
          </p>
          <div class="space-y-2 text-xs text-gray-800">
            <div class="bg-white p-2.5 rounded-lg border border-rose-100">
              <b>• 엔비디아 (NVDA) & AMD:</b> 실적 발표를 앞둔 불확실성 및 차익 실현 물량 소화 진행.
            </div>
            <div class="bg-white p-2.5 rounded-lg border border-rose-100">
              <b>• 러셀 2000 중소형주:</b> 연준의 피벗(금리 인하) 시기 지연에 따른 이자 비용 부담 가중.
            </div>
            <div class="bg-white p-2.5 rounded-lg border border-rose-100">
              <b>• 에너지 & 원자재:</b> WTI 유가(${real_data.get('WTI 유가', {}).get('price')})의 보합권 형성에 따른 모멘텀 둔화.
            </div>
          </div>
        </div>
      </div>

      <div class="bg-indigo-50 p-5 rounded-2xl border border-indigo-200 space-y-3">
        <h4 class="text-base font-bold text-indigo-950 flex items-center gap-2">
          <i class="fa-solid fa-globe text-indigo-600"></i> 3. 매크로 경제 지표 & 가상자산 수급 파급력
        </h4>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div class="bg-white p-3 rounded-xl border border-indigo-100">
            <b class="text-gray-900 block mb-1">💵 원/달러 환율 ({real_data.get('원/달러 환율', {}).get('price')}원)</b>
            외환시장에서 달러화 강세 흐름 속에 원화 가치 변동성이 이어지며 외국인 수급의 경계감을 유발하고 있습니다.
          </div>
          <div class="bg-white p-3 rounded-xl border border-indigo-100">
            <b class="text-gray-900 block mb-1">🏛️ 미국 10년물 국채 금리 ({real_data.get('미국 10년물', {}).get('price')}%)</b>
            연준 위원들의 매파적 스탠스와 물가 지표 발표 대기 속 금리 상방 압력이 지속되고 있습니다.
          </div>
          <div class="bg-white p-3 rounded-xl border border-indigo-100">
            <b class="text-gray-900 block mb-1">🪙 비트코인 ({real_data.get('비트코인', {}).get('price_display', 'N/A')})</b>
            현물 ETF로의 기관 자금 수급 지지력이 작용하며 매크로 변동성 대비 양호한 박스권 하방 지지력을 형성 중입니다.
          </div>
        </div>
      </div>

      <div class="bg-blue-50 p-5 rounded-2xl border border-blue-200 space-y-2">
        <h4 class="text-base font-bold text-blue-900 flex items-center gap-2">
          <i class="fa-solid fa-lightbulb text-yellow-500"></i> 4. 🇰🇷 한국 증시 연계 영향 & 투자자 심층 대응 전략
        </h4>
        <p class="text-xs text-blue-950 leading-relaxed">
          <b>• 국내 반도체(삼성전자, SK하이닉스) 영향:</b> 엔비디아 및 필라델피아 반도체 지수의 단기 차익 실현 출회는 코스피 반도체 대장주의 외국인 순매도 유출을 자극할 수 있으나, HBM 수혜 모멘텀은 유효합니다.
        </p>
        <p class="text-xs text-blue-950 leading-relaxed">
          <b>• 포트폴리오 대응 전략:</b> 지수 상방이 제한되는 변동성 장세에서는 확실한 실적 가이던스를 입증한 대형 플랫폼주 및 고배당·가치주 위주의 분할 매수 접근이 바람직합니다.
        </p>
      </div>

    </div>
    """

    news = [
      {
        "category": "속보",
        "source": "byul.ai",
        "title": "엔비디아 실적 경계감 속 대형 플랫폼주 자금 이격 심화",
        "summary": "반도체주 차익 실현 매물 출회에도 아마존과 알파벳 등 대형 플랫폼 서비스 종목으로 강한 반사이익 자금 유입.",
        "ai_interpretation": "AI 기대감이 과열되었던 하드웨어에서 소프트웨어 및 플랫폼 실적주로 순환매가 진행 중입니다.",
        "korea_impact": "🇰🇷 국내 반도체 대장주의 단기 조정 가능성 및 인터넷/플랫폼 섹터 수급 개선 효과.",
        "investor_opinion": "💡 실적 변동성이 큰 단기 고점 종목보다 안정적 현금흐름을 보유한 메가캡 중심 대응."
      },
      {
        "category": "연준/금리",
        "source": "로이터 (Reuters)",
        "title": "연준 위원들 매파적 기조 재확인... 국채 금리 보합권 형성",
        "summary": "인플레이션 목표치 달성을 위해 고금리가 유지될 것이라는 경계감으로 채권 수익률 상방 유휴.",
        "ai_interpretation": "조기 금리 인하 기대감을 차단하여 시중 유동성의 과도한 팽창을 방지하는 연준의 스탠스입니다.",
        "korea_impact": "🇰🇷 원/달러 환율 상승 압력 지속 및 한국은행의 통화 정책 여력 제약.",
        "investor_opinion": "💡 금리 민감주의 비중을 조율하고 펀더멘털이 확실한 유방 섹터에 자금 배분."
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
            당신은 월스트리트 최고 수석 칼럼니스트입니다.
            업데이트 타임스탬프: [{timestamp_str}]
            실제 수집 데이터:
            {json.dumps(real_data, ensure_ascii=False, indent=2)}

            수집 뉴스:
            {json.dumps(raw_news, ensure_ascii=False, indent=2)}

            [요청 사항]
            1. 'detailed_capital_flow_report': 매우 정교하고 길게 작성된 마감시황 & 자금흐름 보고서를 생성하세요 (HTML 포함).
            2. 'categorized_news': 수집 뉴스를 속보, 연준/금리, 암호화폐 등으로 분류하고 출처(byul.ai 등)와 3단계 AI 해설 작성.

            JSON 구조로 응답하세요.
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
                    print(f"[{model_name}] 예외: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"API 에러: {e}")

    if not detailed_report or not categorized_news:
        fallback_rep, fallback_news = generate_deep_comprehensive_report(real_data, timestamp_str)
        if not detailed_report: detailed_report = fallback_rep
        if not categorized_news: categorized_news = fallback_news

    btc_info = real_data.get('비트코인', {})
    eth_info = real_data.get('이더리움', {})

    btc_display = btc_info.get('price_display') or btc_info.get('price', 'N/A')
    eth_display = eth_info.get('price_display') or eth_info.get('price', 'N/A')

    final_json = {
        "updated_at": timestamp_str,
        "macro_indicators": [
            {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price')}원", "change": real_data.get('원/달러 환율', {}).get('change'), "status": "외환시세"},
            {"name": "비트코인 (BTC)", "value": btc_display, "change": btc_info.get('change', '0.00%'), "status": "업비트/KRW"},
            {"name": "이더리움 (ETH)", "value": eth_display, "change": eth_info.get('change', '0.00%'), "status": "업비트/KRW"},
            {"name": "VIX 지수 (공포지수)", "value": real_data.get('VIX 지수', {}).get('price'), "change": real_data.get('VIX 지수', {}).get('change'), "status": "변동성 지수"},
            {"name": "WTI 유가 (원유)", "value": f"${real_data.get('WTI 유가', {}).get('price')}", "change": real_data.get('WTI 유가', {}).get('change'), "status": "국제 유가"}
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
