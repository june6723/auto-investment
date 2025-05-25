"""
한국투자증권 API 연동 모듈
"""
from datetime import datetime, timedelta
import json
import os
from typing import Dict, Optional, Tuple
import requests
from loguru import logger
import sys
import time

from config.settings import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_PAPER_APP_KEY, KIS_PAPER_APP_SECRET, KIS_PAPER_ACCOUNT_NO

# 로그 디렉토리 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 로그 파일 경로 설정 (날짜별)
LOG_FILE = os.path.join(LOG_DIR, f"kis_api_{datetime.now().strftime('%Y%m%d')}.log")

# 기존 로거 제거
logger.remove()

# 터미널 출력 설정 (간단한 포맷)
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True
)

# 파일 출력 설정 (상세 포맷)
logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    level="DEBUG",
    rotation="00:00",  # 매일 자정에 새 파일 생성
    retention="30 days",  # 30일간 보관
    encoding="utf-8"
)

# 토큰 저장 파일 경로
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".token_cache.json")


class KisAPIError(Exception):
    """한국투자증권 API 관련 예외"""
    pass


class KisAPI:
    """한국투자증권 API 클라이언트"""
    
    # API 엔드포인트
    BASE_URL = "https://openapi.koreainvestment.com:9443" 
    PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
    AUTH_URL = f"{BASE_URL}/oauth2/tokenP"
    PAPER_AUTH_URL = f"{PAPER_BASE_URL}/oauth2/tokenP"
    
    # 거래 모드
    MODE_REAL = "real"  # 실전투자
    MODE_PAPER = "paper"  # 모의투자
    
    def __init__(self, mode: str = MODE_REAL):
        """
        API 클라이언트 초기화
        
        Args:
            mode: 거래 모드 (real: 실전투자, paper: 모의투자)
        """
        self._access_token: Optional[str] = None
        self._token_expired_at: Optional[datetime] = None
        self.mode = mode
        self._last_request_time = 0  # 마지막 요청 시간
        
        # API 키 검증
        if not all([KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO]):
            raise KisAPIError("API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        # 저장된 토큰이 있으면 불러오기, 없으면 새로 발급
        if not self._load_token():
            self._issue_token()
            self._save_token()
            
        logger.info(f"API 클라이언트가 초기화되었습니다. (모드: {'모의투자' if mode == self.MODE_PAPER else '실전투자'})")
    
    def _save_token(self) -> None:
        """토큰 정보를 파일에 저장"""
        if not self._access_token or not self._token_expired_at:
            return
            
        token_data = {
            "access_token": self._access_token,
            "expired_at": self._token_expired_at.isoformat()
        }
        
        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f)
            logger.debug("토큰이 파일에 저장되었습니다.")
        except Exception as e:
            logger.warning(f"토큰 저장 실패: {str(e)}")

    def _load_token(self) -> bool:
        """파일에서 토큰 정보 불러오기
        
        Returns:
            bool: 토큰 로드 성공 여부
        """
        if not os.path.exists(TOKEN_FILE):
            return False
            
        try:
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
                
            self._access_token = token_data["access_token"]
            self._token_expired_at = datetime.fromisoformat(token_data["expired_at"])
            
            # 토큰이 만료되었는지 확인
            if datetime.now() >= self._token_expired_at:
                logger.info("저장된 토큰이 만료되었습니다.")
                return False
                
            logger.debug("저장된 토큰을 불러왔습니다.")
            return True
            
        except Exception as e:
            logger.warning(f"토큰 로드 실패: {str(e)}")
            return False
    
    def _issue_token(self) -> None:
        """인증 토큰 발급"""
        try:
            # 모의투자/실전투자 API 키 선택
            if self.mode == self.MODE_PAPER:
                app_key = KIS_PAPER_APP_KEY
                app_secret = KIS_PAPER_APP_SECRET
            else:
                app_key = KIS_APP_KEY
                app_secret = KIS_APP_SECRET

            data = {
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret
            }
            
            auth_url = self.PAPER_AUTH_URL if self.mode == self.MODE_PAPER else self.AUTH_URL
            response = requests.post(auth_url, json=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data["access_token"]
            
            # 토큰 만료 시간 설정 (실제 만료 시간보다 1분 일찍 갱신)
            expires_in = token_data.get("expires_in", 86400)  # 기본값 24시간
            self._token_expired_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("인증 토큰이 발급되었습니다.")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"토큰 발급 중 오류 발생: {str(e)}")
            raise KisAPIError(f"토큰 발급 실패: {str(e)}")
    
    def _get_headers(self) -> Dict[str, str]:
        """API 요청에 필요한 헤더 생성"""
        # 토큰이 만료되었거나 없는 경우 갱신
        if not self._access_token or (
            self._token_expired_at and datetime.now() >= self._token_expired_at
        ):
            self._issue_token()
            self._save_token()
        
        # 모의투자/실전투자 API 키 선택
        if self.mode == self.MODE_PAPER:
            app_key = KIS_PAPER_APP_KEY
            app_secret = KIS_PAPER_APP_SECRET
        else:
            app_key = KIS_APP_KEY
            app_secret = KIS_APP_SECRET
        
        return {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self._access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": "",  # 각 API 호출 시 tr_id 설정 필요
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        tr_id: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        API 요청 실행
        
        Args:
            method: HTTP 메서드 (GET, POST 등)
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: URL 파라미터
            data: 요청 본문 데이터
            
        Returns:
            Dict: API 응답 데이터
            
        Raises:
            KisAPIError: API 요청 실패 시
        """
        # API 호출 제한 준수
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        # 모의투자: 초당 1회, 실전투자: 초당 5회
        min_interval = 1.0 if self.mode == self.MODE_PAPER else 0.2
        
        if time_since_last_request < min_interval:
            sleep_time = min_interval - time_since_last_request
            logger.debug(f"API 호출 제한 준수를 위해 {sleep_time:.2f}초 대기")
            time.sleep(sleep_time)
        
        url = f"{self.PAPER_BASE_URL}{endpoint}"
        headers = self._get_headers()
        headers["tr_id"] = tr_id
        
        try:
            # 요청 URL과 파라미터를 함께 로깅
            if params:
                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                full_url = f"{url}?{query_string}"
                logger.debug(f"Request URL with params: {full_url}")
            else:
                logger.debug(f"Request URL: {url}")
            
            self._last_request_time = time.time()  # 요청 시간 기록
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data
            )
            
            # 상세 로그는 파일에만 기록
            logger.debug(f"Request Method: {method}")
            logger.debug(f"Request Headers: {headers}")
            if params:
                logger.debug(f"Request Params: {params}")
            if data:
                logger.debug(f"Request Data: {data}")
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Headers: {response.headers}")
            logger.debug(f"Response Content: {response.text}")
            
            try:
                result = response.json()
            except json.JSONDecodeError:
                logger.error(f"JSON 파싱 실패. 응답 내용: {response.text}")
                raise KisAPIError(f"응답을 JSON으로 파싱할 수 없습니다: {response.text}")
            
            # API 에러 체크
            if response.status_code != 200 or ("rt_cd" in result and result["rt_cd"] != "0"):
                error_msg = f"API 오류 발생 (Status: {response.status_code})"
                if "rt_cd" in result:
                    error_msg += f"\nrt_cd: {result.get('rt_cd')}"
                    error_msg += f"\nmsg_cd: {result.get('msg_cd')}"
                    error_msg += f"\nmsg1: {result.get('msg1')}"
                logger.error(error_msg)
                raise KisAPIError(error_msg)
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API 요청 실패: {str(e)}"
            if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
                logger.debug(f"에러 응답 내용: {e.response.text}")  # 상세 내용은 파일에만 기록
            logger.error(error_msg)
            raise KisAPIError(error_msg)
    
    def get_account_balance(self) -> Dict:
        """
        계좌 잔고 조회
        
        Returns:
            Dict: 계좌 잔고 정보
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-balance"

        tr_id = "TTTC8434R" if self.mode == self.MODE_REAL else "VTTC8434R"  # 실전투자 계좌 잔고 조회
        account_no = KIS_PAPER_ACCOUNT_NO if self.mode == self.MODE_PAPER else KIS_ACCOUNT_NO
        params = {
            "CANO": account_no[:8],  # 계좌번호 앞 8자리
            "ACNT_PRDT_CD": account_no[8:],  # 계좌번호 뒤 2자리
            "AFHR_FLPR_YN": "N",  # 시간외 여부
            "OFL_YN": "",  # 오프라인 여부
            "INQR_DVSN": "02",  # 조회구분
            "UNPR_DVSN": "01",  # 단가구분
            "FUND_STTL_ICLD_YN": "N",  # 펀드결제분 포함여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액 자동상환여부
            "PRCS_DVSN": "01",  # 처리구분
            "CTX_AREA_FK100": "",  # 연속조회검색조건
            "CTX_AREA_NK100": "",  # 연속조회키
        }
        
        return self._request("GET", endpoint, tr_id, params=params)

    def get_stock_price(self, code: str, market: str = "1") -> dict:
        """
        국내주식 현재가(시세) 조회
        Args:
            code: 종목코드 (6자리 문자열)
            market: 시장구분 (1: 코스피, J: 코스닥, 2: 코넥스)
        Returns:
            dict: 시세 정보
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-price"
        tr_id = "FHKST01010100"   # 시세 조회는 동일한 tr_id 사용
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": code
        }
        return self._request("GET", endpoint, tr_id, params=params)

    def place_order(
        self,
        code: str,
        quantity: int,
        order_type: str = "00",  # 00: 지정가, 01: 시장가
        side: str = "BUY",  # BUY: 매수, SELL: 매도
        price: Optional[int] = None,  # 지정가 주문시 필요
        market: str = "J",  # KRX
    ) -> Dict:
        """
        주식 주문 실행
        
        Args:
            code: 종목코드 (6자리 문자열)
            quantity: 주문 수량
            order_type: 주문 유형 (00: 지정가, 01: 시장가)
            side: 매매 구분 (BUY: 매수, SELL: 매도)
            price: 주문 가격 (지정가 주문시 필수)
            market: 시장구분 (1: 코스피, J: 코스닥, 2: 코넥스)
            
        Returns:
            Dict: 주문 결과
            
        Raises:
            KisAPIError: 주문 실패시
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-cash"
        
        # 실전투자/모의투자 tr_id 설정
        if self.mode == self.MODE_PAPER:
            BUY_TR_ID = "VTTC0012U"  # 모의투자 매수
            SELL_TR_ID = "VTTC0011U"  # 모의투자 매도
        else:
            BUY_TR_ID = "TTTC0012U"  # 실전투자 매수
            SELL_TR_ID = "TTTC0011U"  # 실전투자 매도
            
        tr_id = BUY_TR_ID if side == "BUY" else SELL_TR_ID
        
        # 주문 파라미터 검증
        if order_type == "00" and price is None:
            raise KisAPIError("지정가 주문시 가격을 입력해주세요.")
        
        account_no = KIS_PAPER_ACCOUNT_NO if self.mode == self.MODE_PAPER else KIS_ACCOUNT_NO
        data = {
            "CANO": account_no[:8],  # 계좌번호 앞 8자리
            "ACNT_PRDT_CD": account_no[8:],  # 계좌번호 뒤 2자리
            "PDNO": code,  # 종목코드
            "ORD_DVSN": order_type,  # 주문구분
            "ORD_QTY": str(quantity),  # 주문수량
            "EXCG_ID_DVSN_CD": "KRX",  # 거래소코드
            "ORD_UNPR": str(price) if order_type == "00" else "0",  # 지정가 주문시 가격 시장가 주문시 0 입력
        }
        
        # 매도 주문시 추가 파라미터
        if side == "SELL":
            data["SLL_TYPE"] = "01"  # 매도시 주문구분코드 변경
        
        try:
            result = self._request("POST", endpoint, tr_id, data=data)
            logger.info(f"주문 실행 완료: {'모의투자' if self.mode == self.MODE_PAPER else '실전투자'} {side} {code} {quantity}주")
            return result
            
        except KisAPIError as e:
            logger.error(f"주문 실행 실패: {str(e)}")
            raise

    def calculate_order_quantity(self, code: str, budget: int, market: str = "J") -> Tuple[int, int]:
        """
        주어진 예산 내에서 주문 가능한 최대 수량 계산
        
        Args:
            code: 종목코드
            budget: 주문 예산 (원)
            market: 시장구분 (1: 코스피, J: 코스닥, 2: 코넥스)
            
        Returns:
            Tuple[int, int]: (주문 수량, 예상 주문 금액)
            
        Raises:
            KisAPIError: 시세 조회 실패시
        """
        # 현재가 조회
        price_info = self.get_stock_price(code, market=market)
        current_price = int(price_info.get("output", {}).get("stck_prpr", 0))
        
        if current_price == 0:
            raise KisAPIError(f"종목 {code}의 현재가를 조회할 수 없습니다.")
        
        # 주문 가능 수량 계산 (예산을 현재가로 나눈 몫)
        quantity = budget // current_price
        
        if quantity == 0:
            raise KisAPIError(f"예산 {budget:,}원으로는 1주도 매수할 수 없습니다. (현재가: {current_price:,}원)")
        
        # 예상 주문 금액 계산
        expected_amount = quantity * current_price
        
        logger.info(f"종목 {code} 주문 수량 계산: {quantity}주 (현재가: {current_price:,}원, 예상금액: {expected_amount:,}원)")
        
        return quantity, expected_amount

    def place_regular_order(self, code: str, budget: int, market: str = "J") -> Dict:
        """
        정기 주문 실행 (시장가)
        
        Args:
            code: 종목코드
            budget: 주문 예산 (원)
            market: 시장구분 (1: 코스피, J: 코스닥, 2: 코넥스)
            
        Returns:
            Dict: 주문 결과
            
        Raises:
            KisAPIError: 주문 실패시
        """
        try:
            # 주문 수량 계산
            quantity, expected_amount = self.calculate_order_quantity(code, budget, market)
            
            # 시장가 주문 실행
            order = self.place_order(
                code=code,
                quantity=quantity,
                order_type="01",  # 시장가
                side="BUY",
                market=market
            )
            
            logger.info(f"정기 주문 실행 완료: {code} {quantity}주 (예상금액: {expected_amount:,}원)")
            return order
            
        except KisAPIError as e:
            logger.error(f"정기 주문 실패: {str(e)}")
            raise

    def get_historical_prices(
        self,
        code: str,
        start_date: str,
        end_date: str,
        market: str = "J"
    ) -> Dict:
        """
        과거 시세 데이터 조회
        
        Args:
            code: 종목코드
            start_date: 시작일자 (YYYYMMDD)
            end_date: 종료일자 (YYYYMMDD)
            market: 시장구분 (1: 코스피, J: 코스닥, 2: 코넥스)
            
        Returns:
            Dict: 일별 시세 데이터
            
        Raises:
            KisAPIError: API 요청 실패시
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        tr_id = "FHKST03010100"  # 일별 시세 조회
        
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": "D",  # 일별
            "FID_ORG_ADJ_PRC": "1",  # 수정주가
        }
        
        try:
            result = self._request("GET", endpoint, tr_id, params=params)
            
            # 응답 데이터 가공
            price_data = []
            for item in result.get("output2", []):
                price_data.append({
                    "date": item.get("stck_bsop_date"),  # 기준일자
                    "open": int(item.get("stck_oprc", 0)),  # 시가
                    "high": int(item.get("stck_hgpr", 0)),  # 고가
                    "low": int(item.get("stck_lwpr", 0)),   # 저가
                    "close": int(item.get("stck_clpr", 0)), # 종가
                    "volume": int(item.get("acml_vol", 0)), # 거래량
                    "amount": int(item.get("acml_tr_pbmn", 0)), # 거래대금
                })
            
            logger.info(f"과거 시세 데이터 조회 완료: {code} ({start_date} ~ {end_date})")
            return {
                "code": code,
                "start_date": start_date,
                "end_date": end_date,
                "prices": price_data
            }
            
        except KisAPIError as e:
            logger.error(f"과거 시세 데이터 조회 실패: {str(e)}")
            raise


# 사용 예시
if __name__ == "__main__":
    try:
        # 모의투자 모드로 API 클라이언트 초기화
        api = KisAPI(mode=KisAPI.MODE_PAPER)
        logger.info("API 클라이언트가 초기화되었습니다.")
        
        # 정기 주문 테스트
        BUDGET = 125_000  # 12.5만원
        
        # KODEX 미국S&P500 정기 주문
        sp500_order = api.place_regular_order(
            code="379800",  # KODEX 미국S&P500
            budget=BUDGET,
            market="J"
        )
        print("\n[KODEX 미국S&P500 주문 결과]")
        print(json.dumps(sp500_order, indent=2, ensure_ascii=False))
        
        # KODEX 미국나스닥100 정기 주문
        nasdaq_order = api.place_regular_order(
            code="379800",  # KODEX 미국나스닥100
            budget=BUDGET,
            market="J"
        )
        print("\n[KODEX 미국나스닥100 주문 결과]")
        print(json.dumps(nasdaq_order, indent=2, ensure_ascii=False))
        
    except KisAPIError as e:
        logger.error(f"에러 발생: {str(e)}")
        print(f"\n에러 발생: {str(e)}") 