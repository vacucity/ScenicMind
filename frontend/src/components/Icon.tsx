import type { ReactNode } from "react";

export type IconName = "dashboard" | "forecast" | "agent" | "prepare" | "history" | "bell" | "chevron" | "back";

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    forecast: <><path d="M4 18V9m6 9V5m6 13v-7m5 7H3"/><path d="m4 8 6-4 6 6 5-5"/></>,
    agent: <><path d="M8 4h8a4 4 0 0 1 4 4v7a4 4 0 0 1-4 4h-5l-4 3v-3a4 4 0 0 1-3-4V8a4 4 0 0 1 4-4Z"/><path d="M8 10h.01M12 10h.01M16 10h.01"/></>,
    prepare: <><path d="M4 5h16v14H4z"/><path d="M8 3v4m8-4v4M4 10h16M8 14h3m2 0h3"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5m4-1v5l3 2"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    back: <path d="m15 18-6-6 6-6"/>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}