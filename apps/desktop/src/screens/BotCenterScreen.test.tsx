import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createDemoBotCenter, type BotActionRequest } from "../bot_center";
import { BotCenterScreen, dispatchAvailableBotAction } from "./BotCenterScreen";

const request: BotActionRequest = { kind: "approve", botId: "test-bot", sessionId: "test-session", approvalId: "test-approval" };

describe("Bot Center action availability", () => {
  it("keeps readonly approval history visible while disabling both decisions", () => {
    const snapshot = createDemoBotCenter();
    snapshot.actionAuthority = "unavailable";
    const onAction = vi.fn().mockResolvedValue(undefined);
    const html = renderToStaticMarkup(<BotCenterScreen snapshot={snapshot} onAction={onAction} />);
    expect(html).toContain("Contrato indisponível");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Aprovar<\/button>/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Negar<\/button>/);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("never calls the action or changes busy state without action authority", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    const onBusy = vi.fn();
    const pending = { current: false };
    await dispatchAvailableBotAction({ request, authority: "unavailable", pending, onAction, onBusy });
    expect(onAction).not.toHaveBeenCalled();
    expect(onBusy).not.toHaveBeenCalled();
    expect(pending.current).toBe(false);
  });

  it.each(["runtime", "preview"] as const)("dispatches once while a %s action is pending", async (authority) => {
    let finish!: () => void;
    const onAction = vi.fn(() => new Promise<void>((resolve) => { finish = resolve; }));
    const onBusy = vi.fn();
    const pending = { current: false };
    const first = dispatchAvailableBotAction({ request, authority, pending, onAction, onBusy });
    expect(pending.current).toBe(true);
    await dispatchAvailableBotAction({ request: { ...request, kind: "deny" }, authority, pending, onAction, onBusy });
    expect(onAction).toHaveBeenCalledExactlyOnceWith(request);
    expect(onBusy).toHaveBeenCalledExactlyOnceWith("approve");
    finish();
    await first;
    expect(pending.current).toBe(false);
    expect(onBusy.mock.calls).toEqual([["approve"], [null]]);
  });

  it("releases local busy state after rejection without hiding the failure or retrying", async () => {
    const failure = new Error("test-only action failure");
    const onAction = vi.fn().mockRejectedValue(failure);
    const onBusy = vi.fn();
    const pending = { current: false };
    await expect(dispatchAvailableBotAction({ request, authority: "runtime", pending, onAction, onBusy })).rejects.toBe(failure);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(pending.current).toBe(false);
    expect(onBusy.mock.calls).toEqual([["approve"], [null]]);
  });
});
