"""한국 외환·증시 신호 수집기 패키지.

각 수집기는 (실제 소스 → 실패 시 --csv 오프라인 폴백) 패턴을 따르며,
정규화된 pandas DataFrame 을 반환한다. orchestrator 가 이들을 모아
SQLite 에 적재하고 signals 모듈이 교차 신호를 계산한다.
"""
