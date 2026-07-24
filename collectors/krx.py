"""외국인 주식 수급 수집기 (pykrx) — 정규화 컬럼: date, foreign_net.

foreign_net = 외국인 순매수 금액(원). 양수면 외국인 주식 순매수.
pykrx 는 KRX 에서 데이터를 받으므로 KRX 도메인이 차단된 환경(원격 세션)에서는
실패한다 → 로컬/GitHub Actions 전제. 실패 시 --csv 폴백.

pykrx API (설치본 기준 검증):
  get_market_trading_value_by_date(fromdate, todate, ticker, on='순매수', freq='d')
    → 날짜 인덱스, 투자자별 컬럼(… 개인, 외국인, 전체 …). ticker 에 'KOSPI'/'KOSDAQ'
      시장명을 넣으면 시장 전체 집계. 한 번 호출로 시계열을 받는다.
  (폴백) get_market_trading_value_by_investor(fromdate, todate, ticker)
    → 투자자 인덱스, 매도/매수/순매수 컬럼. 단일 기간 집계라 일자별 루프 필요.
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

        s = pd.to_datetime(start).strftime("%Y%m%d")
        e = (pd.to_datetime(end) if end else pd.Timestamp.today()).strftime("%Y%m%d")

        # 1) 시계열 한 방 호출 (권장)
        raw = stock.get_market_trading_value_by_date(s, e, market, on="순매수")
        df = _from_by_date(raw)
        if df is not None and len(df):
            return _norm(df)

        # 2) 폴백: 일자별 투자자 집계 루프
        rows = []
        for d in pd.bdate_range(s, e):
            ds = d.strftime("%Y%m%d")
            try:
                t = stock.get_market_trading_value_by_investor(ds, ds, market)
                col = _pick_foreign_row(t)
                if col is not None:
                    rows.append({"date": d, "foreign_net": col})
            except Exception:  # noqa: BLE001 - 개별 일자 실패는 건너뜀
                continue
        if rows:
            return _norm(pd.DataFrame(rows))
    except Exception as ex:  # noqa: BLE001
        print(f"[krx] pykrx 실패(폴백 필요): {ex}", file=sys.stderr)

    return pd.DataFrame(columns=["date", "foreign_net"])


def _from_by_date(raw: pd.DataFrame) -> pd.DataFrame | None:
    """get_market_trading_value_by_date 결과 → date/foreign_net."""
    if raw is None or raw.empty:
        return None
    col = _foreign_col(raw.columns)
    if col is None:
        return None
    out = raw[[col]].copy()
    out.index.name = "date"
    out = out.reset_index().rename(columns={col: "foreign_net"})
    return out


def _foreign_col(cols) -> str | None:
    """투자자 컬럼 중 '외국인'(기타외국인 제외)을 고른다."""
    cols = list(cols)
    if "외국인" in cols:
        return "외국인"
    cand = [c for c in cols if "외국인" in str(c) and "기타" not in str(c)]
    return cand[0] if cand else None


def _pick_foreign_row(t: pd.DataFrame):
    """get_market_trading_value_by_investor 결과에서 외국인 순매수 값."""
    if t is None or t.empty:
        return None
    idx = _foreign_col(t.index)
    if idx is None or "순매수" not in t.columns:
        return None
    return float(t.loc[idx, "순매수"])


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["date", "foreign_net"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["foreign_net"] = pd.to_numeric(out["foreign_net"], errors="coerce")
    return out.dropna().sort_values("date").reset_index(drop=True)
