"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { GitBranch } from "lucide-react";
import { TEvent, RawDoc } from "./types";
import { buildTimeline } from "./timelineUtils";
import { drawTimeline } from "./drawTimeline";
import { TimelineControls } from "./TimelineControls";
import { TimelineSidebar } from "./TimelineSidebar";

const API = "http://localhost:8000";
const token = () =>
    typeof window !== "undefined" ? (localStorage.getItem("token") ?? "") : "";

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

    const [step,     setStep]     = useState(-1);
    const [playing,  setPlaying]  = useState(false);
    const [speed,    setSpeed]    = useState(700);
    const [selected, setSelected] = useState<TEvent | null>(null);
    const [tip, setTip] = useState<{ x: number; y: number; ev: TEvent } | null>(null);

    const maxStep = events.length - 1;

    /* Load data */
    useEffect(() => {
        fetch(`${API}/api/graph/timeline`, { headers: { Authorization: `Bearer ${token()}` } })
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(data => {
                const result = buildTimeline((data.docs ?? []) as RawDoc[]);
                setEvents(result.events);
                setVers(result.vers);
                setBases(result.bases);
                setSvgW(result.svgW);
                setSvgH(result.svgH);
                setStep(result.events.length - 1);
            })
            .catch(e => setError(`加载失败 (${e})`))
            .finally(() => setLoading(false));
    }, []);

    /* Setup D3 zoom once events are ready */
    useEffect(() => {
        if (!svgRef.current || !gRef.current || events.length === 0) return;
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.25, 4])
            .on("zoom", e => { d3.select(gRef.current!).attr("transform", e.transform.toString()); });
        zoomRef.current = zoom;
        d3.select(svgRef.current).call(zoom);
    }, [events.length]);

    /* Draw chart */
    useEffect(() => {
        if (!gRef.current || !svgRef.current || events.length === 0) return;
        drawTimeline({
            g:           d3.select(gRef.current),
            svgEl:       svgRef.current,
            events, vers, bases, svgW, step, selected,
            setTip,
            setSelected: fn => setSelected(prev => fn(prev)),
        });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [events, step, selected]);

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
        if (svgRef.current && zoomRef.current)
            d3.select(svgRef.current).call(zoomRef.current.transform, d3.zoomIdentity);
    }
    function zoomIn()  { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).call(zoomRef.current.scaleBy, 1.4); }
    function zoomOut() { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).call(zoomRef.current.scaleBy, 1 / 1.4); }

    return (
        <div className="min-h-screen bg-gray-950 text-white flex flex-col select-none">

            {/* Header */}
            <div className="border-b border-gray-800 px-6 py-4 flex items-center gap-3 shrink-0">
                <GitBranch size={20} className="text-indigo-400 shrink-0" />
                <div>
                    <h1 className="text-lg font-bold leading-tight">版本时间线</h1>
                    <p className="text-xs text-gray-400 mt-0.5">
                        知识库文档版本演进与章节变更历史 — X 轴：版本号，Y 轴：文档，气泡大小：变更量
                    </p>
                </div>
            </div>

            <TimelineControls
                playing={playing} step={step} maxStep={maxStep} speed={speed}
                totalEvents={events.length}
                onTogglePlay={playing ? () => setPlaying(false) : handlePlay}
                onReset={() => { setPlaying(false); setStep(-1); }}
                onSkipToEnd={() => { setPlaying(false); setStep(maxStep); }}
                onSpeedChange={setSpeed}
                onScrub={v => { setPlaying(false); setStep(v); }}
                onZoomIn={zoomIn} onZoomOut={zoomOut} onResetZoom={resetZoom}
            />

            <div className="flex flex-1 overflow-hidden min-h-0">

                {/* Chart area */}
                <div className="flex-1 overflow-auto relative bg-gray-950">
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
                        <svg ref={svgRef} width={svgW} height={svgH} className="cursor-grab active:cursor-grabbing">
                            <g ref={gRef} />
                        </svg>
                    </div>

                    {/* Tooltip */}
                    {tip && (
                        <div className="absolute pointer-events-none z-20" style={{ left: tip.x, top: tip.y }}>
                            <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-xs shadow-2xl w-48">
                                <div className="font-semibold text-white font-mono">{tip.ev.doc_id}</div>
                                <div className="text-gray-300 mt-0.5 leading-tight line-clamp-2">{tip.ev.title}</div>
                                {tip.ev.issue_date && <div className="text-gray-500 mt-0.5">{tip.ev.issue_date}</div>}
                                <div className="mt-2 space-y-0.5 border-t border-gray-700 pt-1.5">
                                    {tip.ev.added   > 0 && <div className="text-green-400">+{tip.ev.added} 新增章节</div>}
                                    {tip.ev.removed > 0 && <div className="text-red-400">−{tip.ev.removed} 删除章节</div>}
                                    {tip.ev.changed > 0 && <div className="text-blue-400">≈{tip.ev.changed} 内容变更</div>}
                                    {tip.ev.total   === 0 && <div className="text-indigo-400">初始版本</div>}
                                </div>
                                {tip.ev.supersedes.length > 0 && (
                                    <div className="mt-1 text-gray-500">继承自 {tip.ev.supersedes.join(", ")}</div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                <TimelineSidebar
                    bases={bases} vers={vers} events={events}
                    displayStep={step < 0 ? 0 : step + 1}
                    selected={selected}
                    setSelected={setSelected}
                />
            </div>
        </div>
    );
}
