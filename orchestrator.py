"""통합 오케스트레이터: 수집 → SQLite 적재 → 교차 신호 → 리포트.

세 소스(fx, krx, kosis)를 각각 수집해 SQLite 에 쌓고, signals.compute 로
외국인 수급 × 환율 괴리 신호를 계산해 마크다운 리포트를 생성한다.

각 소스는 온라인 실패 시 --*-csv 로 오프라인 폴백한다. 네트워크가 차단된
환경(KRX 403 등)에서도 CSV 만 있으면 파이프라인 전체가 E2E 로 돈다.

사용 예(오프라인):
  python orchestrator.py \
    --fx-csv data/fx.csv --krx-csv data/flows.csv --out reports

사용 예(온라인):
  python orchestrator.py --start 2024-01-01 --out reports
"""

from __future__ import annotations

import argparse
from pathlib import Path

from collectors import fx, kosis, krx, store
import signals


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--fx-csv")
    p.add_argument("--krx-csv")
    p.add_argument("--kosis-csv")
    p.add_argument("--db", default="reports/market.sqlite")
    p.add_argument("--out", default="reports")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    fx_df = fx.collect(args.start, args.fx_csv)
    krx_df = krx.collect(args.start, csv=args.krx_csv)
    kosis_df = kosis.collect(args.kosis_csv)

    conn = store.connect(args.db)
    n_fx = store.upsert(conn, "fx", fx_df)
    n_krx = store.upsert(conn, "foreign_flows", krx_df)
    n_kosis = store.upsert(conn, "macro", kosis_df)
    conn.close()
    print(f"적재: fx={n_fx}, foreign_flows={n_krx}, macro={n_kosis}")

    sig = signals.compute(fx_df, krx_df)
    report = out_dir / "signal_report.md"
    report.write_text(
        "# 외국인 수급 × 환율 교차 신호 리포트\n\n"
        + signals.summarize(sig)
        + "\n\n## 최근 신호 상세\n\n"
        + _table(sig)
        + "\n",
        encoding="utf-8",
    )
    print(f"리포트: {report}")


def _table(sig, n: int = 15) -> str:
    if sig.empty:
        return "_데이터 없음_"
    rows = sig.tail(n)
    head = "| 날짜 | 종가 | 수익률 | 원화강세 | 외국인순매수 | 괴리 | ★신호 |"
    sep = "|---|---|---|---|---|---|---|"
    body = [
        f"| {d.date()} | {r.close:,.2f} | {r.ret * 100:+.2f}% "
        f"| {'Y' if r.krw_strength else '-'} | {r.foreign_net:,.0f} "
        f"| {'Y' if r.divergence else '-'} | {'★' if r.signal else '-'} |"
        for d, r in rows.iterrows()
    ]
    return "\n".join([head, sep, *body])


if __name__ == "__main__":
    main()
