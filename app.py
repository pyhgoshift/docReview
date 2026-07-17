from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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
    base_url = st.text_input("Base URL", os.getenv("TUFTECH_BASE_URL", "https://api.tuftech.org"))
    model_options = [
        "claude-sonnet-4-6 (Sonnet)",
        "claude-fable-5 (Fable 5)",
        "claude-opus-4-8 (Opus 4.8)",
        "gpt-5-6 (GPT 5.6)",
        "codex-cl (Codex CL)",
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
        "모델 선택",
        model_options,
        index=default_index
    )

    if "직접 입력" in selected_model_opt:
        model = st.text_input("모델명 직접 입력", value="" if env_model in ["claude-sonnet-4-6", "claude-fable-5", "claude-opus-4-8", "gpt-5-6", "codex-cl"] else env_model)
    else:
        model = selected_model_opt.split(" ")[0]
    api_format = st.selectbox(
        "API 형식",
        ["anthropic", "openai"],
        index=0 if os.getenv("TUFTECH_API_FORMAT", "anthropic") == "anthropic" else 1,
    )
    auth_mode = st.selectbox(
        "인증 방식",
        ["bearer", "x-api-key"],
        index=0 if os.getenv("TUFTECH_AUTH_MODE", "bearer") == "bearer" else 1,
    )
    env_key = os.getenv("TUFTECH_API_KEY", "")
    api_key = st.text_input("API 키", value=env_key, type="password")
    max_chars = st.number_input(
        "API 전송 최대 문자 수",
        min_value=10000,
        max_value=200000,
        value=int(os.getenv("DOCREVIEW_MAX_INPUT_CHARS", "50000")),
        step=5000,
        help="문서가 길면 중요 문장을 우선 선택하여 이 크기로 압축합니다.",
    )
    st.info("API 키는 화면에 표시되지 않습니다. `.env` 파일은 GitHub에 올리지 마십시오.")

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

        prompt = build_prompt(optimized, facts, uploaded.name)
        with st.spinner("AI가 문서를 분석하고 있습니다..."):
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

        st.success("분석이 완료되었습니다.")
        
        # 캐시 상태 시각화
        st.subheader("프롬프트 캐싱 상태")
        ch1, ch2, ch3 = st.columns(3)
        ch1.metric("캐시 요청 여부 (requested)", str(cache_status["requested"]))
        ch2.metric("캐시 지원 여부 (supported)", str(cache_status["supported"]))
        ch3.metric("비캐시 재시도 여부 (fallback_used)", str(cache_status["fallback_used"]))

        if usage:
            st.json(usage)

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
            st.json(result)

        st.download_button(
            "분석 결과 JSON 다운로드",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name=f"{Path(uploaded.name).stem}_review.json",
            mime="application/json",
        )
else:
    st.info("PDF, DOCX, TXT 또는 MD 문서를 한 개 올리면 전처리 통계를 먼저 확인할 수 있습니다.")

