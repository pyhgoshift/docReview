from __future__ import annotations
import os
import re
import requests
from pathlib import Path

class GatewayDetector:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.detected_models: list[str] = []

    def detect_compatibility(self) -> dict:
        """
        API 게이트웨이의 호환 규격 및 인증 수단을 교차 탐색하여 성공 조합을 반환합니다.
        """
        if not self.api_key:
            return {"status": "error", "message": "API 인증 키가 누락되었습니다."}

        # 1단계: GET /v1/models 를 통한 제공 모델 사전 탐색 (Bearer & x-api-key 둘 다 시도)
        self._probe_models()

        # 2단계: API 규격 및 인증 헤더 교차 검증 테스트
        # 4가지 가능한 조합 교차 탐색
        combinations = [
            {"format": "anthropic", "auth": "bearer", "path": "/v1/messages"},
            {"format": "anthropic", "auth": "x-api-key", "path": "/v1/messages"},
            {"format": "openai", "auth": "bearer", "path": "/v1/chat/completions"},
            {"format": "openai", "auth": "x-api-key", "path": "/v1/chat/completions"},
        ]

        # 탐색된 모델명 중 기본 모델 매핑 우선순위 결정
        test_model = "claude-sonnet-4-6"  # 기본 탐색 타겟
        if self.detected_models:
            # 탐색된 모델이 있는 경우 첫 번째 모델 혹은 Sonnet 계열 사용
            for m in self.detected_models:
                if "sonnet" in m or "claude" in m:
                    test_model = m
                    break
            else:
                test_model = self.detected_models[0]

        for combo in combinations:
            url = self.base_url + combo["path"]
            headers = {"Content-Type": "application/json"}
            
            # 인증 헤더 세팅
            if combo["auth"] == "bearer":
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers["x-api-key"] = self.api_key

            # 간단한 헬로월드 페이로드 세팅
            if combo["format"] == "anthropic":
                headers["anthropic-version"] = "2023-06-01"
                payload = {
                    "model": test_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "Hi"}],
                }
            else:
                payload = {
                    "model": test_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "Hi"}],
                }

            try:
                # 빠른 검출을 위해 타임아웃 6초 지정
                response = requests.post(url, headers=headers, json=payload, timeout=6)
                if response.status_code == 200:
                    return {
                        "status": "success",
                        "api_format": combo["format"],
                        "auth_mode": combo["auth"],
                        "recommended_model": test_model,
                        "available_models": self.detected_models
                    }
            except Exception:
                continue

        return {
            "status": "error",
            "message": "모든 API 형식 및 인증 헤더 조합에 대한 응답 테스트가 실패하였습니다. 주소 혹은 API 키를 재확인해 주십시오."
        }

    def _probe_models(self):
        """
        GET /v1/models 엔드포인트를 찔러 가용한 모델 리스트를 미리 탐색합니다.
        """
        endpoints = ["/v1/models", "/models"]
        auth_headers = [
            {"Authorization": f"Bearer {self.api_key}"},
            {"x-api-key": self.api_key}
        ]

        for path in endpoints:
            url = self.base_url + path
            for headers in auth_headers:
                try:
                    r = requests.get(url, headers=headers, timeout=4)
                    if r.status_code == 200:
                        data = r.json()
                        models = []
                        # One API / OpenAI 규격의 모델 리스트 파싱
                        if isinstance(data, dict) and "data" in data:
                            for item in data["data"]:
                                if isinstance(item, dict) and "id" in item:
                                    models.append(item["id"])
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "id" in item:
                                    models.append(item["id"])
                        
                        if models:
                            self.detected_models = sorted(list(set(models)))
                            return
                except Exception:
                    continue

    @staticmethod
    def update_env_file(env_path: Path, config: dict) -> bool:
        """
        .env 파일을 안전하게 읽어 기존 주석이나 형식을 보존하며 지정된 키 값을 갱신 및 저장합니다.
        """
        env_path = Path(env_path)
        if not env_path.exists():
            # 파일이 없을 시 새로 생성
            lines = []
            for k, v in config.items():
                lines.append(f"{k}={v}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True

        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        for k, v in config.items():
            pattern = re.compile(rf"^\s*{k}\s*=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{k}={v}", content)
            else:
                # 기존에 키가 없다면 파일 끝에 추가
                if not content.endswith("\n") and content:
                    content += "\n"
                content += f"{k}={v}\n"

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
