from docreview.optimizer import optimize_document
from docreview.local_checks import extract_facts

def test_duplicate_removal():
    text = "매출 목표는 10억원이다.\n\n매출 목표는 10억원이다.\n일정은 2026-12-31이다."
    optimized, stats = optimize_document(text, max_chars=1000)
    assert optimized.count("매출 목표") == 1
    assert stats.removed_duplicate_lines == 1

def test_max_chars():
    text = "\n".join(f"{i}번째 사업 목표와 매출 100억원 계획" for i in range(5000))
    optimized, stats = optimize_document(text, max_chars=10000)
    assert len(optimized) <= 10000
    assert stats.truncated is True

def test_extract_facts():
    facts = extract_facts("일정은 2026-12-31, 예산은 3억원이며 목표는 20%다.")
    assert "2026-12-31" in facts["dates"]
    assert any("3억원" in x for x in facts["amounts_and_rates"])
