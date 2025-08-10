#!/bin/bash

# 에러 발생시 스크립트 중단
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 로그 함수
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# 작업 디렉토리 확인
if [ ! -d ".git" ]; then
    error "이 스크립트는 git 저장소 루트 디렉토리에서 실행해야 합니다."
fi

# 1. Git 업데이트
log "Git 저장소 업데이트 중..."
git fetch origin
if [ $? -ne 0 ]; then
    error "Git fetch 실패"
fi

# 현재 브랜치 확인
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "현재 브랜치: $CURRENT_BRANCH"

# 변경사항 확인
LOCAL_CHANGES=$(git status --porcelain)
if [ ! -z "$LOCAL_CHANGES" ]; then
    warn "로컬 변경사항이 있습니다:"
    echo "$LOCAL_CHANGES"
    read -p "계속 진행하시겠습니까? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "배포가 취소되었습니다."
    fi
fi

# 원격 변경사항 확인
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count)
if [ $BEHIND -eq 0 ]; then
    log "최신 버전입니다. 업데이트가 필요하지 않습니다."
    read -p "서비스를 재시작하시겠습니까? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "배포가 취소되었습니다."
        exit 0
    fi
else
    log "$BEHIND 개의 커밋을 가져옵니다..."
    git pull origin $CURRENT_BRANCH
    if [ $? -ne 0 ]; then
        error "Git pull 실패"
    fi
fi

# 2. 가상환경 업데이트
log "가상환경 업데이트 중..."
if [ ! -d "venv" ]; then
    warn "가상환경이 없습니다. 새로 생성합니다..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    error "의존성 설치 실패"
fi

# 3. 서비스 재시작
log "서비스 재시작 중..."
sudo systemctl restart auto-trader.service
if [ $? -ne 0 ]; then
    error "서비스 재시작 실패"
fi

# 4. 서비스 상태 확인
log "서비스 상태 확인 중..."
sleep 2  # 서비스 시작 대기
if systemctl is-active --quiet auto-trader.service; then
    log "서비스가 정상적으로 시작되었습니다."
else
    error "서비스 시작 실패"
fi

# 5. 로그 확인
log "최근 로그 확인 중..."
echo "----------------------------------------"
journalctl -u auto-trader.service -n 20 --no-pager
echo "----------------------------------------"

log "배포가 완료되었습니다!"
log "전체 로그를 보려면: journalctl -u auto-trader.service -f"