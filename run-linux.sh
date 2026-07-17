#!/usr/bin/env bash
set -e

# 프로젝트 디렉토리로 이동
cd "$(dirname "$0")"

# PYTHONPATH 환경변수 설정
export PYTHONPATH="$PWD/src"

# 가상환경 내 streamlit을 사용하여 사내 망에 바인딩
if [ -f ".venv/bin/streamlit" ]; then
    echo "DocReview AI 구동 중 (포트: 8501)..."
    .venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
else
    echo "오류: 가상환경 혹은 streamlit 패키지를 찾을 수 없습니다. setup-linux.sh를 먼저 실행하십시오."
    exit 1
fi
