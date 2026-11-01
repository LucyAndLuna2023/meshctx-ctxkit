import json
import time

import pytest

from meshctx_ctxkit.memory import MemoryStore, _tokenize


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(root=tmp_path / "ctx")


def test_remember_and_recall_basic(store):
    store.remember("Deploy bot to server 003 every Friday", tags=["ops"])
    store.remember("Quant V4 uses moving take-profit 8 percent", tags=["quant"])
    hits = store.recall("deploy friday")
    assert hits, "should find the deploy note"
    assert "003" in hits[0]["text"]


def test_recall_bm25_ranks_better_match_first(store):
    # BM25 normalises by length, so a doubled term is NOT automatically a
    # better hit (b=0.75 keeps length normalisation live). "stripe" is in
    # both docs; only "mcp" is in the second, so "stripe mcp" must prefer it.
    store.remember("stripe billing integration")
    store.remember("stripe billing integration for the mcp server stripe keys")
    hits = store.recall("stripe mcp")
    assert len(hits) == 2
    assert "mcp" in hits[0]["text"]
    assert hits[0]["score"] >= hits[1]["score"]
    # pure "stripe" query still returns both, highest score first
    both = store.recall("stripe")
    assert both[0]["score"] >= both[1]["score"]


def test_exact_phrase_hit_ranks_first(store):
    store.remember("deploy notes for server 003")
    store.remember("deploy notes for a totally unrelated topic with many words "
                   "that dilute the score across the document length")
    hits = store.recall("deploy notes for server 003")
    assert "server 003" in hits[0]["text"]


def test_cjk_retrieval(store):
    store.remember("MeshCtx 是本地优先的跨会话记忆代理")
    hits = store.recall("记忆")
    assert hits and "MeshCtx" in hits[0]["text"]


def test_empty_and_overlong_input_rejected(store):
    with pytest.raises(ValueError):
        store.remember("   ")
    with pytest.raises(ValueError):
        store.remember("x" * 100_001)


def test_forget_removes_from_index_and_disk(store):
    mem = store.remember("temporary note")
    assert store.recall("temporary")
    assert store.forget(mem.id) is True
    assert store.recall("temporary") == []
    assert store.forget(mem.id) is False  # second delete is a no-op
    # persistence: new instance must not resurrect it
    store2 = MemoryStore(root=store.path.parent)
    assert store2.recall("temporary") == []


def test_persistence_across_instances(tmp_path):
    s1 = MemoryStore(root=tmp_path / "c")
    s1.remember("persist me please", tags=["t1"])
    s2 = MemoryStore(root=tmp_path / "c")
    assert s2.recall("persist")
    assert s2.stats()["count"] == 1
    assert "t1" in s2.stats()["tags"]


def test_torn_last_line_does_not_break_load(tmp_path):
    p = tmp_path / "c"
    s = MemoryStore(root=p)
    s.remember("good line")
    with s.path.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "torn", "text": "trun')  # simulate a crash mid-write
    s2 = MemoryStore(root=p)
    assert s2.stats()["count"] == 1
    assert s2.recall("good")


def test_tokenize_cjk_split_per_char():
    assert "记" in _tokenize("记忆")
    assert "memory" in _tokenize("Memory!")


def test_tags_filter(store):
    store.remember("alpha doc", tags=["a"])
    store.remember("beta doc", tags=["b"])
    assert store.recall("doc", tags=["a"])[0]["text"] == "alpha doc"
    assert store.recall("doc", tags=["b"])[0]["text"] == "beta doc"
    assert len(store.recall("doc")) == 2


def test_age_days_recorded(store):
    store.remember("fresh")
    time.sleep(0.01)
    assert store.recall("fresh")[0]["age_days"] >= 0
