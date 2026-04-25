export type Tab = "profile" | "password" | "model" | "admin" | "audit";

export interface UserInfo {
    username:   string;
    full_name:  string;
    department: string;
    email:      string;
    is_admin:   boolean;
}

export interface ModelSettings {
    llm_mode:           string;
    llm_provider:       string;
    llm_api_url:        string;
    llm_api_key:        string;
    llm_api_secret:     string;
    llm_model:          string;
    embedding_mode:    string;
    embedding_provider:string;
    embedding_model:   string;
    embedding_api_url: string;
    embedding_api_key: string;
    reranker_mode:     string;
    reranker_provider: string;
    reranker_model:    string;
    reranker_api_url:  string;
    reranker_api_key:  string;
    reranker_enabled:  string;
    vision_mode:       string;
    qwen_vl_model:     string;
    vlm_model:         string;
    query_top_k:       string;
    query_strategy:    string;
}

export interface UserRow {
    user_id:    string;
    username:   string;
    full_name:  string;
    department: string;
    is_admin:   boolean;
    is_active:  boolean;
    created_at: string;
}

export interface AuditRow {
    id:         number;
    username:   string;
    full_name:  string;
    action:     string;
    resource:   string;
    detail:     string;
    created_at: string;
}

export function getToken(): string {
    return localStorage.getItem("token") ?? "";
}
