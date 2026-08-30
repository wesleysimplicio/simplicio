import type { DesktopSnapshot } from "./contracts";

export interface TrayProjection {
  schema: "desktop.tray/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  visible: boolean;
  label: "Simplicio";
  activeWorkCount: number;
  unreadAttentionCount: number;
  notifications: Array<{ id: string; title: string; reasonCode: string }>;
  keepsRuntimeAlive: false;
  reasonCode: string;
}

export function createTrayProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): TrayProjection {
  const attention = snapshot.activity.filter((item) => item.status === "attention");
  return {
    schema: "desktop.tray/v1",
    generatedAt,
    source: snapshot.source,
    visible: attention.length > 0,
    label: "Simplicio",
    activeWorkCount: snapshot.activity.filter((item) => item.status === "running").length,
    unreadAttentionCount: attention.length,
    notifications: attention.map((item) => ({ id: item.id, title: item.title, reasonCode: "attention_receipt" })),
    keepsRuntimeAlive: false,
    reasonCode: snapshot.source === "runtime" ? "desktop.tray_projection_ready" : "desktop.tray_projection_unavailable",
  };
}
