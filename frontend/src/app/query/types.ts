export interface SourceSection {
    chunk_id: string;
    doc_id: string;
    number: string;
    title: string;
    score: number;
}

export interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: SourceSection[];
    images?: string[];           // base64 data URIs (user messages only)
    causalChain?: CausalChainData;
    timestamp: number;
}

export interface Conversation {
    id: string;
    title: string;
    messages: Message[];
    timestamp: number;
}

export type Strategy = "parallel" | "sequential" | "graph_augmented" | "multi_hop" | "counterfactual";

// ── 反事实因果链数据结构 ──────────────────────────────────────────
export interface CausalConstraint {
    type:        string;
    value:       string;
    value_max?:  string;
    unit:        string;
    description: string;
}

export interface CausalSection {
    chunk_id:    string;
    number:      string;
    title:       string;
    doc_id:      string;
    rel_type:    string;
    rel_type_cn: string;
    constraints: CausalConstraint[];
}

export interface CausalChainData {
    entity_name:       string;
    entity_type:       string;
    affected_sections: CausalSection[];
    constraints:       CausalConstraint[];
    alternatives:      string[];
    intent: {
        removed_type: string;
        removed_name: string;
        subject:      string;
        requirement:  string;
    };
}
