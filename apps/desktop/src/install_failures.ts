const REVIEW_BEFORE_RETRY = "Pode haver alterações parciais. Atualize o diagnóstico e revise um novo plano antes de tentar novamente.";

const MESSAGES: Readonly<Record<string, string>> = {
  integration_plan_changed_review_again: "O plano mudou. Revise a configuração novamente antes de aplicar.",
  integration_install_busy: "Uma instalação já está em andamento. Aguarde a conclusão antes de tentar novamente.",
  integration_install_output_unavailable: `Não foi possível obter o resultado do instalador. ${REVIEW_BEFORE_RETRY}`,
  integration_install_no_exit_code: `O instalador terminou sem um código de saída confirmado. ${REVIEW_BEFORE_RETRY}`,
  integration_install_invalid_json: `O instalador devolveu uma resposta inválida. ${REVIEW_BEFORE_RETRY}`,
  integration_install_response_too_large: `A resposta do instalador ultrapassou o limite permitido. ${REVIEW_BEFORE_RETRY}`,
  integration_install_receipt_unconfirmed: `O Runtime não confirmou um recibo de instalação completo. ${REVIEW_BEFORE_RETRY}`,
  integration_install_applied_snapshot_unavailable: "O instalador confirmou a aplicação, mas não foi possível consultar o estado final do Runtime. As configurações ainda não foram verificadas; atualize o diagnóstico antes de tentar outra instalação.",
};

/** Translate only closed native codes; never reflect stdout, stderr or user paths. */
export function installFailureMessage(error: unknown): string {
  const code = typeof error === "string" ? error : error instanceof Error ? error.message : "";
  if (code.length <= 100 && Object.prototype.hasOwnProperty.call(MESSAGES, code)) return MESSAGES[code];
  if (code.length <= 100) {
    const match = /^integration_install_exit_code:(-?\d{1,11})$/.exec(code);
    if (match) {
      const exitCode = Number(match[1]);
      if (Number.isInteger(exitCode) && exitCode !== 0 && exitCode >= -2_147_483_648 && exitCode <= 2_147_483_647) {
        return `O instalador encerrou com código ${exitCode}. ${REVIEW_BEFORE_RETRY}`;
      }
    }
  }
  return `O Runtime não confirmou a instalação completa. ${REVIEW_BEFORE_RETRY}`;
}
