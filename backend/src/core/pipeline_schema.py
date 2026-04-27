from __future__ import annotations

from .pipeline_node_defs import NODE_TYPES

RETRIEVAL_TYPES = frozenset(k for k, v in NODE_TYPES.items() if v["category"] == "retrieval")
GENERATION_TYPES = frozenset(k for k, v in NODE_TYPES.items() if v["category"] == "generation")
CONTROL_TYPES = frozenset(k for k, v in NODE_TYPES.items() if v["category"] == "control")


def validate_pipeline(nodes: list[dict], edges: list[dict]) -> dict:
    """验证链路合法性，返回 {valid, errors}。"""
    errors: list[str] = []

    if not nodes:
        return {"valid": False, "errors": ["链路不能为空"]}

    node_map: dict[str, str] = {}  # node_id -> node_type
    for n in nodes:
        nid = n.get("id", "")
        ntype = n.get("data", {}).get("nodeType", "")
        if ntype not in NODE_TYPES:
            errors.append(f"未知节点类型：{ntype}")
        node_map[nid] = ntype

    # 1. 至少一个检索节点
    retrieval_nodes = [nid for nid, nt in node_map.items() if nt in RETRIEVAL_TYPES]
    if not retrieval_nodes:
        errors.append("至少需要一个检索节点")

    # 2. 有且仅有一个生成节点（控制节点不计入）
    gen_nodes = [nid for nid, nt in node_map.items() if nt in GENERATION_TYPES]
    if not gen_nodes:
        errors.append("缺少生成节点（LLM生成、摘要生成等）")
    elif len(gen_nodes) > 1:
        errors.append(f"只能有一个生成节点，当前有 {len(gen_nodes)} 个")

    # 3. 连线端口类型匹配
    for edge in edges:
        src_id = edge.get("source", "")
        tgt_id = edge.get("target", "")
        src_handle = edge.get("sourceHandle") or ""
        tgt_handle = edge.get("targetHandle") or ""

        src_nt = node_map.get(src_id, "")
        tgt_nt = node_map.get(tgt_id, "")
        if not src_nt or not tgt_nt:
            errors.append("连线引用了不存在的节点")
            continue

        src_outputs = NODE_TYPES[src_nt]["outputs"]
        tgt_inputs = NODE_TYPES[tgt_nt]["inputs"]

        port = src_handle or (src_outputs[0] if len(src_outputs) == 1 else "")
        if port and port not in src_outputs:
            errors.append(f"节点「{NODE_TYPES[src_nt]['label']}」没有输出端口「{port}」")
        if tgt_handle and tgt_handle not in tgt_inputs:
            errors.append(f"节点「{NODE_TYPES[tgt_nt]['label']}」没有输入端口「{tgt_handle}」")
        if not set(src_outputs) & set(tgt_inputs):
            src_lbl = NODE_TYPES[src_nt]["label"]
            tgt_lbl = NODE_TYPES[tgt_nt]["label"]
            errors.append(f"「{src_lbl}」→「{tgt_lbl}」端口类型不兼容：{src_outputs} 无法连接到 {tgt_inputs}")

    # 4. 孤立节点
    if len(node_map) > 1:
        connected: set[str] = set()
        for edge in edges:
            connected.add(edge.get("source", ""))
            connected.add(edge.get("target", ""))
        for nid in node_map:
            if nid not in connected:
                label = NODE_TYPES.get(node_map[nid], {}).get("label", nid)
                errors.append(f"节点「{label}」是孤立节点，请连接到链路中")

    # 5. 环路检测（DFS）—— 反馈循环节点本身标记为允许环
    non_loop_nodes = {nid for nid, nt in node_map.items() if nt != "feedback_loop"}
    adj: dict[str, list[str]] = {nid: [] for nid in node_map}
    for edge in edges:
        src, tgt = edge.get("source", ""), edge.get("target", "")
        if src in adj and tgt in non_loop_nodes:
            adj[src].append(tgt)

    visited: set[str] = set()
    in_stack: set[str] = set()
    has_cycle = False

    def _dfs(nid: str) -> None:
        nonlocal has_cycle
        visited.add(nid)
        in_stack.add(nid)
        for nb in adj.get(nid, []):
            if nb not in visited:
                _dfs(nb)
            elif nb in in_stack:
                has_cycle = True
        in_stack.discard(nid)

    for nid in node_map:
        if nid not in visited:
            _dfs(nid)

    if has_cycle:
        errors.append("链路中存在循环依赖，请检查连线方向")

    return {"valid": len(errors) == 0, "errors": errors}
