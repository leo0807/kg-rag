import ParticleCanvas from "@/components/home/ParticleCanvas";
import HeroTitle from "@/components/home/HeroTitle";
import StatsRow from "@/components/home/StatsRow";
import FeatureGrid from "@/components/home/FeatureGrid";
import CtaButton from "@/components/home/CtaButton";

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-gray-950 flex flex-col items-center justify-center overflow-hidden px-5 py-14">
      {/* Particle network background */}
      <ParticleCanvas />

      {/* Dot-grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(27,107,181,0.12) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      {/* Radial glow behind hero */}
      <div
        className="absolute pointer-events-none"
        style={{
          top: "32%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: "680px",
          height: "380px",
          background:
            "radial-gradient(ellipse, rgba(27,107,181,0.13) 0%, transparent 70%)",
        }}
      />

      {/* Top scan-line accent */}
      <div
        className="absolute top-0 left-0 right-0 h-px pointer-events-none"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.5) 50%, transparent 100%)",
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center gap-10 w-full max-w-3xl">
        <HeroTitle />
        <StatsRow />
        <FeatureGrid />
        <CtaButton />

        <p
          className="text-[11px] text-gray-700 tracking-widest"
          style={{ animation: "slide-up-fade 0.6s ease 0.9s both" }}
        >
          商用飞机有限责任公司 · 航空工艺规范知识图谱系统
        </p>
      </div>
    </div>
  );
}
