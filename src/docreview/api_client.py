from __future__ import annotations
import json
import requests

class APIError(RuntimeError):
    pass

def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise APIError("모델 응답에서 JSON을 읽지 못했습니다.")

def call_tuftech(
    *,
    base_url: str,
    api_key: str,
    model: str,
    api_format: str,
    auth_mode: str,
    system_prompt: str,
    user_prompt: str,
    enable_prompt_cache: bool = True,
    timeout: int = 180,
) -> tuple[dict, dict, dict]:
    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if auth_mode == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["x-api-key"] = api_key

    # 캐시 시도 여부
    attempt_cache = (api_format == "anthropic" and enable_prompt_cache)
    fallback_used = False

    def build_payload(use_cache: bool) -> dict:
        if api_format == "anthropic":
            url_path = "/v1/messages"
            headers["anthropic-version"] = "2023-06-01"
            
            # 캐시 사용 시 system 지시어를 배열 객체 형태로 작성하고 cache_control 부여
            if use_cache:
                system_payload = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            else:
                system_payload = system_prompt
                
            payload = {
                "model": model,
                "max_tokens": 5000,
                "temperature": 0.1,
                "system": system_payload,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        elif api_format == "openai":
            url_path = "/v1/chat/completions"
            payload = {
                "model": model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        else:
            raise APIError("api_format은 anthropic 또는 openai여야 합니다.")
        
        return base + url_path, payload

    url, payload = build_payload(use_cache=attempt_cache)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise APIError(f"API 연결 실패: {exc}") from exc

    # 캐시 요청 후 400 에러(Tuftech/상위 API가 cache_control 필드를 모르거나 지원하지 않음) 발생 시 fallback 작동
    if not response.ok and attempt_cache and response.status_code == 400:
        fallback_used = True
        url, payload = build_payload(use_cache=False)
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            raise APIError(f"API 연결 실패 (비캐시 재시도): {exc}") from exc

    if not response.ok:
        safe = response.text[:1000]
        raise APIError(f"HTTP {response.status_code}: {safe}")

    body = response.json()
    if api_format == "anthropic":
        parts = body.get("content", [])
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        usage = body.get("usage", {})
    else:
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})

    # 캐시 지원 여부 판단 (응답에 cache 토큰 정보가 있으면 True)
    supported = (
        "cache_creation_input_tokens" in usage 
        or "cache_read_input_tokens" in usage
    )

    cache_status = {
        "requested": attempt_cache,
        "supported": supported,
        "fallback_used": fallback_used
    }

    return _extract_json(text), usage, cache_status

