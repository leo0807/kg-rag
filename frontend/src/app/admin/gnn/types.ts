export interface GNNServiceStatus {
    loaded:    boolean;
    num_nodes: number;
    emb_dim:   number;
    metadata:  Record<string, unknown>;
}

export interface TrainingStatus {
    running:  boolean;
    progress: string;
    error:    string;
}

export interface StatusResponse {
    service:  GNNServiceStatus;
    training: TrainingStatus;
}

export const DEFAULT_PARAMS = {
    epochs:      100,
    lr:          0.001,
    batch_size:  256,
    dropout:     0.2,
    temperature: 0.07,
    patience:    15,
    device:      "cpu",
};

export function formatTs(ts: number): string {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString("zh-CN");
}
