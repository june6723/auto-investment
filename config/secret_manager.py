import oci
from oci.config import from_file
from pathlib import Path
import os
from typing import Dict
import base64

class SecretManager:
    def __init__(self):
        self.config = from_file()
        # VaultsClient 대신 SecretsClient 사용
        self.secrets_client = oci.secrets.SecretsClient(self.config)
        
        # Vault 시크릿 ID 매핑
        self.secret_ids = {
            # 모의투자 API 설정
            'KIS_PAPER_APP_KEY': os.getenv('KIS_PAPER_APP_KEY_SECRET_ID'),
            'KIS_PAPER_APP_SECRET': os.getenv('KIS_PAPER_APP_SECRET_SECRET_ID'),
            'KIS_PAPER_ACCOUNT_NO': os.getenv('KIS_PAPER_ACCOUNT_NO_SECRET_ID'),
            
            # 실전투자 API 설정
            'KIS_APP_KEY': os.getenv('KIS_APP_KEY_SECRET_ID'),
            'KIS_APP_SECRET': os.getenv('KIS_APP_SECRET_SECRET_ID'),
            'KIS_ACCOUNT_NO': os.getenv('KIS_ACCOUNT_NO_SECRET_ID')
        }
        
    def get_secret(self, secret_id: str) -> str:
        """Vault에서 시크릿을 가져옵니다."""
        try:
            # get_secret_bundle 메서드 사용
            secret_bundle = self.secrets_client.get_secret_bundle(secret_id)
            # base64로 인코딩된 시크릿 내용을 디코딩
            secret_content = base64.b64decode(secret_bundle.data.secret_bundle_content.content).decode('utf-8')
            return secret_content
        except Exception as e:
            raise Exception(f"Failed to get secret {secret_id}: {str(e)}")
    
    def create_env_file(self, env_path: str = '.env') -> None:
        """Vault에서 시크릿을 가져와 .env 파일을 생성합니다."""
        env_vars: Dict[str, str] = {}
        
        # 각 시크릿 가져오기
        for env_key, secret_id in self.secret_ids.items():
            if not secret_id:
                print(f"Warning: Secret ID for {env_key} is not set in environment variables")
                continue
            try:
                env_vars[env_key] = self.get_secret(secret_id)
                print(f"Successfully retrieved secret for {env_key}")
            except Exception as e:
                print(f"Warning: Failed to get secret for {env_key}: {str(e)}")
                continue
        
        # .env 파일 생성
        env_path = Path(env_path)
        with env_path.open('w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        # 파일 권한 설정 (소유자만 읽기/쓰기 가능)
        env_path.chmod(0o600)
        
        print(f"Created .env file at {env_path.absolute()}")
        print(f"Retrieved {len(env_vars)} secrets")

if __name__ == "__main__":
    # 환경 변수에서 시크릿 ID를 가져와야 합니다
    required_env_vars = [
        # 모의투자 시크릿 ID
        'KIS_PAPER_APP_KEY_SECRET_ID',
        'KIS_PAPER_APP_SECRET_SECRET_ID',
        'KIS_PAPER_ACCOUNT_NO_SECRET_ID',
        
        # 실전투자 시크릿 ID
        'KIS_APP_KEY_SECRET_ID',
        'KIS_APP_SECRET_SECRET_ID',
        'KIS_ACCOUNT_NO_SECRET_ID'
    ]
    
    # 환경 변수 확인
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Available secrets will still be retrieved.")
    
    # .env 파일 생성
    secret_manager = SecretManager()
    secret_manager.create_env_file() 