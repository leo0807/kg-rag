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
    images?: string[];   // base64 data URIs (user messages only)
    timestamp: number;
}

export interface Conversation {
    id: string;
    title: string;        // 第一条消息的前20个字
    messages: Message[];
    timestamp: number;
}

export type Strategy = "parallel" | "sequential" | "graph_augmented" | "multi_hop";