"""
src/services/counterfactual.py
反事实图查询服务

支持"如果去掉 X 工序，Y 零件还能满足 Z 要求吗？"类型的假设推理：
1. LLM 解析问题中的反事实意图（被去掉的实体、受影响的主体、目标要求）
2. 图谱遍历：找到该实体关联的章节 → 约束节点 → 替代路径
3. 构建因果链上下文，交给 LLM 进行推理
"""
import json
import logging
import re
import requests
from neo4j import Driver
from ..core.config import settings

logger = logging.getLogger(__name__)

# ── 类型标签映射 ──────────────────────────────────────────────
_TYPE_CN = {
    "Process":    "工艺/工序",
    "Tool":       "工具",
    "Material":   "材料",
    "Constraint": "约束条件",
}

# ── 关系标签映射 ──────────────────────────────────────────────
_REL_CN = {
    "INVOLVES_PROCESS": "包含工序",
    "REQUIRES_TOOL":    "需要工具",
    "USES_MATERIAL":    "使用材料",
}


def _call_llm(prompt: str, timeout: int = 30) -> str:
    """调用 LLM（复用 settings 配置）"""
    res = requests.post(
        f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model":    settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream":   False,
        },
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def parse_counterfactual_intent(question: str) -> dict:
    """
    用 LLM 解析反事实问题中的关键实体。
    返回:
        removed_type  — Process | Tool | Material | unknown
        removed_name  — 被去掉的实体名称
        subject       — 受影响的零件/产品
        requirement   — 需要满足的要求/标准
    """
    prompt = f"""从以下反事实假设问题中提取关键信息，返回 JSON（只输出 JSON，不要有其他文字）。

问题：{question}

返回格式：
{{
  "removed_type": "Process 或 Tool 或 Material 或 unknown",
  "removed_name": "被去掉/省略/移除的具体名称（字符串）",
  "subject": "受影响的零件或产品（若问题中未提及则为空字符串）",
  "requirement": "需要满足的技术要求或标准（若未提及则为空字符串）"
}}

示例：
Q: "如果去掉热处理工序，铝合金蒙皮还能满足强度要求吗？"
A: {{"removed_type":"Process","removed_name":"热处理","subject":"铝合金蒙皮","requirement":"强度要求"}}

Q: "省略打孔前脱脂步骤，铆钉连接处是否仍满足密封标准？"
A: {{"removed_type":"Process","removed_name":"脱脂","subject":"铆钉连接处","requirement":"密封标准"}}

Q: "不用扭矩扳手，螺栓装配能否满足力矩要求？"
A: {{"removed_type":"Tool","removed_name":"扭矩扳手","subject":"螺栓装配","requirement":"力矩要求"}}

Q: "如果用普通铝合金代替钛合金，零件还能符合强度标准吗？"
A: {{"removed_type":"Material","removed_name":"钛合金","subject":"零件","requirement":"强度标准"}}"""

    try:
        raw   = _call_llm(prompt)
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning("反事实意图解析失败: %s", e)

    # 降级：关键词提取
    return _extract_intent_by_keywords(question)


def _extract_intent_by_keywords(question: str) -> dict:
    """LLM 解析失败时的关键词降级方案"""
    removed_name = ""
    removed_type = "unknown"

    # 尝试从 "去掉X"、"省略X"、"不用X" 等模式提取
    patterns = [
        r"(?:去掉|省略|移除|不用|取消|跳过)[了的]?([^，。,\s]{2,10}?)(?:工序|步骤|处理|工具|材料)",
        r"(?:如果|假设|假如)(?:没有|不[使用做进行])[了的]?([^，。,\s]{2,10})",
    ]
    for p in patterns:
        m = re.search(p, question)
        if m:
            removed_name = m.group(1)
            break

    return {
        "removed_type": removed_type,
        "removed_name": removed_name,
        "subject":      "",
        "requirement":  "",
    }


def get_causal_chain(driver: Driver, entity_name: str, entity_type: str) -> dict:
    """
    图谱遍历：从被移除的实体出发，获取：
    - 受影响的章节（affected_sections）
    - 关键约束节点（constraints）
    - 替代方案（alternatives / compatible）

    返回结构：
    {
        entity_name, entity_type,
        affected_sections: [{chunk_id, number, title, doc_id, rel_type, constraints}],
        constraints:       [{type, value, value_max, unit, description}],
        alternatives:      [str],
    }
    """
    result: dict = {
        "entity_name":       entity_name,
        "entity_type":       entity_type,
        "affected_sections": [],
        "constraints":       [],
        "alternatives":      [],
    }

    if not entity_name or len(entity_name) < 2:
        return result

    try:
        with driver.session() as session:

            # ── 1. 关联章节 + 约束 ──────────────────────────────────
            chain_q = session.run("""
                MATCH (e)
                WHERE (e:Process OR e:Tool OR e:Material)
                  AND toLower(e.name) CONTAINS toLower($name)
                WITH e LIMIT 5
                MATCH (s:Section)-[r:INVOLVES_PROCESS|REQUIRES_TOOL|USES_MATERIAL]-(e)
                OPTIONAL MATCH (s)-[:HAS_CONSTRAINT]->(c:Constraint)
                WITH s, e, type(r) AS rel_type,
                     collect(DISTINCT {
                         type:        c.type,
                         value:       c.value,
                         value_max:   c.value_max,
                         unit:        c.unit,
                         description: c.description
                     }) AS cons
                RETURN
                    e.name     AS entity,
                    rel_type,
                    s.chunk_id AS chunk_id,
                    s.number   AS number,
                    s.title    AS title,
                    s.doc_id   AS doc_id,
                    cons
                ORDER BY s.doc_id, s.number
                LIMIT 12
            """, name=entity_name)

            seen: set[str] = set()
            all_constraints: list[dict] = []

            for row in chain_q:
                cid = row["chunk_id"]
                if cid in seen:
                    continue
                seen.add(cid)

                valid_cons = [
                    c for c in row["cons"]
                    if c and (c.get("type") or c.get("description"))
                ]

                result["affected_sections"].append({
                    "chunk_id":    cid,
                    "number":      row["number"] or "",
                    "title":       row["title"]  or "",
                    "doc_id":      row["doc_id"] or "",
                    "rel_type":    row["rel_type"] or "",
                    "rel_type_cn": _REL_CN.get(row["rel_type"] or "", row["rel_type"] or ""),
                    "constraints": valid_cons,
                })
                all_constraints.extend(valid_cons)

            result["constraints"] = all_constraints[:10]

            # ── 2. 替代方案 ──────────────────────────────────────────
            alt_q = session.run("""
                MATCH (e)
                WHERE (e:Process OR e:Tool OR e:Material)
                  AND toLower(e.name) CONTAINS toLower($name)
                WITH e LIMIT 3
                OPTIONAL MATCH (e)-[:ALTERNATIVE_TO]-(alt)
                OPTIONAL MATCH (e)-[:COMPATIBLE_WITH]-(compat)
                RETURN
                    collect(DISTINCT alt.name)    AS alternatives,
                    collect(DISTINCT compat.name) AS compatible
            """, name=entity_name)

            alt_row = alt_q.single()
            if alt_row:
                alts   = [a for a in (alt_row["alternatives"] or []) if a]
                compts = [c for c in (alt_row["compatible"]   or []) if c]
                result["alternatives"] = list(dict.fromkeys(alts + compts))

            # ── 3. 广度回退：若无关联章节，用全文匹配章节 ──────────────
            if not result["affected_sections"]:
                fallback_q = session.run("""
                    MATCH (s:Section)
                    WHERE toLower(s.content) CONTAINS toLower($name)
                       OR toLower(s.title)   CONTAINS toLower($name)
                    OPTIONAL MATCH (s)-[:HAS_CONSTRAINT]->(c:Constraint)
                    WITH s, collect(DISTINCT {
                             type:        c.type,
                             value:       c.value,
                             value_max:   c.value_max,
                             unit:        c.unit,
                             description: c.description
                         }) AS cons
                    RETURN
                        s.chunk_id AS chunk_id,
                        s.number   AS number,
                        s.title    AS title,
                        s.doc_id   AS doc_id,
                        cons
                    ORDER BY s.doc_id, s.number
                    LIMIT 8
                """, name=entity_name)

                seen2: set[str] = set()
                for row in fallback_q:
                    cid = row["chunk_id"]
                    if not cid or cid in seen2:
                        continue
                    seen2.add(cid)
                    valid_cons = [
                        c for c in row["cons"]
                        if c and (c.get("type") or c.get("description"))
                    ]
                    result["affected_sections"].append({
                        "chunk_id":    cid,
                        "number":      row["number"] or "",
                        "title":       row["title"]  or "",
                        "doc_id":      row["doc_id"] or "",
                        "rel_type":    "TEXT_MENTION",
                        "rel_type_cn": "文本提及",
                        "constraints": valid_cons,
                    })
                    result["constraints"].extend(valid_cons)
                result["constraints"] = result["constraints"][:10]

    except Exception as e:
        logger.warning("因果链查询失败 entity=%s: %s", entity_name, e)

    return result


def prepare_counterfactual(question: str, driver: Driver, top_k: int = 5) -> tuple:
    """
    反事实查询的主入口，供 stream.py 调用。
    返回: (sections, causal_chain, messages)
        sections    — 检索到的章节列表（用于 sources 事件）
        causal_chain — 因果链数据（用于 causal_chain 事件）
        messages    — 组装好的 LLM messages 列表（用于流式调用）
    """
    from ..routers.query.core import get_section_details
    from ..services.es_store import search_sections_es

    # ── 1. 解析意图 ────────────────────────────────────────────
    intent = parse_counterfactual_intent(question)
    logger.info("反事实意图 question=%r intent=%s", question[:50], intent)

    # ── 2. 图谱因果链 ─────────────────────────────────────────
    causal_chain = get_causal_chain(
        driver,
        intent.get("removed_name", ""),
        intent.get("removed_type", "Process"),
    )
    causal_chain["intent"] = intent  # 把意图一并带给前端

    # ── 3. 背景章节检索 ───────────────────────────────────────
    try:
        es_results = search_sections_es(question, top_k=top_k * 2)
        ft_ids     = [r["chunk_id"] for r in es_results]
    except Exception:
        ft_ids = []

    # 把因果链章节优先放在前面
    chain_ids = [s["chunk_id"] for s in causal_chain["affected_sections"]]
    all_ids   = list(dict.fromkeys(chain_ids + ft_ids))[: top_k * 2]
    sections  = get_section_details(driver, all_ids)[: top_k + 3]

    # ── 4. 构建因果链文本（给 LLM） ───────────────────────────
    removed_name    = intent.get("removed_name") or "该条目"
    removed_type_cn = _TYPE_CN.get(intent.get("removed_type", ""), "条目")
    subject         = intent.get("subject")      or "相关零件"
    requirement     = intent.get("requirement")  or "技术要求"

    chain_lines: list[str] = []
    for sec in causal_chain["affected_sections"][:5]:
        line = f"  • [{sec['doc_id']} §{sec['number']}] {sec['title']}（{sec['rel_type_cn']}）"
        if sec["constraints"]:
            ctext = "；".join(
                f"{(c.get('description') or c.get('type', '')).strip()} "
                f"{c.get('value', '')}"
                f"{'~' + c.get('value_max','') if c.get('value_max') else ''}"
                f" {c.get('unit', '')}".strip()
                for c in sec["constraints"][:3]
                if c.get("description") or c.get("type")
            )
            if ctext:
                line += f"\n    约束：{ctext}"
        chain_lines.append(line)

    chain_text = "\n".join(chain_lines) if chain_lines \
        else "  （图谱中未找到该实体的直接关联章节）"

    if causal_chain["alternatives"]:
        alt_text = f"规范中已知替代方案：{', '.join(causal_chain['alternatives'][:5])}"
    else:
        alt_text = "规范图谱中未发现已知替代方案（ALTERNATIVE_TO 关系为空）"

    # ── 5. 标准章节上下文 ─────────────────────────────────────
    context = "\n\n".join(
        f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
        for s in sections
    )

    # ── 6. 组装 LLM messages ─────────────────────────────────
    system_msg = (
        "你是一名航空制造工艺规范专家，擅长基于规范图谱进行因果推理与反事实分析。"
        "请严格依据规范内容作答，不要凭空添加规范外的信息。"
    )

    user_text = f"""## 反事实假设
{removed_type_cn} 「{removed_name}」被去掉或省略。

## 图谱因果链（该实体关联的章节与约束）
{chain_text}

{alt_text}

## 相关规范内容
{context}

## 反事实问题
{question}

## 分析要求
1. 指出去掉「{removed_name}」后，哪些约束条件（力矩、温度、材料性能、工艺参数等）将无法被保证；
2. 若存在替代方案，评估其是否能弥补缺失；
3. 对「{subject}」能否满足「{requirement}」给出明确结论：
   ✅ 可以满足 / ❌ 无法满足 / ⚠️ 需要进一步评估；
4. 引用具体章节号支持结论。

请进行反事实分析："""

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_text},
    ]

    return sections, causal_chain, messages
