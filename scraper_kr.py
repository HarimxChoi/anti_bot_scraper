#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 부동산 상세 매물 정보 크롤러 (인간형 맵 이동 + 매물 상세 확장)

이 스크래퍼는 네이버 부동산에서 매물 정보를 자동으로 수집합니다.
Anti-bot 우회 기술을 사용하여 안정적으로 데이터를 수집하고,
갭투자 기회를 자동으로 분석합니다.
"""

import asyncio, math, random, re
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import pandas as pd
from playwright.async_api import async_playwright

# ======== 설정 ========
# 이 설정값들을 수정하여 수집 범위와 성능을 조정할 수 있습니다.
# 자세한 설명은 README.md의 "설정 상세 설명" 섹션을 참고하세요.

KOR_BOUNDS = (33.0, 39.5, 124.0, 132.1)  # 한국 영토 범위 (제주도~강원도, 서해~동해)
MAX_COMPLEX_DETAIL = 800                   # 방문할 단지/건물 최대 개수 (너무 많으면 시간 오래 걸림)
MAX_ARTICLE_DETAIL = 10000                 # 상세 정보를 가져올 매물 최대 개수
USE_MOBILE_DETAIL = True                   # 모바일 페이지 사용 (더 빠르고 안정적)
ONLY_WITH_PREV_JEONSE = True               # 과거 전세 기록이 있는 매물만 수집 (갭투자 분석용)
BLOCK_HEAVY_RESOURCES = True               # 이미지/폰트 차단 (속도 2-3배 향상)
MIN_LISTING_COUNT = 2                      # 이 개수 이상 매물이 있는 단지만 우선 처리
PRIORITIZE_BY_COUNT = False                # True면 매물 많은 단지부터 방문 (시간 제한 시 유용)
DETAIL_WORKERS = 12                        # 동시에 처리할 브라우저 탭 수 (4-20 권장)
GRID_RINGS = 1                             # 중심에서 바깥으로 몇 고리까지 스캔할지 (넓은 지역은 2-3)
GRID_STEP_PX = 480                         # 각 스캔 지점 간 간격 (작을수록 촘촘)
SWEEP_DWELL = 0.6                          # 각 지점에서 머무는 시간(초) - 너무 짧으면 데이터 누락
ZOOM_MIN, ZOOM_MAX = 15, 17                # 줌 레벨 범위 (15=구 단위, 17=동네 단위)
ASSET_TYPES = "APT:VL"                     # "APT"=아파트만, "VL"=빌라만, "APT:VL"=둘 다

ONLY_PREV_GT_SALE = True                   # True면 기전세금≥매매가 매물만 결과에 포함 (갭투자 후보만)
# =====================

# 단지별 메타정보 저장소 (이름, 매물 수)
complex_meta = {}

def _build_scenarios():
    """
    사용자가 선택한 자산 유형(아파트/빌라)에 따라
    어떤 API 엔드포인트를 호출할지 결정합니다.
    
    APT → /complexes 엔드포인트
    VL → /houses 엔드포인트
    """
    want = set([s.strip().upper() for s in ASSET_TYPES.split(":") if s.strip()])
    scenarios = []
    if "APT" in want:
        scenarios.append(("complexes", "APT"))
    if "VL" in want:
        scenarios.append(("houses", "VL"))
    return scenarios

def pixel_to_ll(x: float, y: float, z: float):
    """
    픽셀 좌표를 위도/경도로 역변환합니다.
    
    지도를 드래그할 때 정확한 위치를 계산하기 위해 필요합니다.
    메르카토르 투영법을 사용합니다.
    """
    scale = 256 * (2 ** z)
    lon = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lon

async def grid_sweep(page, center_lat, center_lon, zoom, rings=1, step_px=360, dwell=0.5):
    """
    중심 좌표 주변을 그리드 패턴으로 스캔합니다.
    
    왜 필요한가?
    - 한 번에 보이는 맵 영역은 제한적
    - 주변 지역까지 체계적으로 스캔해야 매물 누락 방지
    - 위/아래 행만 스캔하여 봇처럼 보이지 않게 함
    
    예시: rings=1, step_px=480이면 중심 주변 8-12개 지점 방문
    """
    # 중심점의 픽셀 좌표 계산
    cx, cy = ll_to_pixel(center_lat, center_lon, zoom)
    coords = []
    
    # 각 링(고리)마다 위/아래 행의 지점들 생성
    for r in range(1, rings + 1):
        for dx in range(-r, r + 1):
            for dy in (-r, r):  # 위, 아래 행만 (중간 행은 건너뜀)
                x, y = cx + dx * step_px, cy + dy * step_px
                coords.append(pixel_to_ll(x, y, zoom))

    # 생성된 모든 지점을 순회하며 맵 이동
    total = len(coords)
    for i, (lat_, lon_) in enumerate(coords, 1):
        print(f"   ↪ 스윕 {i}/{total} 이동 중...")
        await drag_to_latlon(page, lat_, lon_)
        await page.mouse.wheel(0, -40)  # 약간 스크롤하여 새 마커 로딩 트리거
        await asyncio.sleep(dwell)


def clamp_korea(lat: float, lon: float):
    """
    좌표가 한국 영토 범위를 벗어나지 않도록 제한합니다.
    
    잘못된 좌표 입력 시 자동으로 가장 가까운 한국 내 좌표로 보정합니다.
    """
    mnLat, mxLat, mnLon, mxLon = KOR_BOUNDS
    return max(mnLat, min(lat, mxLat)), max(mnLon, min(lon, mxLon))

def ll_to_pixel(lat: float, lon: float, z: float):
    """
    위도/경도를 픽셀 좌표로 변환합니다.
    
    메르카토르 투영법 사용:
    - 구체(지구)를 평면(화면)으로 변환하는 수학 공식
    - 정확한 맵 드래그를 위해 필수
    
    이 함수 덕분에 "강남역"이라는 위도/경도를 화면의 정확한 픽셀로 이동 가능
    """
    scale = 256 * (2 ** z)
    x = (lon + 180.0) / 360.0 * scale
    siny = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y

async def setup_blocking(ctx):
    """
    무거운 리소스(이미지, 폰트, 미디어)를 차단합니다.
    
    효과:
    - 페이지 로딩 속도 2-3배 향상
    - 네트워크 대역폭 절약
    - 봇 탐지에는 영향 없음 (오히려 자연스러움)
    """
    if not BLOCK_HEAVY_RESOURCES:
        return
    async def _route(route):
        rt = route.request.resource_type
        if rt in ("image", "media", "font"):
            return await route.abort()  # 이미지/미디어/폰트 요청 차단
        return await route.continue_()
    await ctx.route("**/*", _route)


async def get_ms(page):
    """
    현재 페이지 URL에서 맵 상태(위도, 경도, 줌 레벨)를 추출합니다.
    
    네이버 지도 URL 형식: ?ms=37.5608,126.9888,15
    → 위도 37.5608, 경도 126.9888, 줌 레벨 15
    
    이 정보로 현재 맵 위치를 파악하고 다음 동작을 결정합니다.
    """
    u = urlparse(page.url)
    ms = parse_qs(u.query).get("ms", [None])[0]
    if not ms: 
        return None
    try:
        la, lo, zz = ms.split(",")
        return float(la), float(lo), float(zz)
    except Exception:
        return None

async def wheel_to_zoom(page, target_zoom: int, step_delay=0.3):
    """
    마우스 휠로 특정 줌 레벨까지 확대/축소합니다.
    
    사람처럼 행동하기 위해:
    - 한 번에 확 바꾸지 않고 여러 번 스크롤
    - 각 스크롤 사이에 딜레이
    - 목표 줌에 도달하면 정지
    """
    for _ in range(20):
        cur = await get_ms(page)
        if not cur:
            await asyncio.sleep(0.3)
            continue
        _, _, z = cur
        z = round(z)
        if z == target_zoom:
            return  # 목표 달성
        # 확대 필요하면 -300 (위로 스크롤), 축소 필요하면 +300 (아래로 스크롤)
        await page.mouse.move(960, 540)
        await page.mouse.wheel(0, -300 if target_zoom > z else 300)
        await asyncio.sleep(step_delay)

async def drag_to_latlon(page, lat: float, lon: float, tolerance_px=3.5):
    """
    맵을 드래그하여 특정 위도/경도로 이동합니다.
    
    사람처럼 행동하기 위해:
    - 한 번에 정확히 이동하지 않음
    - 여러 번 드래그하여 점진적으로 접근
    - 마우스 이동을 20단계로 부드럽게 (steps=20)
    - 3.5픽셀 이내 오차면 충분히 가까운 것으로 판단
    """
    for _ in range(18):
        cur = await get_ms(page)
        if not cur:
            await asyncio.sleep(0.3)
            continue
        cur_lat, cur_lon, z = cur
        
        # 현재 위치와 목표 위치의 픽셀 거리 계산
        x1, y1 = ll_to_pixel(cur_lat, cur_lon, z)
        x2, y2 = ll_to_pixel(lat, lon, z)
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        
        # 충분히 가까우면 종료
        if dist <= tolerance_px:
            return
        
        # 한 번에 최대 800픽셀까지만 이동 (자연스럽게)
        step = min(800.0, dist)
        r = step / (dist + 1e-9)
        mx, my = dx * r, dy * r
        
        # 드래그 동작 수행
        await page.mouse.move(960, 540)
        await page.mouse.down()
        await page.mouse.move(960 - mx, 540 - my, steps=20)  # 20단계로 부드럽게 이동
        await page.mouse.up()
        await asyncio.sleep(0.35)

async def human_like_recenter(page, lat: float, lon: float, zoom: int):
    """
    사람처럼 자연스럽게 맵의 중심을 특정 위치로 이동합니다.
    
    봇 탐지를 우회하는 핵심 기법:
    1. 랜덤하게 줌 아웃 (9-12레벨)
    2. 목표 위치로 대략 이동
    3. 원하는 줌 레벨로 확대
    4. 정확한 위치로 미세 조정
    
    이렇게 하면 "한 번에 정확히 찾아가는 봇"처럼 보이지 않습니다.
    """
    rand_out = random.randint(9, 12)  # 랜덤 줌 아웃 레벨
    await wheel_to_zoom(page, rand_out)
    await drag_to_latlon(page, lat, lon)
    await wheel_to_zoom(page, zoom)
    await drag_to_latlon(page, lat, lon)

async def switch_to_listing_markers(page):
    """
    네이버 부동산 맵에서 '매물 보기' 모드로 전환합니다.
    
    기본은 '단지' 보기인데, '매물' 보기로 바꿔야 개별 매물 정보가 나옵니다.
    여러 가지 버튼 텍스트를 시도하여 UI 변경에 대응합니다.
    """
    # 1순위: 직접적인 매물 관련 버튼
    for txt in ["상세매물검색", "매물", "매물검색", "매물 보기"]:
        try:
            await page.locator(f"text={txt}").first.click()
            await asyncio.sleep(0.5)
            return True
        except:
            pass
    
    # 2순위: 드롭다운 방식
    try:
        await page.locator('button:has-text("단지")').first.click()
        await asyncio.sleep(0.3)
        await page.locator('text=매물').first.click()
        await asyncio.sleep(0.5)
        return True
    except:
        return False


def parse_kr_money_to_won(s: str) -> int | None:
    """
    한국식 금액 표기를 원(₩) 단위 숫자로 변환합니다.
    
    처리 가능한 형식:
    - "3억 8,000만원" → 380,000,000
    - "8,500" → 85,000,000 (만원 단위로 가정)
    - "7.5억" → 750,000,000
    - "320000000원" → 320,000,000
    
    이 함수 덕분에 네이버의 다양한 금액 표기를 통일된 숫자로 처리 가능
    """
    if not s:
        return None

    orig = s
    t = s.strip().replace(" ", "").replace(",", "")
    has_won = "원" in t
    t = t.replace("원", "")

    eok = 0  # 억 (100,000,000)
    man = 0  # 만 (10,000)
    total = 0

    # "억" 단위 처리 (소수점 허용: "7.5억")
    m = re.search(r"(\d+(?:\.\d+)?)억", t)
    if m:
        try:
            total += int(float(m.group(1)) * 100_000_000)
        except:
            pass
        
        # 억 뒤의 만 단위 처리: "3억8000만", "3억8000", "3억2천"
        m2 = re.search(r"억(\d+)만", t)
        if m2:
            man = int(m2.group(1))
        else:
            m2 = re.search(r"억(\d+)$", t)
            if m2:
                man = int(m2.group(1))
            else:
                m2 = re.search(r"억(\d+)천", t)
                if m2:
                    man = int(m2.group(1)) * 1000

    else:
        # 억이 없을 때 만/천 단위 처리
        m = re.search(r"(\d+)만", t)
        if m:
            man = int(m.group(1))
        else:
            m = re.search(r"(\d+)천만?", t)
            if m:
                man = int(m.group(1)) * 1000

    # 순수 숫자만 있는 경우
    # "원" 표기 있으면 원 단위, 없으면 만원 단위로 가정
    if total == 0 and man == 0 and re.fullmatch(r"\d+", t):
        return int(t) if has_won else int(t) * 10_000

    return total + man * 10_000


async def scrape_article_detail(detail_page, article_no: str) -> dict:
    """
    매물 상세 페이지에서 중개사 정보와 과거 전세가를 추출합니다.
    
    수집 정보:
    - 부동산 상호 (예: 강남부동산)
    - 중개사 이름 (예: 홍길동)
    - 연락처 2개
    - 과거 전세가 (기전세금) ← 갭투자 분석의 핵심!
    - 최근 N년간 전세가 최고/최저
    
    ONLY_WITH_PREV_JEONSE=True면 기전세금 없는 매물은 즉시 건너뜀 (시간 절약)
    """
    async def _goto(url: str):
        """페이지 이동 + 리다이렉트 처리"""
        await detail_page.goto(url, wait_until='domcontentloaded')
        await asyncio.sleep(0.3)
        # 만약 fin.land로 리다이렉트되면 다시 원래 URL로
        if "fin.land.naver.com" in detail_page.url:
            await detail_page.goto(f"https://m.land.naver.com/article/info/{article_no}",
                                   wait_until='domcontentloaded')
            await asyncio.sleep(0.3)

    # 매물 정보 페이지 접근 시도
    await _goto(f"https://m.land.naver.com/article/info/{article_no}")
    try:
        body_txt = await detail_page.inner_text("body")
    except:
        body_txt = ""
    
    # 페이지가 비어있거나 에러 페이지면 다른 URL 시도
    if ("요청하신 페이지를 찾을 수 없어요" in body_txt) or (len(body_txt.strip()) < 50):
        await _goto(f"https://m.land.naver.com/article/view/{article_no}")
        try:
            body_txt = await detail_page.inner_text("body")
        except:
            body_txt = ""

    # -------- 프리체크: 기전세금 먼저 확인 --------
    # 갭투자 분석에 기전세금은 필수입니다.
    # 없으면 분석 불가능하므로 시간 낭비하지 않고 즉시 스킵
    def grab(regex, flags=0):
        """정규식으로 텍스트에서 패턴 추출"""
        m = re.search(regex, body_txt, flags)
        return m.group(1).strip() if m else ""

    prev_jeonse_txt = grab(r"기전세금\s*([\d,억\s만]+)")
    prev_jeonse = parse_kr_money_to_won(prev_jeonse_txt) if prev_jeonse_txt else None
    
    if ONLY_WITH_PREV_JEONSE and not prev_jeonse:
        return {"__skip__": True}  # 기전세금 없으면 건너뛰기

    # -------- 전세 탭으로 전환하여 기간별 최고/최저 확인 --------
    # 실거래가 탭에서는 매매 정보만 나오므로 전세 탭으로 전환 필요
    try:
        await detail_page.locator("text=실거래가").first.click()
        await asyncio.sleep(0.2)
        await detail_page.locator("text=전세").first.click()
        await asyncio.sleep(0.25)
        body_txt = await detail_page.inner_text("body")
    except:
        pass

    # -------- 중개사 정보 추출 --------
    lines = [l.strip() for l in body_txt.splitlines() if l.strip()]
    agent_name, office, cand_idx = "", "", -1
    
    # 2-4글자 한글 이름 찾기 (주변에 "중개사" 키워드 있는지 확인)
    for i, l in enumerate(lines):
        if re.fullmatch(r"[가-힣]{2,4}", l) and l not in ("이미지","상세보기","중개사","중개소"):
            ctx = "\n".join(lines[max(0,i-3):i+2])
            if ("중개사" in ctx) or ("프로필" in ctx) or ("중개소" in ctx):
                agent_name, cand_idx = l, i
                break
    
    # 중개사 이름 아래에서 "공인중개사" 또는 "부동산" 포함된 줄 찾기
    office_pat = re.compile(r"(공인중개사|부동산)")
    if cand_idx >= 0:
        for l in lines[cand_idx+1:cand_idx+6]:
            if office_pat.search(l) and ("상세보기" not in l) and ("전화" not in l):
                office = l
                break
    
    # 백업: "중개소" 키워드로 상호 찾기
    if not office:
        m = re.search(r"중개소\s+([^\n]+)", body_txt)
        if m:
            tmp = m.group(1).strip()
            if "이미지" not in tmp:
                office = tmp

    # -------- 전세 기간별 최고/최저 추출 --------
    # "3년 내 최고 3억 5천", "3년 내 최저 3억 2천" 같은 패턴
    m_max = re.search(r"(\d+)\s*년\s*내\s*최고\s*([\d,억\s만]+)", body_txt)
    m_min = re.search(r"(\d+)\s*년\s*내\s*최저\s*([\d,억\s만]+)", body_txt)
    
    period_years = int(m_max.group(1)) if m_max else (int(m_min.group(1)) if m_min else None)
    jeonse_max = parse_kr_money_to_won(m_max.group(2)) if m_max else None
    jeonse_min = parse_kr_money_to_won(m_min.group(2)) if m_min else None

    # -------- 전화번호 추출 --------
    # 02-1234-5678, 010-1234-5678 형식
    phones = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", body_txt)
    phone1 = phones[0] if len(phones) >= 1 else ""
    phone2 = phones[1] if len(phones) >= 2 else ""

    return {
        "부동산상호": office,
        "중개사이름": agent_name,
        "전화1": phone1,
        "전화2": phone2,
        "전세_기간(년)": period_years,
        "전세_기간내_최고(원)": jeonse_max,
        "전세_기간내_최저(원)": jeonse_min,
        "기전세금(원)": prev_jeonse,
    }

async def crawl_detailed(lat=37.5608, lon=126.9888, zoom=14):
    """
    메인 크롤링 로직
    
    전체 프로세스:
    1. 브라우저 실행 (데스크톱 + 모바일)
    2. 네이버 부동산 맵 접속
    3. 중심 좌표 주변 그리드 스윕 → 단지/매물 마커 수집
    4. 매물 많은 단지 우선 방문 → 상세 매물 리스트 수집
    5. 각 매물의 상세 페이지 방문 → 중개사 정보 + 전세가 수집
    6. 갭투자 분석 → 엑셀 저장
    """
    # 좌표가 한국 범위를 벗어나면 자동 보정
    lat, lon = clamp_korea(lat, lon)
    zoom = int(zoom)

    async with async_playwright() as p:
        print("\n🚀 브라우저 실행 중...")
        print("\n5~10초의 로딩시간이 있으니 기다려주세요")
        
        # -------- 브라우저 초기화 --------
        # 데스크톱 브라우저: 맵 네비게이션용
        browser = await p.chromium.launch(headless=False)  # headless=True하면 화면 안 보임
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        await setup_blocking(context)  # 이미지/폰트 차단 활성화
        page = await context.new_page()
        
        # webdriver 속성 숨기기 (봇 탐지 우회)
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        # -------- 모바일 브라우저 초기화 (상세 페이지용) --------
        # 모바일 페이지가 더 가볍고 빠름
        if USE_MOBILE_DETAIL:
            print("📱 모바일 브라우저 초기화 중... (상세 정보 수집용)")
            device = p.devices["iPhone 14 Pro Max"]
            mctx = await browser.new_context(
                **device,
                locale="ko-KR",
                extra_http_headers={
                    "referer": "https://m.land.naver.com/",
                    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            )
        else:
            mctx = context

        await setup_blocking(mctx)

        # -------- 워커 탭 풀 생성 --------
        # 동시에 여러 매물 상세 페이지를 처리하기 위한 브라우저 탭들
        # DETAIL_WORKERS=12면 12개 탭이 동시에 작동
        worker_count = DETAIL_WORKERS if USE_MOBILE_DETAIL else 1
        detail_pages = []
        print(f"🔧 {worker_count}개 워커 탭 생성 중...")
        
        for _ in range(max(1, worker_count)):
            dp = await mctx.new_page()
            await dp.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.open = (u)=>{ location.href = u; };
            """)
            detail_pages.append(dp)

        # 탭 큐: 사용 가능한 탭을 관리
        page_q = asyncio.Queue()
        for dp in detail_pages:
            page_q.put_nowait(dp)

        # -------- 데이터 수집 버퍼 초기화 --------
        complex_list, article_list, trade_history = [], [], []
        seen_complex, seen_article, seen_trade = set(), set(), set()
        flags = {"capture": False}  # 수집 활성화 플래그

        async def handle_response(response):
            """
            네이버 API 응답을 가로채서 데이터를 추출합니다.
            
            네이버는 맵을 움직일 때마다 API로 매물 정보를 받아옵니다.
            이 함수가 그 응답을 실시간으로 가로채서 파싱합니다.
            
            수집하는 API 종류:
            1. single-markers: 맵에 표시되는 단지/건물 마커
            2. /api/articles/complex|house/{id}: 단지별 매물 리스트
            3. /api/complexes/{id}/prices: 실거래가 이력
            """
            if not flags["capture"]:
                return  # 아직 수집 시작 전
            
            url = response.url

            def _is_villa_marker(it: dict) -> bool:
                """마커가 빌라/연립인지 판단"""
                code = (it.get('realEstateTypeCode') or it.get('estateType') or it.get('rletTpCd') or '').upper()
                name = (it.get('realEstateTypeName') or it.get('estateTypeName') or it.get('rletTpNm') or '')
                if code:
                    return code == 'VL'
                return any(k in name for k in ('빌라','연립','다세대'))

            def _is_villa_article(a: dict) -> bool:
                """매물이 빌라/연립인지 판단"""
                code = (a.get('realEstateTypeCode') or a.get('rletTpCd') or '').upper()
                name = (a.get('realEstateTypeName') or a.get('rletTpNm') or '')
                if code:
                    return code == 'VL'
                return any(k in name for k in ('빌라','연립','다세대'))

            # 1) 단지/빌라 마커 수집
            if ('complexes/single-markers' in url) or ('houses/single-markers' in url):
                try:
                    data = await response.json()
                    if isinstance(data, list):
                        for it in data:
                            # houses 엔드포인트에서 온 건데 VL이 아니면 건너뜀
                            if 'houses/single-markers' in url and not _is_villa_marker(it):
                                continue
                            
                            cno = str(it.get('markerId') or it.get('complexNo') or it.get('houseNo') or '')
                            name = it.get('complexName') or it.get('houseName') or ''
                            cnt = (it.get('articleCount') or it.get('dealCount') or it.get('totalCount') or it.get('cnt') or 0)
                            
                            if cno:
                                if cno not in seen_complex:
                                    seen_complex.add(cno)
                                    complex_list.append(it)
                                
                                # 메타정보 업데이트 (이름, 매물 수)
                                meta = complex_meta.setdefault(cno, {"name": name, "count": 0})
                                meta["name"] = name or meta["name"]
                                if isinstance(cnt, int) and cnt > meta["count"]:
                                    meta["count"] = cnt
                except:
                    pass

            # 2) 단지별 매물 리스트 수집
            elif ('/api/articles/complex/' in url) or ('/api/articles/house/' in url):
                try:
                    data = await response.json()
                    
                    # URL에서 단지 ID 추출
                    m = re.search(r'/api/articles/(?:complex|house)/(\d+)', url)
                    cno = m.group(1) if m else None
                    
                    # 총 매물 수 업데이트
                    total = data.get('totalCount') or data.get('count') or 0
                    if cno and total:
                        meta = complex_meta.setdefault(cno, {"name": "", "count": 0})
                        if total > meta["count"]:
                            meta["count"] = int(total)

                    # 매물 리스트 파싱
                    articles = data.get('articleList') or data.get('articles') or []
                    for a in articles:
                        # houses 응답인데 VL이 아니면 건너뜀
                        if '/api/articles/house/' in url and not _is_villa_article(a):
                            continue
                        
                        # 매매 거래만 수집 (전세/월세 제외)
                        tcode = (a.get('tradeType') or "").upper()
                        tname = (a.get('tradeTypeName') or "").strip()
                        if tcode not in ('A1',) and tname not in ('매매', 'SALE'):
                            continue
                        
                        k = a.get('articleNo')
                        if k and k not in seen_article:
                            seen_article.add(k)
                            article_list.append(a)
                except:
                    pass

            # 3) 실거래가 이력 수집
            elif ('/api/complexes/' in url) and ('/prices' in url):
                try:
                    data = await response.json()
                    if isinstance(data, list):
                        for t in data:
                            k = (t.get('dealDate'), t.get('area'), t.get('floor'), t.get('dealPrice'))
                            if k not in seen_trade:
                                seen_trade.add(k)
                                trade_history.append(t)
                except:
                    pass

            # 4) 백업: 기타 API에서 매물 찾기
            elif '/api/' in url:
                try:
                    data = await response.json()
                except:
                    data = None

                def collect_from(obj):
                    """재귀적으로 JSON에서 매물 정보 찾기"""
                    added = 0
                    if isinstance(obj, dict):
                        if 'articleList' in obj and isinstance(obj['articleList'], list):
                            return collect_from(obj['articleList'])
                        for v in obj.values():
                            added += collect_from(v)
                    elif isinstance(obj, list):
                        for it in obj:
                            if isinstance(it, dict):
                                k = it.get('articleNo') or it.get('atclNo')
                                if k:
                                    tcode = (it.get('tradeType') or it.get('tradTp') or "").upper()
                                    tname = (it.get('tradeTypeName') or "").strip()
                                    if tcode not in ('A1',) and tname not in ('매매', 'SALE'):
                                        continue
                                    if k not in seen_article:
                                        seen_article.add(k)
                                        article_list.append(it)
                                        added += 1
                            else:
                                added += collect_from(it)
                    return added

                added = collect_from(data)
                if added:
                    print(f"✅ 매물 발견: +{added}개  / 누적 {len(seen_article)}개")

        # API 응답 가로채기 시작
        page.on('response', handle_response)

        # -------- 1단계: 맵 네비게이션 & 데이터 수집 --------
        print(f"\n📍 수집 위치: 위도 {lat:.4f}, 경도 {lon:.4f}, 줌 {zoom}")
        z_clamped = max(ZOOM_MIN, min(ZOOM_MAX, int(zoom)))

        scenarios = _build_scenarios()
        for base_kind, a_param in scenarios:
            base = f"https://new.land.naver.com/{base_kind}"
            url = urlunparse(urlparse(base)._replace(query=urlencode({
                'ms': f'{lat},{lon},{z_clamped}',
                'a': a_param,  # APT 또는 VL
                'b': 'A1',     # 매매
            })))
            
            asset_type = "아파트" if a_param == "APT" else "빌라/연립"
            print(f"\n🏘️  {asset_type} 매물 수집 시작...")
            await page.goto(url, wait_until='domcontentloaded')

            # 캔버스(맵) 로딩 대기
            try:
                await page.wait_for_selector("canvas", timeout=20000)
            except:
                print("⚠️  맵 로딩 타임아웃 (계속 진행)")

            # 첫 API 응답 대기
            try:
                await page.wait_for_response(
                    lambda r: (
                        (f"{base_kind}/single-markers" in r.url) or
                        ("/api/articles/complex/" in r.url) or
                        ("/api/articles/house/" in r.url) or
                        ("/api/map/" in r.url)
                    ),
                    timeout=20000
                )
            except:
                print("⚠️  API 응답 타임아웃 (계속 진행)")

            print("🎯 사람처럼 맵 이동 중... (봇 탐지 우회)")
            await human_like_recenter(page, lat, lon, z_clamped)
            await switch_to_listing_markers(page)  # '매물 보기' 모드로 전환
            await wheel_to_zoom(page, max(15, z_clamped))

            # 수집 시작!
            flags["capture"] = True

            # 첫 마커 로드 트리거
            await page.mouse.move(960, 540)
            await page.mouse.wheel(0, -60)
            await asyncio.sleep(0.8)

            # 중심 주변 그리드 스윕
            print(f"🔍 주변 지역 스캔 중... (링: {GRID_RINGS}, 간격: {GRID_STEP_PX}px)")
            await grid_sweep(
                page,
                center_lat=lat, center_lon=lon,
                zoom=z_clamped, rings=GRID_RINGS,
                step_px=GRID_STEP_PX, dwell=SWEEP_DWELL,
            )

        print(f"\n✅ 1단계 완료: 단지 {len(seen_complex)}개, 매물 {len(seen_article)}개 발견")

        # -------- 2단계: 단지별 상세 정보 수집 --------
        if complex_list:
            print(f"\n📋 2단계: 단지 상세 정보 수집 중... (최대 {MAX_COMPLEX_DETAIL}개)")
            targets = []
            
            # 단지 리스트를 (매물수, ID, 이름, 종류) 튜플로 변환
            for c in complex_list:
                cno = str(c.get('complexNo') or c.get('houseNo') or c.get('markerId') or '')
                kind = 'houses' if c.get('houseNo') else 'complexes'
                name = c.get('complexName') or c.get('houseName') or ''
                cnt = complex_meta.get(cno, {}).get("count", 0)
                targets.append((cnt, cno, name, kind))

            # 최소 매물 수 필터링
            targets = [t for t in targets if t[0] >= MIN_LISTING_COUNT]
            
            # 매물 많은 순으로 정렬 (옵션)
            if PRIORITIZE_BY_COUNT:
                targets.sort(key=lambda x: x[0], reverse=True)
                print(f"💡 매물이 많은 단지부터 우선 처리합니다")

            # 타겟이 너무 적으면 백업 리스트 사용
            if not targets:
                print(f"⚠️  매물≥{MIN_LISTING_COUNT} 단지가 없습니다. 전체 리스트에서 선택...")
                for c in complex_list[:MAX_COMPLEX_DETAIL*2]:
                    cno = c.get('markerId') or c.get('complexNo') or ''
                    name = c.get('complexName') or ''
                    cnt = complex_meta.get(cno, {}).get("count", 0)
                    kind = 'houses' if c.get('houseNo') else 'complexes'
                    targets.append((cnt, cno, name, kind))
                targets.sort(key=lambda x: x[0], reverse=True)

            # 단지 방문
            print(f"\n🎯 {min(len(targets), MAX_COMPLEX_DETAIL)}개 단지 방문 예정")
            for idx, (cnt, complex_no, complex_name, kind) in enumerate(targets[:MAX_COMPLEX_DETAIL], 1):
                if not complex_no:
                    continue
                
                type_kr = "빌라/연립" if kind == "houses" else "아파트"
                print(f"\n[{idx}/{min(MAX_COMPLEX_DETAIL, len(targets))}] {complex_name} ({type_kr}, 매물: {cnt}개)")

                detail_url = f"https://new.land.naver.com/{kind}/{complex_no}"
                await page.goto(detail_url, wait_until='domcontentloaded')
                await asyncio.sleep(1.0)

                # '매매' 탭 클릭하여 매물 리스트 API 호출 트리거
                try:
                    await page.locator('button:has-text("매매")').first.click()
                    await asyncio.sleep(0.6)
                except:
                    pass

        # -------- 3단계: 매물 상세 정보 수집 --------
        print(f"\n📊 수집 요약:")
        print(f"  - 단지: {len(seen_complex)}개")
        print(f"  - 매물: {len(seen_article)}개")
        print(f"  - 실거래: {len(seen_trade)}건")

        results = []

        # 가격 낮은 순으로 정렬 (갭투자 후보를 먼저 찾기 위해)
        def _sale_price_of(a):
            raw = re.sub(r'^\s*매매\s*', '', (a.get('dealOrWarrantPrc', '') or '')).strip()
            return parse_kr_money_to_won(raw) or 10**12
        
        try:
            article_list.sort(key=_sale_price_of)
            print("\n💡 매매가가 낮은 매물부터 처리합니다 (갭투자 후보 우선)")
        except Exception:
            pass

        limit = MAX_ARTICLE_DETAIL if MAX_ARTICLE_DETAIL else len(article_list)
        print(f"\n🔍 3단계: 매물 상세 정보 수집 중... (최대 {limit}개)")
        print(f"   {worker_count}개 워커가 동시에 작업합니다")

        async def fetch_one(a):
            """
            하나의 매물에 대한 상세 정보를 가져옵니다.
            
            프로세스:
            1. 매매가 파싱
            2. 워커 탭 할당 받기
            3. 상세 페이지 스크래핑 (중개사 정보, 전세가)
            4. 갭투자 분석 (매매가 vs 기전세금)
            5. 필터링 (기전세금 >= 매매가만 통과)
            """
            # 매매가 파싱
            raw_price = re.sub(r'^\s*매매\s*', '', (a.get("dealOrWarrantPrc", "") or "")).strip()
            deal_value_won = parse_kr_money_to_won(raw_price)

            # 워커 탭 할당
            dp = await page_q.get()
            try:
                extra = await scrape_article_detail(dp, str(a.get("articleNo", "")))
            finally:
                await page_q.put(dp)  # 탭 반환

            # 기전세금 없으면 스킵
            if extra.get("__skip__"):
                return None

            prev_j = extra.get("기전세금(원)")

            # 갭투자 필터: 기전세금 >= 매매가
            if ONLY_PREV_GT_SALE and (prev_j is None or deal_value_won is None or prev_j < deal_value_won):
                return None

            # 갭 금액/비율 계산
            gap_amount = (deal_value_won - prev_j) if (deal_value_won is not None and prev_j is not None) else None
            gap_ratio = (gap_amount / deal_value_won) if (gap_amount is not None and deal_value_won) else None

            return {
                "매물명": a.get("articleName", ""),
                "매물번호": str(a.get("articleNo", "")),
                "거래유형": a.get("tradeTypeName", ""),
                "매매 금액(원)": deal_value_won,
                "층수": a.get("floorInfo", ""),
                "면적(㎡)": a.get("area1", ""),
                "전용면적": a.get("area2", ""),
                "방향": a.get("direction", ""),
                "특징": a.get("articleFeatureDesc", ""),
                "등록일": a.get("articleConfirmYmd", ""),
                "부동산상호": extra.get("부동산상호", ""),
                "중개사이름": extra.get("중개사이름", ""),
                "전화1": extra.get("전화1", ""),
                "전화2": extra.get("전화2", ""),
                "전세_기간(년)": extra.get("전세_기간(년)"),
                "전세_기간내_최고(원)": extra.get("전세_기간내_최고(원)"),
                "전세_기간내_최저(원)": extra.get("전세_기간내_최저(원)"),
                "기전세금(원)": prev_j,
                "갭금액(원)": gap_amount,
                "갭비율": gap_ratio,
            }

        # 모든 매물에 대해 비동기 작업 생성
        tasks = [asyncio.create_task(fetch_one(a)) for a in article_list[:limit]]

        # 작업 완료되는 대로 결과 수집
        processed = 0
        for coro in asyncio.as_completed(tasks):
            row = await coro
            if row:
                results.append(row)
                processed += 1
                if processed % 100 == 0:
                    print(f"   진행: {processed}/{limit} 처리 완료...")

        # -------- 4단계: 결과 저장 --------
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if results:
            print(f"\n💾 엑셀 파일 생성 중...")
            df = pd.DataFrame(results)
            out = f'매물정보_확장_{ts}.xlsx'
            df.to_excel(out, index=False, engine='openpyxl')
            
            print(f"\n{'='*60}")
            print(f"✅ 수집 완료!")
            print(f"{'='*60}")
            print(f"📁 파일: {out}")
            print(f"📊 갭투자 후보: {len(df)}개")
            
            if len(df) > 0:
                # 갭비율 상위 5개 미리보기
                top5 = df.nsmallest(5, '갭비율')[['매물명', '매매 금액(원)', '기전세금(원)', '갭금액(원)', '갭비율']]
                print(f"\n🎯 갭비율 TOP 5:")
                for idx, row in top5.iterrows():
                    gap_pct = row['갭비율'] * 100 if row['갭비율'] else 0
                    sale_m = row['매매 금액(원)'] / 100_000_000 if row['매매 금액(원)'] else 0
                    gap_m = row['갭금액(원)'] / 10_000_000 if row['갭금액(원)'] else 0
                    print(f"   {idx+1}. {row['매물명'][:20]:20s} | 매매 {sale_m:.1f}억 | 갭 {gap_m:.0f}백만 ({gap_pct:.1f}%)")
        else:
            print(f"\n⚠️  갭투자 조건({ONLY_PREV_GT_SALE=})을 만족하는 매물이 없습니다.")
            print(f"   설정을 변경하거나 다른 지역을 시도해보세요.")

        print("\n🔚 브라우저 종료 중...")
        await asyncio.sleep(0.5)
        await mctx.close()
        await browser.close()

def main():
    """
    프로그램 시작점
    
    사용자로부터 좌표와 줌 레벨을 입력받아 크롤링을 시작합니다.
    """
    print("=" * 60)
    print("🏘️  네이버 부동산 갭투자 스크래퍼")
    print("=" * 60)
    print("\n💡 좌표 찾는 법:")
    print("   1. https://map.naver.com 접속")
    print("   2. 원하는 지역 검색")
    print("   3. 마우스 우클릭 → 'URL 복사'")
    print("   4. URL에서 lat, lng 값 확인")

    lat = float(input("\n📍 위도 (기본: 37.5608): ").strip() or "37.5608")
    lon = float(input("📍 경도 (기본: 126.9888): ").strip() or "126.9888")
    zoom = int(input("🔍 줌 (기본: 15, 범위: 15-17): ").strip() or "15")

    print(f"\n{'='*60}")
    print(f"🚀 크롤링 시작")
    print(f"{'='*60}")
    print(f"📌 위치: 위도 {lat}, 경도 {lon}, 줌 {zoom}")
    print(f"🎯 설정: {ASSET_TYPES}, 워커 {DETAIL_WORKERS}개")
    print(f"💰 필터: 기전세금≥매매가 = {ONLY_PREV_GT_SALE}")
    print(f"{'='*60}\n")

    asyncio.run(crawl_detailed(lat, lon, zoom))

if __name__ == "__main__":
    main()
