import type { ActivityItem, DesktopSnapshot } from "./contracts";

export interface BriefingProjection {
  schema: "ambient.briefing/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  title: string;
  items: Array<{ id: string; title: string; context: string; sourceEventId: string }>;
  schedule: { configured: boolean; nextRun: string | null };
  delivery: { configured: boolean; target: string | null; reasonCode: string };
  reasonCode: string;
}

export function createBriefingProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): BriefingProjection {
  const item = (activity: ActivityItem) => ({ id: `brief-${activity.id}`, title: activity.title, context: activity.detail, sourceEventId: activity.id });
  return {
    schema: "ambient.briefing/v1",
    generatedAt,
    source: snapshot.source,
    title: "Simplicio Briefing",
    items: snapshot.activity.slice(0, 3).map(item),
    schedule: { configured: false, nextRun: null },
    delivery: { configured: false, target: null, reasonCode: "delivery_unconfigured" },
    reasonCode: snapshot.source === "runtime" ? "ambient.briefing_projection_ready" : "ambient.briefing_projection_unavailable",
  };
}
