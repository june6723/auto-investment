"""
백테스팅 엔진 모듈
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from src.api.kis_api import KisAPI


class BacktestResult:
    """백테스팅 결과 클래스"""
    
    def __init__(self):
        self.initial_balance = 0  # 초기 자본금
        self.final_balance = 0    # 최종 자본금
        self.total_invested = 0   # 총 투자금액
        self.total_profit = 0     # 총 수익금
        self.total_return = 0.0   # 총 수익률
        self.trades = []          # 거래 내역
        self.daily_balance = []   # 일별 자산 현황
        
    def calculate_metrics(self):
        """수익률 및 성과 지표 계산"""
        if not self.daily_balance:
            return
            
        # 일별 수익률 계산
        daily_returns = pd.Series([b['balance'] for b in self.daily_balance])
        daily_returns = daily_returns.pct_change().dropna()
        
        # 연간화된 수익률 계산
        years = len(self.daily_balance) / 252  # 252는 연간 거래일 수
        annual_return = (1 + self.total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 변동성 계산 (연간화)
        volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0
        
        # 샤프 비율 계산 (무위험 수익률 3% 가정)
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # 최대 낙폭 계산
        cumulative_returns = (1 + daily_returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdowns = cumulative_returns / rolling_max - 1
        max_drawdown = drawdowns.min()
        
        # 승률 계산 (현재는 매수만 있으므로 100%)
        win_rate = 1.0 if self.trades else 0.0
        
        self.metrics = {
            "total_return": self.total_return,
            "annual_return": annual_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_trades": len(self.trades),
            "win_rate": win_rate
        }
    
    def print_summary(self):
        """백테스팅 결과 요약 출력"""
        if not hasattr(self, 'metrics'):
            self.calculate_metrics()
            
        print("\n=== 백테스팅 결과 요약 ===")
        print(f"초기 자본금: {self.initial_balance:,}원")
        print(f"최종 자본금: {self.final_balance:,}원")
        print(f"총 투자금액: {self.total_invested:,}원")
        print(f"총 수익금: {self.total_profit:,}원")
        print(f"총 수익률: {self.total_return:.2%}")
        print(f"\n=== 성과 지표 ===")
        print(f"연간 수익률: {self.metrics['annual_return']:.2%}")
        print(f"변동성: {self.metrics['volatility']:.2%}")
        print(f"샤프 비율: {self.metrics['sharpe_ratio']:.2f}")
        print(f"최대 낙폭: {self.metrics['max_drawdown']:.2%}")
        print(f"총 거래 횟수: {self.metrics['total_trades']}회")
        print(f"승률: {self.metrics['win_rate']:.2%}")


class BacktestEngine:
    """백테스팅 엔진 클래스"""
    
    def __init__(self, api: KisAPI):
        """
        백테스팅 엔진 초기화
        
        Args:
            api: KisAPI 인스턴스
        """
        self.api = api
        self.result = BacktestResult()
        
    def run(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        initial_balance: int,
        weekly_budget: int,
        market: str = "J"
    ) -> BacktestResult:
        """
        백테스팅 실행
        
        Args:
            codes: 종목코드 리스트
            start_date: 시작일자 (YYYYMMDD)
            end_date: 종료일자 (YYYYMMDD)
            initial_balance: 초기 자본금
            weekly_budget: 주간 투자 예산
            market: 시장구분
            
        Returns:
            BacktestResult: 백테스팅 결과
        """
        # 초기화
        self.result = BacktestResult()
        self.result.initial_balance = initial_balance
        current_balance = initial_balance
        holdings = {code: 0 for code in codes}  # 보유 수량
        
        # 각 종목별 과거 시세 데이터 조회
        price_data = {}
        for code in codes:
            try:
                data = self.api.get_historical_prices(code, start_date, end_date, market)
                # 날짜별 가격 데이터를 딕셔너리로 변환
                price_data[code] = {
                    item['date']: item for item in data['prices']
                }
            except Exception as e:
                logger.error(f"종목 {code} 시세 데이터 조회 실패: {str(e)}")
                continue
        
        # 백테스팅 기간의 모든 거래일 구하기
        all_dates = set()
        for prices in price_data.values():
            all_dates.update(prices.keys())
        all_dates = sorted(list(all_dates))
        
        # 각 거래일별 백테스팅 실행
        for date in all_dates:
            # 월요일인지 확인 (1: 월요일)
            is_monday = datetime.strptime(date, "%Y%m%d").weekday() == 0
            
            # 월요일이고 10시라면 주문 실행
            if is_monday:
                # 각 종목별 주문 실행
                for code in codes:
                    if code not in price_data or date not in price_data[code]:
                        continue
                        
                    price_info = price_data[code][date]
                    current_price = price_info['close']
                    
                    # 주간 예산으로 주문 가능한 수량 계산
                    budget = weekly_budget // len(codes)  # 종목당 예산
                    quantity = budget // current_price
                    
                    if quantity > 0:
                        # 주문 실행
                        order_amount = quantity * current_price
                        if order_amount <= current_balance:
                            # 거래 기록
                            trade = {
                                'date': date,
                                'code': code,
                                'type': 'BUY',
                                'quantity': quantity,
                                'price': current_price,
                                'amount': order_amount,
                                'balance': current_balance - order_amount,
                                'profit': 0,  # 매수 시점에는 수익이 없음
                                'profit_rate': 0.0  # 매수 시점에는 수익률이 없음
                            }
                            self.result.trades.append(trade)
                            
                            # 잔고 및 보유 수량 업데이트
                            current_balance -= order_amount
                            holdings[code] += quantity
                            self.result.total_invested += order_amount
            
            # 일별 자산 현황 기록 및 수익 계산
            total_value = current_balance
            for code, quantity in holdings.items():
                if code in price_data and date in price_data[code]:
                    price = price_data[code][date]['close']
                    position_value = quantity * price
                    total_value += position_value
                    
                    # 해당 종목의 매수 거래 내역 업데이트
                    for trade in self.result.trades:
                        if trade['code'] == code and trade['type'] == 'BUY':
                            # 매수 금액 대비 현재 가치의 수익 계산
                            trade_profit = position_value - trade['amount']
                            trade['profit'] = trade_profit
                            trade['profit_rate'] = trade_profit / trade['amount']
            
            self.result.daily_balance.append({
                'date': date,
                'balance': total_value,
                'holdings': holdings.copy()
            })
        
        # 최종 결과 계산
        self.result.final_balance = self.result.daily_balance[-1]['balance']
        self.result.total_profit = self.result.final_balance - self.result.initial_balance
        self.result.total_return = (self.result.final_balance / self.result.initial_balance) - 1
        
        # 성과 지표 계산
        self.result.calculate_metrics()
        
        return self.result


# 사용 예시
if __name__ == "__main__":
    try:
        # API 클라이언트 초기화
        api = KisAPI(mode=KisAPI.MODE_PAPER)
        
        # 백테스팅 엔진 초기화
        engine = BacktestEngine(api)
        
        # 백테스팅 파라미터 설정
        codes = ["379800", "379800"]  # KODEX 미국S&P500, KODEX 미국나스닥100
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        initial_balance = 10_000_000  # 1천만원
        weekly_budget = 250_000  # 주 25만원 (월 100만원)
        
        # 백테스팅 실행
        result = engine.run(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            weekly_budget=weekly_budget
        )
        
        # 결과 출력
        result.print_summary()
        
    except Exception as e:
        logger.error(f"백테스팅 실행 중 오류 발생: {str(e)}")
        print(f"\n오류 발생: {str(e)}") 