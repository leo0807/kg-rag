"use client";

import { useEffect, useRef } from "react";

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  r: number;
  opacity: number;
  hue: number;   // 180=cyan 220=blue 270=purple
  pulse: number; // 0=off >0=node with ring
}

interface Pulse {
  from: number; to: number;
  t: number;    // 0→1 progress
  speed: number;
}

export default function ParticleCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -9999, y: -9999 });

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const C = canvas;
    const X = ctx;

    const resize = () => { C.width = C.offsetWidth; C.height = C.offsetHeight; };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(C);

    // Track mouse via window so the canvas can be pointer-events-none
    // (a fullscreen pointer-events-auto canvas eats every click on the page)
    const onMove = (e: MouseEvent) => {
      const rect = C.getBoundingClientRect();
      mouse.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    window.addEventListener("mousemove", onMove);

    const mkParticle = (): Particle => ({
      x: Math.random() * C.width,
      y: Math.random() * C.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      r: Math.random() * 1.6 + 0.7,
      opacity: Math.random() * 0.5 + 0.2,
      hue: [180, 200, 220, 260][Math.floor(Math.random() * 4)],
      pulse: Math.random() < 0.12 ? Math.random() * Math.PI * 2 : 0,
    });

    const count = Math.min(55, Math.floor(C.width / 22));
    const particles: Particle[] = Array.from({ length: count }, mkParticle);
    const MAX_DIST = 120;
    const MOUSE_REPEL = 90;
    const pulses: Pulse[] = [];
    let animId: number;
    let frame = 0;

    function spawnPulse() {
      const candidates: number[] = [];
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          if (Math.sqrt(dx * dx + dy * dy) < MAX_DIST) candidates.push(i * 1000 + j);
        }
      }
      if (candidates.length > 0) {
        const pick = candidates[Math.floor(Math.random() * candidates.length)];
        pulses.push({ from: Math.floor(pick / 1000), to: pick % 1000, t: 0, speed: 0.012 + Math.random() * 0.01 });
      }
    }

    function tick() {
      frame++;
      const w = C.width;
      const h = C.height;
      const mx = mouse.current.x;
      const my = mouse.current.y;
      X.clearRect(0, 0, w, h);

      if (frame % 70 === 0 && pulses.length < 5) spawnPulse();

      for (const p of particles) {
        // Mouse repel
        const dx = p.x - mx;
        const dy = p.y - my;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < MOUSE_REPEL && d > 0) {
          const force = (MOUSE_REPEL - d) / MOUSE_REPEL * 0.012;
          p.vx += (dx / d) * force;
          p.vy += (dy / d) * force;
        }
        // Velocity damping
        p.vx *= 0.995;
        p.vy *= 0.995;
        // Speed cap
        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        if (speed > 0.9) { p.vx *= 0.9 / speed; p.vy *= 0.9 / speed; }

        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        // Pulse ring on "node" particles
        if (p.pulse > 0) {
          p.pulse += 0.025;
          const ring = ((p.pulse % (Math.PI * 2)) / (Math.PI * 2));
          X.beginPath();
          X.arc(p.x, p.y, p.r + ring * 12, 0, Math.PI * 2);
          X.strokeStyle = `hsla(${p.hue},85%,65%,${(1 - ring) * 0.25})`;
          X.lineWidth = 0.8;
          X.stroke();
        }

        // Particle dot
        X.beginPath();
        X.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        X.fillStyle = `hsla(${p.hue},85%,68%,${p.opacity})`;
        X.fill();
      }

      // Connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < MAX_DIST) {
            const alpha = (1 - d / MAX_DIST) * 0.22;
            const hAvg = (particles[i].hue + particles[j].hue) / 2;
            X.beginPath();
            X.moveTo(particles[i].x, particles[i].y);
            X.lineTo(particles[j].x, particles[j].y);
            X.strokeStyle = `hsla(${hAvg},80%,60%,${alpha})`;
            X.lineWidth = 0.6;
            X.stroke();
          }
        }
      }

      // Data pulses traveling along edges
      for (let k = pulses.length - 1; k >= 0; k--) {
        const pl = pulses[k];
        pl.t += pl.speed;
        if (pl.t >= 1) { pulses.splice(k, 1); continue; }
        const pa = particles[pl.from];
        const pb = particles[pl.to];
        const dx = pb.x - pa.x;
        const dy = pb.y - pa.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d >= MAX_DIST) { pulses.splice(k, 1); continue; }
        const px = pa.x + dx * pl.t;
        const py = pa.y + dy * pl.t;
        const trail = 0.15;
        const grad = X.createLinearGradient(
          pa.x + dx * (pl.t - trail), pa.y + dy * (pl.t - trail),
          px, py
        );
        grad.addColorStop(0, "rgba(34,211,238,0)");
        grad.addColorStop(1, "rgba(34,211,238,0.9)");
        X.beginPath();
        X.moveTo(pa.x + dx * Math.max(0, pl.t - trail), pa.y + dy * Math.max(0, pl.t - trail));
        X.lineTo(px, py);
        X.strokeStyle = grad;
        X.lineWidth = 1.5;
        X.stroke();

        X.beginPath();
        X.arc(px, py, 2.2, 0, Math.PI * 2);
        X.fillStyle = "rgba(34,211,238,0.95)";
        X.fill();
      }

      animId = requestAnimationFrame(tick);
    }

    tick();
    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      className="absolute inset-0 w-full h-full pointer-events-none opacity-75"
    />
  );
}
