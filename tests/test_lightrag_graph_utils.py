from src.modules.lightraglocal.routes.graph_utils import build_relationship_edges


def test_build_relationship_edges_processes_every_relationship() -> None:
    nodes = [
        {"id": "1", "label": "A"},
        {"id": "2", "label": "B"},
        {"id": "3", "label": "C"},
    ]
    relationships = [
        {
            "src_id": "A",
            "tgt_id": "B",
            "content": "A\tB\nbusiness relationship\nworks with",
        },
        {
            "src_id": "B",
            "tgt_id": "C",
            "content": "B\tC\nproduct relationship\ncontains",
        },
    ]

    edges = build_relationship_edges(nodes, relationships)

    assert [(edge["source"], edge["target"]) for edge in edges] == [
        ("1", "2"),
        ("2", "3"),
    ]
    assert edges[0]["label"] == "商业关系 (works with)"
    assert edges[1]["label"] == "产品关系 (contains)"


def test_build_relationship_edges_skips_unknown_nodes() -> None:
    edges = build_relationship_edges(
        [{"id": "1", "label": "A"}],
        [{"src_id": "A", "tgt_id": "missing", "content": ""}],
    )

    assert edges == []
