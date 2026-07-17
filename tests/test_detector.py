from __future__ import annotations
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from docreview.detector import GatewayDetector

def test_probe_models_success():
    detector = GatewayDetector("https://mock-gateway.org", "test-key")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "claude-sonnet-4-6"},
            {"id": "claude-fable-5"}
        ]
    }
    
    with patch("requests.get", return_value=mock_response):
        detector._probe_models()
        
    assert "claude-sonnet-4-6" in detector.detected_models
    assert "claude-fable-5" in detector.detected_models

def test_detect_compatibility_openai_bearer():
    detector = GatewayDetector("https://mock-gateway.org", "test-key")
    detector.detected_models = ["gpt-5-6", "claude-sonnet-4-6"]

    # 4대 조합 중 OpenAI + Bearer 에 해당하는 requests.post 시점에만 200을 리턴하게 흉내냄
    # 조합 순서:
    # 1. Anthropic + Bearer
    # 2. Anthropic + x-api-key
    # 3. OpenAI + Bearer
    # 4. OpenAI + x-api-key
    
    def side_effect(url, headers, json, timeout):
        resp = MagicMock()
        if "chat/completions" in url and "Bearer" in headers.get("Authorization", ""):
            resp.status_code = 200
        else:
            resp.status_code = 400
        return resp

    with patch("requests.post", side_effect=side_effect):
        result = detector.detect_compatibility()

    assert result["status"] == "success"
    assert result["api_format"] == "openai"
    assert result["auth_mode"] == "bearer"
    assert result["recommended_model"] == "claude-sonnet-4-6"

def test_update_env_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        
        # 1. 초기 생성 테스트
        config = {
            "TUFTECH_API_FORMAT": "openai",
            "TUFTECH_AUTH_MODE": "bearer",
            "TUFTECH_MODEL": "gpt-5-6"
        }
        GatewayDetector.update_env_file(env_file, config)
        
        content = env_file.read_text(encoding="utf-8")
        assert "TUFTECH_API_FORMAT=openai" in content
        assert "TUFTECH_AUTH_MODE=bearer" in content
        
        # 2. 값 갱신 테스트
        updated_config = {
            "TUFTECH_API_FORMAT": "anthropic",
            "TUFTECH_MODEL": "claude-fable-5"
        }
        GatewayDetector.update_env_file(env_file, updated_config)
        
        content_updated = env_file.read_text(encoding="utf-8")
        assert "TUFTECH_API_FORMAT=anthropic" in content_updated
        assert "TUFTECH_AUTH_MODE=bearer" in content_updated # 보존
        assert "TUFTECH_MODEL=claude-fable-5" in content_updated
