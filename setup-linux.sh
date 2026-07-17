#!/usr/bin/env bash
set -e

# Python 3 설치 여부 확인
if ! command -v python3 &> /dev/null; then
    echo "오류: Python 3가 필요합니다. 시스템에 Python3가 설치되어 있는지 확인하십시오."
    exit 1
fi

# venv 모듈 설치 여부 확인 및 가상환경 생성
if [ ! -d ".venv" ]; then
    echo "가상환경(.venv)을 생성합니다..."
    python3 -m venv .venv || {
        echo "오류: python3-venv 패키지가 필요할 수 있습니다. 시스템 관리자 권한으로 'apt install python3-venv' 등을 실행하십시오."
        exit 1
    }
fi

# 가상환경 패키지 설치
echo "가상환경 pip 업그레이드 및 패키지 설치 중..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# .env 파일 생성
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env 파일이 복사되었습니다. 파일 내 API 키 및 모델명을 설정하십시오."
else
    echo ".env 파일이 이미 존재합니다."
fi

echo "--------------------------------------------------------"
echo "설치가 완료되었습니다."
echo "실행 명령: bash run-linux.sh"
echo "--------------------------------------------------------"
