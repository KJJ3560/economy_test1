---
name: kr-fx-signals
description: >-
  원/달러 대량 환전·원화 강세 선행 신호를 감지하기 위한 한국 외환·증시 데이터
  수집·분석 노하우. 현물환 거래량/매매기준율(smbs.biz), NDF 순매수 포지션(한국은행
  보도자료), 스왑레이트(ECOS API) 세 신호를 다룬다. "환율 데이터 수집", "원화 강세
  신호", "코스피/코스닥/환율 분석", "smbs.biz / ECOS / 수출입은행 API",
  "FinanceDataReader / yfinance", "USD/KRW z-score" 같은 요청에서 사용한다.
---

# 한국 외환·증시 신호 수집·분석 (kr-fx-signals)

대량 환전이 진행 중일 때 나타나는 **원화 강세 선행 신호**를 감지한다.
핵심 아이디어: *거래량 급증 + 환율 눌림(원화 강세)* 이 동시에 나타나고,
그것이 **KRX 개장 전 새벽 역외 시간대**에 먼저 붙으면 대량 환전 가능성이 크다.

## 0. 먼저 확인할 것 — 네트워크 제약

Claude Code 원격 세션의 네트워크 정책은 한국 금융 도메인(`ecos.bok.or.kr`,
`www.smbs.biz`, `oapi.koreaexim.go.kr`, `finance.yahoo.com`, `stooq`, `fred` 등)을
**403으로 차단**하는 경우가 많다. 실행 전에 반드시 도달성을 확인한다:

```bash
curl -sS "$HTTPS_PROXY/__agentproxy/status"   # recentRelayFailures 에 차단 이력이 보임
```

차단돼 있으면: (1) 환경 설정에서 해당 도메인을 허용 목록에 추가하도록 사용자에게
안내하거나, (2) 코드만 작성/검증하고 실제 수집은 로컬·GitHub Actions에서 돌리게
한다. **차단된 환경에서 "데이터를 못 구했다"로 끝내지 말고 오프라인 CSV 폴백으로
파이프라인을 E2E 검증**하라 (합성 fixture 사용).

## 1. 신호별 데이터 소스 — API 키 필요 여부

| 신호 | 소스 | 방법 | 키 |
|---|---|---|---|
| 현물환 **거래량** + 매매기준율(MAR) | 서울외국환중개 smbs.biz | JSP 페이지 스크레이핑 (`requests`+`BeautifulSoup`) | **불필요** |
| 새벽 역외 환율(장중) | Yahoo `KRW=X` | `yfinance` 1분봉 | **불필요** |
| 일봉 환율 | KRX/네이버/야후 | `FinanceDataReader` `fdr.DataReader('USD/KRW')` | **불필요** |
| 매매기준율(일별, 확정치) | 한국수출입은행 Open API | REST/JSON `oapi.koreaexim.go.kr` | 무료·즉시발급 |
| **NDF** 순매수 포지션 | 한국은행 "외환시장 동향" 보도자료 | 게시판 스크레이핑 + PDF 파싱 | **불필요**(월간·후행) |
| **스왑레이트**(CRS/외환스왑) | 한국은행 ECOS API | REST/JSON `ecos.bok.or.kr/api` | 무료·즉시발급 |
| 실시간 스왑포인트·NDF 호가 | 인포맥스/Bloomberg/LSEG | 유료 단말 | 유료 |

**키 없이 시작하는 최소 조합**: smbs.biz 거래량 z-score + yfinance 새벽 세션
원화 강세. 이 둘로 "거래량 급증 + 역외 선행 매수"를 매일 체크할 수 있다.
스왑레이트는 나중에 ECOS 키(발급 5분)로 보강한다.

## 2. 도구 선택 규칙

- **키가 필요 없는 경로를 항상 먼저** 시도: `FinanceDataReader` → `yfinance` → 로컬 CSV 폴백.
- 시세(주가·환율·지수)는 `FinanceDataReader`, 통계 시계열(스왑레이트 등)은 `PublicDataReader`(ECOS/KOSIS 래퍼).
- 인트라데이(새벽 역외)는 `yfinance` `KRW=X`, `interval="1m"`, `period="5d"` → `tz_convert("Asia/Seoul")`.

```bash
pip install finance-datareader yfinance pandas numpy matplotlib PublicDataReader
```

## 3. 신호 계산 규칙

- **거래량 z-score**: 20거래일 이동평균 대비. z ≥ +2 면 거래량 급증.
- **원화 강세 연속일수**: 환율(원/달러) 하락이 며칠 연속인지. 거래량 급증과 겹치면 경보.
- **수익률 z-score**: 일간 수익률의 20일 이동 z-score, |z| ≥ 1.5 이상신호 플래그.
- **세션 분리**: 새벽 역외(KST 00:00~09:00) vs 주간(09:00~15:30) 수익률을 나눠 비교.
  새벽에 원화 강세가 주간보다 먼저 나타나면 역외발 선행 매수 신호.
- 교차 검증: 환율 신호는 반드시 smbs.biz **거래량**과 함께 해석. 거래량 없는 환율
  하락은 신호로 치지 않는다.

## 4. 참조 구현

이 리포지토리의 `analysis/fx_analysis.py`가 위 규칙을 구현한 참조 파이프라인이다.
소스 폴백(FDR→yfinance→CSV), z-score 이상신호, 변동성, 원화 강세 연속일수,
새벽/주간 세션 비교, 리포트(md)+차트(png) 생성을 포함한다.

```bash
python analysis/fx_analysis.py --start 2024-01-01           # 온라인
python analysis/fx_analysis.py --csv path/to/usdkrw.csv     # 오프라인 폴백
```

새 수집기(smbs 스크레이퍼, ECOS 수집기 등)를 만들 때는 이 스크립트의
`fetch_daily()` 폴백 패턴과 리포트 형식을 재사용한다.

## 4-1. 외국인 수급 × 환율 결합 (pykrx / KOSIS)

환율 신호만으로는 "왜 원화가 강한가"를 구분하지 못한다. **외국인 주식 수급**과
**거시 통계**를 결합해 대량 환전 신호를 증권 자금 유입과 분리한다.

### 소스 (둘 다 MCP 서버 존재)
- **pykrx-mcp** (github.com/sharebook-kr/pykrx-mcp) — KRX 마이크로, 키 불필요.
  핵심 도구: `get_market_net_purchases_of_equities`(투자자별 순매수),
  `get_exhaustion_rates_of_foreign_investment`(외국인 소진율),
  `get_market_trading_value_by_investor`, 공매도(`get_shorting_*`), 지수 OHLCV.
  라이브러리로도 직접 호출 가능: `pip install pykrx`.
- **korea-stats-mcp** (github.com/Dayoooun/korea-stats-mcp) — KOSIS 매크로, 키 내장.
  원격 서버(`https://korea-stats-mcp-yxup.vercel.app/mcp`)라 서버가 대신 조회.
  경상수지·외환보유액 등 월/분기 통계로 환전 수요의 구조적 배경 확인.

### 교차 규칙 (핵심)
| 외국인 주식 | 원화 방향 + 거래량 | 해석 |
|---|---|---|
| 순매도 | 원화 강세 + 거래량 급증 | **★ 대량 환전 신호** — 증시 자금 이탈과 무관한 별도 원화 매수 수요 |
| 순매수 | 원화 강세 | 단순 증시 유입으로 설명됨 (환전 신호 약함) |
| 순매도 | 원화 약세 | 자금 이탈 + 원화 약세, 정합적 (특이신호 아님) |

즉 **외국인 주식 순매도인데 원화가 강세**인 괴리(divergence)가 나타날 때가
가장 강한 신호다. 두 소스가 있어야만 이 괴리를 판별할 수 있다.

### 결합 구현 방침
- 권장: MCP 체이닝 대신 **단일 오케스트레이터**(collectors/krx.py + kosis.py + fx.py
  → SQLite → signals.py)로 묶는다. 견고하고 백테스트가 쉽다.
- 이 세션(원격)은 **KRX 도메인 403 차단**이라 pykrx 실행 불가 → 로컬/GitHub Actions
  전제. korea-stats는 원격 Vercel 서버라 이 세션에서도 붙을 수 있음.
- Claude Code에서 MCP를 붙일 땐 `claude_desktop_config.json`이 아니라 프로젝트
  `.mcp.json` 또는 `claude mcp add`를 쓴다 (Claude Desktop 설정 파일은 무관).

## 5. 엔드포인트 참고

- 수출입은행: `https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={KEY}&searchdate=YYYYMMDD&data=AP01`
  (2025-06-25부로 `www.koreaexim.go.kr`→`oapi.koreaexim.go.kr` 도메인 변경. 거래량 없음, 매매기준율만.)
- ECOS: `https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/{start}/{end}/{표코드}/{주기}/{시작일}/{종료일}/{항목코드}`
  통계표 코드는 하드코딩 전 `StatisticTableList`로 "스왑레이트/외환스왑/통화스왑" 검색해 확정.
- smbs.biz: 매매기준율 `/ExRate/StdExRate.jsp`, 오늘 환율/30분 고저 `/ExRate/TodayExRate*.jsp`.
  모바일 페이지(`/mobile/business/inquiry_tab1.jsp`)가 구조 단순해 파싱 쉬움. 공식 API 없음.
- 한국은행 보도자료 게시판: 일일 금융외환시장 동향 `B0000348`, 외환당국 순거래 `B0000299`.

## 6. 흔한 함정

- ECOS 통계표 코드는 개편될 수 있음 → 매번 목록 API로 확인.
- yfinance 컬럼이 MultiIndex로 올 수 있음 → `get_level_values(0)`로 평탄화.
- NDF는 발표 주기가 월/분기라 실시간 감지엔 부적합. 사후 검증·백테스트용으로만.
- 실시간 스왑포인트는 무료 API 없음. 무료 범위에선 ECOS 일별 확정치가 최선.
