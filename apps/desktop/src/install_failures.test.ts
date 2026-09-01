import { describe, expect, it } from "vitest";
import { installFailureMessage, installFailureRecovery } from "./install_failures";

describe("host plugin failures", () => {
  it("permits a new review only for an unambiguously rejected plan", () => {
    expect(installFailureRecovery("host_plugin_plan_digest_mismatch")).toBe("review");
    expect(installFailureRecovery(new Error("host_plugin_plan_precondition_changed"))).toBe("review");
    for (const failure of ["runtime_install_timeout", "host_plugin_apply_unavailable", "unknown_runtime_error", { code: "host_plugin_plan_digest_mismatch" }]) {
      expect(installFailureRecovery(failure)).toBe("reconcile");
    }
  });

  it("uses fixed messages and never reflects output, paths or structured details", () => {
    expect(installFailureMessage("host_plugin_plan_precondition_changed")).toContain("O plano mudou");
    expect(installFailureMessage("runtime_install_timeout")).toContain("não confirmou");
    for (const failure of [
      "SECRET /private/user",
      { code: "host_plugin_failure", detail: "SECRET /private/user" },
      new Error("SECRET /private/user"),
    ]) {
      const message = installFailureMessage(failure);
      expect(message).not.toContain("SECRET");
      expect(message).not.toContain("/private/user");
      expect(message).toContain("estado canônico");
    }
  });
});
