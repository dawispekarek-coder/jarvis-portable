"""Persistent state for the Devin bridge.

- Atomic JSON writes (write .tmp + os.replace; fsync before replace).
- Append-only JSONL event log for audit.
- Idempotent dispatch keys: sha256(task_id | prompt_sha | base_head).
  A task can only be dispatched once per (id, prompt, base commit) —
  a restart or duplicate call returns the existing record, never resends.
- Cross-process safety via an advisory sidecar lockfile (msvcrt.locking)
  so the daemon and the plugin/CLI cannot interleave a read-modify-write.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import msvcrt
import os
import time
from pathlib import Path
from typing import Any


import os

# Every CUI subprocess spawned from the bridge MUST use this — without
# it Windows allocates a transient console that flashes a black window
# on screen (user-reported) and can deliver CTRL_C (0xC000013A) when it
# tears down. Applies to git, test runners, tool launches — everything.
SUBPROCESS_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    blob = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
    # Windows: os.replace can transiently fail (sharing violation /
    # WinError 5) while a concurrent reader holds the destination open.
    # Retry briefly — the destination is never locked for long.
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON state, tolerating the brief window where a concurrent
    atomic_write_json's os.replace makes the file momentarily
    unreadable/half-visible on Windows. Retries ~0.5s before returning
    the default — a genuinely absent/corrupt file resolves the same way,
    just slower (correctness over micro-optimisation)."""
    last_err: Exception | None = None
    for _ in range(10):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(0.05)
    return default


def append_jsonl(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(record)
    rec.setdefault("ts", utcnow())
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    out = []
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def dispatch_key(task_id: str, prompt_sha: str, base_head: str) -> str:
    h = hashlib.sha256()
    h.update(task_id.encode("utf-8"))
    h.update(b"|")
    h.update(prompt_sha.encode("utf-8"))
    h.update(b"|")
    h.update((base_head or "").encode("utf-8"))
    return h.hexdigest()[:24]


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    """Advisory exclusive lock over a sidecar .lock file (Windows-safe)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
    try:
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.time() > deadline:
                    os.close(fd)
                    raise TimeoutError(f"lock timeout: {path.name}")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
