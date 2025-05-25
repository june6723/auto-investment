"""
자동 주문 시스템 테스트 스크립트
"""
from src.api.kis_api import KisAPI
from src.auto_trade.auto_trader import AutoTrader
from loguru import logger


class TestTrader(AutoTrader):
    """테스트용 트레이더 클래스"""
    
    def _is_market_open(self) -> bool:
        """테스트를 위해 시장 시간 체크 비활성화"""
        return True


def main():
    try:
        # API 클라이언트 초기화 (모의투자 모드)
        api = KisAPI(mode=KisAPI.MODE_PAPER)
        logger.info("API 클라이언트가 초기화되었습니다.")
        
        # 계좌 잔고 확인
        balance_info = api.get_account_balance()
        available_balance = int(balance_info.get("output2", [{}])[0].get("prvs_rcdl_excc_amt", 0))
        logger.info(f"현재 계좌 잔고: {available_balance:,}원")
        
        # 테스트용 트레이더 초기화
        trader = TestTrader(
            api=api,
            codes=["379800", "379800"],  # KODEX 미국S&P500, KODEX 미국나스닥100
            weekly_budget=250_000,  # 주 25만원 (월 100만원)
            market="J"
        )
        
        # 주문 한 번 실행
        logger.info("테스트 주문을 실행합니다...")
        trader.run_once()
        logger.info("테스트 주문이 완료되었습니다.")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}")
        print(f"\n오류 발생: {str(e)}")


if __name__ == "__main__":
    main() 