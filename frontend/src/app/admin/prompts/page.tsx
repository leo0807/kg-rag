"use client";

import { PromptsAdminPanel } from "./PromptsAdminPanel";

export default function AdminPromptsPage() {
  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <PromptsAdminPanel />
    </div>
  );
}
