$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3가 필요합니다. python.org 또는 winget으로 설치하십시오."
}
$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "설치 완료. .env 파일에 API 키와 정확한 모델명을 입력한 뒤 실행하십시오."
Write-Host "실행 명령: .\run-windows.bat"
