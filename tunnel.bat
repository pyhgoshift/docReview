@echo off
title DocReview AI SSH Tunnel Gateway
echo ==============================================================
echo  DocReview AI 사내 서버 방화벽 우회 터널을 활성화합니다.
echo  이 창을 열어두고 브라우저에서 http://localhost:8501 로 접속하십시오.
echo ==============================================================
ssh -i C:\Users\freud\.ssh\itcen_server_key -p 7722 -L 8501:localhost:8501 devadm01@192.168.64.31
pause
