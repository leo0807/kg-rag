"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import {
    Play, Pause, SkipBack, SkipForward,
    ZoomIn, ZoomOut, RotateCcw, GitBranch, X,
} from "lucide-react";

const API = "http://localhost:8000";
const token = () =>
    typeof window !== "undefined" ? (localStorage.getItem("token") ?? "") : "";

/* ── Types ──────────────────────────────────────────────────────────────── */
interface RawDoc {
    doc_id: string;
    title: string;
    version: string;
    issue_date: string;
    supersedes: string[];
    added_sections: number;
    removed_sections: number;
    changed_sections: number;
}

interface TEvent {
    doc_id: string;
    base: string;
    ver: string;       // "" | "A" | "B" | …
    title: string;
    issue_date: string;
    supersedes: string[];
    added: number;
    removed: number;
    changed: number;
    total: number;
    xi: number;        // column index → X position
    yi: number;        // row index    → Y position
    step: number;      // playback order (0-based)
}

/* ── Layout constants ────────────────────────────────────────────────────── */
const ML = 164;   // left margin (Y-axis labels)
const MT = 72;    // top margin  (X-axis labels)
const CW = 108;   // column width
const RH = 68;    // row height
const MR = 48;    // right margin
const MB = 48;    // bottom margin

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function parseVer(doc_id: string, version: string): { base: string; ver: string } {
    const m = doc_id.match(/^(.+?)([A-Z])$/);
    if (m) return { base: m[1], ver: m[2] };
    const v = (version ?? "").trim().slice(0, 1).toUpperCase();
    return { base: doc_id, ver: /^[A-Z]$/.test(v) ? v : "" };
}

function bubbleColor(added: number, removed: number, changed: number): string {
    const total = added + removed + changed;
    if (total === 0)                                       return "#6366f1"; // indigo  – 初版
    if (changed > 0 && added === 0 && removed === 0)       return "#3b82f6"; // blue    – 仅变更
    if (added > removed && added >= changed)               return "#22c55e"; // green   – 净增
    if (removed > added && removed >= changed)             return "#ef4444"; // red     – 净减
    return "#f59e0b";                                                         // amber   – 混合
}

function buildTimeline(raw: RawDoc[]): {
    events: TEvent[];
    vers: string[];
    bases: string[];
    svgW: number;
    svgH: number;
} {
    const parsed = raw.map(d => ({ ...d, ...parseVer(d.doc_id, d.version) }));

    const vers = [...new Set(parsed.map(p => p.ver))].sort((a, b) => {
        if (!a && b) return -1;
        if (a && !b) return 1;
        return a.localeCompare(b);
    });
    const bases = [...new Set(parsed.map(p => p.base))].sort();

    const events: TEvent[] = parsed.map(p => ({
        doc_id:    p.doc_id,
        base:      p.base,
        ver:       p.ver,
        title:     p.title,
        issue_date: p.issue_date,
        supersedes: p.supersedes,
        added:     p.added_sections,
        removed:   p.removed_sections,
        changed:   p.changed_sections,
        total:     p.added_sections + p.removed_sections + p.changed_sections,
        xi:        vers.indexOf(p.ver),
        yi:        bases.indexOf(p.base),
        step:      0,
    }));

    // 动画顺序：先按版本字母（左→右），再按基名（上→下）
    events.sort((a, b) => a.ver.localeCompare(b.ver) || a.base.localeCompare(b.base));
    events.forEach((e, i) => { e.step = i; });

    return {
        events,
        vers,
        bases,
        svgW: Math.max(600, ML + vers.length * CW + MR),
        svgH: Math.max(300, MT + bases.length * RH + MB),
    };
}

/* ── Main Component ──────────────────────────────────────────────────────── */
export default function TimelinePage() {
    const svgRef   = useRef<SVGSVGElement>(null);
    const gRef     = useRef<SVGGElement>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const zoomRef  = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

    const [events,  setEvents]  = useState<TEvent[]>([]);
    const [vers,    setVers]    = useState<string[]>([]);
    const [bases,   setBases]   = useState<string[]>([]);
    const [svgW,    setSvgW]    = useState(700);
    const [svgH,    setSvgH]    = useState(400);
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState("");

    const [step,     setStep]    = useState(-1);
    const [playing,  setPlaying] = useState(false);
    const [speed,    setSpeed]   = useState(700);
    const [selected, setSelected] = useState<TEvent | null>(null);
    const [tip, setTip] = useState<{ x: number; y: number; ev: TEvent } | null>(null);

    const maxStep = events.length - 1;

    /* Load data */
    useEffect(() => {
        fetch(`${API}/api/graph/timeline`, {
            headers: { Authorization: `Bearer ${token()}` },
        })
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(data => {
                const result = buildTimeline((data.docs ?? []) as RawDoc[]);
                setEvents(result.events);
                setVers(result.vers);
                setBases(result.bases);
                setSvgW(result.svgW);
                setSvgH(result.svgH);
                setStep(result.events.length - 1); // 默认全部显示
            })
            .catch(e => setError(`加载失败 (${e})`))
            .finally(() => setLoading(false));
    }, []);

    /* Setup D3 zoom once events are ready */
    useEffect(() => {
        if (!svgRef.current || !gRef.current || events.length === 0) return;
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.25, 4])
            .on("zoom", e => {
                d3.select(gRef.current!).attr("transform", e.transform.toString());
            });
        zoomRef.current = zoom;
        d3.select(svgRef.current).call(zoom);
    }, [events.length]);

    /* Draw chart */
    useEffect(() => {
        if (!gRef.current || events.length === 0) return;
        draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [events, step, selected]);

    function draw() {
        const g       = d3.select(gRef.current!);
        const svgEl   = svgRef.current!;
        g.selectAll("*").remove();

        const visible = step < 0 ? [] : events.filter(e => e.step <= step);
        const future  = step < 0 ? events : events.filter(e => e.step > step);
        const docMap  = new Map(events.map(e => [e.doc_id, e]));
        const maxT    = d3.max(events, e => e.total) ?? 1;
        const rScale  = d3.scaleSqrt().domain([0, maxT]).range([9, 32]);

        /* Arrow marker */
        const defs = g.append("defs");
        defs.append("marker")
            .attr("id", "tl-arrow")
            .attr("viewBox", "0 -4 8 8")
            .attr("refX", 8).attr("refY", 0)
            .attr("markerWidth", 6).attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path").attr("d", "M0,-4L8,0L0,4")
            .attr("fill", "#374151");

        /* Grid */
        const grid = g.append("g");
        bases.forEach((_, i) => {
            grid.append("line")
                .attr("x1", ML - 16).attr("y1", MT + i * RH)
                .attr("x2", svgW - MR).attr("y2", MT + i * RH)
                .attr("stroke", "#1f2937").attr("stroke-width", 1);
        });
        // bottom row border
        grid.append("line")
            .attr("x1", ML - 16).attr("y1", MT + bases.length * RH)
            .attr("x2", svgW - MR).attr("y2", MT + bases.length * RH)
            .attr("stroke", "#1f2937").attr("stroke-width", 1);
        vers.forEach((_, i) => {
            grid.append("line")
                .attr("x1", ML + i * CW).attr("y1", MT - 12)
                .attr("x2", ML + i * CW).attr("y2", MT + bases.length * RH)
                .attr("stroke", "#1f2937").attr("stroke-width", 1);
        });

        /* X-axis labels */
        const xLab = g.append("g");
        vers.forEach((ver, i) => {
            xLab.append("text")
                .attr("x", ML + i * CW + CW / 2)
                .attr("y", MT - 24)
                .attr("text-anchor", "middle")
                .attr("fill", "#d1d5db")
                .attr("font-size", "13px")
                .attr("font-weight", "600")
                .text(ver ? `版本 ${ver}` : "初  版");
        });
        xLab.append("text")
            .attr("x", ML + (vers.length * CW) / 2)
            .attr("y", 20)
            .attr("text-anchor", "middle")
            .attr("fill", "#374151")
            .attr("font-size", "11px")
            .text("版  本  号");

        /* Y-axis labels */
        const yLab = g.append("g");
        bases.forEach((base, i) => {
            const label = base.length > 13 ? base.slice(0, 11) + "…" : base;
            yLab.append("text")
                .attr("x", ML - 14)
                .attr("y", MT + i * RH + RH / 2)
                .attr("text-anchor", "end")
                .attr("dominant-baseline", "central")
                .attr("fill", "#9ca3af")
                .attr("font-size", "12px")
                .text(label);
        });
        yLab.append("text")
            .attr("transform",
                `rotate(-90) translate(${-(MT + (bases.length * RH) / 2)}, 16)`)
            .attr("text-anchor", "middle")
            .attr("fill", "#374151")
            .attr("font-size", "11px")
            .text("文  档");

        /* SUPERSEDES connections */
        const connG = g.append("g");
        visible.forEach(ev => {
            ev.supersedes.forEach(oldId => {
                const old = docMap.get(oldId);
                if (!old || old.step > step) return;
                const x1 = ML + old.xi * CW + CW / 2;
                const y1 = MT + old.yi * RH + RH / 2;
                const x2 = ML + ev.xi  * CW + CW / 2;
                const y2 = MT + ev.yi  * RH + RH / 2;
                const len = Math.hypot(x2 - x1, y2 - y1) || 1;
                const dx  = (x2 - x1) / len;
                const dy  = (y2 - y1) / len;
                const r1  = rScale(old.total);
                const r2  = rScale(ev.total);
                connG.append("line")
                    .attr("x1", x1 + dx * (r1 + 2))
                    .attr("y1", y1 + dy * (r1 + 2))
                    .attr("x2", x2 - dx * (r2 + 10))
                    .attr("y2", y2 - dy * (r2 + 10))
                    .attr("stroke", "#374151")
                    .attr("stroke-width", 1.5)
                    .attr("stroke-dasharray", "5,3")
                    .attr("marker-end", "url(#tl-arrow)");
            });
        });

        /* Future bubbles (faint outline only) */
        g.append("g").selectAll("circle")
            .data(future).join("circle")
            .attr("cx", d => ML + d.xi * CW + CW / 2)
            .attr("cy", d => MT + d.yi * RH + RH / 2)
            .attr("r",  d => rScale(d.total))
            .attr("fill", d => bubbleColor(d.added, d.removed, d.changed))
            .attr("opacity", 0.1)
            .attr("stroke", d => bubbleColor(d.added, d.removed, d.changed))
            .attr("stroke-width", 1)
            .attr("stroke-opacity", 0.25);

        /* Visible bubbles */
        const latestId = step >= 0 && step < events.length ? events[step].doc_id : null;
        const bubblesG = g.append("g");

        visible.forEach(d => {
            const cx = ML + d.xi * CW + CW / 2;
            const cy = MT + d.yi * RH + RH / 2;
            const r  = rScale(d.total);
            const col = bubbleColor(d.added, d.removed, d.changed);
            const isSelected = selected?.doc_id === d.doc_id;
            const isLatest   = d.doc_id === latestId;

            // Glow ring for latest step
            if (isLatest) {
                bubblesG.append("circle")
                    .attr("cx", cx).attr("cy", cy)
                    .attr("r", r + 7)
                    .attr("fill", "none")
                    .attr("stroke", col)
                    .attr("stroke-width", 2)
                    .attr("opacity", 0.35);
            }

            bubblesG.append("circle")
                .datum(d)
                .attr("cx", cx).attr("cy", cy).attr("r", r)
                .attr("fill", col)
                .attr("opacity", 0.88)
                .attr("stroke", isSelected || isLatest ? "#fff" : "none")
                .attr("stroke-width", isSelected ? 2.5 : 1.5)
                .style("cursor", "pointer")
                .on("click", (_, ev) =>
                    setSelected(prev => prev?.doc_id === ev.doc_id ? null : ev))
                .on("mousemove", (event: MouseEvent) => {
                    const rect = svgEl.getBoundingClientRect();
                    setTip({ x: event.clientX - rect.left + 14, y: event.clientY - rect.top - 8, ev: d });
                })
                .on("mouseleave", () => setTip(null));

            // Version label inside bubble
            if (r >= 11) {
                bubblesG.append("text")
                    .attr("x", cx).attr("y", cy)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "central")
                    .attr("fill", "#fff")
                    .attr("font-size", r > 18 ? "11px" : "9px")
                    .attr("font-weight", "700")
                    .attr("pointer-events", "none")
                    .text(d.ver || "v0");
            }
        });
    }

    /* Playback */
    useEffect(() => {
        if (!playing) { if (timerRef.current) clearTimeout(timerRef.current); return; }
        if (step >= maxStep) { setPlaying(false); return; }
        timerRef.current = setTimeout(() => setStep(s => s + 1), speed);
        return () => { if (timerRef.current) clearTimeout(timerRef.current); };
    }, [playing, step, maxStep, speed]);

    const handlePlay = useCallback(() => {
        if (step >= maxStep) setStep(-1);
        setPlaying(true);
    }, [step, maxStep]);

    function resetZoom() {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).call(zoomRef.current.transform, d3.zoomIdentity);
        }
    }
    function zoomIn() {
        if (svgRef.current && zoomRef.current)
            d3.select(svgRef.current).call(zoomRef.current.scaleBy, 1.4);
    }
    function zoomOut() {
        if (svgRef.current && zoomRef.current)
            d3.select(svgRef.current).call(zoomRef.current.scaleBy, 1 / 1.4);
    }

    const displayStep = step < 0 ? 0 : step + 1;

    return (
        <div className="min-h-screen bg-gray-950 text-white flex flex-col select-none">

            {/* ── Header ─────────────────────────────────────────────── */}
            <div className="border-b border-gray-800 px-6 py-4 flex items-center gap-3 shrink-0">
                <GitBranch size={20} className="text-indigo-400 shrink-0" />
                <div>
                    <h1 className="text-lg font-bold leading-tight">版本时间线</h1>
                    <p className="text-xs text-gray-400 mt-0.5">
                        知识库文档版本演进与章节变更历史 — X 轴：版本号，Y 轴：文档，气泡大小：变更量
                    </p>
                </div>
            </div>

            {/* ── Controls ───────────────────────────────────────────── */}
            <div className="border-b border-gray-800 px-5 py-2 flex items-center gap-3 bg-gray-900/40 shrink-0 flex-wrap">

                {/* Playback */}
                <button onClick={() => { setPlaying(false); setStep(-1); }}
                    title="重置到起点"
                    className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                    <SkipBack size={14} />
                </button>

                <button
                    onClick={playing ? () => setPlaying(false) : handlePlay}
                    disabled={events.length === 0}
                    className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500
                               disabled:opacity-40 disabled:cursor-not-allowed
                               text-white text-sm flex items-center gap-1.5 transition-colors">
                    {playing ? <><Pause size={13} />暂停</> : <><Play size={13} />播放</>}
                </button>

                <button onClick={() => { setPlaying(false); setStep(maxStep); }}
                    title="跳到末尾（全部显示）"
                    className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                    <SkipForward size={14} />
                </button>

                <div className="w-px h-4 bg-gray-700 shrink-0" />

                {/* Speed */}
                <span className="text-xs text-gray-500 shrink-0">速度</span>
                <input type="range" min={150} max={2000} step={50}
                    value={speed}
                    onChange={e => setSpeed(+e.target.value)}
                    className="w-20 accent-indigo-500" />
                <span className="text-xs text-gray-400 w-16 shrink-0">{speed} ms/步</span>

                <div className="w-px h-4 bg-gray-700 shrink-0" />

                {/* Scrub slider */}
                <span className="text-xs text-gray-500 shrink-0">
                    {displayStep} / {events.length}
                </span>
                <input type="range" min={-1} max={Math.max(0, maxStep)} step={1}
                    value={step}
                    onChange={e => { setPlaying(false); setStep(+e.target.value); }}
                    className="w-36 accent-indigo-500" />

                <div className="w-px h-4 bg-gray-700 shrink-0" />

                {/* Zoom */}
                <button onClick={zoomIn}  title="放大" className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><ZoomIn  size={14} /></button>
                <button onClick={zoomOut} title="缩小" className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><ZoomOut size={14} /></button>
                <button onClick={resetZoom} title="重置视角" className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><RotateCcw size={14} /></button>
            </div>

            {/* ── Body ───────────────────────────────────────────────── */}
            <div className="flex flex-1 overflow-hidden min-h-0">

                {/* Chart area */}
                <div className="flex-1 overflow-auto relative bg-gray-950">

                    {/* States */}
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-gray-400 text-sm animate-pulse">加载中…</span>
                        </div>
                    )}
                    {error && (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-red-400 text-sm">{error}</span>
                        </div>
                    )}
                    {!loading && !error && events.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center flex-col gap-3">
                            <GitBranch size={40} className="text-gray-700" />
                            <p className="text-gray-500 text-sm">暂无版本演进数据</p>
                            <p className="text-gray-600 text-xs">导入多版本文档（如 CPS1220A、CPS1220B）后将自动生成时间线</p>
                        </div>
                    )}

                    <div className="p-4">
                        <svg
                            ref={svgRef}
                            width={svgW}
                            height={svgH}
                            className="cursor-grab active:cursor-grabbing"
                        >
                            <g ref={gRef} />
                        </svg>
                    </div>

                    {/* Tooltip */}
                    {tip && (
                        <div
                            className="absolute pointer-events-none z-20"
                            style={{ left: tip.x, top: tip.y }}
                        >
                            <div className="bg-gray-800 border border-gray-600 rounded-lg
                                            px-3 py-2.5 text-xs shadow-2xl w-48">
                                <div className="font-semibold text-white font-mono">{tip.ev.doc_id}</div>
                                <div className="text-gray-300 mt-0.5 leading-tight line-clamp-2">{tip.ev.title}</div>
                                {tip.ev.issue_date && (
                                    <div className="text-gray-500 mt-0.5">{tip.ev.issue_date}</div>
                                )}
                                <div className="mt-2 space-y-0.5 border-t border-gray-700 pt-1.5">
                                    {tip.ev.added   > 0 && <div className="text-green-400">+{tip.ev.added} 新增章节</div>}
                                    {tip.ev.removed > 0 && <div className="text-red-400">−{tip.ev.removed} 删除章节</div>}
                                    {tip.ev.changed > 0 && <div className="text-blue-400">≈{tip.ev.changed} 内容变更</div>}
                                    {tip.ev.total   === 0 && <div className="text-indigo-400">初始版本</div>}
                                </div>
                                {tip.ev.supersedes.length > 0 && (
                                    <div className="mt-1 text-gray-500">
                                        继承自 {tip.ev.supersedes.join(", ")}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* ── Right panel ──────────────────────────────────────── */}
                <div className="w-52 border-l border-gray-800 flex flex-col shrink-0 bg-gray-900/20">

                    {/* Legend */}
                    <div className="p-4 border-b border-gray-800 shrink-0">
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">图例</div>
                        {(
                            [
                                { color: "#6366f1", label: "初始版本" },
                                { color: "#22c55e", label: "章节净增加" },
                                { color: "#ef4444", label: "章节净减少" },
                                { color: "#3b82f6", label: "内容变更" },
                                { color: "#f59e0b", label: "混合变更" },
                            ] as const
                        ).map(({ color, label }) => (
                            <div key={label} className="flex items-center gap-2 mb-1.5">
                                <div className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                                <span className="text-xs text-gray-400">{label}</span>
                            </div>
                        ))}
                        <div className="mt-3 space-y-0.5 text-xs text-gray-600">
                            <div>气泡大小 = 变更总量</div>
                            <div>虚线箭头 = 版本继承</div>
                            <div>淡色轮廓 = 未来版本</div>
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="px-4 py-3 border-b border-gray-800 shrink-0">
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">统计</div>
                        <div className="space-y-1">
                            <div className="flex justify-between text-xs">
                                <span className="text-gray-500">文档家族</span>
                                <span className="text-white">{bases.length}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-gray-500">版本跨度</span>
                                <span className="text-white">{vers.length}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-gray-500">事件总数</span>
                                <span className="text-white">{events.length}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-gray-500">已播放</span>
                                <span className="text-indigo-300">{displayStep} / {events.length}</span>
                            </div>
                        </div>
                    </div>

                    {/* Selected detail */}
                    {selected ? (
                        <div className="flex-1 overflow-auto p-4">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    版本详情
                                </span>
                                <button onClick={() => setSelected(null)}
                                    className="text-gray-600 hover:text-white transition-colors">
                                    <X size={13} />
                                </button>
                            </div>
                            <div className="space-y-3">
                                <div>
                                    <div className="text-xs text-gray-600 mb-0.5">文档 ID</div>
                                    <div className="text-sm text-white font-mono">{selected.doc_id}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-600 mb-0.5">标题</div>
                                    <div className="text-xs text-gray-300 leading-snug">{selected.title || "—"}</div>
                                </div>
                                <div className="flex gap-4">
                                    <div>
                                        <div className="text-xs text-gray-600 mb-0.5">版本</div>
                                        <div className="text-xs text-white font-mono">{selected.ver || "初版"}</div>
                                    </div>
                                    {selected.issue_date && (
                                        <div>
                                            <div className="text-xs text-gray-600 mb-0.5">日期</div>
                                            <div className="text-xs text-gray-300">{selected.issue_date}</div>
                                        </div>
                                    )}
                                </div>
                                <div className="border-t border-gray-800 pt-2">
                                    <div className="text-xs text-gray-600 mb-1.5">章节变更统计</div>
                                    <div className="space-y-1.5">
                                        <div className="flex items-center justify-between text-xs">
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                                                新增
                                            </span>
                                            <span className="text-white font-medium">{selected.added}</span>
                                        </div>
                                        <div className="flex items-center justify-between text-xs">
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                                                删除
                                            </span>
                                            <span className="text-white font-medium">{selected.removed}</span>
                                        </div>
                                        <div className="flex items-center justify-between text-xs">
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
                                                变更
                                            </span>
                                            <span className="text-white font-medium">{selected.changed}</span>
                                        </div>
                                        <div className="flex items-center justify-between text-xs border-t border-gray-800 pt-1 mt-1">
                                            <span className="text-gray-500">合计</span>
                                            <span className="text-white font-semibold">{selected.total}</span>
                                        </div>
                                    </div>
                                </div>
                                {selected.supersedes.length > 0 && (
                                    <div className="border-t border-gray-800 pt-2">
                                        <div className="text-xs text-gray-600 mb-1">继承自</div>
                                        {selected.supersedes.map(id => (
                                            <div key={id} className="text-xs text-indigo-400 font-mono">{id}</div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="flex-1 flex items-center justify-center p-4">
                            <p className="text-xs text-gray-700 text-center leading-relaxed">
                                点击气泡<br />查看版本详情
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
