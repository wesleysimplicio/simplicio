import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createMultiChatProjection } from "./multi_chat_projection";

describe("chat.workspace/v1", () => {
  it("lists sessions by canonical IDs and revisions", () => {
    const projection = createMultiChatProjection(createDemoBotCenter());
    expect(projection.schema).toBe("chat.workspace/v1");
    expect(projection.selectedSessionId).toBe("bot-cora-session-01");
    expect(projection.sessions[0]).toMatchObject({ botId: "bot-cora", revision: 7 });
    expect(projection.sessions[0].unread).toBeGreaterThan(0);
  });

  it("does not expose a create-session effect in preview", () => {
    expect(createMultiChatProjection(createDemoBotCenter()).reasonCode).toBe("chat.workspace_projection_unavailable");
  });
});
