"""외국인 주식 수급 수집기 (pykrx) — 정규화 컬럼: date, foreign_net.

foreign_net = 외국인 순매수 금액(원). 양수면 외국인 주식 순매수.
pykrx 는 KRX 에서 데이터를 받으므로 KRX 도메인이 차단된 환경(원격 세션)에서는
실패한다 → 로컬/GitHub Actions 전제. 실패 시 --csv 폴백.

NOTE: 아래 pykrx 호출부는 네트워크가 열린 환경에서 pykrx 버전에 맞춰
반드시 검증할 것(함수명·반환 컬럼이 버전에 따라 다름). 여기서는 실패해도
파이프라인이 죽지 않도록 try 로 감싸고 폴백한다.
"""

from __future__ import annotations

import sys

import pandas as pd


def collect(
    start: str = "2023-01-01",
    end: str | None = None,
    market: str = "KOSPI",
    csv: str | None = None,
) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv, parse_dates=["date"])
        return _norm(df)

    try:
        from pykrx import stock

        end = end or pd.Timestamp.today().strftime("%Y%m%d")
        s = pd.to_datetime(start).strftime("%Y%m%d")
        # 일자별 투자자 거래대금 → 외국인 순매수 시계열.
        # (버전에 따라 get_market_trading_value_by_date 등으로 대체 필요)
        rows = []
        for d in pd.bdate_range(s, end):
            ds = d.strftime("%Y%m%d")
            try:
                t = stock.get_market_trading_value_by_investor(ds, ds, market)
                if t is not None and "외국인" in t.index:
                    rows.append({"date": d, "foreign_net": float(t.loc["외국인", "순매수"])})
            except Exception:  # noqa: BLE001 - 개별 일자 실패는 건너뜀
                continue
        if rows:
            return _norm(pd.DataFrame(rows))
    except Exception as e:  # noqa: BLE001
        print(f"[krx] pykrx 실패(폴백 필요): {e}", file=sys.stderr)

    return pd.DataFrame(columns=["date", "foreign_net"])


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["date", "foreign_net"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    return out.dropna().sort_values("date").reset_index(drop=True)
