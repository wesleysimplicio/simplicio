import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BoundSessionUsageReport } from "./BoundSessionUsageReport";
import type { BoundSessionUsage } from "../session_idle";

describe("bound session evidence", () => {
  it("shows unknown totals, preserved subtotals and collection limits separately", () => {
    const usage: BoundSessionUsage = {
      schema: "simplicio.bound-session-usage/v1", scope: "bound_runtime_sessions",
      collection_partial: true,
      session_reports: [{
        session_id: "runtime-session", status: "partial", binding_count: 1, events: 2,
        totals: { input_tokens: 12, output_tokens: null, reasoning_tokens: null, cache_read_tokens: null, cache_write_tokens: null },
        known_totals: { input_tokens: 12, output_tokens: 3 },
      }],
    };
    const html = renderToStaticMarkup(<BoundSessionUsageReport usage={usage} />);
    expect(html).toContain("runtime-session");
    expect(html).toContain("2 eventos preservados");
    expect(html).toContain("subtotal conhecido 3");
    expect(html).toContain("fontes indisponíveis");
    expect(html).toContain("<dt>Raciocínio</dt><dd>—");
    expect(html).not.toContain("coleta concluída");
  });
});
