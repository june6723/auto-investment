"""
설정 파일
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# API 설정
KIS_APP_KEY = os.getenv('KIS_APP_KEY')
KIS_APP_SECRET = os.getenv('KIS_APP_SECRET')
KIS_ACCOUNT_NO = os.getenv('KIS_ACCOUNT_NO')

# 모의투자 API 설정
KIS_PAPER_APP_KEY = os.getenv('KIS_PAPER_APP_KEY')
KIS_PAPER_APP_SECRET = os.getenv('KIS_PAPER_APP_SECRET')
KIS_PAPER_ACCOUNT_NO = os.getenv('KIS_PAPER_ACCOUNT_NO')

# 데이터베이스 설정
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./trading.db')

# 거래 설정
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '1000000'))  # 최대 포지션 크기 (원)
DAILY_TRADE_LIMIT = float(os.getenv('DAILY_TRADE_LIMIT', '5000000'))  # 일일 거래 한도 (원)
STOP_LOSS_PERCENTAGE = float(os.getenv('STOP_LOSS_PERCENTAGE', '5.0'))  # 손절매 비율 (%)

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'trading.log')

# 스케줄링 설정
MARKET_OPEN_TIME = '09:00'
MARKET_CLOSE_TIME = '15:30'
REBALANCE_TIME = '09:30'  # 포트폴리오 리밸런싱 시간 