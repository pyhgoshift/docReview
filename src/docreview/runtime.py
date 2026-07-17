from __future__ import annotations
import json
import os
import time
import hashlib
from pathlib import Path

class CircuitOpenError(RuntimeError):
    pass

class CircuitBreaker:
    def __init__(self, state_file: Path, max_failures: int = 3, cooldown_seconds: int = 300):
        self.state_file = Path(state_file)
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self._ensure_dir()

    def _ensure_dir(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        if not self.state_file.exists():
            return {"failures": 0, "cooldown_until": 0.0}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"failures": 0, "cooldown_until": 0.0}

    def _save_state(self, state: dict):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def check_state(self):
        state = self._load_state()
        now = time.time()
        cooldown_until = state.get("cooldown_until", 0.0)
        
        if cooldown_until > now:
            remaining = int(cooldown_until - now)
            raise CircuitOpenError(
                f"연속 실패 보호가 작동 중입니다. 약 {remaining}초 후 다시 시도하십시오."
            )

    def record_failure(self):
        state = self._load_state()
        state["failures"] = state.get("failures", 0) + 1
        
        if state["failures"] >= self.max_failures:
            state["cooldown_until"] = time.time() + self.cooldown_seconds
        
        self._save_state(state)

    def record_success(self):
        state = self._load_state()
        state["failures"] = 0
        state["cooldown_until"] = 0.0
        self._save_state(state)

    def get_remaining_cooldown(self) -> int:
        state = self._load_state()
        now = time.time()
        cooldown_until = state.get("cooldown_until", 0.0)
        if cooldown_until > now:
            return int(cooldown_until - now)
        return 0


class ArtifactManager:
    def __init__(self, base_dir: Path):
        self.artifacts_dir = Path(base_dir) / "runtime" / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def save_raw(self, filename: str, content: str) -> tuple[Path, str]:
        stem = Path(filename).stem
        h = self._calculate_hash(content)
        file_path = self.artifacts_dir / f"{stem}-raw-{h}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path, h

    def save_optimized(self, filename: str, content: str) -> tuple[Path, str]:
        stem = Path(filename).stem
        h = self._calculate_hash(content)
        file_path = self.artifacts_dir / f"{stem}-optimized-{h}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path, h

    def save_result(self, filename: str, content: dict) -> tuple[Path, str]:
        stem = Path(filename).stem
        json_str = json.dumps(content, ensure_ascii=False, indent=2)
        h = self._calculate_hash(json_str)
        file_path = self.artifacts_dir / f"{stem}-result-{h}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return file_path, h
