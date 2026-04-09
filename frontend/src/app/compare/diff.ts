// ── Myers diff（词级别）────────────────────────────────────────────────────────
export type DiffOp = { type: "equal" | "insert" | "delete"; text: string };

export function myersDiff(a: string[], b: string[]): DiffOp[] {
    const n = a.length, m = b.length;
    const max = n + m;
    if (max === 0) return [];
    const v = new Array(2 * max + 1).fill(0);
    const trace: number[][] = [];

    for (let d = 0; d <= max; d++) {
        trace.push([...v]);
        for (let k = -d; k <= d; k += 2) {
            const idx = k + max;
            let x: number;
            if (k === -d || (k !== d && v[idx - 1] < v[idx + 1])) {
                x = v[idx + 1];
            } else {
                x = v[idx - 1] + 1;
            }
            let y = x - k;
            while (x < n && y < m && a[x] === b[y]) { x++; y++; }
            v[idx] = x;
            if (x >= n && y >= m) return _backtrack(trace, a, b, max);
        }
    }
    return _backtrack(trace, a, b, max);
}

function _backtrack(trace: number[][], a: string[], b: string[], max: number): DiffOp[] {
    const ops: DiffOp[] = [];
    let x = a.length, y = b.length;
    for (let d = trace.length - 1; d >= 0; d--) {
        const v = trace[d];
        const k = x - y;
        const idx = k + max;
        let prevK: number;
        if (k === -d || (k !== d && (v[idx - 1] ?? 0) < (v[idx + 1] ?? 0))) {
            prevK = k + 1;
        } else {
            prevK = k - 1;
        }
        const prevX = v[prevK + max] ?? 0;
        const prevY = prevX - prevK;
        while (x > prevX + 1 && y > prevY + 1) {
            ops.unshift({ type: "equal", text: a[x - 1] }); x--; y--;
        }
        if (d > 0) {
            if (x === prevX) {
                ops.unshift({ type: "insert", text: b[y - 1] }); y--;
            } else if (y === prevY) {
                ops.unshift({ type: "delete", text: a[x - 1] }); x--;
            }
        }
        while (x > prevX && y > prevY) {
            ops.unshift({ type: "equal", text: a[x - 1] }); x--; y--;
        }
        x = prevX; y = prevY;
    }
    return ops;
}

export function renderWordDiff(aText: string, bText: string): { aHtml: string; bHtml: string } {
    const aWords = (aText || "").split(/(\s+)/);
    const bWords = (bText || "").split(/(\s+)/);
    const ops    = myersDiff(aWords, bWords);
    let aHtml = "", bHtml = "";
    for (const op of ops) {
        const esc = op.text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        if (op.type === "equal") {
            aHtml += esc; bHtml += esc;
        } else if (op.type === "delete") {
            aHtml += `<mark class="bg-red-500/30 text-red-300 rounded px-0.5">${esc}</mark>`;
        } else {
            bHtml += `<mark class="bg-green-500/30 text-green-300 rounded px-0.5">${esc}</mark>`;
        }
    }
    return { aHtml, bHtml };
}
