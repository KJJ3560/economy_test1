"""SQLite 저장 계층. DataFrame 을 date 기준으로 upsert/조회한다."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def connect(db_path: str | Path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    """df 를 table 에 저장. 'date' 열(문자열 YYYY-MM-DD)을 PK 로 대체 저장한다.

    스켈레톤 단계에서는 단순 replace 전략을 쓴다(테이블 전체 재적재).
    증분 적재가 필요해지면 임시테이블 + INSERT OR REPLACE 로 교체할 것.
    """
    if df is None or df.empty:
        return 0
    out = df.copy()
    if "date" not in out.columns:
        out = out.reset_index().rename(columns={out.index.name or "index": "date"})
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_sql(table, conn, if_exists="replace", index=False)
    conn.commit()
    return len(out)


def read(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
    except Exception:  # noqa: BLE001 - 테이블 없음 등
        return pd.DataFrame()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    return df
