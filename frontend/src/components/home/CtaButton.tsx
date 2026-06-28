"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function CtaButton() {
  return (
    <div style={{ animation: "slide-up-fade 0.7s ease 0.75s both" }}>
      <Link
        href="/library"
        className="group inline-flex items-center gap-2.5 px-7 py-3 rounded-full font-semibold text-sm text-white transition-all duration-300"
        style={{ background: "linear-gradient(135deg, #1B6BB5 0%, #22d3ee 100%)" }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLAnchorElement).style.boxShadow = "0 0 30px rgba(34,211,238,0.4)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLAnchorElement).style.boxShadow = "";
        }}
      >
        进入系统
        <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
      </Link>
    </div>
  );
}
