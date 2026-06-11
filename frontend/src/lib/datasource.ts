/**
 * J1.2: DataSource abstraction — REST, WebSocket, SSE, and static data.
 */

export type ChartData = {
  rows: Record<string, unknown>[];
  meta?: Record<string, unknown>;
};

export type DataSourceConfig =
  | { type: "api"; endpoint: string; params?: Record<string, unknown>; refresh_interval?: number }
  | { type: "ws"; url: string }
  | { type: "sse"; url: string }
  | { type: "static"; data: Record<string, unknown>[] };

type Unsubscribe = () => void;

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

export class DataSource {
  private config: DataSourceConfig;
  private _cache: ChartData | null = null;
  private _timer: ReturnType<typeof setInterval> | null = null;
  private _subscribers: Set<(data: ChartData) => void> = new Set();

  constructor(config: DataSourceConfig) {
    this.config = config;
  }

  async fetch(params?: Record<string, unknown>): Promise<ChartData> {
    const cfg = this.config;
    if (cfg.type === "static") {
      return { rows: cfg.data };
    }
    if (cfg.type === "api") {
      const merged = { ...cfg.params, ...params };
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(merged).map(([k, v]) => [k, String(v)]))
      ).toString();
      const url = qs ? `${cfg.endpoint}?${qs}` : cfg.endpoint;
      const r = await fetch(url, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!r.ok) throw new Error(`DataSource fetch failed: ${r.status}`);
      const data = await r.json();
      const rows = Array.isArray(data) ? data : data.rows ?? data.data ?? [data];
      this._cache = { rows, meta: data.meta };
      this._notify();
      return this._cache;
    }
    throw new Error(`fetch() not supported for type=${cfg.type}; use subscribe()`);
  }

  subscribe(callback: (data: ChartData) => void): Unsubscribe {
    this._subscribers.add(callback);
    const cfg = this.config;

    if (cfg.type === "api" && cfg.refresh_interval && !this._timer) {
      this._timer = setInterval(() => this.fetch(), cfg.refresh_interval);
      void this.fetch(); // immediate first load
    }

    if (cfg.type === "sse") {
      const es = new EventSource(cfg.url);
      es.onmessage = (e) => {
        try {
          const rows = JSON.parse(e.data);
          this._cache = { rows: Array.isArray(rows) ? rows : [rows] };
          this._notify();
        } catch { /* ignore parse errors */ }
      };
      return () => { this._subscribers.delete(callback); es.close(); };
    }

    if (cfg.type === "ws") {
      const ws = new WebSocket(cfg.url);
      ws.onmessage = (e) => {
        try {
          const rows = JSON.parse(e.data);
          this._cache = { rows: Array.isArray(rows) ? rows : [rows] };
          this._notify();
        } catch { /* ignore parse errors */ }
      };
      return () => { this._subscribers.delete(callback); ws.close(); };
    }

    if (cfg.type === "static") {
      this._cache = { rows: cfg.data };
      callback(this._cache);
    }

    return () => {
      this._subscribers.delete(callback);
      if (!this._subscribers.size && this._timer) {
        clearInterval(this._timer);
        this._timer = null;
      }
    };
  }

  async refresh(): Promise<void> {
    await this.fetch();
  }

  get cached(): ChartData | null {
    return this._cache;
  }

  private _notify() {
    if (!this._cache) return;
    this._subscribers.forEach(cb => cb(this._cache!));
  }
}

/** React hook for DataSource */
import { useEffect, useState } from "react";

export function useDataSource(config: DataSourceConfig, deps: unknown[] = []) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    const ds = new DataSource(config);
    const unsub = ds.subscribe((d) => { setData(d); setLoading(false); });
    if (config.type === "api" && !config.refresh_interval) {
      ds.fetch().catch(e => setError(String(e))).finally(() => setLoading(false));
    }
    return unsub;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}
