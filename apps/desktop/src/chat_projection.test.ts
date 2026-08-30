import { describe, expect, it } from "vitest";
import { createDemoBotCenter, createUnavailableBotCenter } from "./bot_center";
import { createChatProjection } from "./chat_projection";

describe("chat.session/v1", () => {
  it("keeps session identity, revision and causal events together", () => {
    const projection = createChatProjection(createDemoBotCenter());
    expect(projection.schema).toBe("chat.session/v1");
    expect(projection.sessionId).toBe("bot-cora-session-01");
    expect(projection.revision).toBe(7);
    expect(projection.events.some((event) => event.causalParentId !== null)).toBe(true);
    expect(projection.redaction.secrets).toBe(true);
  });

  it("blocks mutating chat actions without Agent API authority", () => {
    const projection = createChatProjection(createUnavailableBotCenter());
    expect(projection.state).toBe("unavailable");
    expect(projection.actions).toEqual({ send: false, interrupt: false, cancel: false, steer: false });
    expect(projection.reasonCode).toBe("agent_api_unavailable");
  });
});
