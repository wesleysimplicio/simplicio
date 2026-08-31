import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createDemoSnapshot } from "../demo";
import { SettingsScreen } from "./SettingsScreen";

describe("diagnostic snapshot timestamp", () => {
  it("renders the legacy Runtime unix timestamp instead of Invalid Date", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.generatedAt = "unix:1704110400";
    const html = renderToStaticMarkup(<SettingsScreen snapshot={snapshot} section="diagnostics"
      busy={false} logoutBusy={false} onRefresh={() => {}} onSubscribe={() => {}} onLogout={() => {}} />);
    expect(html).toContain("Leitura do snapshot");
    expect(html).toContain("2024");
    expect(html).not.toContain("Invalid Date");
    expect(html).not.toContain("unix:1704110400");
  });
});
