"use client";

import { WifiOff, Wifi, RefreshCw, X } from "lucide-react";

export type NetToastType = "offline" | "reconnecting" | "online";

interface Props {
    type: NetToastType;
    label: string;
    onClose: () => void;
}

import type { ReactElement } from "react";

const CONFIG: Record<NetToastType, { iconEl: (cls: string) => ReactElement; bg: string; text: string }> = {
    offline:      { iconEl: cls => <WifiOff  size={14} className={cls} />, bg: "bg-red-950/90 border-red-700/60",         text: "text-red-300"     },
    reconnecting: { iconEl: cls => <RefreshCw size={14} className={cls} />, bg: "bg-gray-900/95 border-gray-700/60",      text: "text-gray-300"    },
    online:       { iconEl: cls => <Wifi      size={14} className={cls} />, bg: "bg-emerald-950/90 border-emerald-700/60", text: "text-emerald-300" },
};

const ICON_CLS: Record<NetToastType, string> = {
    offline:      "text-red-400",
    reconnecting: "text-indigo-400 animate-spin",
    online:       "text-emerald-400",
};

export default function NetToast({ type, label, onClose }: Props) {
    const { iconEl, bg, text } = CONFIG[type];

    return (
        <div className={`fixed top-3 left-1/2 -translate-x-1/2 z-50
                         flex items-center gap-2.5 px-4 py-2.5
                         border rounded-xl shadow-xl backdrop-blur-sm
                         text-sm font-medium
                         ${bg} ${text}`}>
            {iconEl(ICON_CLS[type])}
            <span>{label}</span>
            <button
                onClick={onClose}
                className="ml-1 text-current opacity-50 hover:opacity-100 transition-opacity"
            >
                <X size={12} />
            </button>
        </div>
    );
}
