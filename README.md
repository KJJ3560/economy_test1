# economy_test1

원화 대량 환전 신호 감지를 위한 데이터 수집·분석 실험 리포지토리.

## 구성

- `docs/fx-data-collection.md` — 신호별(현물환 거래량·매매기준율 / NDF / 스왑레이트) 데이터 소스·API·도구 조사
- `analysis/fx_analysis.py` — API 키 없이 동작하는 USD/KRW 분석 파이프라인
- `collectors/` + `signals.py` + `orchestrator.py` — 환율·외국인수급·거시를 SQLite로 모아
  **외국인 순매도 × 원화 강세 괴리**를 대량 환전 신호로 계산하는 통합 파이프라인
- `.claude/skills/kr-fx-signals/` — 위 노하우를 담은 Agent Skill

## 통합 오케스트레이터

세 소스(fx / krx 외국인수급 / kosis 거시)를 수집→SQLite→교차 신호→리포트로 묶는다.
각 수집기는 온라인 실패 시 `--*-csv` 오프라인 폴백을 지원해 KRX가 차단된 환경에서도
CSV만 있으면 전체가 E2E로 돈다.

```bash
python orchestrator.py --start 2024-01-01                          # 온라인
python orchestrator.py --fx-csv fx.csv --krx-csv flows.csv         # 오프라인
```

핵심 신호(★): *외국인 주식 순매도 + 원화 강세 + 거래량 급증* — 증시 자금 이탈과
무관한 별도 원화 매수 수요(대량 환전) 가능성. 자세한 규칙은 `signals.py` 및
`.claude/skills/kr-fx-signals/SKILL.md`의 4-1 참조.

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
