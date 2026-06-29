export default function LoginBackdrop() {
  return (
    <>
      {/* Hex grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.05]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100' viewBox='0 0 56 100'%3E%3Cpath d='M28 66L0 50V18L28 2l28 16v32L28 66zm0 0v34' fill='none' stroke='%2322d3ee' stroke-width='0.5'/%3E%3C/svg%3E")`,
        backgroundSize: "56px 100px",
      }} />

      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full blur-[140px]"
             style={{ background: "radial-gradient(circle,rgba(34,211,238,0.06),rgba(99,102,241,0.04),transparent 70%)" }} />
        <div className="absolute top-1/4 right-1/3 w-72 h-72 bg-blue-600/5 rounded-full blur-[80px]" />
      </div>

      {/* Scanline */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute left-0 right-0 h-px" style={{
          background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.35) 50%,transparent)",
          animation: "scanline 10s ease-in-out infinite",
        }} />
      </div>

      {/* Top / bottom bars */}
      <div className="absolute top-0 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.6) 50%,transparent)" }} />
      <div className="absolute bottom-0 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(99,102,241,0.4) 50%,transparent)" }} />

      {/* HUD corners */}
      {[
        "absolute top-5 left-5 border-l-2 border-t-2",
        "absolute top-5 right-5 border-r-2 border-t-2",
        "absolute bottom-5 left-5 border-l-2 border-b-2",
        "absolute bottom-5 right-5 border-r-2 border-b-2",
      ].map((cls, i) => (
        <div key={i} className={`${cls} w-8 h-8 border-cyan-400/30 pointer-events-none`}
             style={{ animation: `corner-appear 0.8s ease both ${300 + i * 80}ms` }} />
      ))}
    </>
  );
}
