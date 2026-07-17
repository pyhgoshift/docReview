from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, asdict

IMPORTANT_TERMS = (
    "목표", "전략", "시장", "고객", "매출", "비용", "예산", "투자", "성과",
    "위험", "리스크", "일정", "담당", "계약", "수익", "성장", "실행", "가정",
)

@dataclass
class OptimizationStats:
    original_chars: int
    optimized_chars: int
    removed_duplicate_lines: int
    removed_blank_lines: int
    truncated: bool

    @property
    def reduction_percent(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return round((1 - self.optimized_chars / self.original_chars) * 100, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reduction_percent"] = self.reduction_percent
        return d

def normalize_line(line: str) -> str:
    # 1. 반복되는 긴 특수문자 구분선을 '---'로 단순화 (rtk식 구분선 압축)
    line = re.sub(r"[-=*#~]{4,}", "---", line)
    # 2. 마크다운 볼드 기호 중복 정리
    line = re.sub(r"\*{4,}", "**", line)
    # 3. 다중 탭 및 공백을 단일 공백으로 치환
    line = re.sub(r"[ \t]+", " ", line).strip()
    return line

def _line_score(line: str) -> int:
    score = 0
    if re.search(r"\d", line):
        score += 3
    score += sum(2 for term in IMPORTANT_TERMS if term in line)
    if re.match(r"^(#{1,6}\s|[0-9]+[.)]\s|[가-힣A-Za-z]+[:：])", line):
        score += 3
    if 15 <= len(line) <= 300:
        score += 1
    return score

def optimize_document(text: str, max_chars: int = 50000) -> tuple[str, OptimizationStats]:
    original_chars = len(text)
    
    # 4. 마크다운 주석 및 HTML 주석 제거 (rtk식 주석 필터링)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    
    # 5. 들여쓰기 공백 정규화 (4칸 공백 -> 2칸 공백으로 압축하여 구조는 유지하되 토큰 세이빙)
    lines_processed: list[str] = []
    for raw in text.splitlines():
        indent = re.match(r"^( +)", raw)
        if indent:
            spaces = len(indent.group(1))
            compressed_spaces = " " * (spaces // 2)
            raw = compressed_spaces + raw[spaces:]
        lines_processed.append(raw)
        
    seen: set[str] = set()
    unique_lines: list[str] = []
    removed_blank = 0
    removed_dup = 0

    for raw in lines_processed:
        line = normalize_line(raw)
        if not line:
            removed_blank += 1
            continue
        key = hashlib.sha1(line.lower().encode("utf-8")).hexdigest()
        if key in seen:
            removed_dup += 1
            continue
        seen.add(key)
        unique_lines.append(line)

    compact = "\n".join(unique_lines)
    truncated = len(compact) > max_chars

    if truncated:
        # RTK의 그룹화/절단 원리를 문서에 맞게 적용:
        # 문서 앞/뒤 문맥은 보존하고, 중간에서는 숫자·사업 핵심어·제목 문장을 우선 선택한다.
        head_budget = max_chars // 4
        tail_budget = max_chars // 8
        head = compact[:head_budget]
        tail = compact[-tail_budget:]
        middle_lines = unique_lines[max(1, len(unique_lines)//10): max(2, len(unique_lines)*9//10)]
        ranked = sorted(
            enumerate(middle_lines),
            key=lambda item: (_line_score(item[1]), -item[0]),
            reverse=True,
        )
        chosen: list[tuple[int, str]] = []
        budget = max_chars - len(head) - len(tail) - 200
        used = 0
        for idx, line in ranked:
            cost = len(line) + 1
            if used + cost > budget:
                continue
            chosen.append((idx, line))
            used += cost
            if used >= budget:
                break
        chosen.sort()
        middle = "\n".join(line for _, line in chosen)
        compact = (
            head
            + "\n\n[중간 구간: 중요 문장 우선 압축]\n"
            + middle
            + "\n\n[문서 마지막 구간]\n"
            + tail
        )[:max_chars]

    stats = OptimizationStats(
        original_chars=original_chars,
        optimized_chars=len(compact),
        removed_duplicate_lines=removed_dup,
        removed_blank_lines=removed_blank,
        truncated=truncated,
    )
    return compact, stats
