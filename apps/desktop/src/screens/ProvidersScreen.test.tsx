import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createDemoSnapshot } from "../demo";
import { ProvidersScreen } from "./ProvidersScreen";

describe("host plugin freshness", () => {
  it("renders Runtime plugin receipts without inventing catalog updates", () => {
    const html = renderToStaticMarkup(<ProvidersScreen
      snapshot={createDemoSnapshot("active")}
      busy={false}
      repairing={false}
      onRefresh={() => undefined}
      onRepair={async () => { throw new Error("unused"); }}
      onReconcile={async () => { throw new Error("unused"); }}
    />);
    expect(html).toContain("Skills e plugins instalados");
    expect(html).toContain('data-testid="host-plugin-freshness"');
    expect(html).not.toContain("Run Grok");
    expect(html).not.toContain("atualizar agora");
  });

  it("does not show plugin receipts on the inventory-only agents page", () => {
    const html = renderToStaticMarkup(<ProvidersScreen
      snapshot={createDemoSnapshot("active")}
      busy={false}
      repairing={false}
      inventoryOnly
      onRefresh={() => undefined}
      onRepair={async () => { throw new Error("unused"); }}
      onReconcile={async () => { throw new Error("unused"); }}
    />);
    expect(html).not.toContain("Skills e plugins instalados");
  });
});
