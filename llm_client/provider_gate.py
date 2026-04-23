"""
ProviderGate — 每个 LLM 提供商的并发控制门。

用 threading.Semaphore 限制同时在途的 API 调用数，防止单一提供商被打满
触发 429 限流。默认每个提供商最多 3 路并发；可在代码或配置中覆盖。
"""

import threading
from typing import Dict

# 每提供商默认最大并发数（可通过 configure() 动态调整）
_DEFAULT_MAX_CONCURRENT = 3

_gates: Dict[str, threading.Semaphore] = {}
_lock = threading.Lock()


def _get_gate(provider: str) -> threading.Semaphore:
    with _lock:
        if provider not in _gates:
            _gates[provider] = threading.Semaphore(_DEFAULT_MAX_CONCURRENT)
        return _gates[provider]


def acquire(provider: str) -> None:
    """占用一个并发槽（阻塞直到有空位）。"""
    if provider:
        _get_gate(provider).acquire()


def release(provider: str) -> None:
    """释放一个并发槽。"""
    if provider:
        _get_gate(provider).release()


def configure(provider: str, max_concurrent: int) -> None:
    """覆盖指定提供商的并发上限（应在服务启动时调用）。"""
    with _lock:
        _gates[provider] = threading.Semaphore(max(1, max_concurrent))
