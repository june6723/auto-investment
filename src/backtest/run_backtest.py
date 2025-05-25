from src.api.kis_api import KisAPI
from src.backtest.backtest_engine import BacktestEngine
from datetime import datetime, timedelta

# API 클라이언트 초기화
api = KisAPI(mode=KisAPI.MODE_PAPER)

# 백테스팅 엔진 초기화
engine = BacktestEngine(api)

# 백테스팅 실행
result = engine.run(
    codes=["379800", "379800"],  # KODEX 미국S&P500, KODEX 미국나스닥100
    start_date="20230101",       # 시작일
    end_date="20240315",         # 종료일
    initial_balance=10_000_000,  # 초기 자본금 1천만원
    weekly_budget=250_000        # 주간 투자 예산 25만원
)

# 결과 출력
result.print_summary()