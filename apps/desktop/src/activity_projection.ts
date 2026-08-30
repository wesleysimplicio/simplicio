import type { ActivityItem, DesktopSnapshot } from "./contracts";

export interface ActivityProjection {
  schema: "activity.center/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  items: ActivityItem[];
  pageSize: number;
  exportHandle: string | null;
  redaction: { details: false; prompts: true; credentials: true; rawLedgers: true };
  reasonCode: string;
}

export function createActivityProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): ActivityProjection {
  return {
    schema: "activity.center/v1",
    generatedAt,
    source: snapshot.source,
    items: snapshot.activity.slice(0, Math.min(snapshot.limits.maxActivity, 5)),
    pageSize: Math.min(snapshot.limits.maxActivity, 5),
    exportHandle: snapshot.source === "runtime" ? "artifact://activity-report" : null,
    redaction: { details: false, prompts: true, credentials: true, rawLedgers: true },
    reasonCode: snapshot.source === "runtime" ? "activity.center_projection_ready" : "activity.center_projection_unavailable",
  };
}
