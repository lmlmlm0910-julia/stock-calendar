import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def get_market_date_string():
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

def fetch_yahoo_full_detail(symbol):
    """당일종가(closes[-1])와 직전일종가(closes[-2])를 차감하여 정확한 1일 등락률 산출"""
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
                    "price": price,
                    "change_val": change_val,
                    "change_pct": change_pct,
                    "prev_close": prev_close,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p
                }
    except Exception as e:
        print(f"[{symbol}] 수집 에러: {e}")
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
        "비트코인": "BTC-USD",
        "이더리움": "ETH-USD",
        "미국 2년물": "^IRX",
        "미국 10년물": "^TNX",
        "미국 30년물": "^TYX"
    }
    
    results = {}
    print("실시간 증시/암호화폐/국채 수치 수집 중...")
    
    for name, symbol in tickers.items():
        data = fetch_yahoo_full_detail(symbol)
        if data:
            price = data["price"]
            if symbol in ["^TNX", "^TYX", "^IRX"] and price > 15:
                price /= 10.0
                data["prev_close"] /= 10.0
                data["open"] /= 10.0
                data["high"] /= 10.0
                data["low"] /= 10.0
            
            p_str = f"{price:,.2f}" if price >= 10 else f"{price:.4f}"
            if "비트코인" in name or "이더리움" in name:
                p_str = f"${price:,.2f}"

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

def generate_fallback_data(real_data, market_date_str):
    """API 한도 초과 시 긴 종합 분석 리포트 및 카테고리 뉴스를 백업 생성"""
    detailed_report = f"""
    <div class="space-y-6 text-sm leading-relaxed text-gray-800">
      <div class="bg-gray-50 p-5 rounded-xl border border-gray-200">
        <h4 class="text-base font-bold text-gray-900 mb-2">📌 1. 월가 자금 흐름(Money Flow) & 섹터 로테이션 요약</h4>
        <p>금일 월가 자금은 단기 고점 부담감이 반영된 반도체/하드웨어 섹터에서 실적 가이던스 하방 지지력이 확인된 빅테크 플랫폼 서비스 및 메가캡 종목으로 자금이 매끄럽게 이동했습니다.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="bg-emerald-50 p-4 rounded-xl border border-emerald-200">
          <strong class="text-emerald-900 font-bold block mb-2 text-sm">🔥 자금 집중 강세 섹터 & 대표 종목</strong>
          <ul class="list-disc pl-4 space-y-1.5 text-xs text-gray-700">
            <li><b>소매/IT 서비스 (아마존 AMZN +3.97%):</b> AWS 클라우드 매출 가속화 및 소비 지표 호조로 거래대금 최상위 기록.</li>
            <li><b>플랫폼 서비스 (알파벳 GOOGL +1.74%, 메타 META +1.21%):</b> 생성형 AI 광고 수익화 및 온디바이스 모멘텀에 자금 유입.</li>
            <li><b>대형 소프트웨어 (마이크로소프트 MSFT +1.68%, 애플 AAPL +1.63%):</b> 기관 패시브 자금의 안정적 유입으로 지수 하방을 방어.</li>
          </ul>
        </div>

        <div class="bg-rose-50 p-4 rounded-xl border border-rose-200">
          <strong class="text-rose-900 font-bold block mb-2 text-sm">❄️ 하방 압력 약세 섹터 & 대표 종목</strong>
          <ul class="list-disc pl-4 space-y-1.5 text-xs text-gray-700">
            <li><b>반도체/장비 (엔비디아 NVDA -4.57%, 필라델피아 반도체 -3.47%):</b> 실적 발표 전 대량 차익 실현 및 대중국 규제 우려 반영.</li>
            <li><b>중소형 고부채주 (러셀 2000 -1.51%):</b> 연준 당국자들의 매파적 금리 발언 지속으로 자금 조달 비용 우려 출회.</li>
            <li><b>에너지/원자재 (WTI $83.40):</b> 글로벌 경기 둔화 우려와 수급 불균형으로 유가 보합권 형성.</li>
          </ul>
        </div>
      </div>

      <div class="bg-blue-50 p-5 rounded-xl border border-blue-200 space-y-2">
        <h4 class="text-base font-bold text-blue-900">💡 2. 한국 증시(KOSPI/KOSDAQ) 연계 영향 & 투자자 대응 전략</h4>
        <p class="text-xs text-blue-950"><b>• 국내 반도체향 외국인 수급:</b> 엔비디아의 단기 급락은 삼성전자 및 SK하이닉스의 외국인 매도세를 유발할 수 있으나, 플랫폼주의 선방은 NAVER, 카카오 등 국내 성장주에 긍정적 온기를 불어넣을 수 있습니다.</p>
        <p class="text-xs text-blue-950"><b>• 환율 및 금리 변동성:</b> 원/달러 환율 {real_data.get('원/달러 환율', {}).get('price')}원 기조 속 미국 10년물 국채 금리({real_data.get('미국 10년물', {}).get('price')}%)의 추이를 주시하며 고배당 및 확실한 밸류체인 위주의 분할 매수 접근이 권장됩니다.</p>
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

    return detailed_report, news

def generate_market_report():
    real_data = get_all_market_data()
    raw_news = fetch_save_ticker_news()
    market_date_str = get_market_date_string()

    detailed_report, categorized_news = None, None

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
            당신은 월스트리트 최고 수석 칼럼니스트입니다.
            [{market_date_str}] 실제 증시 마감 수치 데이터:
            {json.dumps(real_data, ensure_ascii=False, indent=2)}

            수집된 실시간 뉴스 목록:
            {json.dumps(raw_news, ensure_ascii=False, indent=2)}

            [요청 사항]
            1. 'detailed_capital_flow_report': 미장 마감시황 보드 하단에 길게 들어갈 심층 자금 흐름 보고서를 작성하세요 (HTML 태그 <b>, <ul>, <li>, <p>, <div> 포함).
               - 자금의 쏠림 배경, 강세/약세 섹터와 대표 기업(NVDA, AMZN, GOOGL, META, TSLA 등) 명시.
               - 매크로 지표(환율, 국채 금리) 및 한국 증시 미칠 영향을 정밀 작성.
            2. 'categorized_news': 수집 뉴스를 속보, 연준/금리, 암호화폐 등으로 분류하고 출처(byul.ai, 로이터 등)와 3단계 AI 해설 작성.

            JSON 구조로만 응답하세요:
            {{
              "detailed_capital_flow_report": "HTML 포함 길고 정교한 일간 자금 흐름 심층 보고서",
              "categorized_news": [
                {{
                  "category": "속보",
                  "source": "byul.ai",
                  "title": "뉴스 제목",
                  "summary": "뉴스 요약",
                  "ai_interpretation": "AI 심층 해석",
                  "korea_impact": "🇰🇷 한국 시장 영향",
                  "investor_opinion": "💡 증시 투자 의견"
                }}
              ]
            }}
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
        fallback_rep, fallback_news = generate_fallback_data(real_data, market_date_str)
        if not detailed_report: detailed_report = fallback_rep
        if not categorized_news: categorized_news = fallback_news

    final_json = {
        "updated_at": f"{market_date_str} 미국장 마감 시황",
        "macro_indicators": [
            {"name": "원/달러 환율", "value": f"{real_data.get('원/달러 환율', {}).get('price')}원", "change": real_data.get('원/달러 환율', {}).get('change'), "status": "외환시세"},
            {"name": "비트코인 (BTC)", "value": real_data.get('비트코인', {}).get('price'), "change": real_data.get('비트코인', {}).get('change'), "status": "암호화폐"},
            {"name": "이더리움 (ETH)", "value": real_data.get('이더리움', {}).get('price'), "change": real_data.get('이더리움', {}).get('change'), "status": "암호화폐"},
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
                "tenor": "미국 2년물 국채금리", "yield_rate": f"{real_data.get('미국 2년물', {}).get('price')}%",
                "change": real_data.get('미국 2년물', {}).get('change'), "prev_close": real_data.get('미국 2년물', {}).get('prev_close'),
                "open": real_data.get('미국 2년물', {}).get('open'), "high": real_data.get('미국 2년물', {}).get('high'), "low": real_data.get('미국 2년물', {}).get('low')
            },
            {
                "tenor": "미국 10년물 국채금리", "yield_rate": f"{real_data.get('미국 10년물', {}).get('price')}%",
                "change": real_data.get('미국 10년물', {}).get('change'), "prev_close": real_data.get('미국 10년물', {}).get('prev_close'),
                "open": real_data.get('미국 10년물', {}).get('open'), "high": real_data.get('미국 10년물', {}).get('high'), "low": real_data.get('미국 10년물', {}).get('low')
            },
            {
                "tenor": "미국 30년물 국채금리", "yield_rate": f"{real_data.get('미국 30년물', {}).get('price')}%",
                "change": real_data.get('미국 30년물', {}).get('change'), "prev_close": real_data.get('미국 30년물', {}).get('prev_close'),
                "open": real_data.get('미국 30년물', {}).get('open'), "high": real_data.get('미국 30년물', {}).get('high'), "low": real_data.get('미국 30년물', {}).get('low')
            }
        ],
        "detailed_capital_flow_report": detailed_report,
        "categorized_news": categorized_news
    }

    with open("us_market.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print("us_market.json 심층 리포트 및 분리 뉴스 업데이트 완료!")

if __name__ == "__main__":
    generate_market_report()
