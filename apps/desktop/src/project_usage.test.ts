import { describe, expect, it } from "vitest";
import { parseUsageProjects, projectDiscoveryError } from "./project_usage";

const entry = { id: `project-${"a".repeat(64)}`, name: "Aulas", path: "/tmp/Aulas", evidenceType: "context", lastModifiedEpoch: 1788180000 };
const fixture = () => ({ schema: "simplicio.desktop-project-usage/v1", projects: [entry], candidateCount: 1,
  roots: [{ name: "Projetos", path: "/tmp/Projetos" }], partial: false, reasons: [], directoriesVisited: 3,
  scope: { kind: "conventional_roots_and_configured_repo", maxDepth: 5, maxDirectories: 4000, maxResults: 64, deadlineMs: 2000 } });

describe("automatic project discovery projection", () => {
  it("accepts bounded candidate metadata without treating it as verified token consumption", () => {
    const parsed = parseUsageProjects({ ...fixture(), secret: "not-forwarded", projects: [{ ...entry, prompt: "not-forwarded" }] });
    expect(parsed.projects[0].evidenceType).toBe("context");
    expect(JSON.stringify(parsed)).not.toContain("not-forwarded");
  });

  it("preserves partial coverage instead of calling a bounded scan complete", () => {
    const parsed = parseUsageProjects({ ...fixture(), partial: true, reasons: ["deadline_reached"], candidateCount: 5 });
    expect(parsed.partial).toBe(true);
    expect(parsed.candidateCount).toBe(5);
  });

  it("keeps an unavailable timestamp unknown", () => {
    expect(parseUsageProjects({ ...fixture(), projects: [{ ...entry, lastModifiedEpoch: null }] }).projects[0].lastModifiedEpoch).toBeNull();
  });

  it("retains successful roots while qualifying an isolated directory timeout", () => {
    const parsed = parseUsageProjects({ ...fixture(), partial: true, reasons: ["root_timeout"], unavailableRoots: ["Desktop"] });
    expect(parsed.projects).toHaveLength(1);
    expect(parsed.unavailableRoots).toEqual(["Desktop"]);
    expect(parsed.partial).toBe(true);
  });

  it("accepts the same normalized local Windows paths and project IDs as the native picker", () => {
    const path = "C:\\Users\\person\\Projects\\Aulas";
    const parsed = parseUsageProjects({ ...fixture(), projects: [{ ...entry, path }],
      roots: [{ name: "Projects", path: "C:\\Users\\person\\Projects" }] });
    expect(parsed.projects[0].path).toBe(path);
    expect(parsed.projects[0].id).toMatch(/^project-[a-f0-9]{64}$/);
  });

  it.each([
    { schema: "unknown" }, { projects: [entry, entry] }, { projects: Array.from({ length: 65 }, () => entry) },
    { projects: [{ ...entry, path: "../private" }] }, { projects: [{ ...entry, evidenceType: "billed" }] },
    { projects: [{ ...entry, lastModifiedEpoch: -1 }] }, { candidateCount: 0 }, { candidateCount: 4001 },
    { directoriesVisited: 4001 }, { partial: "no" }, { reasons: ["private-token: secret"] },
    { roots: [{ name: "x", path: "//remote/share" }] },
    { projects: [{ ...entry, id: `sha256:${"a".repeat(64)}` }] },
    { projects: [{ ...entry, path: "\\\\?\\C:\\Users\\person\\Projects\\Aulas" }] },
    { roots: [{ name: "Projects", path: "\\\\?\\C:\\Users\\person\\Projects" }] },
    { unavailableRoots: ["Desktop"], partial: false },
    { unavailableRoots: ["Desktop", "Desktop"], partial: true },
    { unavailableRoots: ["private-token: secret"], partial: true },
    { unavailableRoots: "Desktop", partial: true },
  ])("rejects malformed discovery %j", (patch) => {
    expect(() => parseUsageProjects({ ...fixture(), ...patch })).toThrow();
  });

  it("does not echo native diagnostics", () => {
    expect(projectDiscoveryError("secret=private")).not.toContain("private");
    expect(projectDiscoveryError("preview_no_runtime")).toContain("app desktop");
    expect(projectDiscoveryError("desktop_access_unverified")).toContain("não confirmou");
  });
});
