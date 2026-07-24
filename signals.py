"""교차 신호 계산 — 외국인 수급 × 환율 괴리(divergence).

핵심 규칙(SKILL.md 4-1):
  외국인 주식 순매도 + 원화 강세 + 거래량 급증 → ★ 대량 환전 신호.
  두 소스(fx, krx)가 있어야만 판별되는 괴리다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Z_WINDOW = 20
VOL_Z_FLAG = 2.0        # 거래량 급증 임계(있을 때만)
KRW_STRENGTH_DAYS = 1   # 원화 강세(환율 하락) 최소 연속일


def compute(fx: pd.DataFrame, flows: pd.DataFrame) -> pd.DataFrame:
    """fx(date,close[,volume]) 와 flows(date,foreign_net) 를 병합해 신호 산출."""
    if fx.empty or flows.empty:
        return pd.DataFrame()

    f = fx.set_index("date").sort_index()
    f["ret"] = f["close"].pct_change()
    f["krw_strength"] = f["ret"] < 0          # 환율 하락 = 원화 강세
    if f["volume"].notna().any():
        v = f["volume"].astype(float)
        f["vol_z"] = (v - v.rolling(Z_WINDOW).mean()) / v.rolling(Z_WINDOW).std()
    else:
        f["vol_z"] = np.nan

    g = flows.set_index("date").sort_index()
    m = f.join(g, how="inner")
    if m.empty:
        return pd.DataFrame()

    m["foreign_selling"] = m["foreign_net"] < 0
    # ★ 괴리: 외국인 순매도인데 원화 강세
    m["divergence"] = m["foreign_selling"] & m["krw_strength"]
    # 거래량 급증까지 겹치면 강신호(거래량 없으면 divergence 로만 판정)
    strong_vol = (m["vol_z"] >= VOL_Z_FLAG) | m["vol_z"].isna()
    m["signal"] = m["divergence"] & strong_vol

    return m[
        ["close", "ret", "krw_strength", "vol_z",
         "foreign_net", "foreign_selling", "divergence", "signal"]
    ]


def summarize(sig: pd.DataFrame) -> str:
    if sig.empty:
        return "신호 데이터 없음(수집 실패 또는 날짜 교집합 없음)."
    hits = sig[sig["signal"]]
    lines = [
        f"- 분석 구간: {sig.index[0].date()} ~ {sig.index[-1].date()} ({len(sig)}일)",
        f"- ★ 대량 환전 신호일: {len(hits)}일",
    ]
    if len(hits):
        lines.append("- 신호 발생일: " + ", ".join(str(d.date()) for d in hits.index[-10:]))
    return "\n".join(lines)
