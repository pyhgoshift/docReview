from __future__ import annotations
import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

def get_tuftech_balance(api_key: str) -> dict:
    if not api_key:
        return {"status": "error", "message": "API 키를 입력해 주십시오."}
    api_key = api_key.strip()
    headers = {"Authorization": f"Bearer {api_key}"}
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.tuftech.org/dashboard/billing/usage?start_date=2026-01-01&end_date={today}"
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            total = data.get("total_quota", 30000) / 100
            used = data.get("total_usage", 0) / 100
            remaining = total - used
            return {
                "status": "success",
                "total": total,
                "used": used,
                "remaining": remaining
            }
        else:
            return {"status": "error", "message": f"조회 실패 (HTTP {r.status_code})"}
    except Exception as e:
        return {"status": "error", "message": "네트워크 연결 불안정"}

def calculate_estimated_cost(usage: dict, api_format: str) -> float:
    if not usage:
        return 0.0
    if api_format == "anthropic":
        # Claude 3.5 Sonnet 공식 단가 매핑
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        cache_read_t = usage.get("cache_read_input_tokens", 0)
        cache_create_t = usage.get("cache_creation_input_tokens", 0)
        
        # 캐싱된 인풋 단가: Read ($0.30/MTok), Creation ($3.75/MTok), 일반 Input ($3.00/MTok), Output ($15.00/MTok)
        cost = (
            (input_t * 0.000003) + 
            (output_t * 0.000015) + 
            (cache_read_t * 0.00000030) + 
            (cache_create_t * 0.00000375)
        )
        return cost
    else:
        # OpenAI GPT-4o 급 표준 단가 매핑 ($5.00/MTok Input, $15.00/MTok Output)
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        cost = (prompt_t * 0.000005) + (completion_t * 0.000015)
        return cost

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from docreview.api_client import APIError, call_tuftech
from docreview.extractor import ExtractionError, extract_text
from docreview.local_checks import extract_facts, repeated_sentences
from docreview.optimizer import optimize_document
from docreview.prompts import SYSTEM_PROMPT, build_prompt
from docreview.runtime import CircuitBreaker, ArtifactManager, CircuitOpenError

# .env 로드
load_dotenv(ROOT / ".env")

# Streamlit 세션 정보 설정
st.set_page_config(page_title="DocReview AI", page_icon="📄", layout="wide")
st.title("📄 DocReview AI")
st.caption("사업 문서의 오타·논리 모순·숫자 불일치·누락 요소를 자동 검토합니다.")

# 환경 변수 기반 설정 로드
CIRCUIT_FAILURES = int(os.getenv("DOCREVIEW_CIRCUIT_FAILURES", "3"))
CIRCUIT_COOLDOWN = int(os.getenv("DOCREVIEW_CIRCUIT_COOLDOWN_SECONDS", "300"))
ENABLE_PROMPT_CACHE = os.getenv("DOCREVIEW_ENABLE_PROMPT_CACHE", "true").lower() == "true"

# 서킷 브레이커 및 로컬 저장소 초기화
state_file = ROOT / "runtime" / "circuit_state.json"
circuit_breaker = CircuitBreaker(state_file, max_failures=CIRCUIT_FAILURES, cooldown_seconds=CIRCUIT_COOLDOWN)
artifact_manager = ArtifactManager(ROOT)

with st.sidebar:
    st.header("API 설정")
    
    env_key = os.getenv("TUFTECH_API_KEY", "")
    if env_key:
        balance_info = get_tuftech_balance(env_key)
        if balance_info["status"] == "success":
            st.metric(
                label="💵 TUFTech 잔량",
                value=f"${balance_info['remaining']:.4f}",
                delta=f"소모량: ${balance_info['used']:.4f} / 총 ${balance_info['total']:.0f}"
            )
        else:
            st.caption(f"⚠️ TUFTech 잔량 조회 불가: {balance_info['message']}")

    # 세션 상태 초기화
    if "detected_models" not in st.session_state:
        st.session_state["detected_models"] = []

    base_url = st.text_input("API 기본 주소 (Base URL)", os.getenv("TUFTECH_BASE_URL", "https://api.tuftech.org"))
    
    # 세션에 로드된 실제 제공 모델 목록이 있으면 우선 노출
    if st.session_state["detected_models"]:
        raw_options = st.session_state["detected_models"]
        model_options = []
        for m in raw_options:
            if m == "claude-haiku-4-5":
                model_options.append("claude-haiku-4-5 (★가장 빠르고 가벼움)")
            elif m == "claude-sonnet-4-6":
                model_options.append("claude-sonnet-4-6 (현재 기본값 - 무겁고 정밀함)")
            else:
                model_options.append(m)
        if "직접 입력 (Custom)" not in model_options:
            model_options.append("직접 입력 (Custom)")
    else:
        model_options = [
            "claude-haiku-4-5 (★가장 빠르고 가벼움)",
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6 (현재 기본값 - 무겁고 정밀함)",
            "claude-sonnet-4-5-20250929",
            "claude-sonnet-5",
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-opus-4-5-20251101",
            "claude-fable-5",
            "직접 입력 (Custom)"
        ]
        
    env_model = os.getenv("TUFTECH_MODEL", "claude-sonnet-4-6")
    default_index = 0
    for i, opt in enumerate(model_options):
        if opt.startswith(env_model):
            default_index = i
            break
    else:
        default_index = len(model_options) - 1

    selected_model_opt = st.selectbox(
        "분석 모델 선택",
        model_options,
        index=default_index
    )

    if "직접 입력" in selected_model_opt:
        model = st.text_input("모델명 직접 입력", value="" if env_model in ["claude-sonnet-4-6", "claude-fable-5", "claude-opus-4-8", "gpt-5-6", "codex-cl"] else env_model)
    else:
        model = selected_model_opt.split(" ")[0]
    api_format = st.selectbox(
        "API 프로토콜 규격",
        ["anthropic", "openai"],
        index=0 if os.getenv("TUFTECH_API_FORMAT", "anthropic") == "anthropic" else 1,
    )
    auth_mode = st.selectbox(
        "인증 헤더 규격",
        ["bearer", "x-api-key"],
        index=0 if os.getenv("TUFTECH_AUTH_MODE", "bearer") == "bearer" else 1,
    )
    env_key = os.getenv("TUFTECH_API_KEY", "")
    api_key = st.text_input("API 인증 키", value=env_key, type="password")
    max_chars = st.number_input(
        "API 최대 입력 한도 (문자 수)",
        min_value=10000,
        max_value=200000,
        value=int(os.getenv("DOCREVIEW_MAX_INPUT_CHARS", "50000")),
        step=5000,
        help="문서가 길면 중요 문장을 우선 선택하여 이 크기로 압축합니다.",
    )
    st.info("API 키는 화면에 표시되지 않습니다. `.env` 파일은 GitHub에 올리지 마십시오.")
    
    st.markdown("---")
    st.subheader("자가 진단 도구")
    if st.button("🔧 API 호환성 자동 탐지 시작", use_container_width=True):
        if not api_key:
            st.error("API 인증 키를 입력한 뒤 시도해 주십시오.")
        else:
            with st.spinner("API 규격 및 헤더 인증 방식을 탐색 중..."):
                from docreview.detector import GatewayDetector
                detector = GatewayDetector(base_url, api_key)
                res = detector.detect_compatibility()
                if res["status"] == "success":
                    st.success(f"탐지 성공: {res['api_format']} + {res['auth_mode']}")
                    if "available_models" in res and res["available_models"]:
                        st.session_state["detected_models"] = res["available_models"]
                    config_update = {
                        "TUFTECH_BASE_URL": base_url,
                        "TUFTECH_API_KEY": api_key,
                        "TUFTECH_API_FORMAT": res["api_format"],
                        "TUFTECH_AUTH_MODE": res["auth_mode"],
                        "TUFTECH_MODEL": res["recommended_model"]
                    }
                    GatewayDetector.update_env_file(Path(".env"), config_update)
                    st.toast("API 규격 및 모델 리스트 로드 완료!", icon="✅")
                    st.rerun()
                else:
                    st.error(res["message"])

uploaded = st.file_uploader(
    "문서 한 개를 업로드하세요",
    type=["pdf", "docx", "txt", "md"],
    accept_multiple_files=False,
)

if uploaded:
    # 서킷 브레이커 현재 상태 사전 검증
    try:
        circuit_breaker.check_state()
    except CircuitOpenError as exc:
        st.error(str(exc))
        st.stop()

    try:
        raw_text = extract_text(uploaded.name, uploaded.getvalue())
    except ExtractionError as exc:
        st.error(str(exc))
        st.stop()

    # 원문 및 최적화 문서 생성 및 로컬 저장
    optimized, stats = optimize_document(raw_text, max_chars=int(max_chars))
    raw_path, raw_hash = artifact_manager.save_raw(uploaded.name, raw_text)
    opt_path, opt_hash = artifact_manager.save_optimized(uploaded.name, optimized)

    facts = extract_facts(raw_text)
    duplicates = repeated_sentences(raw_text)

    st.subheader("토큰 절약 전처리")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("원문 문자 수", f"{stats.original_chars:,}")
    c2.metric("API 전송 문자 수", f"{stats.optimized_chars:,}")
    c3.metric("문자 절감률", f"{stats.reduction_percent}%")
    c4.metric("중복 줄 제거", stats.removed_duplicate_lines)
    
    if stats.truncated:
        st.warning("긴 문서이므로 문서 앞·뒤와 중요 문장을 우선하여 압축했습니다.")

    # 디스크 저장 정보 표시 영역
    st.info("📄 문서가 로컬 디스크에 안전하게 보관되었습니다.")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**원본 문서 저장 정보**")
        st.text(f"경로: {raw_path}\n해시: {raw_hash}")
    with d2:
        st.markdown("**최적화 문서 저장 정보**")
        st.text(f"경로: {opt_path}\n해시: {opt_hash}")

    with st.expander("전처리된 API 전송 내용 미리보기 (최대 8000글자)"):
        st.text(optimized[:8000])
        
    with st.expander("로컬 추출 정보"):
        st.json({"facts": facts, "repeated_sentences": duplicates})

    # 분석 시작 버튼 작동 시
    if st.button("자동 전체 분석 시작", type="primary", use_container_width=True):
        # 실행 직전 다시 서킷 브레이커 확인
        try:
            circuit_breaker.check_state()
        except CircuitOpenError as exc:
            st.error(str(exc))
            st.stop()

        if not api_key:
            st.error("API 키를 입력하십시오.")
            st.stop()
        if not model:
            st.error("판매자가 안내한 정확한 모델명을 입력하십시오.")
            st.stop()

        import time
        prompt = build_prompt(optimized, facts, uploaded.name)
        with st.spinner("AI가 문서를 분석하고 있습니다..."):
            start_time = time.time()
            try:
                result, usage, cache_status = call_tuftech(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    api_format=api_format,
                    auth_mode=auth_mode,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                    enable_prompt_cache=ENABLE_PROMPT_CACHE,
                )
                duration = time.time() - start_time
                # 성공 시 서킷 브레이커 실패 횟수 리셋
                circuit_breaker.record_success()
            except (APIError, KeyError, ValueError, Exception) as exc:
                # 에러 시 실패 횟수 누적
                circuit_breaker.record_failure()
                st.error(str(exc))
                st.info("401/403이면 인증 방식을 바꾸고, 404이면 API 형식을 바꾸며, 400이면 모델명을 확인하십시오.")
                st.stop()

        # 분석 결과 로컬 디스크 저장
        res_path, res_hash = artifact_manager.save_result(uploaded.name, result)

        st.success(f"분석이 완료되었습니다. (총 {duration:.1f}초 소요)")
        
        st.subheader("프롬프트 캐싱 상태")
        ch1, ch2, ch3, ch4 = st.columns(4)
        ch1.metric("캐시 요청 상태", "요청 완료" if cache_status["requested"] else "미요청")
        ch2.metric("캐시 적용 완료", "적용 성공" if cache_status["supported"] else "미지원")
        ch3.metric("우회 재시도 작동", "예(Fallback)" if cache_status["fallback_used"] else "아니오")
        ch4.metric("분석 소요 시간", f"{duration:.1f}초")

        if usage:
            st.json(usage)
            
            # 비용 및 잔고 대조 시각화 (사용자 요청 명칭 및 구조 정밀 반영)
            st.markdown("---")
            st.subheader("💡 API 비용 및 잔량 매칭")
            
            cost = calculate_estimated_cost(usage, api_format)
            server_balance = get_tuftech_balance(api_key)
            
            tuftech_actual = 0.0
            if server_balance["status"] == "success":
                tuftech_actual = server_balance["remaining"]
            
            # 현재 예측잔량 = (Tuftech 실제잔량 - 금회사용량)
            predicted_rem = max(0.0, tuftech_actual - cost)
            
            c1, c2, c3 = st.columns(3)
            c1.metric(
                label="📉 금회사용량",
                value=f"${cost:.5f}",
                help="이번 문서 검토 시 사용된 모델 토큰 소모 가격입니다."
            )
            c2.metric(
                label="🔮 현재 예측잔량",
                value=f"${predicted_rem:.5f}",
                help="실제 잔량에서 이번 소모 가격을 차감한 예측 잔액입니다."
            )
            if server_balance["status"] == "success":
                c3.metric(
                    label="💵 TUFTech 실제잔량",
                    value=f"${tuftech_actual:.4f}",
                    help="Tuftech API 서버에서 가져온 실제 잔량입니다."
                )
            else:
                c3.warning(f"TUFTech 실제잔량 조회 실패: {server_balance['message']}")
                
            st.markdown("---")

        # 저장 결과 요약
        st.markdown(f"**결과 보고서 저장 경로:** `{res_path}` (해시: `{res_hash}`)")

        score = result.get("score", 0)
        grade = result.get("grade", "-")
        
        st.subheader("종합 평가")
        a, b = st.columns([1, 3])
        a.metric("문서 품질 점수", f"{score}/100", grade)
        b.write(result.get("executive_summary", ""))

        st.subheader("우선 수정사항")
        actions = result.get("priority_actions", [])
        if actions:
            for item in actions:
                severity = item.get("severity", "medium").upper()
                st.markdown(f"**[{severity}] {item.get('title', '')}**")
                st.write(item.get("reason", ""))
                st.caption("수정 방향: " + item.get("suggestion", ""))
        else:
            st.info("우선 수정사항이 없습니다.")

        tabs = st.tabs(["점수 근거", "오타·표현", "논리 모순", "숫자·날짜", "누락 요소", "수정 예시", "원본 JSON"])
        with tabs[0]:
            for x in result.get("score_reason", []): st.write("•", x)
        with tabs[1]:
            st.dataframe(result.get("typos_and_style", []), use_container_width=True)
        with tabs[2]:
            st.dataframe(result.get("logical_contradictions", []), use_container_width=True)
        with tabs[3]:
            st.dataframe(result.get("numbers_dates_amounts", []), use_container_width=True)
        with tabs[4]:
            st.dataframe(result.get("missing_business_elements", []), use_container_width=True)
        with tabs[5]:
            st.dataframe(result.get("rewritten_examples", []), use_container_width=True)
        with tabs[6]:
            st.markdown("**원본 결과 보고서 (디스크 보관 정보)**")
            st.markdown(f"- **보관 파일 경로:** `{res_path}`")
            st.markdown(f"- **고유 식별 해시:** `{res_hash}`")
            
            # JSON 메타데이터 계산 (Preview)
            key_count = len(result.keys())
            char_count = len(json.dumps(result))
            st.markdown(f"- **데이터 볼륨:** 총 {key_count}개의 최상위 객체 키 (약 {char_count:,} 글자)")
            
            # 명시적 로드 체크박스
            if st.checkbox("원본 JSON 풀 버전 로드 (메모리 렌더링)", key="load_raw_json"):
                st.json(result)

        st.download_button(
            "분석 결과 JSON 다운로드",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name=f"{Path(uploaded.name).stem}_review.json",
            mime="application/json",
        )
else:
    st.info("PDF, DOCX, TXT 또는 MD 문서를 한 개 올리면 전처리 통계를 먼저 확인할 수 있습니다.")

