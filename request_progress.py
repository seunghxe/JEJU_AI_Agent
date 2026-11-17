"""Ephemeral progress only: no prompts, locations or credentials are retained."""
from contextvars import ContextVar
from threading import Lock
from time import monotonic

active = ContextVar("request_progress", default=None)
_rows = {}
_lock = Lock()

def mark(step):
    token = active.get()
    if not token:
        return
    with _lock:
        now = monotonic()
        if step == 1:
            for k in list(_rows):
                if now - _rows[k][0] > 120:
                    _rows.pop(k)
            if len(_rows) >= 2048:
                _rows.pop(next(iter(_rows)))
        _rows[token] = (now, step)

def get(token):
    with _lock:
        ts, stage = _rows.get(token, (0, 0))
        return stage if monotonic() - ts < 120 else 0
