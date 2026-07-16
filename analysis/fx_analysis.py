"""원/달러 환율 분석 파이프라인 (API 키 불필요).

데이터 소스 우선순위:
  1) FinanceDataReader 'USD/KRW' 일봉
  2) yfinance 'KRW=X' 일봉
  3) --csv 로 지정한 로컬 CSV (오프라인 폴백; Date,Close[,Open,High,Low] 형식)

인트라데이(1분봉, 최근 5일)는 yfinance 로 시도하고, 실패하면 건너뛴다.
새벽 역외 시간대(KST 00:00~09:00) 흐름은 대량 환전의 선행 신호로 보고
주간 세션(09:00~15:30)과 분리해 비교한다.

사용 예:
  python analysis/fx_analysis.py                     # 온라인 수집 + 분석
  python analysis/fx_analysis.py --csv data.csv      # 오프라인 CSV 분석
  python analysis/fx_analysis.py --start 2024-01-01 --out reports
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

Z_WINDOW = 20          # 이동 z-score 윈도우 (거래일)
Z_FLAG = 1.5           # 이상 신호로 표시할 z-score 절대값 임계치
VOL_WINDOW = 20        # 변동성 윈도우
KST = "Asia/Seoul"


def check_aistudio_api_key() -> tuple[bool, str]:
    """AISTUDIO_API_KEY 환경변수 확인 및 유효성 검증.

    Returns:
        (is_valid, message) - is_valid: 키 유효성 여부, message: 상태 메시지
    """
    api_key = os.getenv("AISTUDIO_API_KEY", "").strip()

    if not api_key:
        return False, "[warn] AISTUDIO_API_KEY가 설정되지 않았습니다."

    if len(api_key) < 20:
        return False, f"[warn] AISTUDIO_API_KEY가 너무 짧습니다 (길이: {len(api_key)})"

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        _ = client.models.list()
        return True, f"[ok] AISTUDIO_API_KEY 유효함 (길이: {len(api_key)})"
    except Exception as e:
        return False, f"[error] AISTUDIO_API_KEY 검증 실패: {e}"


def fetch_daily(start: str, csv: str | None) -> tuple[pd.DataFrame, str]:
    """일봉 데이터를 (DataFrame[Close], 소스이름) 으로 반환."""
    if csv:
        df = pd.read_csv(csv, parse_dates=["Date"], index_col="Date")
        return df[["Close"]].dropna(), f"csv:{csv}"

    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader("USD/KRW", start)
        if len(df):
            return df[["Close"]].dropna(), "FinanceDataReader USD/KRW"
    except Exception as e:  # noqa: BLE001 - 소스별 실패는 다음 소스로 폴백
        print(f"[warn] FinanceDataReader 실패: {e}", file=sys.stderr)

    try:
        import yfinance as yf

        df = yf.download("KRW=X", start=start, progress=False, auto_adjust=True)
        if len(df):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df[["Close"]].dropna(), "yfinance KRW=X"
    except Exception as e:  # noqa: BLE001
        print(f"[warn] yfinance 실패: {e}", file=sys.stderr)

    raise SystemExit(
        "일봉 데이터를 가져올 수 없습니다. 네트워크가 차단된 환경이면 "
        "--csv 로 로컬 파일을 지정하세요."
    )


def fetch_intraday() -> pd.DataFrame | None:
    """최근 5일 1분봉. 실패하면 None."""
    try:
        import yfinance as yf

        df = yf.download("KRW=X", period="5d", interval="1m", progress=False)
        if not len(df):
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[["Close"]].dropna().tz_convert(KST)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 인트라데이 수집 실패(건너뜀): {e}", file=sys.stderr)
        return None


def analyze_daily(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret"] = out["Close"].pct_change()
    roll = out["ret"].rolling(Z_WINDOW)
    out["z"] = (out["ret"] - roll.mean()) / roll.std()
    out["vol_ann"] = out["ret"].rolling(VOL_WINDOW).std() * np.sqrt(252)
    out["ma20"] = out["Close"].rolling(20).mean()
    out["ma60"] = out["Close"].rolling(60).mean()
    # 원화 강세(환율 하락) 연속일수
    down = out["ret"] < 0
    out["krw_up_streak"] = down.groupby((~down).cumsum()).cumsum()
    return out


def split_sessions(intra: pd.DataFrame) -> pd.DataFrame | None:
    """일자별로 새벽(00~09시)과 주간(09~15:30) 수익률을 분리."""
    if intra is None or intra.empty:
        return None
    g = intra.groupby(intra.index.date)
    rows = []
    for day, d in g:
        dawn = d.between_time("00:00", "09:00")["Close"]
        day_s = d.between_time("09:00", "15:30")["Close"]
        rows.append(
            {
                "date": day,
                "dawn_ret": dawn.iloc[-1] / dawn.iloc[0] - 1 if len(dawn) > 1 else np.nan,
                "day_ret": day_s.iloc[-1] / day_s.iloc[0] - 1 if len(day_s) > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("date")


def make_chart(daily: pd.DataFrame, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, height_ratios=[2, 1]
    )
    ax1.plot(daily.index, daily["Close"], lw=1.2, label="USD/KRW")
    ax1.plot(daily.index, daily["ma20"], lw=0.9, alpha=0.8, label="MA20")
    ax1.plot(daily.index, daily["ma60"], lw=0.9, alpha=0.8, label="MA60")
    flags = daily[daily["z"].abs() >= Z_FLAG]
    ax1.scatter(flags.index, flags["Close"], s=22, zorder=3, label=f"|z|>={Z_FLAG}")
    ax1.set_ylabel("KRW per USD")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.set_title("USD/KRW daily close with anomaly flags")

    ax2.bar(daily.index, daily["z"], width=1.0)
    ax2.axhline(Z_FLAG, ls="--", lw=0.8)
    ax2.axhline(-Z_FLAG, ls="--", lw=0.8)
    ax2.set_ylabel(f"return z-score ({Z_WINDOW}d)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def write_report(
    daily: pd.DataFrame,
    sessions: pd.DataFrame | None,
    source: str,
    out_md: Path,
    chart_name: str,
) -> None:
    last = daily.iloc[-1]
    recent = daily.tail(120)
    flags = recent[recent["z"].abs() >= Z_FLAG]
    streak = int(last["krw_up_streak"])

    lines = [
        "# USD/KRW 분석 리포트",
        "",
        f"- 데이터 소스: {source}",
        f"- 기간: {daily.index[0].date()} ~ {daily.index[-1].date()} ({len(daily)} 거래일)",
        f"- 최근 종가: **{last['Close']:,.2f}** ({daily.index[-1].date()})",
        f"- 최근 일간 수익률: {last['ret'] * 100:+.3f}% (z-score {last['z']:+.2f})",
        f"- 연환산 변동성({VOL_WINDOW}d): {last['vol_ann'] * 100:.2f}%",
        f"- 원화 강세(환율 하락) 연속일수: {streak}일",
        "",
        f"![chart]({chart_name})",
        "",
        f"## 최근 120거래일 이상 신호 (|z| >= {Z_FLAG})",
        "",
    ]
    if flags.empty:
        lines.append("이상 신호 없음.")
    else:
        lines += ["| 날짜 | 종가 | 수익률 | z-score |", "|---|---|---|---|"]
        lines += [
            f"| {idx.date()} | {r['Close']:,.2f} | {r['ret'] * 100:+.3f}% | {r['z']:+.2f} |"
            for idx, r in flags.iterrows()
        ]

    lines += [
        "",
        "## 새벽 역외(00~09시 KST) vs 주간(09~15:30) 세션",
        "",
    ]
    if sessions is None or sessions.dropna().empty:
        lines.append("인트라데이 데이터를 수집하지 못해 세션 분석은 생략.")
    else:
        lines += ["| 날짜 | 새벽 수익률 | 주간 수익률 |", "|---|---|---|"]
        lines += [
            f"| {idx} | {r['dawn_ret'] * 100:+.3f}% | {r['day_ret'] * 100:+.3f}% |"
            for idx, r in sessions.dropna().iterrows()
        ]
        both = sessions.dropna()
        if len(both) >= 3:
            corr = both["dawn_ret"].corr(both["day_ret"])
            lines.append("")
            lines.append(f"새벽-주간 수익률 상관계수: {corr:+.2f}")

    lines += [
        "",
        "## 해석 가이드",
        "",
        "- 음(-)의 z-score 가 크고(원화 강세) 그것이 연속되면 대량 달러 매도(원화 환전)",
        "  가능성을 시사한다. smbs.biz 현물환 거래량과 교차 확인할 것.",
        "- 새벽 역외 세션에서 원화 강세가 주간 세션보다 먼저 나타나면 역외발",
        "  원화 매수세가 선행하고 있다는 신호다.",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--csv", help="오프라인 일봉 CSV (Date,Close,...)")
    p.add_argument("--out", default="reports")
    p.add_argument("--check-api-key", action="store_true", help="AISTUDIO_API_KEY 검증만 수행")
    args = p.parse_args()

    if args.check_api_key:
        is_valid, message = check_aistudio_api_key()
        print(message)
        sys.exit(0 if is_valid else 1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw, source = fetch_daily(args.start, args.csv)
    daily = analyze_daily(raw)
    sessions = None if args.csv else split_sessions(fetch_intraday())

    chart = out_dir / "fx_chart.png"
    make_chart(daily, chart)
    report = out_dir / "fx_report.md"
    write_report(daily, sessions, source, report, chart.name)

    print(f"소스: {source}")
    print(f"리포트: {report}")
    print(f"차트: {chart}")


if __name__ == "__main__":
    main()
