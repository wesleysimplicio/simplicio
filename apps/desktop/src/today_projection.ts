import type { ActivityItem, DesktopSnapshot } from "./contracts";

export interface TodayQueueItem {
  id: string;
  title: string;
  detail: string;
  provider: string;
  status: ActivityItem["status"];
  occurredAt: string;
}

export interface TodayProjection {
  schema: "ambient.today/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  focus: TodayQueueItem | null;
  inProgress: TodayQueueItem[];
  upNext: TodayQueueItem[];
  limits: { focus: 1; inProgress: 3; upNext: 3 };
  reasonCode: "ambient.today_projection_unavailable" | "ambient.today_projection_ready";
}

function item(activity: ActivityItem): TodayQueueItem {
  return {
    id: activity.id,
    title: activity.title,
    detail: activity.detail,
    provider: activity.provider,
    status: activity.status,
    occurredAt: activity.occurredAt,
  };
}

/**
 * The Desktop only projects a bounded queue. Ordering and lifecycle remain
 * Runtime authority once `ambient.today/v1` is available.
 */
export function createTodayProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): TodayProjection {
  const activities = snapshot.activity.map(item);
  return {
    schema: "ambient.today/v1",
    generatedAt,
    source: snapshot.source,
    focus: activities[0] ?? null,
    inProgress: activities.filter((entry) => entry.status === "running").slice(0, 3),
    upNext: activities.filter((entry) => entry.status !== "running").slice(1, 4),
    limits: { focus: 1, inProgress: 3, upNext: 3 },
    reasonCode: snapshot.source === "runtime" ? "ambient.today_projection_ready" : "ambient.today_projection_unavailable",
  };
}
