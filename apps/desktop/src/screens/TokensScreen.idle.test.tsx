import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { IDLE_SESSION_TIMEOUT_MS, type IdleSessionFinalization } from "../session_idle";
import { createUsageChangefeedState } from "../usage_changefeed";
import { TokensScreen } from "./TokensScreen";

describe("TokensScreen idle history", () => {
  it("shows bounded idle-finalization history without inventing token zeros", () => {
    const receipt = (id: string): IdleSessionFinalization => ({
      schema: "simplicio.session-idle-finalization/v1",
      status: "logical_closed",
      finalization_id: id,
      profile_id: "default",
      workspace_id: "/workspace",
      now_millis: 1,
      idle_ms: IDLE_SESSION_TIMEOUT_MS,
      closed_sessions: [{ session_id: "s1", status: "idle", updated_at: 1 }],
      usage: {
        status: "pending_provider_refresh",
        metrics: ["input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens", "cache_write_tokens"],
      },
      provider_processes_terminated: false,
      redacted: true,
    });
    const html = renderToStaticMarkup(<TokensScreen usage={{
      changefeed: createUsageChangefeedState(),
      idleFinalization: receipt("sha256:two"),
      idleHistory: [receipt("sha256:two"), receipt("sha256:one")],
    }} />);
    expect(html).toContain("Última finalização");
    expect(html).toContain("Histórico de 2 finalizações");
    expect(html).toContain("não termina processos");
    expect(html).not.toMatch(/0 tokens/);
  });
});
