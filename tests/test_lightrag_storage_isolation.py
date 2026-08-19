import pytest
import json

from src.modules.lightraglocal.services import enterprise_lightrag_service  # noqa: F401
from src.modules.lightraglocal.storage.rag_storage_adapter import RAGStorageAdapter
from lightrag.kg.json_kv_impl import JsonKVStorage
from lightrag.kg.shared_storage import finalize_share_data, initialize_share_data


@pytest.mark.asyncio
async def test_json_kv_shared_memory_is_scoped_by_workspace(tmp_path) -> None:
    finalize_share_data()


@pytest.mark.asyncio
async def test_legacy_project_cache_is_sanitized_from_its_own_vector_index(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("RAG_DIR", str(tmp_path))
    project_id = "project-a"
    data_dir = tmp_path / f"project_{project_id}" / f"project_{project_id}"
    data_dir.mkdir(parents=True)

    (data_dir / "vdb_chunks.json").write_text(
        json.dumps(
            {
                "embedding_dim": 3,
                "data": [
                    {
                        "__id__": "chunk-own",
                        "full_doc_id": "doc-own",
                        "content": "own content",
                    }
                ],
                "matrix": [],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "kv_store_full_docs.json").write_text(
        json.dumps({"doc-own": {"content": "own"}, "doc-other": {"content": "leaked"}}),
        encoding="utf-8",
    )
    (data_dir / "kv_store_text_chunks.json").write_text(
        json.dumps({"chunk-own": {"content": "own"}, "chunk-other": {"content": "leaked"}}),
        encoding="utf-8",
    )
    (data_dir / "kv_store_doc_status.json").write_text(
        json.dumps({"doc-own": {"status": "processed"}, "doc-other": {"status": "processed"}}),
        encoding="utf-8",
    )
    (data_dir / "kv_store_llm_response_cache.json").write_text(
        json.dumps({"global:query:shared": {"return": "leaked answer"}}),
        encoding="utf-8",
    )

    adapter = RAGStorageAdapter(project_id, storage_type="local")
    await adapter.initialize_storage()

    assert json.loads((data_dir / "kv_store_full_docs.json").read_text()) == {
        "doc-own": {"content": "own"}
    }
    assert json.loads((data_dir / "kv_store_text_chunks.json").read_text()) == {
        "chunk-own": {"content": "own"}
    }
    assert json.loads((data_dir / "kv_store_doc_status.json").read_text()) == {
        "doc-own": {"status": "processed"}
    }
    assert json.loads((data_dir / "kv_store_llm_response_cache.json").read_text()) == {}
    assert (data_dir / ".workspace_isolation_v2.json").is_file()
    initialize_share_data()

    storage_a = JsonKVStorage(
        namespace="full_docs",
        workspace="project_a",
        global_config={"working_dir": str(tmp_path / "a")},
        embedding_func=None,
    )
    storage_b = JsonKVStorage(
        namespace="full_docs",
        workspace="project_b",
        global_config={"working_dir": str(tmp_path / "b")},
        embedding_func=None,
    )
    await storage_a.initialize()
    await storage_b.initialize()

    await storage_a.upsert({"doc-a": {"content": "only project a"}})

    assert await storage_a.get_by_id("doc-a") is not None
    assert await storage_b.get_by_id("doc-a") is None

    finalize_share_data()
