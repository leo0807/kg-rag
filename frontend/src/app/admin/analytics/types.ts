export const STRATEGY_LABEL: Record<string, string> = {
    parallel:        "并行",
    sequential:      "串行",
    graph_augmented: "图增强",
    gnn:             "GNN",
    multi_hop:       "多跳",
    "—":             "—",
};

export interface Summary {
    total_active_users:     number;
    total_queries:          number;
    total_conversations:    number;
    avg_turns_per_session:  number | null;
    avg_daily_active_users: number;
}

export interface UserRow {
    user_id:               string;
    username:              string;
    full_name:             string;
    department:            string;
    active_days:           number;
    total_queries:         number;
    weekly_queries:        number;
    total_conversations:   number;
    avg_turns_per_session: number | null;
    top_strategy:          string;
    last_active:           string | null;
}

export interface DeptRow {
    department:            string;
    user_count:            number;
    avg_active_days:       number;
    total_queries:         number;
    weekly_queries:        number;
    total_conversations:   number;
    avg_turns_per_session: number | null;
    top_strategy:          string;
}

export interface DauPoint { date: string; active_users: number; queries: number; }

export interface Report {
    period:        { days: number; since: string; until: string };
    summary:       Summary;
    by_user:       UserRow[];
    by_department: DeptRow[];
    dau:           DauPoint[];
}

export interface StrategyRow {
    strategy:         string;
    label:            string;
    call_count:       number;
    avg_latency_ms:   number | null;
    avg_tokens:       number | null;
    total_tokens:     number;
    avg_cost_usd:     number | null;
    total_cost_usd:   number;
    explicit_ratings: number;
    positive_count:   number;
    negative_count:   number;
    positive_rate:    number | null;   // 0.0–1.0
    feedback_count:   number;
    avg_source_count: number | null;
}

export interface StrategyStats {
    period:     { days: number; since: string };
    strategies: StrategyRow[];
}

export type Tab = "user" | "dept" | "dau" | "strategy";
