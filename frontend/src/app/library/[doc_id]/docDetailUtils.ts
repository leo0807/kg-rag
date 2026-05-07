"use client";

import type { Section } from "./useDocDetailTypes";

export function sortSections(sections: Section[]): Section[] {
  return [...sections].sort((a, b) => {
    const aParts = a.number.split(".").map((p) => parseInt(p, 10) || 0);
    const bParts = b.number.split(".").map((p) => parseInt(p, 10) || 0);
    for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
      const diff = (aParts[i] ?? 0) - (bParts[i] ?? 0);
      if (diff !== 0) return diff;
    }
    return 0;
  });
}

export function buildWatermarkUrl(name: string, time: string): string {
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="140">
  <g transform="rotate(-30 140 70)" opacity="0.13" fill="#94a3b8"
     font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" text-anchor="middle">
    <text x="140" y="58"  font-size="15" font-weight="600">${name}</text>
    <text x="140" y="82"  font-size="11">${time}</text>
  </g>
</svg>`.trim();
  return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
}

export interface UserInfo {
  username: string;
  full_name: string;
  department: string;
  is_admin?: boolean;
}

export function getCurrentUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
