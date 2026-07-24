"""거시 통계 수집기 (KOSIS / korea-stats-mcp) — 정규화 컬럼: date, indicator, value.

경상수지·외환보유액 등 월/분기 통계로 환전 수요의 구조적 배경을 확인한다.
korea-stats-mcp 는 원격 Vercel 서버(키 내장)라 원격 세션에서도 접근 가능할 수
있으나, 스켈레톤 단계에서는 KOSIS OpenAPI 직접 호출 자리만 잡아두고 --csv 폴백을
쓴다. 실제 연동은 네트워크가 열린 뒤 KOSIS 통계표 ID 를 확정해 채운다.

NOTE: KOSIS OpenAPI 는 별도 키가 필요하지만, korea-stats-mcp 원격 서버를 쓰면
키 없이 조회 가능. 결합 시 어느 경로를 쓸지는 배포 환경에 맞춰 결정.
"""

from __future__ import annotations

import sys

import pandas as pd


def collect(csv: str | None = None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv, parse_dates=["date"])
        return _norm(df)

    # TODO: KOSIS OpenAPI 또는 korea-stats-mcp 원격 서버 호출.
    #   예) 경상수지(통계표ID 확정 필요), 외환보유액 등 월별 시계열을
    #       date/indicator/value 로 정규화해 반환.
    print("[kosis] 원격 연동 미구현 — --csv 폴백 사용", file=sys.stderr)
    return pd.DataFrame(columns=["date", "indicator", "value"])


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["date", "indicator", "value"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    return out.dropna().sort_values("date").reset_index(drop=True)
