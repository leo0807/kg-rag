"use client";

import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  opacity: number;
}

export default function ParticleCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Rebind after null-check so closures keep the narrowed type
    const C: HTMLCanvasElement = canvas;
    const X: CanvasRenderingContext2D = ctx;

    const resize = () => {
      C.width = C.offsetWidth;
      C.height = C.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(C);

    const mkParticle = (): Particle => ({
      x: Math.random() * C.width,
      y: Math.random() * C.height,
      vx: (Math.random() - 0.5) * 0.45,
      vy: (Math.random() - 0.5) * 0.45,
      r: Math.random() * 1.8 + 0.8,
      opacity: Math.random() * 0.55 + 0.15,
    });

    const count = Math.min(90, Math.floor(C.width / 14));
    const particles: Particle[] = Array.from({ length: count }, mkParticle);
    const MAX_DIST = 140;
    let animId: number;

    function tick() {
      const w = C.width;
      const h = C.height;
      X.clearRect(0, 0, w, h);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        X.beginPath();
        X.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        X.fillStyle = `rgba(100,180,255,${p.opacity})`;
        X.fill();
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < MAX_DIST) {
            X.beginPath();
            X.moveTo(particles[i].x, particles[i].y);
            X.lineTo(particles[j].x, particles[j].y);
            X.strokeStyle = `rgba(27,107,181,${(1 - d / MAX_DIST) * 0.28})`;
            X.lineWidth = 0.7;
            X.stroke();
          }
        }
      }

      animId = requestAnimationFrame(tick);
    }

    tick();
    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={ref}
      className="absolute inset-0 w-full h-full pointer-events-none opacity-70"
    />
  );
}
