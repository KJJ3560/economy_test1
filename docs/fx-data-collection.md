# 원화 대량 환전 신호 감지 — 데이터 수집 방법 및 도구 조사

세 가지 선행지표(① 현물환 거래량+매매기준율, ② NDF 포지션, ③ 스왑레이트)를
프로그램으로 수집하기 위한 데이터 소스·API·라이브러리 조사 결과.

## 요약: 신호별 수집 경로

| 신호 | 1차 소스 | 수집 방법 | 무료 여부 |
|---|---|---|---|
| 매매기준율 (일별) | 한국수출입은행 Open API | REST/JSON (`oapi.koreaexim.go.kr`) | 무료 (인증키) |
| 현물환 거래량 (일별) | 서울외국환중개 (smbs.biz) | HTML 스크레이핑 (JSP 페이지) | 무료 |
| 장중/새벽 역외 환율 | Yahoo Finance (`KRW=X`) | `yfinance` 1분봉 / `FinanceDataReader` 일봉 | 무료 |
| NDF 거래 규모 (월/분기) | 한국은행 보도자료 "외환시장 동향" | 게시판 목록 스크레이핑 + PDF/HWP 파싱 | 무료 |
| NDF 역외 포지션 분석 | 국제금융센터(KCIF) 리포트 | 사이트 스크레이핑 (일부 회원제) | 부분 무료 |
| 스왑레이트 (CRS/외환스왑) | 한국은행 ECOS Open API | REST/JSON (`ecos.bok.or.kr/api`) | 무료 (인증키) |
| 실시간 스왑포인트·NDF 호가 | 연합인포맥스, Bloomberg, LSEG | 유료 단말/피드 | 유료 |

## 1. 매매기준율 + 현물환 거래량

### 한국수출입은행 환율 Open API (매매기준율 — 가장 간단)
- 인증키: koreaexim.go.kr에서 본인 인증 후 즉시 발급. 공공데이터포털(data.go.kr, 데이터셋 15059631/3068846)에서도 신청 가능.
- 엔드포인트: `https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={KEY}&searchdate=YYYYMMDD&data=AP01`
- **주의**: 2025-06-25부로 도메인이 `www.koreaexim.go.kr` → `oapi.koreaexim.go.kr`로 변경됨. 구 도메인은 점진 종료 예정.
- 한계: 일별 매매기준율만 제공. **거래량 없음**, 장중 데이터 없음.

### 서울외국환중개 (smbs.biz / smbs.co.kr) — 거래량의 유일한 공개 소스
- 공식 API 없음. JSP 기반 서버 렌더링 페이지라 `requests` + `BeautifulSoup`로 스크레이핑 가능.
- 주요 페이지:
  - 매매기준율(MAR): `/ExRate/StdExRate.jsp` — USD·CNH 익영업일물 현물환 거래량 가중평균으로 산출
  - 오늘의 환율/30분 단위 고저: `/ExRate/TodayExRate*.jsp`
  - 모바일 페이지(`/mobile/business/inquiry_tab1.jsp`)가 구조가 단순해 파싱이 더 쉬움
- 거래량 급증 + 환율 하락(원화 강세) 조합을 일별로 계산하는 지표의 원천 데이터.

### 장중·새벽 역외 시간대 환율
- 2024-07 서울환시 거래시간 연장(새벽 2시까지) 이후 KRX 개장 전 새벽 시간대 흐름 관찰이 중요.
- `yfinance`의 `KRW=X` 티커로 1분봉 인트라데이 수집 가능 (역외 호가 반영, 사실상 24시간 근접).
- 일봉 수준이면 `FinanceDataReader`: `fdr.DataReader('USD/KRW')` 한 줄로 충분.

## 2. NDF (역외 차액결제선물환)

- **한국은행 보도자료**: 월간 "외환시장 동향", 분기 "외국환은행의 외환거래동향"에서 비거주자 NDF 순매수/순매도 규모 공표. bok.or.kr 게시판(예: 일일 금융외환시장 동향 `B0000348`, 외환당국 순거래 `B0000299`)은 목록이 정형화된 HTML이라 스크레이핑으로 신규 게시물 감지 → 첨부 PDF/HWP 다운로드 → 파싱(pdfplumber, hwp5txt) 파이프라인 구성 가능.
- **ECOS**: 외국환은행 외환거래 관련 통계 일부가 ECOS 통계표로도 제공되므로, 아래 ECOS API에서 "선물환", "NDF" 키워드로 통계표 코드를 먼저 검색해 보고 있으면 API가 PDF 파싱보다 훨씬 안정적.
- **국제금융센터(KCIF)**: kcif.or.kr 리포트에 역외 NDF 포지션 분석이 실리지만 상당수 회원제. 목록 페이지 모니터링 정도가 현실적.
- 한계: NDF 데이터는 발표 주기가 월/분기라 **후행성이 큼**. 실시간 NDF 호가는 유료 단말(인포맥스, Bloomberg) 영역.

## 3. 스왑레이트 (외환스왑 / CRS)

### 한국은행 ECOS Open API
- 인증키: ecos.bok.or.kr/api 회원가입 후 발급.
- 엔드포인트 형식:
  ```
  https://ecos.bok.or.kr/api/StatisticSearch/{인증키}/json/kr/{시작건수}/{종료건수}/{통계표코드}/{주기}/{시작일}/{종료일}/{항목코드}
  ```
- 통계표 코드 확인: `StatisticTableList` / `StatisticItemList` API 또는 ECOS 통계검색 화면에서 "스왑레이트", "외환스왑", "통화스왑" 키워드로 검색해 정확한 코드를 확정할 것 (코드가 개편되는 경우가 있어 하드코딩 전 확인 필수).
- 원/달러 매매기준율, 시장금리 등 다른 일별 시계열도 같은 API로 수집 가능 → 수집기 하나로 통합 가능.

### 파이썬 래퍼 라이브러리
- **PublicDataReader** (`pip install PublicDataReader`): ECOS·KOSIS·공공데이터포털 API를 감싼 라이브러리. 통계표 검색과 조회를 pandas DataFrame으로 반환.
- **FinanceDataReader** (`pip install finance-datareader`): 환율·주가·지수 시세 특화 (KRX, 야후, 네이버 소스).
- 그 외 ECOS 전용 경량 래퍼: `ecos_api_loader`, `ecos`(R) 등 오픈소스 존재.

### 실시간 스왑포인트
- 장중 스왑포인트·CRS 호가는 공개 API가 없음. 연합인포맥스, Bloomberg, LSEG(Refinitiv) 등 유료 단말/피드가 필요. 무료 범위에서는 ECOS의 일별 확정치가 최선.

## 4. 권장 수집 아키텍처

```
[스케줄러 (cron / GitHub Actions)]
 ├─ daily 09:30 KST: koreaexim API → 매매기준율
 ├─ daily 15:40 KST: smbs.biz 스크레이핑 → 현물환 거래량 + MAR
 ├─ intraday 10min:  yfinance KRW=X 1분봉 → 새벽 역외 흐름 포함
 ├─ daily:           ECOS API → 스왑레이트, 기타 시계열
 └─ daily:           BOK 보도자료 게시판 감지 → NDF PDF 파싱 (월/분기)
        ↓
 [저장: SQLite/Parquet] → [신호 계산: 거래량 z-score, 스왑레이트 변화율 등] → [알림]
```

## 5. 실행 환경 제약 (중요)

현재 Claude Code 원격 세션의 네트워크 정책은 `ecos.bok.or.kr`, `www.smbs.biz`,
`oapi.koreaexim.go.kr` 등 한국 금융 도메인으로의 아웃바운드 연결을 차단(403)한다.
이 리포지토리에서 수집기를 개발·테스트하려면:
1. 환경 설정에서 네트워크 정책에 해당 도메인을 허용 목록에 추가하거나,
2. 로컬 머신 또는 GitHub Actions에서 수집 스크립트를 실행해야 한다.

## 참고 자료

- 한국은행 Open API: https://ecos.bok.or.kr/api/
- ECOS 사용 가이드 (PublicDataReader): https://github.com/WooilJeong/PublicDataReader
- FinanceDataReader: https://github.com/financedata/financedatareader
- 한국수출입은행 환율 API (공공데이터포털): https://www.data.go.kr/data/3068846/openapi.do
- 서울외국환중개 환율산출 근거: http://www.smbs.biz/Company/Buss_3_4.jsp
- 한국은행 일일 금융외환시장 동향: https://www.bok.or.kr/portal/bbs/B0000348/list.do?menuNo=201109
- 한국은행 외환당국 순거래: https://www.bok.or.kr/portal/bbs/B0000299/list.do?menuNo=200994
- KCIF 국제금융센터: https://www.kcif.or.kr/
