from __future__ import annotations
import json

SYSTEM_PROMPT = """당신은 한국어 사업 문서 전문 검토자다.
추측하지 말고 제공된 문서 안의 근거만 사용하라.
반드시 유효한 JSON 객체 하나만 출력하라. Markdown 코드펜스를 사용하지 마라.
오류가 없으면 빈 배열을 반환하라.
문장 인용은 필요한 최소 길이로 제한하라."""

def build_prompt(document_text: str, local_facts: dict, filename: str) -> str:
    schema = {
        "score": 0,
        "grade": "A/B/C/D/F",
        "executive_summary": "핵심 요약",
        "score_reason": ["점수 근거"],
        "priority_actions": [
            {"severity": "critical/high/medium/low", "title": "항목", "reason": "이유", "suggestion": "수정 방향"}
        ],
        "typos_and_style": [
            {"original": "원문", "issue": "문제", "suggested": "수정문"}
        ],
        "logical_contradictions": [
            {"statement_a": "문장 A", "statement_b": "문장 B", "explanation": "충돌 이유", "resolution": "해결안"}
        ],
        "numbers_dates_amounts": [
            {"evidence": "근거", "issue": "불일치 가능성", "suggestion": "확인 또는 수정안"}
        ],
        "missing_business_elements": [
            {"element": "누락 요소", "why_it_matters": "중요성", "suggestion": "추가 내용"}
        ],
        "rewritten_examples": [
            {"before": "원문", "after": "개선문", "reason": "개선 이유"}
        ],
        "disclaimer": "AI 검토이므로 최종 사실 확인 필요"
    }
    return f"""파일명: {filename}

분석 지침:
1. 사업 문서의 완성도를 0~100점으로 평가한다.
2. 오타·띄어쓰기·어색한 표현을 찾고 수정문을 제시한다.
3. 문서 내부의 논리적 모순, 목표와 실행계획의 충돌, 근거 없는 결론을 찾는다.
4. 날짜·금액·비율·인원·합계의 불일치 가능성을 찾는다.
5. 목표 고객, 가치제안, 시장 근거, 수익모델, 실행계획, KPI, 리스크 등 누락된 사업 요소를 찾는다.
6. 치명적·중요한 문제를 우선한다. 사소한 표현을 과도하게 나열하지 않는다.
7. 아래 JSON 구조와 동일한 키를 사용한다.

출력 구조:
{json.dumps(schema, ensure_ascii=False)}

로컬에서 미리 추출한 숫자/날짜 후보:
{json.dumps(local_facts, ensure_ascii=False)}

분석할 문서:
---BEGIN DOCUMENT---
{document_text}
---END DOCUMENT---
"""
