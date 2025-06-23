"""
자동 주문 시스템 모듈
"""
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict
import pytz
from loguru import logger

from src.api.kis_api import KisAPI


class AutoTrader:
    """자동 주문 시스템 클래스"""
    
    def __init__(
        self,
        api: KisAPI,
        codes: List[str],
        weekly_budget: int,
        market: str = "J"
    ):
        """
        자동 주문 시스템 초기화
        
        Args:
            api: KisAPI 인스턴스
            codes: 종목코드 리스트
            weekly_budget: 주간 투자 예산
            market: 시장구분
        """
        self.api = api
        self.codes = codes
        self.weekly_budget = weekly_budget
        self.market = market
        self.seoul_tz = pytz.timezone('Asia/Seoul')
        
        logger.info(f"자동 주문 시스템이 초기화되었습니다.")
        logger.info(f"종목: {', '.join(codes)}")
        logger.info(f"주간 투자 예산: {weekly_budget:,}원")
        
    def _is_market_open(self) -> bool:
        """
        현재 시장이 열려있는지 확인
        
        Returns:
            bool: 시장 개장 여부
        """
        now = datetime.now(self.seoul_tz)
        
        # 주말 체크
        if now.weekday() >= 5:  # 5: 토요일, 6: 일요일
            return False
            
        # 장 시간 체크 (9:00 ~ 15:30)
        market_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_start <= now <= market_end
        
    def _execute_orders(self):
        """주문 실행"""
        try:
            # 시장 개장 여부 확인
            if not self._is_market_open():
                logger.warning("현재 시장이 닫혀있습니다.")
                return
                
            # API 토큰 상태 확인 및 갱신
            try:
                # 계좌 잔고 확인 (토큰 상태 테스트)
                balance_info = self.api.get_account_balance()
                available_balance = int(balance_info.get("output2", [{}])[0].get("prvs_rcdl_excc_amt", 0))
                logger.info(f"계좌 잔고 확인 완료: {available_balance:,}원")
                
            except Exception as e:
                if "EGW00123" in str(e) or "만료된 token" in str(e):
                    logger.warning("토큰이 만료되었습니다. 토큰을 갱신하고 재시도합니다.")
                    # 토큰 갱신을 위해 새로운 API 인스턴스 생성
                    from src.api.kis_api import KisAPI
                    self.api = KisAPI(mode=self.api.mode)
                    # 재귀 호출로 다시 시도
                    self._execute_orders()
                    return
                else:
                    logger.error(f"계좌 잔고 확인 실패: {str(e)}")
                    return
            
            if available_balance < self.weekly_budget:
                logger.warning(f"잔고 부족: {available_balance:,}원 (필요: {self.weekly_budget:,}원)")
                return
                
            # 각 종목별 주문 실행
            budget_per_stock = self.weekly_budget // len(self.codes)
            
            for code in self.codes:
                try:
                    # 주문 수량 계산 및 주문 실행
                    result = self.api.place_regular_order(
                        code=code,
                        budget=budget_per_stock,
                        market=self.market
                    )
                    
                    # 주문 결과 로깅
                    order_info = result.get("output", {})
                    logger.info(
                        f"주문 실행 완료: {code}\n"
                        f"주문 수량: {order_info.get('ord_qty')}주\n"
                        f"주문 금액: {int(order_info.get('ord_amt', 0)):,}원\n"
                        f"주문 번호: {order_info.get('ord_no')}"
                    )
                    
                except Exception as e:
                    if "EGW00123" in str(e) or "만료된 token" in str(e):
                        logger.warning(f"종목 {code} 주문 중 토큰 만료. 토큰을 갱신하고 재시도합니다.")
                        # 토큰 갱신을 위해 새로운 API 인스턴스 생성
                        from src.api.kis_api import KisAPI
                        self.api = KisAPI(mode=self.api.mode)
                        # 해당 종목 다시 시도
                        try:
                            result = self.api.place_regular_order(
                                code=code,
                                budget=budget_per_stock,
                                market=self.market
                            )
                            order_info = result.get("output", {})
                            logger.info(
                                f"재시도 주문 실행 완료: {code}\n"
                                f"주문 수량: {order_info.get('ord_qty')}주\n"
                                f"주문 금액: {int(order_info.get('ord_amt', 0)):,}원\n"
                                f"주문 번호: {order_info.get('ord_no')}"
                            )
                        except Exception as retry_e:
                            logger.error(f"재시도 후 종목 {code} 주문 실패: {str(retry_e)}")
                    else:
                        logger.error(f"종목 {code} 주문 실패: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"주문 실행 중 오류 발생: {str(e)}")
            
    def _seoul_to_utc_time(self, seoul_time_str: str) -> str:
        """
        서울 시간을 UTC 시간으로 변환
        
        Args:
            seoul_time_str: "HH:MM" 형식의 서울 시간
            
        Returns:
            str: "HH:MM" 형식의 UTC 시간
        """
        # 오늘 날짜로 서울 시간 객체 생성
        today = datetime.now(self.seoul_tz).date()
        hour, minute = map(int, seoul_time_str.split(':'))
        seoul_dt = self.seoul_tz.localize(datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute)))
        
        # UTC로 변환
        utc_dt = seoul_dt.astimezone(pytz.UTC)
        
        return utc_dt.strftime("%H:%M")
        
    def start(self):
        """자동 주문 시스템 시작"""
        # 서울 시간 기준으로 매주 화요일 10시에 주문 실행
        # UTC 시간으로 변환: 서울 10:00 = UTC 01:00 (서머타임 고려)
        seoul_time = "10:00"
        utc_time = self._seoul_to_utc_time(seoul_time)
        
        # 현재 시간 확인
        utc_now = datetime.now(pytz.UTC)
        seoul_now = utc_now.astimezone(self.seoul_tz)
        
        logger.info(f"시스템 UTC 시간: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"서울 시간: {seoul_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"스케줄 설정: 매주 화요일 서울 시간 {seoul_time} (UTC {utc_time})")
        
        # UTC 시간으로 스케줄 설정
        schedule.every().tuesday.at(utc_time).do(self._execute_orders)
        
        logger.info("자동 주문 시스템이 시작되었습니다.")
        logger.info("매주 화요일 오전 10시(서울 시간)에 주문이 실행됩니다.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("자동 주문 시스템이 중지되었습니다.")
            
    def run_once(self):
        """주문 한 번 실행 (테스트용)"""
        logger.info("주문을 한 번 실행합니다.")
        self._execute_orders()


# 사용 예시
if __name__ == "__main__":
    try:
        # API 클라이언트 초기화
        api = KisAPI(mode=KisAPI.MODE_REAL)
        
        # 자동 주문 시스템 초기화
        trader = AutoTrader(
            api=api,
            codes=["379800", "379810", "329750"],  # KODEX 미국S&P500, KODEX 미국나스닥100, TIGER 미국달러단기채권액티브
            weekly_budget=400_000,  # 각 종목당 주 12.5만원 (각 종목당 월 50만원)
            market="J"
        )
        
        # 테스트를 위해 주문 한 번 실행
        # trader.run_once()
        
        # 실제 자동 주문 시작
        trader.start()
        
    except Exception as e:
        logger.error(f"자동 주문 시스템 실행 중 오류 발생: {str(e)}")
        print(f"\n오류 발생: {str(e)}") 