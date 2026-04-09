import * as d3 from "d3";
import { TEvent, ML, MT, CW, RH, MR } from "./types";
import { bubbleColor } from "./timelineUtils";

interface DrawParams {
    g:           d3.Selection<SVGGElement, unknown, null, undefined>;
    svgEl:       SVGSVGElement;
    events:      TEvent[];
    vers:        string[];
    bases:       string[];
    svgW:        number;
    step:        number;
    selected:    TEvent | null;
    setTip:      (tip: { x: number; y: number; ev: TEvent } | null) => void;
    setSelected: (fn: (prev: TEvent | null) => TEvent | null) => void;
}

export function drawTimeline({ g, svgEl, events, vers, bases, svgW, step, selected, setTip, setSelected }: DrawParams) {
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
            .attr("x", ML + i * CW + CW / 2).attr("y", MT - 24)
            .attr("text-anchor", "middle").attr("fill", "#d1d5db")
            .attr("font-size", "13px").attr("font-weight", "600")
            .text(ver ? `版本 ${ver}` : "初  版");
    });
    xLab.append("text")
        .attr("x", ML + (vers.length * CW) / 2).attr("y", 20)
        .attr("text-anchor", "middle").attr("fill", "#374151").attr("font-size", "11px")
        .text("版  本  号");

    /* Y-axis labels */
    const yLab = g.append("g");
    bases.forEach((base, i) => {
        const label = base.length > 13 ? base.slice(0, 11) + "…" : base;
        yLab.append("text")
            .attr("x", ML - 14).attr("y", MT + i * RH + RH / 2)
            .attr("text-anchor", "end").attr("dominant-baseline", "central")
            .attr("fill", "#9ca3af").attr("font-size", "12px")
            .text(label);
    });
    yLab.append("text")
        .attr("transform", `rotate(-90) translate(${-(MT + (bases.length * RH) / 2)}, 16)`)
        .attr("text-anchor", "middle").attr("fill", "#374151").attr("font-size", "11px")
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
                .attr("x1", x1 + dx * (r1 + 2)).attr("y1", y1 + dy * (r1 + 2))
                .attr("x2", x2 - dx * (r2 + 10)).attr("y2", y2 - dy * (r2 + 10))
                .attr("stroke", "#374151").attr("stroke-width", 1.5)
                .attr("stroke-dasharray", "5,3").attr("marker-end", "url(#tl-arrow)");
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
        .attr("stroke-width", 1).attr("stroke-opacity", 0.25);

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

        if (isLatest) {
            bubblesG.append("circle")
                .attr("cx", cx).attr("cy", cy).attr("r", r + 7)
                .attr("fill", "none").attr("stroke", col)
                .attr("stroke-width", 2).attr("opacity", 0.35);
        }

        bubblesG.append("circle")
            .datum(d)
            .attr("cx", cx).attr("cy", cy).attr("r", r)
            .attr("fill", col).attr("opacity", 0.88)
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

        if (r >= 11) {
            bubblesG.append("text")
                .attr("x", cx).attr("y", cy)
                .attr("text-anchor", "middle").attr("dominant-baseline", "central")
                .attr("fill", "#fff").attr("font-size", r > 18 ? "11px" : "9px")
                .attr("font-weight", "700").attr("pointer-events", "none")
                .text(d.ver || "v0");
        }
    });
}
