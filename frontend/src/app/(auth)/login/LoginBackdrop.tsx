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
             style={{ background: "radial-gradient(circle,rgba(34,211,238,0.07),rgba(99,102,241,0.05),transparent 70%)" }} />
        <div className="absolute top-1/4 right-1/3 w-72 h-72 bg-blue-600/5 rounded-full blur-[80px]" />
        {/* Extra glow bottom-left */}
        <div className="absolute bottom-1/4 left-1/4 w-60 h-60 rounded-full blur-[100px]"
             style={{ background: "rgba(99,102,241,0.05)" }} />
      </div>

      {/* Scanline */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute left-0 right-0 h-px" style={{
          background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.35) 50%,transparent)",
          animation: "scanline 10s ease-in-out infinite",
        }} />
      </div>

      {/* Top classification bar */}
      <div className="absolute top-0 inset-x-0 h-6 flex items-center justify-center gap-5 pointer-events-none z-10"
           style={{ background: "rgba(2,6,16,0.8)", borderBottom: "1px solid rgba(34,211,238,0.1)" }}>
        {["COMAC INTERNAL", "CPS-AUTH-PORTAL", "SEC-LEVEL-2", "ATA100", "ENCRYPTED"].map((t, i) => (
          <span key={i} className="text-[8px] font-mono text-gray-700 tracking-widest hidden sm:inline">{t}</span>
        ))}
      </div>

      {/* Top / bottom bars */}
      <div className="absolute top-6 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.6) 50%,transparent)" }} />
      <div className="absolute bottom-0 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(99,102,241,0.4) 50%,transparent)" }} />

      {/* Bottom ticker */}
      <div className="absolute bottom-0 inset-x-0 h-6 flex items-center pointer-events-none overflow-hidden"
           style={{ background: "rgba(2,6,16,0.8)", borderTop: "1px solid rgba(34,211,238,0.1)" }}>
        <div className="flex-shrink-0 flex items-center gap-2 px-3 h-full border-r"
             style={{ borderColor: "rgba(34,211,238,0.12)" }}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"
                style={{ boxShadow: "0 0 5px #4ade80" }} />
          <span className="text-[8px] font-mono text-emerald-500/60 tracking-widest">SECURE</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <div className="flex whitespace-nowrap" style={{ animation: "ticker-scroll 30s linear infinite" }}>
            {[
              "TLS 1.3 加密连接已建立",
              "JWT RS256 签名验证就绪",
              "Neo4j BOLT 连接池正常",
              "身份验证服务在线",
              "访问日志记录中",
              "系统健康状态：全部正常",
            ].concat([
              "TLS 1.3 加密连接已建立",
              "JWT RS256 签名验证就绪",
              "Neo4j BOLT 连接池正常",
              "身份验证服务在线",
              "访问日志记录中",
              "系统健康状态：全部正常",
            ]).map((msg, i) => (
              <span key={i} className="inline-flex items-center gap-2 text-[9px] font-mono text-gray-700 px-5">
                <span className="text-cyan-600/30">◆</span>{msg}
              </span>
            ))}
          </div>
        </div>
        <div className="flex-shrink-0 px-3 border-l h-full flex items-center"
             style={{ borderColor: "rgba(34,211,238,0.12)" }}>
          <span className="text-[8px] font-mono text-gray-700">AES-256</span>
        </div>
      </div>

      {/* HUD corners */}
      {[
        { cls: "absolute top-8 left-5 border-l-2 border-t-2",  label: "CPS//AUTH",  ta: "mt-1" },
        { cls: "absolute top-8 right-5 border-r-2 border-t-2", label: "v1.1.0",     ta: "mt-1 text-right" },
        { cls: "absolute bottom-8 left-5 border-l-2 border-b-2", label: "COMAC",    ta: "mb-1 order-first" },
        { cls: "absolute bottom-8 right-5 border-r-2 border-b-2", label: "SECURE",  ta: "mb-1 order-first text-right" },
      ].map(({ cls, label, ta }, i) => (
        <div key={i} className={`${cls} w-10 h-10 border-cyan-400/30 pointer-events-none flex flex-col`}
             style={{ animation: `corner-appear 0.8s ease both ${300 + i * 80}ms` }}>
          <span className={`${ta} text-[7px] font-mono text-cyan-500/25 tracking-widest`}>{label}</span>
        </div>
      ))}

      {/* Floating data bits — left */}
      <div className="absolute left-12 top-1/3 pointer-events-none hidden lg:flex flex-col gap-2 opacity-[0.15]"
           style={{ animation: "slide-in-left 1s ease both 1.2s" }}>
        {["0x4F3A", "11001010", "AUTH_OK", "0xFF32", "GRANT"].map((v, i) => (
          <div key={i} className="text-[9px] font-mono text-cyan-400/60"
               style={{ animation: `float-y ${3 + i * 0.4}s ease-in-out infinite ${i * 0.3}s` }}>{v}</div>
        ))}
      </div>

      {/* Floating data bits — right */}
      <div className="absolute right-12 top-2/5 pointer-events-none hidden lg:flex flex-col gap-2 opacity-[0.15]"
           style={{ animation: "slide-in-right 1s ease both 1.3s" }}>
        {["NEO4J", "0x1B4F", "BOLT↑", "10110011", "RSA_OK"].map((v, i) => (
          <div key={i} className="text-[9px] font-mono text-indigo-400/60 text-right"
               style={{ animation: `float-y ${3.5 + i * 0.3}s ease-in-out infinite ${i * 0.25}s` }}>{v}</div>
        ))}
      </div>
    </>
  );
}
