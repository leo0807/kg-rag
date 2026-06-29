"use client";

const POOL = [
  "0x3A7F2B","NODE_ID:001","INIT_COMPLETE","0b11010110",
  "AUTH_TOKEN","SYS_READY","0xFF3C94","LINK_UP",
  "T:342.7K","P:3100PSI","CPS-1220","VEC_DIM:512",
  "EMBED_OK","GRAPH_QUERY","NEO4J_OK","0x00FF4A",
  "CHUNK:8472","RANK:0.97","RTT:12ms","ATA_100",
  "MILVUS_OK","BM25_IDX","KV_HIT","RRF_FUSION",
  "SEC_CLR","TLS_1.3","GNN_FWD","CYPHER_OK",
  "MATCH:TOP10","RERANK","LLM_STREAM","0b10110011",
  "COORD:X3847","COORD:Y1293","HASH:9f2a","ECC_OK",
  "PKT:0x44AF","DELTA:0.003","BATCH:128","EPOCH:47",
  "LOSS:0.024","ACC:98.7%","F1:0.991","EMBED:BGE",
];
const HUES  = [180, 195, 210, 230, 250, 265];
const COUNT = 52;

// Generate stable layout (not in component body to avoid re-computation)
const ITEMS = Array.from({ length: COUNT }, (_, i) => ({
  text:     POOL[i % POOL.length],
  x:        2 + (i * 1.97 * 7.3) % 94,           // left %
  startY:   5 + (i * 2.31 * 11.7) % 88,           // top %
  dur:      10 + (i * 3 + 7) % 10,                 // s
  delay:    -(((i * 2.17) % 15)),                   // s, already in-flight
  hue:      HUES[i % HUES.length],
  opacity:  0.045 + (i % 5) * 0.022,
  size:     i % 7 === 0 ? 10 : 9,                  // px
}));

export default function FloatingData() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
      {ITEMS.map((it, i) => (
        <span
          key={i}
          className="absolute font-mono whitespace-nowrap"
          style={{
            left:      `${it.x}%`,
            top:       `${it.startY}%`,
            fontSize:  `${it.size}px`,
            color:     `hsl(${it.hue},80%,65%)`,
            opacity:   it.opacity,
            animation: `float-up ${it.dur}s ease-in-out infinite ${it.delay}s`,
          }}
        >
          {it.text}
        </span>
      ))}
    </div>
  );
}
