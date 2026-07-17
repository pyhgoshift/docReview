# RTK 적용 가이드

## 무엇을 줄이는가

RTK는 DocReview AI가 문서를 Tuftech API로 보낼 때의 입력 토큰을 직접 압축하지 않습니다.
RTK는 Claude Code, Codex, Cursor 같은 코딩 에이전트가 셸 명령의 긴 출력을 읽을 때 토큰을 줄입니다.

예:

```powershell
rtk pytest
rtk ruff check
rtk git status
rtk git diff
rtk read app.py
rtk grep "APIError" .
```

## Windows 설치

1. RTK GitHub Releases에서 `rtk-x86_64-pc-windows-msvc.zip`을 받습니다.
2. 압축을 풀어 `rtk.exe`를 `D:\\Tools\\rtk`에 둡니다.
3. Windows 환경변수 PATH에 `D:\\Tools\\rtk`를 추가합니다.
4. 새 PowerShell에서 확인합니다.

```powershell
rtk --version
rtk gain
```

5. Claude Code에 전역 적용하려면:

```powershell
rtk init -g
```

6. Codex에 적용하려면:

```powershell
rtk init -g --codex
```

## 이 프로젝트에서 권장 명령

```powershell
$env:PYTHONPATH="$PWD\\src"
rtk pytest
rtk git status
rtk git diff
```

## 주의

RTK 훅은 Bash/셸 명령 출력에 적용됩니다. Claude Code의 내장 Read, Grep, Glob 도구에는 자동 적용되지 않을 수 있습니다.
그 경우 `rtk read`, `rtk grep`, `rtk find`를 직접 사용합니다.
