import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";
import { createCapabilityRegistry } from "./capability_registry";

export type SearchEntityKind = "capability" | "session" | "work_item" | "artifact" | "team";

export interface SearchEntity {
  id: string;
  kind: SearchEntityKind;
  label: string;
  target: string;
  indexed: true;
  secretIndexed: false;
}

export interface OmniSearchProjection {
  schema: "search.omni/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  entities: SearchEntity[];
  reasonCode: string;
}

export function createOmniSearchProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): OmniSearchProjection {
  const capabilities = createCapabilityRegistry(snapshot).capabilities;
  const entities: SearchEntity[] = capabilities.map((capability) => ({ id: capability.id, kind: "capability", label: capability.name, target: `apps/${capability.id}`, indexed: true, secretIndexed: false }));
  for (const session of botCenter.sessions) entities.push({ id: session.sessionId, kind: "session", label: botCenter.bots.find((bot) => bot.botId === session.botId)?.displayName ?? session.sessionId, target: `chats/${session.sessionId}`, indexed: true, secretIndexed: false });
  entities.push({ id: "WI-01", kind: "work_item", label: "Revisar integração do Desktop", target: "work/WI-01", indexed: true, secretIndexed: false });
  entities.push({ id: "desktop-bot-mode-plan.md", kind: "artifact", label: "desktop-bot-mode-plan.md", target: "library/desktop-bot-mode-plan.md", indexed: true, secretIndexed: false });
  entities.push({ id: "team-desktop", kind: "team", label: "Desktop", target: "teams/team-desktop", indexed: true, secretIndexed: false });
  return { schema: "search.omni/v1", generatedAt, source: snapshot.source, entities, reasonCode: snapshot.source === "runtime" ? "search.omni_projection_ready" : "search.omni_projection_unavailable" };
}

export function searchOmni(projection: OmniSearchProjection, query: string): SearchEntity[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return projection.entities;
  return projection.entities.filter((entity) => `${entity.label} ${entity.kind}`.toLocaleLowerCase().includes(normalized));
}
