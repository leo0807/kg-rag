"use client";

import { Play, Pause, SkipBack, SkipForward, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

interface Props {
    playing:       boolean;
    step:          number;
    maxStep:       number;
    speed:         number;
    totalEvents:   number;
    onTogglePlay:  () => void;
    onReset:       () => void;
    onSkipToEnd:   () => void;
    onSpeedChange: (v: number) => void;
    onScrub:       (v: number) => void;
    onZoomIn:      () => void;
    onZoomOut:     () => void;
    onResetZoom:   () => void;
}

export function TimelineControls({
    playing, step, maxStep, speed, totalEvents,
    onTogglePlay, onReset, onSkipToEnd,
    onSpeedChange, onScrub,
    onZoomIn, onZoomOut, onResetZoom,
}: Props) {
    const displayStep = step < 0 ? 0 : step + 1;

    return (
        <div className="border-b border-gray-800 px-5 py-2 flex items-center gap-3 bg-gray-900/40 shrink-0 flex-wrap">
            <button onClick={onReset} title="重置到起点"
                className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                <SkipBack size={14} />
            </button>

            <button onClick={onTogglePlay} disabled={totalEvents === 0}
                className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500
                           disabled:opacity-40 disabled:cursor-not-allowed
                           text-white text-sm flex items-center gap-1.5 transition-colors">
                {playing ? <><Pause size={13} />暂停</> : <><Play size={13} />播放</>}
            </button>

            <button onClick={onSkipToEnd} title="跳到末尾（全部显示）"
                className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                <SkipForward size={14} />
            </button>

            <div className="w-px h-4 bg-gray-700 shrink-0" />

            <span className="text-xs text-gray-500 shrink-0">速度</span>
            <input type="range" min={150} max={2000} step={50}
                value={speed}
                onChange={e => onSpeedChange(+e.target.value)}
                className="w-20 accent-indigo-500" />
            <span className="text-xs text-gray-400 w-16 shrink-0">{speed} ms/步</span>

            <div className="w-px h-4 bg-gray-700 shrink-0" />

            <span className="text-xs text-gray-500 shrink-0">{displayStep} / {totalEvents}</span>
            <input type="range" min={-1} max={Math.max(0, maxStep)} step={1}
                value={step}
                onChange={e => onScrub(+e.target.value)}
                className="w-36 accent-indigo-500" />

            <div className="w-px h-4 bg-gray-700 shrink-0" />

            <button onClick={onZoomIn}    title="放大"   className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><ZoomIn    size={14} /></button>
            <button onClick={onZoomOut}   title="缩小"   className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><ZoomOut   size={14} /></button>
            <button onClick={onResetZoom} title="重置视角" className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"><RotateCcw size={14} /></button>
        </div>
    );
}
