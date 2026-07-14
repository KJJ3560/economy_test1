# economy_test1

원화 대량 환전 신호 감지를 위한 데이터 수집·분석 실험 리포지토리.

## 구성

- `docs/fx-data-collection.md` — 신호별(현물환 거래량·매매기준율 / NDF / 스왑레이트) 데이터 소스·API·도구 조사
- `analysis/fx_analysis.py` — API 키 없이 동작하는 USD/KRW 분석 파이프라인

## 빠른 시작 (API 키 불필요)

```bash
pip install -r analysis/requirements.txt
python analysis/fx_analysis.py --start 2024-01-01
```

`reports/fx_report.md` 와 `reports/fx_chart.png` 가 생성된다.

- 데이터: FinanceDataReader(USD/KRW) → 실패 시 yfinance(KRW=X) → `--csv` 로컬 파일 순서로 폴백
- 분석: 일간 수익률 20일 이동 z-score 이상 신호, 연환산 변동성, 원화 강세 연속일수,
  새벽 역외(00~09시 KST) vs 주간 세션 수익률 비교(인트라데이 수집 가능 시)

네트워크가 차단된 환경에서는 일봉 CSV(`Date,Close`)를 준비해 실행:

```bash
python analysis/fx_analysis.py --csv path/to/usdkrw.csv
```
