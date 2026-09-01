export type InstallFailureRecovery = "review" | "reconcile";

const REVIEW_CODES = new Set([
  "host_plugin_plan_digest_mismatch",
  "host_plugin_plan_precondition_changed",
]);

function nativeCode(error: unknown): string {
  const candidate = typeof error === "string" ? error : error instanceof Error ? error.message : "";
  return typeof candidate === "string" && /^[a-z][a-z0-9_]{0,95}$/.test(candidate) ? candidate : "";
}

/**
 * A hint for the UI, never authority to retry an effect. Only Runtime errors
 * that unambiguously reject the reviewed plan before apply permit a new review.
 * Every other unknown result must be clarified from Runtime-owned state.
 */
export function installFailureRecovery(error: unknown): InstallFailureRecovery {
  return REVIEW_CODES.has(nativeCode(error)) ? "review" : "reconcile";
}

/** Translate only closed codes. Runtime output, paths and diagnostic detail are never reflected. */
export function installFailureMessage(error: unknown): string {
  switch (nativeCode(error)) {
    case "host_plugin_plan_digest_mismatch":
    case "host_plugin_plan_precondition_changed":
      return "O plano mudou. Revise a configuração e confirme o novo digest antes de aplicar.";
    case "host_plugin_response_invalid":
    case "host_plugin_contract_invalid":
    case "host_plugin_failure_invalid":
      return "O Runtime não devolveu um contrato canônico de plugins. Nenhuma nova aplicação será iniciada até o estado ser esclarecido.";
    case "runtime_install_timeout":
    case "runtime_process_cleanup_unconfirmed":
    case "host_plugin_apply_unavailable":
    case "host_plugin_reconcile_unavailable":
      return "O Runtime não confirmou o resultado da operação. Consulte o estado canônico antes de qualquer nova aplicação.";
    case "host_plugin_plan_digest_invalid":
    case "host_plugin_receipt_id_invalid":
      return "O identificador autorizado não é válido. Prepare um novo plano ou consulte o estado do Runtime.";
    default:
      return "O Runtime não confirmou o resultado da operação de plugins. Consulte o estado canônico; atualizar a tela não repete nem reconcilia a aplicação.";
  }
}
