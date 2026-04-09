import { RawDoc, TEvent, ML, MT, MR, MB, CW, RH } from "./types";

export function parseVer(doc_id: string, version: string): { base: string; ver: string } {
    const m = doc_id.match(/^(.+?)([A-Z])$/);
    if (m) return { base: m[1], ver: m[2] };
    const v = (version ?? "").trim().slice(0, 1).toUpperCase();
    return { base: doc_id, ver: /^[A-Z]$/.test(v) ? v : "" };
}

export function bubbleColor(added: number, removed: number, changed: number): string {
    const total = added + removed + changed;
    if (total === 0)                                      return "#6366f1"; // indigo  – 初版
    if (changed > 0 && added === 0 && removed === 0)      return "#3b82f6"; // blue    – 仅变更
    if (added > removed && added >= changed)              return "#22c55e"; // green   – 净增
    if (removed > added && removed >= changed)            return "#ef4444"; // red     – 净减
    return "#f59e0b";                                                        // amber   – 混合
}

export function buildTimeline(raw: RawDoc[]): {
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
        doc_id:     p.doc_id,
        base:       p.base,
        ver:        p.ver,
        title:      p.title,
        issue_date: p.issue_date,
        supersedes: p.supersedes,
        added:      p.added_sections,
        removed:    p.removed_sections,
        changed:    p.changed_sections,
        total:      p.added_sections + p.removed_sections + p.changed_sections,
        xi:         vers.indexOf(p.ver),
        yi:         bases.indexOf(p.base),
        step:       0,
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
