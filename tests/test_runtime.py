from __future__ import annotations
import time
import json
from pathlib import Path
import pytest
from docreview.runtime import CircuitBreaker, CircuitOpenError, ArtifactManager

def test_circuit_breaker_success_reset(tmp_path):
    state_file = tmp_path / "circuit_state.json"
    cb = CircuitBreaker(state_file, max_failures=3, cooldown_seconds=2)
    
    # 기본 상태 확인
    cb.check_state()
    
    # 2회 실패 기록
    cb.record_failure()
    cb.record_failure()
    cb.check_state()  # 아직 max_failures 미만이므로 허용
    
    # 성공 기록 -> 리셋
    cb.record_success()
    cb.check_state()

def test_circuit_breaker_cooldown_trigger(tmp_path):
    state_file = tmp_path / "circuit_state.json"
    cb = CircuitBreaker(state_file, max_failures=3, cooldown_seconds=2)
    
    # 3회 연속 실패 기록
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    
    # 서킷 오픈되어 check_state가 예외를 던져야 함
    with pytest.raises(CircuitOpenError) as excinfo:
        cb.check_state()
    assert "연속 실패 보호" in str(excinfo.value)
    
    # 2초 쿨다운 대기 후 재확인
    time.sleep(2.1)
    cb.check_state()  # 예외 없이 통과해야 함

def test_artifact_manager_save(tmp_path):
    manager = ArtifactManager(tmp_path)
    
    # 원문 저장
    raw_path, raw_hash = manager.save_raw("test_doc.md", "hello world raw")
    assert raw_path.exists()
    assert "-raw-" in raw_path.name
    assert raw_hash == "f93e23961a26d01b"  # sha256 16자 해시
    
    # 최적화 저장
    opt_path, opt_hash = manager.save_optimized("test_doc.md", "hello optimized")
    assert opt_path.exists()
    assert "-optimized-" in opt_path.name
    
    # 결과 저장
    res_path, res_hash = manager.save_result("test_doc.md", {"score": 90, "grade": "A"})
    assert res_path.exists()
    assert "-result-" in res_path.name
    with open(res_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["score"] == 90
