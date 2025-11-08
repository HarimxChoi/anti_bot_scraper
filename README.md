# 네이버 부동산 스크래퍼 🏘️

네이버 부동산 플랫폼에서 매물 정보를 자동으로 수집하는 고급 웹 스크래핑 시스템입니다.
Anti-bot 우회 기술과 갭투자 분석 기능이 포함되어 있습니다.

> **English**: Advanced web scraper for Korean real estate platform (Naver Land) with anti-bot detection and gap investment analysis. Designed for Korean property market research and investment opportunities. [English documentation →](#english-documentation)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Latest-green.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎬 데모

<div align="center">
  <img src="demo.gif" alt="네이버 부동산 스크래퍼 실행 데모" width="800">
</div>

---

## 📋 목차

- [주요 기능](#🎯-주요-기능)
- [설치 방법](#설치-방법)
- [사용법](#사용법)
- [설정 상세 설명](#설정-상세-설명)
- [출력 결과](#출력-결과)
- [기술 상세](#기술-상세)
- [갭투자 분석](#갭투자-분석)
- [주의사항](#주의사항)
- [English Documentation](#english-documentation)

---

## 🎯 주요 기능

### 🛡️ Anti-Bot 우회 기술

이 스크래퍼가 네이버의 봇 탐지를 우회하는 핵심 기술들:

- **사람처럼 움직이는 맵 네비게이션**: 랜덤 줌 레벨, 자연스러운 드래그 동작
- **마우스 이동 시뮬레이션**: 20단계로 부드럽게 이동하여 봇 티 안 남
- **그리드 스윕 알고리즘**: 체계적이지만 패턴이 명확하지 않은 수집 방식
- **리소스 차단 최적화**: 이미지/폰트 차단으로 빠른 로딩 + 실제 브라우저처럼 보임

최근 네이버 업데이트로 대부분의 스크래퍼가 차단되어 네이버 부동산 스크래퍼를 교육 목적으로 개발하였습니다.

### 📊 데이터 수집

- **아파트(APT)** 및 **빌라/연립/다세대(VL)** 매물 정보
- 중개사 상호, 이름, 연락처 (전화 2개까지)
- 과거 전세가 분석 (최근 몇 년간 최고가/최저가)
- 매물 상세 정보 (층수, 면적, 방향, 특징)
- 실시간 등록 매물

### 💰 갭투자 분석

**핵심 기능**: 기전세금이 매매가보다 높거나 비슷한 매물 자동 필터링
```
갭금액 = 매매가 - 기전세금
갭비율 = 갭금액 / 매매가

예시: 매매 3억, 기전세 2.9억 → 갭 1,000만원 (3.3%)
```

### ⚡ 고성능 처리

- **12개 동시 워커**: 병렬로 매물 상세 정보 수집
- **1회 실행당 10,000+ 매물** 수집 가능
- **지리적 그리드 기반 수집**: 누락 없이 체계적으로 수집
- **비동기 처리**: Python asyncio 기반 고속 처리

---

## 🚀 설치 방법

### 1. 필수 요구사항

- Python 3.9 이상
- 안정적인 인터넷 연결
- 최소 2GB RAM (12 워커 사용 시)

### 2. 의존성 설치
```bash
# 패키지 설치
pip install playwright pandas openpyxl

# Playwright 브라우저 설치
playwright install chromium
```

### 3. 코드 다운로드
```bash
git clone https://github.com/HarimxChoi/naver-estate-scraper.git
cd naver-estate-scraper
```

---

## 💻 사용법

### 기본 사용
```bash
python realEstate.py
```

실행하면 다음 정보를 입력하라고 나옵니다:
```
위도 (기본: 37.5608): 37.5608
경도 (기본: 126.9888): 126.9888
줌 (기본: 14): 14
```

**좌표 찾는 법**:
1. [네이버 지도](https://map.naver.com) 접속
2. 원하는 지역 검색
3. 마우스 우클릭 → "이 장소의 URL 복사"
4. URL에서 `?lng=126.9888&lat=37.5608` 부분 확인

### 실행 예시

**강남역 주변 수집**:
```
위도: 37.4979
경도: 127.0276
줌: 15
```

**여의도 주변 수집**:
```
위도: 37.5219
경도: 126.9245
줌: 16
```

### 실행 과정
```
1. 🌐 네이버 부동산 맵 접속
2. ⏳ 사람처럼 맵 중심 이동
3. 📍 그리드 패턴으로 주변 스윕
4. 📋 단지 정보 수집 (수백~수천 개)
5. 🎯 매물이 많은 단지 우선 방문
6. 📄 각 매물의 상세 정보 수집 (12개 동시)
7. 💾 엑셀 파일로 저장
```

실행 시간: 줌 레벨과 지역에 따라 **1분~7분**

---

## ⚙️ 설정 상세 설명

코드 상단의 설정값들을 수정하여 동작을 커스터마이징할 수 있습니다.

### 지리적 범위 설정
```python
KOR_BOUNDS = (33.0, 39.5, 124.0, 132.1)
# (최소위도, 최대위도, 최소경도, 최대경도)
```

**설명**: 한국 영토 범위를 정의합니다. 스크래퍼가 이 범위를 벗어나지 않도록 제한합니다.
- 제주도 포함: 33.0 (최남단)
- 강원도 북부: 39.5 (최북단)
- 서해안: 124.0 (최서단)
- 동해안: 132.1 (최동단)

**수정 필요**: 없음 (한국 전역 포함)

---

### 수집 규모 설정
```python
MAX_COMPLEX_DETAIL = 800
```

**설명**: 단지 상세 페이지에 진입할 최대 단지 개수입니다.
- 단지당 상세 정보 수집에 1초 미만 소요
- 800개 = 약 10분 소요

**추천값**:
- 빠른 테스트: `100`
- 일반 수집: `500-800`
- 전체 수집: `2000+` (시간 오래 걸림)
```python
MAX_ARTICLE_DETAIL = 10000
```

**설명**: 상세 페이지를 파싱할 매물의 최대 개수입니다.
- 매물당 처리 시간: 1-3초 (12 워커 사용 시)
- 10,000개 = 약 4~6분 소요

**추천값**:
- 테스트: `100`
- 소규모 지역: `1000-3000`
- 대규모 지역: `10000+`

---

### 필터링 설정
```python
ONLY_WITH_PREV_JEONSE = True
```

**설명**: `True`로 설정 시, 과거 전세 기록이 있는 매물만 수집합니다.
- 갭투자 분석을 위해서는 과거 전세가 필요
- `False`: 모든 매물 수집 (더 많지만 분석 불가능한 것 포함)

```python
ONLY_PREV_GT_SALE = True
```

**설명**: `True`로 설정 시, **기전세금 ≥ 매매가**인 매물만 최종 결과에 포함합니다.
- 갭투자 후보만 선별
- 결과 파일이 훨씬 작아짐 (수만 건 → 수십~수백 건)

**추천**:
- 갭투자 목적: `True`
- 전체 시장 조사: `False`

```python
MIN_LISTING_COUNT = 2
```

**설명**: 단지별 최소 매물 개수입니다. 이 값 미만인 단지는 우선순위가 낮아집니다.
- `2`: 매물 2개 이상인 단지만 우선 처리
- 매물 많은 단지 = 더 활발한 거래, 더 많은 정보

```python
PRIORITIZE_BY_COUNT = False
```

**설명**: `True`로 설정 시, 매물이 많은 단지부터 우선 방문합니다.

---

### 성능 설정
```python
DETAIL_WORKERS = 12
```

**설명**: 매물 상세 정보를 동시에 수집하는 브라우저 탭 개수입니다.
- 각 워커는 독립적인 브라우저 탭
- 많을수록 빠르지만 메모리/네트워크 부담

**추천값**:
- 느린 네트워크/저사양: `4-6`
- 일반 환경: `8-12`
- 고사양: `16-20`

⚠️ **주의**: 너무 많으면 IP 차단 위험 증가
```python
BLOCK_HEAVY_RESOURCES = True
```

**설명**: 이미지, 폰트, 미디어 등 무거운 리소스를 차단합니다.
- `True`: 2-3배 빠른 로딩, 네트워크 대역폭 절약
- `False`: 모든 리소스 로드 (느리지만 실제 브라우저와 동일)

**추천**: `True` (성능상 이점이 크고 봇 탐지에도 문제없음)

---

### 수집 전략 설정
```python
GRID_RINGS = 1
```

**설명**: 중심 좌표를 기준으로 몇 개의 바깥 고리를 스윕할지 결정합니다.
- `RINGS=1`: 중심 주변 8-12개 지점 방문
- `RINGS=2`: 중심 주변 24-32개 지점 방문
- 링이 많을수록 넓은 지역 커버, 시간 증가

**추천값**:
- 좁은 지역 (구 단위): `1`
- 넓은 지역 (시 단위): `2-3`
```python
GRID_STEP_PX = 480
```

**설명**: 그리드 스윕 시 각 지점 간 간격(픽셀 단위)입니다.
- 작을수록 촘촘하게, 많은 지점 방문
- 클수록 성글게, 빠르지만 누락 가능

**추천값**:
- 정밀한 탐색: `360-400`
- 일반: `480-520`
- 빠른 탐색: `600+`
```python
SWEEP_DWELL = 0.6
```

**설명**: 각 그리드 지점에서 머무르는 시간(초)입니다.
- 이 시간 동안 API 응답 수집
- 너무 짧으면 응답 놓칠 수 있음
- 너무 길면 시간 낭비

**추천값**: `0.5-0.8` (테스트 결과 최적값)

---

### 줌 레벨 설정
```python
ZOOM_MIN, ZOOM_MAX = 15, 17
```

**설명**: 허용하는 줌 레벨 범위입니다.
- 줌 레벨이 높을수록 = 더 확대 = 상세 정보 많음
- 줌 15: 구 단위 view
- 줌 17: 동네 단위 view

---

### 자산 유형 설정
```python
ASSET_TYPES = "APT:VL"
```

**설명**: 수집할 부동산 유형을 지정합니다.

**옵션**:
- `"APT"`: 아파트만
- `"VL"`: 빌라/연립/다세대만
- `"APT:VL"`: 둘 다 수집

**API 엔드포인트**:
- `APT` → `/complexes` 엔드포인트
- `VL` → `/houses` 엔드포인트

**추천**:
- 아파트 투자: `"APT"`
- 빌라 투자: `"VL"`
- 전체 시장: `"APT:VL"`

---

### 모바일 페이지 사용
```python
USE_MOBILE_DETAIL = True
```

**설명**: 매물 상세 정보를 가져올 때 모바일 페이지를 사용할지 여부입니다.
- `True`: `m.land.naver.com` 사용 (더 가볍고 빠름)
- `False`: 데스크톱 페이지 사용

**추천**: `True` (모바일이 더 안정적)

---

### 설정 예시

#### 예시 1: 빠른 테스트
```python
MAX_COMPLEX_DETAIL = 50
MAX_ARTICLE_DETAIL = 100
DETAIL_WORKERS = 8
GRID_RINGS = 1
ONLY_PREV_GT_SALE = True
```

#### 예시 2: 표준 수집
```python
MAX_COMPLEX_DETAIL = 500
MAX_ARTICLE_DETAIL = 5000
DETAIL_WORKERS = 12
GRID_RINGS = 1
ONLY_PREV_GT_SALE = True
```

#### 예시 3: 전체 수집
```python
MAX_COMPLEX_DETAIL = 2000
MAX_ARTICLE_DETAIL = 20000
DETAIL_WORKERS = 16
GRID_RINGS = 2
ONLY_PREV_GT_SALE = False  # 모든 매물
```

---

## 📊 출력 결과

### 엑셀 파일

실행이 완료되면 `매물정보_확장_YYYYMMDD_HHMMSS.xlsx` 파일이 생성됩니다.

### 컬럼 설명

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| 매물명 | 아파트/빌라 이름 | 래미안강남힐스테이트 |
| 매물번호 | 네이버 매물 고유 번호 | 2444012345 |
| 거래유형 | 매매/전세/월세 | 매매 |
| 매매 금액(원) | 매매가 (원 단위) | 380000000 |
| 층수 | 층 정보 | 15/25 |
| 면적(㎡) | 공급면적 | 84.93 |
| 전용면적 | 전용면적 | 59.92 |
| 방향 | 향 | 남동 |
| 특징 | 매물 특징 | 풀옵션, 역세권 |
| 등록일 | 매물 등록일 | 20240115 |
| **부동산상호** | 중개사 상호 | 강남부동산 |
| **중개사이름** | 중개사 이름 | 홍길동 |
| **전화1** | 중개사 연락처 1 | 02-1234-5678 |
| **전화2** | 중개사 연락처 2 | 010-1234-5678 |
| **전세_기간(년)** | 전세 데이터 기간 | 3 |
| **전세_기간내_최고(원)** | 기간 내 최고 전세가 | 350000000 |
| **전세_기간내_최저(원)** | 기간 내 최저 전세가 | 320000000 |
| **기전세금(원)** | 직전 전세가 | 340000000 |
| **갭금액(원)** | 매매가 - 기전세금 | 40000000 |
| **갭비율** | 갭금액 / 매매가 | 0.1053 (10.53%) |

### 결과 예시
```
매물명: 래미안강남힐스테이트
매매 금액: 380,000,000원 (3억 8천만원)
기전세금: 340,000,000원 (3억 4천만원)
갭금액: 40,000,000원 (4천만원)
갭비율: 10.53%

→ 전세를 3.4억에 놓고, 본인 돈 4천만원으로 구매 가능!
```

---

## 🔧 기술 상세

### Anti-Bot 우회 메커니즘

#### 1. 인간형 맵 네비게이션
```python
async def human_like_recenter(page, lat, lon, zoom):
    rand_out = random.randint(9, 12)  # 랜덤 줌 아웃
    await wheel_to_zoom(page, rand_out)
    await drag_to_latlon(page, lat, lon)
    await wheel_to_zoom(page, zoom)
    await drag_to_latlon(page, lat, lon)
```

**전략**: 목표 위치로 바로 가지 않고, 줌 아웃 → 이동 → 줌 인 → 미세조정 순서로 사람처럼 행동

#### 2. 마우스 이동 시뮬레이션
```python
await page.mouse.move(960 - mx, 540 - my, steps=20)
```

**전략**: 한 번에 점프하지 않고 20단계로 부드럽게 이동 (베지어 곡선)

#### 3. 그리드 스윕 알고리즘
```python
# 상·하(Top/Bottom) 행만 스캔
for r in range(1, rings + 1):
    for dx in range(-r, r + 1):
        for dy in (-r, r):  # Top, bottom rows only
```

**전략**: 전체 그리드를 순서대로 방문하지 않고, 위/아래 행만 스캔하여 패턴 숨김

#### 4. 변칙적 타이밍
```python
await asyncio.sleep(0.6)  # 고정값 아님, 코드 여러 곳에 분산
```

**전략**: 각 동작 사이에 자연스러운 딜레이 추가

---

### 지리 알고리즘

#### Mercator Projection (메르카토르 투영법)
```python
def ll_to_pixel(lat: float, lon: float, z: float):
    scale = 256 * (2 ** z)
    x = (lon + 180.0) / 360.0 * scale
    siny = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y
```

**설명**: 위도/경도를 픽셀 좌표로 변환하여 정확한 맵 드래그 제어

**역변환**:
```python
def pixel_to_ll(x: float, y: float, z: float):
    scale = 256 * (2 ** z)
    lon = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lon
```

### 동시 처리 아키텍처
```python
# 12개 워커 풀 생성
page_q = asyncio.Queue()
for _ in range(DETAIL_WORKERS):
    dp = await mctx.new_page()
    await page_q.put(dp)

# 작업 분배
tasks = [asyncio.create_task(fetch_one(a)) for a in article_list]

# 탭 재사용
dp = await page_q.get()  # 탭 할당
try:
    result = await scrape_article_detail(dp, article_no)
finally:
    await page_q.put(dp)  # 탭 반환
```

**장점**: 
- 탭 재사용으로 메모리 효율적
- 동시 처리로 10,000 매물을 15-30분 내 처리

## 🚀 프로덕션 배포 문의

이 코드는 **교육 및 연구 목적의 참고 구현**입니다.

### 문의 방법

📧 **이메일**: 2.harimchoi@gmail.com

---

## ⚠️ 주의사항 및 법적 고지

### 법적 준수사항

이 도구는 **교육 및 연구 목적**으로 제작되었습니다.

사용 시 반드시 다음 사항을 준수해주세요:

#### 1. 네이버 이용약관 준수

- [네이버 이용약관](https://policy.naver.com/rules/service.html) 숙지 필수
- 과도한 요청으로 서버에 부담을 주지 마세요
- 적절한 딜레이 설정 (현재 코드는 안전한 수준으로 설정됨)

#### 2. 개인정보 보호

- 수집한 중개사 연락처는 **본인의 부동산 거래 목적으로만** 사용
- 제3자에게 판매하거나 스팸 발송 금지
- 개인정보보호법 준수

#### 3. 데이터 사용 제한

- 수집한 데이터의 **상업적 재판매 금지**
- 네이버와 경쟁하는 서비스 제공 금지
- 데이터 출처 명시 권장

#### 4. 책임의 한계

- 사용자의 부적절한 사용으로 발생하는 법적 문제는 사용자 책임
- 네이버 플랫폼 변경으로 코드가 작동하지 않을 수 있음
- 수집된 데이터의 정확성을 보장하지 않음

### 윤리적 사용 가이드

✅ **권장되는 사용**:
- 개인 투자 목적의 시장 조사
- 학술 연구 및 데이터 분석
- 자신의 매물 가격 분석

❌ **금지되는 사용**:
- 대량 스팸 발송
- 개인정보 불법 수집 및 판매
- 네이버와 경쟁하는 부동산 플랫폼 구축
- 서버에 과부하를 주는 공격적 크롤링

### 기술적 제한사항

- 네이버는 언제든지 플랫폼 구조를 변경할 수 있습니다
- IP 차단 위험이 있으니 적절한 간격으로 실행하세요
- 공용 IP에서 여러 명이 동시 실행 시 차단 위험

### 업데이트 정책

- 이 코드는 2025년 10월 기준으로 작성되었습니다
- 네이버 플랫폼 변경 시 업데이트가 필요할 수 있습니다
- Star를 눌러주시면 업데이트 소식을 받을 수 있습니다

---

### Star & Update

이 프로젝트가 도움이 되셨다면:
- ⭐ **Star**를 눌러주세요

---

## 📄 라이선스

MIT License

Copyright (c) 2024  Harim Choi

자유롭게 사용, 수정, 배포 가능합니다. 단, 원저작자 표시를 유지해주세요.


## English Documentation

### Overview

Advanced web scraper for **Naver Land** (Korean real estate platform) with sophisticated anti-bot detection techniques.

### Key Features

🛡️ **Anti-Bot Technology**
- Human-like map navigation with randomized patterns
- Mouse movement simulation
- Grid sweep algorithm
- Resource blocking optimization

💰 **Gap Investment Analysis**
- Automatically finds properties where: `Previous Jeonse ≥ Sale Price`
- Calculates gap amount and ratio
- Filters investment opportunities

⚡ **High Performance**
- 12 concurrent workers
- 10,000+ listings per run
- Async/await architecture
- Geographic grid-based collection

### Technical Highlights

**Geographic Algorithm (Mercator Projection)**:
```python
def ll_to_pixel(lat: float, lon: float, z: float):
    scale = 256 * (2 ** z)
    x = (lon + 180.0) / 360.0 * scale
    siny = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y
```

**Concurrent Processing**:
```python
# 12 browser tabs working in parallel
DETAIL_WORKERS = 12
tasks = [asyncio.create_task(fetch_one(a)) for a in articles]
```

### Installation
```bash
pip install playwright pandas openpyxl
playwright install chromium
python realEstateTest2.py
```

### Configuration

See detailed configuration section above (Korean) for all settings.

Key settings:
- `DETAIL_WORKERS = 12` - Concurrent browser tabs
- `MAX_ARTICLE_DETAIL = 10000` - Maximum listings to collect
- `ONLY_PREV_GT_SALE = True` - Filter for gap investment opportunities
- `ASSET_TYPES = "APT:VL"` - Apartment and Villa/Townhouse

### Output

Generates Excel file: `매물정보_확장_YYYYMMDD_HHMMSS.xlsx`

Columns include:
- Property details (name, floor, size, direction)
- Sale price and previous jeonse price
- Broker information (name, phone numbers)
- **Gap analysis** (amount and ratio)
- Registration date

### Why This Project?

Demonstrates:
- ✅ Advanced anti-bot techniques that actually work
- ✅ Korean market domain expertise (jeonse, gap investment)
- ✅ Production-grade async architecture
- ✅ Geographic algorithms (Mercator projection)
- ✅ Concurrent processing optimization

Perfect for:
- Korean real estate market research
- Investment opportunity identification
- Demonstrating web scraping expertise
- Anti-detection technique portfolio

### Legal Notice

For educational and research purposes only. Users must comply with:
- Naver Terms of Service
- Korean web scraping regulations
- Personal information protection laws
- Ethical data collection practices

### Author

**Harim Choi** - AI/ML Engineer specializing in web automation and Korean market data systems

- 📧 Email: 2.harim.choi@gmail.com
- 💼 LinkedIn: [linkedin.com/in/choi-harim-266799361](https://linkedin.com/in/choi-harim-266799361)
- 💻 GitHub: [github.com/HarimxChoi](https://github.com/HarimxChoi)

### License

MIT License - Free to use, modify, and distribute with attribution.

---

**⭐ If this project helps you, please star it!**

