import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

const executionReport = {
  "schema": "simplicio.execution-report/v1",
  "present": true,
  "owner": "simplicio-runtime",
  "run_id": "run-current",
  "status": "COMPLETE",
  "started_at_unix": 1788796000,
  "finished_at_unix": 1788796064,
  "wall_ms": 64000,
  "execution_profile": "runtime-backed",
  "engine": "native",
  "engine_version": "3.8.47",
  "loop_decision": {
    "verdict": "required"
  },
  "operators_used": [
    "simplicio-loop",
    "simplicio-mapper"
  ],
  "revision": "rev-2",
  "coverage": {
    "status": "partial",
    "fields": [
      "tasks",
      "stages",
      "tools"
    ],
    "missing": [
      "cost_microusd"
    ]
  },
  "measured_fields": [
    "task_wall_ms",
    "tokens_per_task"
  ],
  "unverified_fields": [
    "cost_microusd"
  ],
  "unavailable_reasons": {
    "cost_microusd": "no pricing receipt"
  },
  "history": [
    {
      "run_id": "run-current",
      "status": "COMPLETE",
      "wall_ms": 64000,
      "task_count": 2,
      "recorded_at_unix": 1788796064
    },
    {
      "run_id": "run-failed",
      "status": "FAIL",
      "wall_ms": 21000,
      "task_count": 1,
      "recorded_at_unix": 1788700000
    }
  ],
  "tasks": [
    {
      "task_id": "task-native",
      "issue": "#390",
      "title": "Relatório via Loop nativo",
      "wall_ms": 1800,
      "model": "gpt-5.6",
      "provider": "openai",
      "engine": "native",
      "engine_version": "3.8.47",
      "attempt_id": "attempt-1",
      "parent_span_id": "span-root",
      "completion_verdict": "verified",
      "run_id": "run-current",
      "session_ids": [
        "session-a"
      ],
      "receipts": [
        "receipt-native"
      ],
      "tokens": {
        "tokens_in": 100,
        "tokens_out": 40,
        "tokens_total": 140,
        "tokens_cached": 20,
        "cache_read_provenance": "provider",
        "tokens_reasoning": 10,
        "reasoning_semantics": "included_in_output",
        "source": "provider-reported",
        "cost_status": "known",
        "cost_provenance": "runtime-receipt"
      },
      "stages": [
        {
          "stage_id": "discover",
          "name": "Descoberta",
          "status": "complete",
          "wall_ms": 240,
          "tokens": {},
          "tool_count": 1,
          "error_count": 0,
          "attempt_count": 1
        },
        {
          "stage_id": "verify",
          "name": "Verificação",
          "status": "complete",
          "wall_ms": 420,
          "tokens": {},
          "tool_count": 1,
          "error_count": 0,
          "attempt_count": 1
        }
      ],
      "tools": [
        {
          "name": "simplicio_map",
          "status": "complete",
          "invocations": 1,
          "wall_ms": 120,
          "error_count": 0
        }
      ],
      "errors": [],
      "retries": [],
      "validation": {
        "status": "passed",
        "checks": 3,
        "executed": 3,
        "passed": 3,
        "failures": 0,
        "source": "vitest"
      },
      "coverage": {
        "status": "complete",
        "fields": [
          "stages",
          "tools",
          "validation"
        ],
        "missing": []
      },
      "outcome": "COMPLETE",
      "operators_used": [
        "simplicio-loop"
      ],
      "notes": []
    },
    {
      "task_id": "task-python",
      "issue": "#390",
      "title": "Fallback Python do relatório",
      "wall_ms": 2600,
      "model": "gpt-5.6",
      "provider": "openai",
      "engine": "python",
      "engine_version": "3.8.47",
      "fallback_reason": "native_unavailable",
      "attempt_id": "attempt-2",
      "parent_span_id": "span-root",
      "completion_verdict": "partial",
      "run_id": "run-current",
      "session_ids": [
        "session-b"
      ],
      "receipts": [
        "receipt-python"
      ],
      "unresolved": [
        "late-correction"
      ],
      "tokens": {
        "tokens_in": 80,
        "tokens_out": 30,
        "tokens_total": 110,
        "tokens_cached": 10,
        "cache_read_provenance": "local",
        "tokens_reasoning": 6,
        "reasoning_semantics": "unknown",
        "source": "provider-reported",
        "cost_status": "estimated",
        "cost_provenance": "catalog"
      },
      "stages": [
        {
          "stage_id": "act",
          "name": "Execução",
          "status": "partial",
          "wall_ms": 700,
          "tokens": {},
          "tool_count": 1,
          "error_count": 1,
          "attempt_count": 2
        }
      ],
      "tools": [
        {
          "name": "simplicio-dev-cli",
          "status": "partial",
          "invocations": 2,
          "wall_ms": 500,
          "error_count": 1
        }
      ],
      "errors": [
        {
          "code": "fallback_started",
          "stage_id": "act",
          "retryable": false
        }
      ],
      "retries": [
        {
          "attempt": 2,
          "reason_code": "native_unavailable",
          "status": "complete",
          "wall_ms": 500
        }
      ],
      "validation": {
        "status": "partial",
        "checks": 2,
        "executed": 2,
        "passed": 1,
        "failures": 1,
        "source": "vitest"
      },
      "coverage": {
        "status": "partial",
        "fields": [
          "stages",
          "tools"
        ],
        "missing": [
          "cost_microusd"
        ]
      },
      "outcome": "COMPLETE",
      "operators_used": [
        "simplicio-loop",
        "python-fallback"
      ],
      "notes": []
    }
  ],
  "consolidated": {
    "task_count": 2,
    "wall_ms_run": 64000,
    "wall_ms_tasks_sum": 4400,
    "tokens_in_sum": 180,
    "tokens_out_sum": 70,
    "tokens_total_sum": 250,
    "tokens_rollup": "complete",
    "tokens_cache_read_sum": 30,
    "tokens_cache_read_rollup": "complete",
    "tokens_cache_write_sum": null,
    "tokens_cache_write_rollup": "absent",
    "tokens_reasoning_sum": 16,
    "tokens_reasoning_rollup": "partial",
    "cost_microusd_sum": 45,
    "cost_rollup": "complete",
    "cost_status": "estimated",
    "cost_provenance": "catalog",
    "tool_invocations": 3,
    "error_count": 1,
    "retry_count": 1,
    "validation": {
      "status": "partial",
      "checks": 5,
      "executed": 5,
      "passed": 4,
      "failures": 1,
      "source": "vitest"
    }
  }
};

async function mockExecutionReport(page: Page, mode: "success" | "loading" | "error" | "stale" = "success", report = executionReport) {
  await page.addInitScript(({ snapshot, mode, executionReport }) => {
    Object.assign(window, {
      __releaseExecutionReport: undefined,
      __executionReportCalls: 0,
      __TAURI_INTERNALS__: {
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          if (command === "desktop_runtime_install_status") {
            return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
          }
          if (command === "desktop_preparation_status") return true;
          if (command === "desktop_snapshot") return snapshot;
          if (command === "desktop_context_report") throw "context_ledger_unavailable";
          if (command === "desktop_unified_usage") throw "usage_snapshot_unavailable";
          if (command === "desktop_session_close_idle") throw "session_idle_finalization_unavailable";
          if (command === "desktop_execution_report") {
            (window as any).__executionReportCalls += 1;
            if (mode === "error" || (mode === "stale" && (window as any).__executionReportCalls > 1)) {
              throw "execution_report_transport_error";
            }
            if (mode === "loading" && (window as any).__executionReportCalls === 1) {
              await new Promise<void>((resolve) => { (window as any).__releaseExecutionReport = resolve; });
            }
            return executionReport;
          }
          throw "unexpected_test_command:" + command;
        },
      },
    });
  }, { snapshot: { ...createDemoSnapshot("active"), source: "runtime" }, mode, executionReport: report });
}

test("renders task report provenance, partial coverage and accessible filters", async ({ page }) => {
  await mockExecutionReport(page);
  await page.goto("/?state=active&view=reports");

  await expect(page.getByRole("heading", { name: "Relatórios de execução", exact: true })).toBeVisible();
  await expect(page.getByText("Atualização ao vivo", { exact: true })).toBeVisible();
  await expect(page.getByText(/Engine native · 3\.8\.47/)).toBeVisible();
  await expect(page.getByText(/Decisão Loop: required/)).toBeVisible();
  await expect(page.getByText("cobertura parcial", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/raciocínio 16 \(subtotal parcial\)/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tarefas deste run", exact: true })).toBeVisible();

  await page.getByRole("textbox", { name: "Filtrar tarefas" }).fill("Fallback Python");
  await expect(page.getByText("1 de 2 item(ns)", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Filtrar tarefas" }).fill("");
  await page.locator("details").nth(1).locator("summary").click();
  await expect(page.getByText("fallback registrado", { exact: true })).toBeVisible();
  await expect(page.getByText("native_unavailable", { exact: true })).toBeVisible();

  await page.getByLabel("Filtrar histórico por estado").selectOption("FAIL");
  await expect(page.getByText("1 de 2 run(s)", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /run-failed falhou/ })).toBeVisible();
});

test("keeps the loading state until the first report read resolves", async ({ page }) => {
  await mockExecutionReport(page, "loading");
  await page.goto("/?state=active&view=reports");
  await expect(page.getByRole("status")).toContainText("Consultando o último relatório do Runtime");
  await page.evaluate(() => (window as any).__releaseExecutionReport());
  await expect(page.getByText("Atualização ao vivo", { exact: true })).toBeVisible();
});

test("shows a generic error and no report data when Runtime is unavailable", async ({ page }) => {
  await mockExecutionReport(page, "error");
  await page.goto("/?state=active&view=reports");
  await expect(page.getByRole("alert")).toContainText("Não foi possível ler o relatório do Runtime");
  await expect(page.getByRole("alert")).not.toContainText("execution_report_transport_error");
  await expect(page.getByText("Tarefas deste run", { exact: true })).toHaveCount(0);
});

test("keeps the confirmed revision visible and marks a failed refresh as stale", async ({ page }) => {
  await mockExecutionReport(page);
  await page.goto("/?state=active&view=reports");
  await expect(page.getByText("Atualização ao vivo", { exact: true })).toBeVisible();

  await page.addInitScript(() => undefined);
  await page.evaluate(() => {
    const internals = (window as any).__TAURI_INTERNALS__;
    const original = internals.invoke;
    internals.invoke = async (command: string, args: Record<string, unknown> = {}) => {
      if (command === "desktop_execution_report") throw "execution_report_transport_error";
      return original(command, args);
    };
  });
  await page.getByRole("button", { name: "Atualizar", exact: true }).click();
  await expect(page.getByText("Dados desatualizados", { exact: true })).toBeVisible();
  await expect(page.getByText("A leitura mais recente falhou; os dados exibidos são da última revisão confirmada.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /run-current concluída/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconectar", exact: true })).toBeVisible();
});

test("clears the previous run when a different run cannot be loaded", async ({ page }) => {
  await mockExecutionReport(page);
  await page.goto("/?state=active&view=reports");
  await expect(page.getByText("Atualização ao vivo", { exact: true })).toBeVisible();
  await page.evaluate(() => {
    const internals = (window as any).__TAURI_INTERNALS__;
    const original = internals.invoke;
    internals.invoke = async (command: string, args: Record<string, unknown> = {}) => {
      if (command === "desktop_execution_report" && args.runId === "run-failed") {
        throw "selected_run_unavailable";
      }
      return original(command, args);
    };
  });
  await page.getByLabel("Selecionar run exibido").selectOption("run-failed");
  await expect(page.getByRole("alert")).toContainText("Não foi possível ler o relatório do Runtime");
  await expect(page.getByText("Tarefas deste run", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Exportar JSON", exact: true })).toHaveCount(0);
});

test("does not present zero executed tests as a successful validation", async ({ page }) => {
  const report = structuredClone(executionReport);
  report.tasks[0].validation = { status: "passed", checks: 0, executed: 0, passed: 0, failures: 0, source: "vitest" };
  await mockExecutionReport(page, "success", report);
  await page.goto("/?state=active&view=reports");
  await expect(page.getByText("Atualização ao vivo", { exact: true })).toBeVisible();
  const task = page.locator("details").first();
  await task.locator("summary").click();
  await expect(task.locator(".report-validation")).not.toHaveClass(/report-validation-success/);
  await expect(task.locator(".report-validation")).toContainText("não executada");
});
