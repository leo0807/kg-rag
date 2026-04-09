import React from "react";

export function Stat({
    label, value, icon, accent = "text-white",
}: {
    label: string;
    value: string;
    icon?: React.ReactNode;
    accent?: string;
}) {
    return (
        <div className="bg-gray-800/60 rounded-lg px-4 py-3">
            <div className="text-xs text-gray-500 mb-1">{label}</div>
            <div className={`font-semibold flex items-center gap-1.5 ${accent}`}>
                {icon}
                {value}
            </div>
        </div>
    );
}

export function ParamInput({
    label, value, onChange, type = "text", ...rest
}: {
    label: string;
    value: number | string;
    onChange: (v: string) => void;
    type?: string;
    [k: string]: unknown;
}) {
    return (
        <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">{label}</label>
            <input
                type={type}
                value={value}
                onChange={e => onChange(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5
                           text-sm text-white focus:outline-none focus:border-violet-500"
                {...rest}
            />
        </div>
    );
}
