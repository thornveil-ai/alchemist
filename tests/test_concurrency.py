"""Concurrency recognition + safe-Rust mapping (typing, not verification)."""

from alchemist.autonomy.concurrency import (
    detect_concurrency, map_primitive, shared_state_type, concurrency_plan,
)

SRC = ("pthread_mutex_t lock;\n"
       "void worker(void) {\n"
       "    pthread_mutex_lock(&lock);\n    counter++;\n    pthread_mutex_unlock(&lock);\n}\n"
       "void start(void) {\n    pthread_t th;\n    pthread_create(&th, 0, worker, 0);\n"
       "    pthread_join(th, 0);\n}\n")


def test_detect_concurrency_primitives():
    prims = detect_concurrency(SRC)
    assert "pthread_mutex_lock" in prims and "pthread_create" in prims and "pthread_join" in prims


def test_map_primitive_to_safe_rust():
    assert "Mutex" in map_primitive("pthread_mutex_t")
    assert "thread::spawn" in map_primitive("pthread_create")
    assert map_primitive("atomic_fetch_add").startswith(".fetch_add")
    assert map_primitive("not_a_primitive") is None


def test_shared_state_is_arc_mutex():
    assert shared_state_type("i32") == "std::sync::Arc<std::sync::Mutex<i32>>"


def test_concurrency_plan_flags_review():
    plan = concurrency_plan(SRC)
    assert "pthread_mutex_lock" in plan["mapping"]
    assert plan["shared_state"] is not None      # threads spawned -> shared state note
    assert plan["needs_review"] is True          # non-deterministic -> not byte-exact verifiable
