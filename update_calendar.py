import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def fetch_investing_and_byul_events():
    """인베스팅닷컴 및 byul.ai 증시 일정 크롤링 수집"""
    urls = [
        "https://news.google.com/rss/search?q=site:investing.com+economic+calendar&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=byul+증시+일정+경제지표&hl=ko&gl=KR&ceid=KR:ko"
    ]
    raw_titles = []
    for url in urls:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall('.//item')[:5]:
                    t = item.find('title').text
                    if t and t not in raw_titles:
                        raw_titles.append(t)
        except Exception as e:
            print(f"일정 수집 오류: {e}")
    return raw_titles

def generate_fallback_schedules():
    """크롤링/API 예외 시 백업용 2026년 9월 인베스팅닷컴 & byul.ai 통합 일정"""
    return [
        {
            "id": 1,
            "date": "2026-09-01",
            "time": "08:30",
            "stars": 3,
            "impact": "상",
            "category": "국내 경제지표",
            "title": "한국 8월 수출입 동향 지표 발표",
            "overview": "산업통상자원부 주관 8월 월간 수출입 동향 및 무역수지 최종 통계 발표입니다.",
            "importance": "HBM3e/HBM4 및 차세대 반도체 수출 흑자 폭과 자동차·배터리 밸류체인의 글로벌 수요를 검증하는 선행 지표입니다.",
            "key_points": "반도체 수출 전년 대비 증가율 지속 여부, 대중국 및 대미국 수출 성장세 차별화.",
            "korea_impact": "코스피 시가총액 상위 반도체 대장주(삼성전자, SK하이닉스) 수급에 직접적 기여.",
            "us_impact": "글로벌 IT 하드웨어 공급망 및 메모리 반도체 턴어라운드 흐름의 선행 지표로 작용.",
            "stocks": ["삼성전자", "SK하이닉스", "현대차"],
            "stock_reasons": "반도체 월간 수출액 최고치 경신 지속 시 대형 반도체주로 외국인 순매수 집중 예상."
        },
        {
            "id": 2,
            "date": "2026-09-29",
            "time": "00:30",
            "stars": 2,
            "impact": "중",
            "category": "미국 경제지표",
            "title": "9월 댈러스 연은 제조업지수",
            "overview": "미국 텍사스 및 댈러스 지역 제조업 경기 동향 및 생산지수를 측정하는 지표입니다.",
            "importance": "미국 제조업 체감 경기 수준과 연준의 자금 조달 금리 부담을 미리 가늠할 수 있습니다.",
            "key_points": "신규 주문 지수 및 신규 고용 지수의 회복세 여부.",
            "korea_impact": "국내 수출 제조업 경기와 연동된 산업재 섹터 투자 심리 영향.",
            "us_impact": "연준의 경제연착륙 가능성 판단 재료.",
            "stocks": ["Caterpillar", "Deere"],
            "stock_reasons": "제조업 지수 회복 시 미국 대형 기계 및 산업재 종목 수급 개선."
        },
        {
            "id": 3,
            "date": "2026-09-29",
            "time": "22:15",
            "stars": 3,
            "impact": "상",
            "category": "미국 경제지표",
            "title": "ADP 주간 고용변화 보고서",
            "overview": "민간 고용 조사업체 ADP가 발표하는 비농업 부문 민간 고용 변동 데이터입니다.",
            "importance": "미국 노동시장 열기와 연준의 기준금리 인하 경로를 판단하는 핵심 고용 지표입니다.",
            "key_points": "민간 고용 건수의 예상치 상회 여부 및 임금 상승률 속도.",
            "korea_impact": "미국 금리 향방에 따른 원/달러 환율 및 외국인 증시 수급 변동.",
            "us_impact": "미국 채권 금리 변동성 및 나스닥 기술주 투심 직결.",
            "stocks": ["Microsoft", "Apple", "NVIDIA"],
            "stock_reasons": "고용 냉각 시 금리 인하 기대감 상승으로 빅테크 랠리 가능성."
        },
        {
            "id": 4,
            "date": "2026-09-29",
            "time": "23:00",
            "stars": 2,
            "impact": "중",
            "category": "미국 경제지표",
            "title": "7월 주택가격지수 MoM / YoY",
            "overview": "S&P/Case-Shiller 미국 20대 도시 주택 가격 변동률 지수입니다.",
            "importance": "주거비 인플레이션 압력을 확인하는 핵심 부동산 지표입니다.",
            "key_points": "주택 가격 상승세 둔화 여부 및 신규 주택 수급 균형.",
            "korea_impact": "글로벌 부동산 경기 체감 및 국내 리츠 종목 투심 고조.",
            "us_impact": "미국 소비자 물가지수(CPI) 내 주거비 하락 가능성 가늠.",
            "stocks": ["Home Depot", "Lennar"],
            "stock_reasons": "주택 경기 안정화 시 미국 주택 건설 및 인테리어 종목 수혜."
        },
        {
            "id": 5,
            "date": "2026-09-30",
            "time": "00:00",
            "stars": 3,
            "impact": "상",
            "category": "미국 경제지표",
            "title": "8월 JOLTS 구인·이직 보고서",
            "overview": "미국 노동부 노동통계국에서 발표하는 구인 건수 및 이직 동향 보고서입니다.",
            "importance": "구인 비율 수치를 통해 노동 시장 수급 불균형 완화 여부를 정밀 체크합니다.",
            "key_points": "자발적 퇴직자 수 및 기업들의 채용 공고 감소세.",
            "korea_impact": "미국 기준금리 인하 속도에 따른 국내 증시 유동성 유입 환경.",
            "us_impact": "연준(Fed)의 통화정책 수립 시 가장 비중 있게 참조하는 고용 지표.",
            "stocks": ["Tesla", "Amazon"],
            "stock_reasons": "구인건수 감소 시 금리 인하 압력 확대로 성장주 투심 자극."
        }
    ]

def update_calendar_json():
    raw_news = fetch_investing_and_byul_events()
    schedules = generate_fallback_schedules()

    if GEMINI_API_KEY and raw_news:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
            수집된 일정 데이터: {json.dumps(raw_news, ensure_ascii=False)}
            위 수집 데이터를 바탕으로 2026년 9월 인베스팅닷컴 및 byul.ai 스타일의 주요 증시 일정을 아래 구조의 JSON 배열로 생성하세요:
            [
              {{
                "id": 1,
                "date": "2026-09-29",
                "time": "22:15",
                "stars": 3,
                "impact": "상",
                "category": "미국 경제지표",
                "title": "ADP 주간 고용변화 보고서",
                "overview": "개요",
                "importance": "중요성",
                "key_points": "관전 포인트",
                "korea_impact": "한국 영향",
                "us_impact": "미국 영향",
                "stocks": ["종목1", "종목2"],
                "stock_reasons": "수혜 이유"
              }}
            ]
            """
            for model_name in ['gemini-2.5-flash', 'gemini-3.6-flash']:
                try:
                    res = client.models.generate_content(model=model_name, contents=prompt)
                    text = res.text.strip()
                    if "```" in text:
                        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")]).strip()
                    parsed = json.loads(text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        schedules = parsed
                    break
                except Exception as e:
                    print(f"Gemini API 일정 파싱 실패: {e}")
        except Exception as e:
            print(f"Gemini 클라이언트 오류: {e}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

    print("data.json 캘린더 일정 업데이트 성공!")

if __name__ == "__main__":
    update_calendar_json()
