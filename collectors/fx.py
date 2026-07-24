"""환율 수집기 — 정규화 컬럼: date, close[, volume].

소스 우선순위: FinanceDataReader(USD/KRW) → yfinance(KRW=X) → 로컬 CSV.
거래량(volume)은 smbs.biz 스크레이핑이 붙기 전까지는 없을 수 있다(NaN 허용).
"""

from __future__ import annotations

import sys

import pandas as pd


def collect(start: str = "2023-01-01", csv: str | None = None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv, parse_dates=["date"] if _has(csv, "date") else ["Date"])
        df = df.rename(columns={"Date": "date", "Close": "close", "Volume": "volume"})
        return _norm(df)

    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader("USD/KRW", start).reset_index()
        df = df.rename(columns={"Date": "date", "Close": "close"})
        if len(df):
            return _norm(df)
    except Exception as e:  # noqa: BLE001
        print(f"[fx] FinanceDataReader 실패: {e}", file=sys.stderr)

    try:
        import yfinance as yf

        raw = yf.download("KRW=X", start=start, progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw.reset_index().rename(columns={"Date": "date", "Close": "close"})
        if len(df):
            return _norm(df)
    except Exception as e:  # noqa: BLE001
        print(f"[fx] yfinance 실패: {e}", file=sys.stderr)

    print("[fx] 온라인 소스 실패 — --csv 폴백 필요", file=sys.stderr)
    return pd.DataFrame(columns=["date", "close", "volume"])


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "close"] + (["volume"] if "volume" in df.columns else [])
    out = df[cols].copy()
    out["date"] = pd.to_datetime(out["date"])
    if "volume" not in out.columns:
        out["volume"] = pd.NA
    return out[["date", "close", "volume"]].dropna(subset=["close"]).reset_index(drop=True)


def _has(path: str, col: str) -> bool:
    return col in pd.read_csv(path, nrows=0).columns
