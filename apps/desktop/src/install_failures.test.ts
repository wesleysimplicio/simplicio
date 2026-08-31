import { describe, expect, it } from "vitest";
import { installFailureMessage } from "./install_failures";

describe("safe installer failure messages", () => {
  it("shows only a bounded nonzero OS exit code and warns about partial effects", () => {
    for (const code of [1, 7, -1, -2_147_483_648, 2_147_483_647]) {
      const message = installFailureMessage(`integration_install_exit_code:${code}`);
      expect(message).toContain(`código ${code}.`);
      expect(message).toContain("alterações parciais");
    }
    for (const value of ["0", "2147483648", "-2147483649", "999999999999999", "1 extra"]) {
      expect(installFailureMessage(`integration_install_exit_code:${value}`)).not.toContain("encerrou com código");
    }
  });

  it("distinguishes invalid output, missing receipts and post-apply verification failure", () => {
    expect(installFailureMessage("integration_install_invalid_json")).toContain("resposta inválida");
    expect(installFailureMessage("integration_install_response_too_large")).toContain("limite permitido");
    expect(installFailureMessage("integration_install_receipt_unconfirmed")).toContain("recibo de instalação completo");
    expect(installFailureMessage(new Error("integration_install_applied_snapshot_unavailable"))).toContain("confirmou a aplicação");
    expect(installFailureMessage("integration_install_no_exit_code")).toContain("sem um código de saída confirmado");
  });

  it("never echoes native output, credentials, paths or object property names", () => {
    for (const error of ["secret-do-not-reflect /private/user/path", new Error("secret-do-not-reflect"),
      "__proto__", "constructor", { message: "secret-do-not-reflect" }, null, "x".repeat(100_000)]) {
      const message = installFailureMessage(error);
      expect(message).not.toContain("secret-do-not-reflect");
      expect(message).not.toContain("/private/user/path");
      expect(message).toContain("O Runtime não confirmou");
      expect(message.length).toBeLessThan(400);
    }
  });

  it("requires fresh review after a changed plan and does not claim a busy install failed", () => {
    expect(installFailureMessage("integration_plan_changed_review_again")).toContain("Revise a configuração");
    expect(installFailureMessage("integration_install_busy")).toContain("já está em andamento");
    expect(installFailureMessage("integration_install_busy")).not.toContain("alterações parciais");
  });
});
