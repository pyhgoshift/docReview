# DocReview AI MVP v1.0

Tuftech API를 이용해 사업 문서를 자동 검토하는 로컬 웹 애플리케이션입니다.

## 기능

- PDF, DOCX, TXT, Markdown 문서 한 개 업로드
- 문서 품질 점수와 우선 수정사항
- 오타·맞춤법·어색한 표현
- 논리적 모순
- 숫자·날짜·금액 불일치 가능성
- 사업 문서 누락 요소
- 문장 수정안
- 분석 결과 JSON 다운로드
- 토큰 절약 전처리 통계

## RTK 아이디어 반영

RTK의 핵심 전략인 필터링, 그룹화, 절단, 중복 제거를 문서 입력에 맞게 구현했습니다.

1. 빈 줄과 불필요한 공백 제거
2. 동일한 줄 중복 제거
3. 숫자·날짜는 로컬에서 먼저 추출
4. 긴 문서는 앞·뒤 문맥 보존
5. 중간 구간은 사업 핵심어·숫자·제목 문장을 우선 선택
6. API에 실제 전송될 문자 수와 절감률 표시

RTK 자체는 개발 중 셸 출력 토큰을 줄이는 선택 도구입니다. 자세한 내용은 `docs/RTK_GUIDE.md`를 보십시오.

## Windows 설치 & 실행

PowerShell에서:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-windows.ps1
```

`.env` 파일에 API 정보를 입력한 후 실행합니다:

```powershell
.\run-windows.bat
```

## 회사 서버(Linux) 설치 & 실행

사내 개발 서버(`192.168.64.31`) 환경에서 구동하는 방법입니다.

1. **저장소 클론 및 이동**
   ```bash
   git clone https://github.com/pyhgoshift/docReview.git
   cd docReview
   ```

2. **설치 스크립트 실행**
   ```bash
   bash setup-linux.sh
   ```
   * 설치 과정에서 `.env.example` 복사본 `.env`가 생성됩니다.

3. **환경 변수 설정 (`.env`)**
   ```env
   TUFTECH_API_KEY=실제_API_키
   TUFTECH_BASE_URL=https://api.tuftech.org
   TUFTECH_MODEL=판매자가_안내한_정확한_모델명
   TUFTECH_API_FORMAT=anthropic
   TUFTECH_AUTH_MODE=bearer
   DOCREVIEW_MAX_INPUT_CHARS=50000
   DOCREVIEW_ENABLE_PROMPT_CACHE=true
   DOCREVIEW_CIRCUIT_FAILURES=3
   DOCREVIEW_CIRCUIT_COOLDOWN_SECONDS=300
   ```

4. **실행**
   ```bash
   bash run-linux.sh
   ```
   * 기본적으로 8501 포트와 `0.0.0.0` 인터페이스에 바인딩됩니다.

## Cloudflare Tunnel을 통한 외부 웹 배포

Streamlit은 백엔드 실행 환경이 필요하므로, Cloudflare Pages 단독 배포 대신 사내 서버(`192.168.64.31:8501`)를 **Cloudflare Tunnel**로 연결하여 외부 배포를 진행합니다.

1. **cloudflared 설치 (사내 서버)**
   ```bash
   curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
   sudo dpkg -i cloudflared.deb
   ```

2. **Cloudflare 로그인 및 터널 생성**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create docreview-tunnel
   ```

3. **터널 설정 파일 작성 (`~/.cloudflared/config.yml`)**
   ```yaml
   tunnel: <TUNNEL_UUID>
   credentials-file: /home/devadm01/.cloudflared/<TUNNEL_UUID>.json

   ingress:
     - hostname: docreview.yourdomain.com
       service: http://localhost:8501
     - service: http_status:404
   ```

4. **DNS 라우팅 및 터널 구동**
   ```bash
   cloudflared tunnel route dns docreview-tunnel docreview.yourdomain.com
   cloudflared tunnel run docreview-tunnel
   ```

## 연결 오류 해결

- HTTP 401/403: `TUFTECH_AUTH_MODE`를 `bearer`와 `x-api-key` 사이에서 변경
- HTTP 404: `TUFTECH_API_FORMAT`을 `anthropic`과 `openai` 사이에서 변경
- HTTP 400/model not found: 판매자가 안내한 정확한 모델명 입력
- 스캔 PDF: 현재 MVP는 OCR 미지원. 텍스트 PDF 또는 DOCX를 사용

## 테스트

Windows:
```powershell
.\.venv\Scripts\activate
$env:PYTHONPATH="$PWD\src"
pytest
```

Linux:
```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
pytest
```

## 보안

`api.tuftech.org`는 제3자 게이트웨이입니다. 공급자의 저장·로그·학습·삭제 정책을 확인하기 전에는 민감한 고객 문서나 회사 기밀을 업로드하지 마십시오.

