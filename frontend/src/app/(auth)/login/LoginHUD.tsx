"use client";

const STREAM_COLS = [
  ["4F3A","1B9C","2E7D","A4F1","0x3C","B8E2","91CF","7A4D","0xFF","2B1E","D4C7","F3A8","0x2B","95E1","3D8F","C7A2","0x6E","48D1"],
  ["AUTH","GRANT","SCAN","VERIFY","ACCESS","CHECK","INIT","TOKEN","RSA","JWT","TLS","BOLT","QUERY","HASH","HMAC","PBKDF","AUDIT","LOG"],
  ["0101","1010","1100","0011","1111","0000","1010","0110","1001","0101","1100","0010","1011","0111","1000","0100","1110","0001"],
];

function DataStream({ lines, dur, delay, color }: { lines: string[]; dur: number; delay: number; color: string }) {
  const q = [...lines, ...lines, ...lines, ...lines];
  return (
    <div className="overflow-hidden flex-1 h-full">
      <div className="font-mono text-[8px] leading-[18px] select-none"
           style={{ color, opacity: 0.11, animation: `data-stream-up ${dur}s linear ${delay}s infinite` }}>
        {q.map((v, i) => <div key={i}>{v}</div>)}
      </div>
    </div>
  );
}

export default function LoginHUD() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-[1]">

      {/* ── Orbital rings ── */}
      <div className="absolute left-1/2 top-1/2" style={{ transform: "translate(-50%,-50%)" }}>
        {[
          { w: 920, op: 0.022, spd: "80s", dir: "normal" as const,  dashes: "" },
          { w: 760, op: 0.018, spd: "60s", dir: "reverse" as const, dashes: "4 8" },
          { w: 600, op: 0.015, spd: "45s", dir: "normal" as const,  dashes: "2 12" },
        ].map(({ w, op, spd, dir, dashes }, i) => (
          <div key={i} className="absolute rounded-full"
               style={{
                 width: w, height: w,
                 top: "50%", left: "50%",
                 transform: "translate(-50%,-50%)",
                 border: `1px ${dashes ? "dashed" : "solid"} rgba(34,211,238,${op})`,
                 animation: `spin-slow ${spd} linear infinite ${dir}`,
               }} />
        ))}
        {/* Orbital marker dots on outermost ring */}
        {[0, 90, 180, 270].map(deg => {
          const r = 460;
          const x = Math.sin(deg * Math.PI / 180) * r;
          const y = -Math.cos(deg * Math.PI / 180) * r;
          return (
            <div key={deg} className="absolute w-1.5 h-1.5 rounded-full bg-cyan-400"
                 style={{ opacity: 0.15, top: `calc(50% + ${y}px - 3px)`, left: `calc(50% + ${x}px - 3px)` }} />
          );
        })}
      </div>

      {/* ── Axis crosshair ── */}
      <div className="absolute top-1/2 left-0 right-0 h-px"
           style={{ background: "linear-gradient(90deg,transparent 5%,rgba(34,211,238,0.05) 30%,rgba(34,211,238,0.07) 50%,rgba(34,211,238,0.05) 70%,transparent 95%)" }} />
      <div className="absolute left-1/2 top-0 bottom-0 w-px"
           style={{ background: "linear-gradient(180deg,transparent 5%,rgba(34,211,238,0.05) 30%,rgba(34,211,238,0.07) 50%,rgba(34,211,238,0.05) 70%,transparent 95%)" }} />

      {/* ── Coordinate readouts ── */}
      <div className="absolute top-8 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        <div className="w-2 h-px bg-cyan-500/20" />
        <span className="text-[7px] font-mono text-cyan-500/20 tracking-wider">31.2278°N 121.4692°E</span>
        <div className="w-2 h-px bg-cyan-500/20" />
      </div>
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2">
        <span className="text-[7px] font-mono text-cyan-500/15 tracking-wider">CPS-GRAPHRAG · CLUSTER-01 · ZONE-CN-EAST</span>
      </div>
      <div className="absolute left-6 top-1/2 -translate-y-1/2 hidden xl:block">
        <span className="text-[7px] font-mono text-cyan-500/15 tracking-wider [writing-mode:vertical-rl]">W 121.469°</span>
      </div>
      <div className="absolute right-6 top-1/2 -translate-y-1/2 hidden xl:block">
        <span className="text-[7px] font-mono text-cyan-500/15 tracking-wider [writing-mode:vertical-lr]">E 121.469°</span>
      </div>

      {/* ── Data stream columns — left ── */}
      <div className="absolute left-0 top-7 bottom-8 w-32 hidden xl:flex gap-1 px-1">
        {STREAM_COLS.map((lines, i) => (
          <DataStream key={i} lines={lines} dur={18 + i * 5} delay={-i * 4} color="#22d3ee" />
        ))}
      </div>

      {/* ── Data stream columns — right ── */}
      <div className="absolute right-0 top-7 bottom-8 w-32 hidden xl:flex gap-1 px-1">
        {STREAM_COLS.map((lines, i) => (
          <DataStream key={i} lines={lines} dur={22 + i * 4} delay={-i * 5} color="#818cf8" />
        ))}
      </div>

      {/* ── Signal bars — bottom left ── */}
      <div className="absolute left-36 bottom-9 hidden xl:flex items-end gap-0.5">
        {[4, 6, 9, 12, 15].map((h, i) => (
          <div key={i} className="w-[3px] rounded-sm bg-cyan-400/18" style={{ height: h }} />
        ))}
        <span className="text-[7px] font-mono text-cyan-500/18 ml-1.5 mb-0.5">-72dBm</span>
      </div>

      {/* ── Signal bars — bottom right ── */}
      <div className="absolute right-36 bottom-9 hidden xl:flex items-end gap-0.5">
        <span className="text-[7px] font-mono text-indigo-400/18 mr-1.5 mb-0.5">UPLINK</span>
        {[15, 12, 9, 6, 4].map((h, i) => (
          <div key={i} className="w-[3px] rounded-sm bg-indigo-400/18" style={{ height: h }} />
        ))}
      </div>

      {/* ── Distance markers on axis ── */}
      {[-300, -150, 150, 300].map(x => (
        <div key={x} className="absolute top-1/2 hidden lg:block"
             style={{ left: `calc(50% + ${x}px)`, transform: "translate(-50%, -50%)" }}>
          <div className="w-px h-2 bg-cyan-400/12 mx-auto" />
          <div className="text-[6px] font-mono text-cyan-500/12 text-center">{Math.abs(x)}</div>
        </div>
      ))}
      {[-200, 200].map(y => (
        <div key={y} className="absolute left-1/2 hidden lg:block"
             style={{ top: `calc(50% + ${y}px)`, transform: "translate(-50%, -50%)" }}>
          <div className="h-px w-2 bg-cyan-400/12 my-auto" />
        </div>
      ))}
    </div>
  );
}
