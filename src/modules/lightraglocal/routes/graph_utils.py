from typing import Any, Dict, Iterable, List


def build_relationship_edges(
    nodes: Iterable[Dict[str, Any]],
    relationships: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert every stored relationship into a visual edge when both nodes exist."""
    node_list = list(nodes)
    entity_name_to_id = {
        node.get("label", ""): node["id"]
        for node in node_list
        if node.get("label") and node.get("id") is not None
    }
    node_ids = {node["id"] for node in node_list if node.get("id") is not None}
    edges: List[Dict[str, Any]] = []

    relation_mapping = {
        "athlete activity,event location": "运动活动与场地关系",
        "athlete activity": "运动活动",
        "event location": "活动地点",
        "product relationship": "产品关系",
        "business relationship": "商业关系",
        "organizational relationship": "组织关系",
    }

    for relationship in relationships:
        source_name = relationship.get("src_id")
        target_name = relationship.get("tgt_id")
        source_id = entity_name_to_id.get(source_name, source_name)
        target_id = entity_name_to_id.get(target_name, target_name)
        if source_id not in node_ids or target_id not in node_ids:
            continue

        relation_type = "关联"
        content = relationship.get("content", "")
        if content:
            lines = content.split("\n")
            if len(lines) >= 2 and lines[1].strip():
                keywords = lines[1].strip()
                relation_type = relation_mapping.get(keywords, keywords)
            if len(lines) >= 3 and lines[2].strip():
                relation_type = f"{relation_type} ({lines[2][:80]})"

        edges.append(
            {
                "source": str(source_id),
                "target": str(target_id),
                "label": str(relation_type),
                "type": "relationship",
                "properties": relationship,
            }
        )

    return edges
