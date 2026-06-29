export default function LoginBackdrop() {
  return (
    <>
      {/* Hex grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.05]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100' viewBox='0 0 56 100'%3E%3Cpath d='M28 66L0 50V18L28 2l28 16v32L28 66zm0 0v34' fill='none' stroke='%2322d3ee' stroke-width='0.5'/%3E%3C/svg%3E")`,
        backgroundSize: "56px 100px",
      }} />

      {/* Circuit traces — top-left */}
      <svg className="absolute top-0 left-0 w-80 h-64 pointer-events-none opacity-[0.09]" viewBox="0 0 320 256">
        <path d="M0 90 L60 90 L80 70 L190 70 L210 50 L320 50" stroke="#22d3ee" strokeWidth="0.9" fill="none"
              strokeDasharray="6 4" style={{ animation: "circuit-flow 4s linear infinite" }} />
        <path d="M0 130 L40 130 L60 110 L130 110 L150 90" stroke="#22d3ee" strokeWidth="0.6" fill="none"
              strokeDasharray="4 8" style={{ animation: "circuit-flow 6s linear infinite" }} />
        <path d="M0 55 L30 55 L30 110" stroke="#22d3ee" strokeWidth="0.5" fill="none"
              strokeDasharray="3 6" style={{ animation: "circuit-flow 5s linear infinite" }} />
        <path d="M110 0 L110 70" stroke="#22d3ee" strokeWidth="0.5" fill="none"
              strokeDasharray="3 6" style={{ animation: "circuit-flow 7s linear infinite reverse" }} />
        <circle cx="60" cy="90" r="2.5" fill="#22d3ee" opacity="0.7" />
        <circle cx="80" cy="70" r="2" fill="#22d3ee" opacity="0.5" />
        <circle cx="210" cy="50" r="2.5" fill="#22d3ee" opacity="0.7" />
        <circle cx="40" cy="130" r="1.5" fill="#22d3ee" opacity="0.5" />
        <circle cx="110" cy="70" r="3" fill="none" stroke="#22d3ee" strokeWidth="0.8" opacity="0.5" />
      </svg>

      {/* Circuit traces — bottom-right */}
      <svg className="absolute bottom-0 right-0 w-80 h-64 pointer-events-none opacity-[0.09]" viewBox="0 0 320 256">
        <path d="M320 166 L260 166 L240 186 L130 186 L110 206 L0 206" stroke="#818cf8" strokeWidth="0.9" fill="none"
              strokeDasharray="6 4" style={{ animation: "circuit-flow 4s linear infinite reverse" }} />
        <path d="M320 126 L280 126 L260 146 L190 146 L170 166" stroke="#818cf8" strokeWidth="0.6" fill="none"
              strokeDasharray="4 8" style={{ animation: "circuit-flow 5.5s linear infinite reverse" }} />
        <path d="M320 201 L290 201 L290 146" stroke="#818cf8" strokeWidth="0.5" fill="none"
              strokeDasharray="3 6" style={{ animation: "circuit-flow 6s linear infinite reverse" }} />
        <path d="M210 256 L210 186" stroke="#818cf8" strokeWidth="0.5" fill="none"
              strokeDasharray="3 6" style={{ animation: "circuit-flow 7.5s linear infinite" }} />
        <circle cx="260" cy="166" r="2.5" fill="#818cf8" opacity="0.7" />
        <circle cx="240" cy="186" r="2" fill="#818cf8" opacity="0.5" />
        <circle cx="110" cy="206" r="2.5" fill="#818cf8" opacity="0.7" />
        <circle cx="280" cy="126" r="1.5" fill="#818cf8" opacity="0.5" />
        <circle cx="210" cy="186" r="3" fill="none" stroke="#818cf8" strokeWidth="0.8" opacity="0.5" />
      </svg>

      {/* Center targeting reticle (very subtle) */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.025]">
        <div className="relative w-[500px] h-[500px]">
          <div className="absolute inset-0 border border-cyan-400 rounded-full"
               style={{ animation: "spin-slow 30s linear infinite" }} />
          <div className="absolute inset-10 border border-indigo-400/80 rounded-full"
               style={{ animation: "spin-slow 22s linear infinite reverse" }} />
          <div className="absolute inset-20 border border-cyan-400/50 rounded-full" />
          <div className="absolute top-1/2 left-0 right-0 h-px bg-cyan-400/40" />
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-cyan-400/40" />
          <div className="absolute inset-0 rounded-full overflow-hidden"
               style={{ animation: "radar-sweep 12s linear infinite" }}>
            <div className="absolute top-1/2 left-1/2 w-60 h-px origin-left"
                 style={{ background: "linear-gradient(90deg,rgba(34,211,238,0.6),transparent)" }} />
          </div>
        </div>
      </div>

      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full blur-[140px]"
             style={{ background: "radial-gradient(circle,rgba(34,211,238,0.07),rgba(99,102,241,0.05),transparent 70%)" }} />
        <div className="absolute top-1/4 right-1/3 w-72 h-72 bg-blue-600/5 rounded-full blur-[80px]" />
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
           style={{ background: "rgba(2,6,16,0.85)", borderBottom: "1px solid rgba(34,211,238,0.1)" }}>
        {["COMAC INTERNAL", "CPS-AUTH-PORTAL", "SEC-LEVEL-2", "ATA100", "ENCRYPTED"].map((t, i) => (
          <span key={i} className="text-[8px] font-mono text-gray-700 tracking-widest hidden sm:inline">{t}</span>
        ))}
      </div>

      {/* Top / bottom bars */}
      <div className="absolute top-6 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.6) 50%,transparent)" }} />
      <div className="absolute bottom-6 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(99,102,241,0.4) 50%,transparent)" }} />

      {/* Bottom ticker */}
      <div className="absolute bottom-0 inset-x-0 h-6 flex items-center pointer-events-none overflow-hidden"
           style={{ background: "rgba(2,6,16,0.85)", borderTop: "1px solid rgba(34,211,238,0.1)" }}>
        <div className="flex-shrink-0 flex items-center gap-2 px-3 h-full border-r"
             style={{ borderColor: "rgba(34,211,238,0.12)" }}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ boxShadow: "0 0 5px #4ade80" }} />
          <span className="text-[8px] font-mono text-emerald-500/60 tracking-widest">SECURE</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <div className="flex whitespace-nowrap" style={{ animation: "ticker-scroll 30s linear infinite" }}>
            {[
              "TLS 1.3 加密连接已建立", "JWT RS256 签名验证就绪",
              "Neo4j BOLT 连接池正常", "身份验证服务在线",
              "访问日志记录中", "系统健康状态：全部正常",
              "TLS 1.3 加密连接已建立", "JWT RS256 签名验证就绪",
              "Neo4j BOLT 连接池正常", "身份验证服务在线",
              "访问日志记录中", "系统健康状态：全部正常",
            ].map((msg, i) => (
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
        { cls: "absolute top-8 left-5 border-l-2 border-t-2",    label: "CPS//AUTH", ta: "mt-1" },
        { cls: "absolute top-8 right-5 border-r-2 border-t-2",   label: "v1.1.0",    ta: "mt-1 text-right" },
        { cls: "absolute bottom-8 left-5 border-l-2 border-b-2", label: "COMAC",     ta: "mb-1 order-first" },
        { cls: "absolute bottom-8 right-5 border-r-2 border-b-2",label: "SECURE",    ta: "mb-1 order-first text-right" },
      ].map(({ cls, label, ta }, i) => (
        <div key={i} className={`${cls} w-10 h-10 border-cyan-400/30 pointer-events-none flex flex-col`}
             style={{ animation: `corner-appear 0.8s ease both ${300 + i * 80}ms` }}>
          <span className={`${ta} text-[7px] font-mono text-cyan-500/25 tracking-widest`}>{label}</span>
        </div>
      ))}

      {/* Floating data bits — left */}
      <div className="absolute left-10 top-1/3 pointer-events-none hidden lg:flex flex-col gap-2 opacity-[0.14]"
           style={{ animation: "slide-in-left 1s ease both 1.2s" }}>
        {["0x4F3A", "11001010", "AUTH_OK", "0xFF32", "GRANT", "1B4F9B"].map((v, i) => (
          <div key={i} className="text-[9px] font-mono text-cyan-400/70"
               style={{ animation: `float-y ${3 + i * 0.4}s ease-in-out infinite ${i * 0.3}s` }}>{v}</div>
        ))}
      </div>

      {/* Floating data bits — right */}
      <div className="absolute right-10 top-1/3 pointer-events-none hidden lg:flex flex-col gap-2 opacity-[0.14]"
           style={{ animation: "slide-in-right 1s ease both 1.3s" }}>
        {["NEO4J", "0x1B4F", "BOLT↑", "10110011", "RSA_OK", "SHA256"].map((v, i) => (
          <div key={i} className="text-[9px] font-mono text-indigo-400/70 text-right"
               style={{ animation: `float-y ${3.5 + i * 0.3}s ease-in-out infinite ${i * 0.25}s` }}>{v}</div>
        ))}
      </div>
    </>
  );
}
