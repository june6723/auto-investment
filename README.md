# Auto Investment System

한국투자증권 API를 활용한 자동 주식 거래 시스템입니다.

## 프로젝트 구조

```
auto-investment/
├── config/             # 설정 파일
├── src/               # 소스 코드
│   ├── api/          # API 연동
│   ├── models/       # 데이터베이스 모델
│   ├── strategies/   # 거래 전략
│   └── utils/        # 유틸리티
├── tests/            # 테스트 코드
├── .env              # 환경 변수
└── requirements.txt  # 의존성 패키지
```

## 시작하기

1. 환경 설정
   ```bash
   # 가상환경 생성
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows

   # 의존성 설치
   pip install -r requirements.txt
   ```

2. 환경 변수 설정
   - `.env` 파일을 프로젝트 루트 디렉토리에 생성하고 다음 변수들을 설정합니다:
   ```
   # API 설정
   KIS_APP_KEY=your_app_key_here
   KIS_APP_SECRET=your_app_secret_here
   KIS_ACCOUNT_NO=your_account_number_here

   # 데이터베이스 설정
   DATABASE_URL=sqlite:///./trading.db

   # 거래 설정
   MAX_POSITION_SIZE=1000000
   DAILY_TRADE_LIMIT=5000000
   STOP_LOSS_PERCENTAGE=5.0

   # 로깅 설정
   LOG_LEVEL=INFO
   LOG_FILE=trading.log
   ```

3. 실행
   ```bash
   python src/main.py
   ```

## 주요 기능

- 한국투자증권 API 연동
- 자동 주식 거래 실행
- 다양한 거래 전략 지원
- 포트폴리오 관리
- 거래 내역 기록

## 라이선스

MIT License 