import type { DesktopSnapshot } from "./contracts";

export interface WidgetProjection {
  id: string;
  kind: "today" | "tokens" | "activity" | "live" | "library";
  title: string;
  pinned: boolean;
  readonly: true;
  source: "runtime" | "preview";
}

export interface WidgetsProjection {
  schema: "capability.widgets/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  maxPinned: 3;
  widgets: WidgetProjection[];
  writesAvailable: boolean;
  reasonCode: string;
}

export function createWidgetsProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): WidgetsProjection {
  return {
    schema: "capability.widgets/v1",
    generatedAt,
    source: snapshot.source,
    maxPinned: 3,
    widgets: [],
    writesAvailable: snapshot.source === "runtime" && snapshot.runtime.state === "healthy",
    reasonCode: snapshot.source === "runtime" ? "capability.widgets_projection_ready" : "capability.widgets_projection_unavailable",
  };
}
