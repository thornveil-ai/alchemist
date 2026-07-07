"""Concurrency & thread-safety — the last major out-of-scope class.

C hands thread-safety to the programmer (pthread mutexes, raw shared globals, manual
atomics); Rust encodes it in the type system (Mutex, Arc, Atomic, Send/Sync). This
RECOGNIZES the concurrency primitives a function uses and maps each to its safe-Rust
equivalent, and flags shared mutable state that must become `Arc<Mutex<T>>`.

Honest scope: recognition + typing is tractable and useful (it turns a blanket
'refused' into a concrete migration plan). Differentially VERIFYING concurrent
behavior is genuinely hard — thread interleavings are non-deterministic, so the
byte-exact oracle doesn't directly apply — and stays the deep frontier. What we can
promise here is a correct, safe MAPPING, clearly labelled as needing review.
"""

from __future__ import annotations

import re

# C concurrency primitive -> safe-Rust equivalent
_MAP = {
    "pthread_mutex_t": "std::sync::Mutex<T>",
    "pthread_mutex_lock": ".lock().unwrap()  // guard drops -> unlock",
    "pthread_mutex_unlock": "drop(guard)",
    "pthread_mutex_init": "Mutex::new(..)",
    "pthread_t": "std::thread::JoinHandle<T>",
    "pthread_create": "std::thread::spawn",
    "pthread_join": ".join().unwrap()",
    "pthread_cond_t": "std::sync::Condvar",
    "pthread_rwlock_t": "std::sync::RwLock<T>",
    "sem_t": "std::sync::Condvar  // or a semaphore crate",
    "atomic_int": "std::sync::atomic::AtomicI32",
    "atomic_uint": "std::sync::atomic::AtomicU32",
    "_Atomic": "std::sync::atomic::Atomic*",
    "atomic_load": ".load(Ordering::SeqCst)",
    "atomic_store": ".store(v, Ordering::SeqCst)",
    "atomic_fetch_add": ".fetch_add(v, Ordering::SeqCst)",
}

_CONC = re.compile(r"\b(pthread_\w+|pthread_[a-z]+_t|sem_\w+|_Atomic|atomic_\w+|"
                   r"mtx_\w+|thrd_\w+|cnd_\w+)\b")


def detect_concurrency(src: str) -> list[str]:
    """The concurrency primitives a snippet uses (deduped, sorted)."""
    return sorted(set(m.group(0) for m in _CONC.finditer(src)))


def map_primitive(c_name: str) -> str | None:
    """The safe-Rust equivalent of a C concurrency primitive, or None if unknown."""
    return _MAP.get(c_name)


def shared_state_type(inner_rust: str) -> str:
    """Shared mutable state crossing threads must be Arc<Mutex<T>> for Send+Sync."""
    return "std::sync::Arc<std::sync::Mutex<%s>>" % inner_rust


def concurrency_plan(src: str) -> dict:
    """A migration plan for a concurrent function: each primitive it uses -> its safe
    Rust mapping, plus the thread-safety note. `needs_review` because concurrent
    behavior can't be differentially verified byte-exact."""
    prims = detect_concurrency(src)
    mapping = {p: map_primitive(p) for p in prims if map_primitive(p)}
    uses_threads = any(p.startswith(("pthread", "thrd_")) for p in prims)
    return {
        "primitives": prims,
        "mapping": mapping,
        "shared_state": shared_state_type("_") if uses_threads else None,
        "needs_review": True,   # non-deterministic -> not byte-exact verifiable
    }
