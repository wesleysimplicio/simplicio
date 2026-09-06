import { afterEach, describe, expect, it, vi } from "vitest";
import { checkDesktopUpdate, compareVersions, DESKTOP_RELEASES_API, DESKTOP_RELEASES_URL, MAX_RELEASE_BYTES, MAX_RELEASE_NOTES, MAX_RELEASES, parseDesktopUpdateTarget, selectDesktopRelease, type DesktopUpdateProgress, type DesktopUpdateTarget } from "./desktop_updates";

const mac: DesktopUpdateTarget = { platform: "macos", arch: "arm64" };
const windows: DesktopUpdateTarget = { platform: "windows", arch: "x64" };
const linux: DesktopUpdateTarget = { platform: "linux", arch: "x64" };

function release(version: string, names = [`Simplicio-${version}-arm64.dmg`]) {
  const tag = `v${version}`;
  return {
    tag_name: tag, draft: false, prerelease: false, html_url: `${DESKTOP_RELEASES_URL}/tag/${tag}`,
    assets: [
      ...names.map((name) => ({ name, state: "uploaded", size: 100_000, browser_download_url: `${DESKTOP_RELEASES_URL}/download/${tag}/${encodeURIComponent(name)}` })),
      ...names.filter((name) => !name.endsWith(".sig")).map((name) => ({ name: `${name}.sig`, state: "uploaded", size: 92, browser_download_url: `${DESKTOP_RELEASES_URL}/download/${tag}/${encodeURIComponent(name + ".sig")}` })),
    ],
  };
}

function jsonResponse(payload: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(payload), { headers: { "content-type": "application/json; charset=utf-8", ...headers } });
}

afterEach(() => { vi.useRealTimers(); });

describe("Desktop version identity", () => {
  it.each([
    ["3.8.9", "3.8.39", -1], ["3.9.0", "3.8.100", 1], ["4.0.0", "3.99.99", 1],
    ["3.8.39", "3.8.39", 0], ["3.8.39+local.2", "3.8.39+release", 0],
    ["3.8.40-beta.2", "3.8.40-beta.10", -1], ["3.8.40-beta", "3.8.40", -1],
    ["3.8.40", "3.8.40-beta", 1], ["3.8.40-1", "3.8.40-alpha", -1],
    ["3.8.40-beta", "3.8.40-beta.1", -1],
  ] as const)("compares %s against %s numerically", (a, b, expected) => {
    expect(compareVersions(a, b)).toBe(expected);
  });

  it.each(["latest", "v3.8.39", "3.8", "03.8.39", "3.08.39", "3.8.39-beta.01", "3.8.39\n", "9007199254740992.0.0", "3.8.39<script>"])("rejects invalid version %s", (version) => {
    expect(() => compareVersions(version, "3.8.39")).toThrow("invalid_version");
  });

  it("accepts only exact native platform and architecture identifiers", () => {
    expect(parseDesktopUpdateTarget({ ...mac, secret: "not-needed", url: "https://untrusted.invalid" })).toEqual(mac);
    for (const value of [null, [], {}, { platform: "unknown", arch: "x64" }, { platform: "darwin", arch: "arm64" },
      { platform: "macos", arch: "unknown" }, { platform: { toString: () => "macos" }, arch: "arm64" }]) {
      expect(() => parseDesktopUpdateTarget(value)).toThrow("unsupported_target");
    }
  });
});

describe("published Desktop asset selection", () => {
  it("does not mistake a newer Runtime-only release for a Desktop update", () => {
    const payload = [release("3.8.41", ["simplicio-macos-arm64", "simplicio-update-manifest.json"]), release("3.8.39")];
    expect(selectDesktopRelease(payload, mac)).toMatchObject({ version: "3.8.39", assetName: "Simplicio-3.8.39-arm64.dmg" });
  });

  it("chooses the highest stable version, not array order or a draft/prerelease", () => {
    const payload = [release("3.8.9"), { ...release("3.8.99"), draft: true }, { ...release("3.8.90"), prerelease: true },
      release("3.8.39"), release("3.8.40-beta")];
    expect(selectDesktopRelease(payload, mac).version).toBe("3.8.39");
  });

  it("prefers a macOS installer to its published ZIP and supports universal", () => {
    expect(selectDesktopRelease([release("3.8.39", ["Simplicio-3.8.39-arm64.zip", "Simplicio-3.8.39-arm64.dmg"])], mac).assetName).toMatch(/\.dmg$/);
    expect(selectDesktopRelease([release("3.8.39", ["Simplicio_3.8.39_universal.dmg"])], { platform: "macos", arch: "x64" }).version).toBe("3.8.39");
  });

  it.each([
    [windows, "Simplicio_3.8.39_x64-setup.exe"], [windows, "Simplicio_3.8.39_x64_en-US.msi"],
    [linux, "Simplicio_3.8.39_amd64.AppImage"], [linux, "Simplicio_3.8.39_amd64.deb"],
    [linux, "Simplicio-3.8.39-1.x86_64.rpm"], [mac, "Simplicio_3.8.39_aarch64.dmg"],
    [linux, "simplicio_3.8.39_amd64.deb"], [linux, "simplicio-3.8.39-1.x86_64.rpm"],
    [windows, "simplicio_3.8.39_x64-setup.exe"],
  ] as const)("selects an explicit platform installer %s %s", (target, name) => {
    expect(selectDesktopRelease([release("3.8.39", [name])], target).assetName).toBe(name);
  });

  it("never substitutes a different OS, architecture, version, or raw Runtime binary", () => {
    for (const name of ["Simplicio-3.8.39-x64.dmg", "Simplicio_3.8.39_arm64-setup.exe", "Simplicio-3.8.38-arm64.dmg",
      "simplicio-macos-arm64", "Simplicio-3.8.39-arm64.dmg.sig", "Simplicio-3.8.39-arm64.dmg.exe", "Simplicio-3.8.39-arm64.dmg\n"]) {
      expect(() => selectDesktopRelease([release("3.8.39", [name])], mac)).toThrow("no_compatible_release");
    }
  });

  it("fails unknown when no compatible installer is published", () => {
    expect(() => selectDesktopRelease([], mac)).toThrow("no_compatible_release");
    expect(() => selectDesktopRelease([release("3.8.39", [])], mac)).toThrow("no_compatible_release");
  });

  it("requires a Windows installer suffix instead of a raw Runtime executable", () => {
    for (const name of ["simplicio-windows-x64.exe", "simplicio-3.8.39-windows-x64.exe", "simplicio_3.8.39_x64.exe", "simplicio_3.8.39_x64.zip"]) {
      expect(() => selectDesktopRelease([release("3.8.39", [name])], windows)).toThrow("no_compatible_release");
    }
  });

  it("requires a matching uploaded Ed25519 sidecar", () => {
    const fixture = release("3.8.39");
    expect(() => selectDesktopRelease([{ ...fixture, assets: fixture.assets.filter((asset) => !asset.name.endsWith(".sig")) }], mac)).toThrow("no_compatible_release");
    const signature = fixture.assets.find((asset) => asset.name.endsWith(".sig"));
    expect(() => selectDesktopRelease([{ ...fixture, assets: [{ ...signature!, browser_download_url: "https://evil.invalid/signature" }, fixture.assets[0]] }], mac)).toThrow("no_compatible_release");
    expect(selectDesktopRelease([fixture], mac).assetName).toBe("Simplicio-3.8.39-arm64.dmg");
  });

  it("requires exact official release and download URLs", () => {
    for (const html_url of ["https://example.com/releases/v3.8.39", `${DESKTOP_RELEASES_URL}/tag/v3.8.39?redirect=1`]) {
      expect(() => selectDesktopRelease([{ ...release("3.8.39"), html_url }], mac)).toThrow("no_compatible_release");
    }
    const fixture = release("3.8.39");
    for (const browser_download_url of ["https://github.com.evil.invalid/file.dmg", "file:///tmp/file.dmg", `${fixture.assets[0].browser_download_url}?redirect=1`]) {
      expect(() => selectDesktopRelease([{ ...fixture, assets: [{ ...fixture.assets[0], browser_download_url }] }], mac)).toThrow("no_compatible_release");
    }
  });

  it("rejects empty, incomplete and excessively large assets", () => {
    const fixture = release("3.8.39");
    for (const asset of [{ ...fixture.assets[0], size: 0 }, { ...fixture.assets[0], size: 9 * 1024 ** 3 }, { ...fixture.assets[0], state: "new" }]) {
      expect(() => selectDesktopRelease([{ ...fixture, assets: [asset] }], mac)).toThrow("no_compatible_release");
    }
  });

  it("bounds release/asset counts and strips unrelated metadata", () => {
    expect(() => selectDesktopRelease({ releases: [] }, mac)).toThrow("invalid_response");
    expect(() => selectDesktopRelease(Array.from({ length: MAX_RELEASES + 1 }, () => release("3.8.39")), mac)).toThrow("invalid_response");
    const fixture = release("3.8.39");
    expect(() => selectDesktopRelease([{ ...fixture, assets: Array.from({ length: 129 }, () => fixture.assets[0]) }], mac)).toThrow("invalid_response");
    const selected = selectDesktopRelease([{ ...fixture, body: "Notas públicas", author: { token: "secret" } }], mac);
    expect(Object.keys(selected).sort()).toEqual(["assetBytes", "assetName", "notes", "publishedAt", "releaseUrl", "tag", "version"]);
    expect(JSON.stringify(selected)).not.toContain("secret");
  });

  it("returns bounded public notes as inert text, without bidi or control characters", () => {
    const body = "\u202e## Novidades\u0000\r\n<img src='https://untrusted.invalid'>\rTexto público";
    const selected = selectDesktopRelease([{ ...release("3.8.39"), body }], mac);
    expect(selected.notes).toEqual({ text: "## Novidades\n<img src='https://untrusted.invalid'>\nTexto público", truncated: false });
    const long = selectDesktopRelease([{ ...release("3.8.39"), body: "x".repeat(MAX_RELEASE_NOTES + 20) }], mac);
    expect(long.notes).toEqual({ text: "x".repeat(MAX_RELEASE_NOTES), truncated: true });
    const emoji = selectDesktopRelease([{ ...release("3.8.39"), body: "x".repeat(MAX_RELEASE_NOTES - 1) + "🌱" }], mac);
    expect(emoji.notes?.text).toBe("x".repeat(MAX_RELEASE_NOTES - 1));
  });

  it("treats missing or non-text notes as unavailable rather than inventing a changelog", () => {
    for (const body of [null, undefined, {}, "\r\n\u0000\u202e"]) {
      expect(selectDesktopRelease([{ ...release("3.8.39"), body }], mac).notes).toBeNull();
    }
  });

  it("accepts only a real publication date in the expected ISO format", () => {
    expect(selectDesktopRelease([{ ...release("3.8.39"), published_at: "2026-08-31T01:34:29Z" }], mac).publishedAt).toBe("2026-08-31T01:34:29Z");
    for (const published_at of [null, 123, "yesterday", "2026-02-30T01:34:29Z", "2026-13-31T01:34:29Z", "2026-08-31T01:34:29Z\n"]) {
      expect(selectDesktopRelease([{ ...release("3.8.39"), published_at }], mac).publishedAt).toBeNull();
    }
  });
});

describe("bounded metadata-only update checks", () => {
  it("reports real metadata stages and decoded bytes, not an installer download percentage", async () => {
    const payload = [{ ...release("3.8.39"), body: "Atualização pública" }];
    const byteLength = new TextEncoder().encode(JSON.stringify(payload)).byteLength;
    const onProgress = vi.fn<(value: DesktopUpdateProgress) => void>();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload, { "content-length": "40", "content-encoding": "gzip" }));
    await checkDesktopUpdate({ currentVersion: "3.8.38", target: mac, fetcher, onProgress });
    expect(onProgress.mock.calls.map(([value]) => value)).toEqual([
      { stage: "requesting", receivedBytes: 0 }, { stage: "receiving", receivedBytes: 0 },
      { stage: "receiving", receivedBytes: byteLength }, { stage: "validating", receivedBytes: byteLength },
    ]);
  });

  it("bounds progress notifications for tiny stream chunks and isolates observer failures", async () => {
    const bytes = new TextEncoder().encode(JSON.stringify([{ ...release("3.8.39"), body: "x".repeat(40_000) }]));
    const body = new ReadableStream<Uint8Array>({ start(controller) {
      for (let offset = 0; offset < bytes.length; offset += 128) controller.enqueue(bytes.slice(offset, offset + 128));
      controller.close();
    } });
    const onProgress = vi.fn<(value: DesktopUpdateProgress) => void>(() => { throw new Error("observer failed"); });
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(body, { headers: { "content-type": "application/json" } }));
    await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, onProgress })).resolves.toMatchObject({ state: "up_to_date" });
    expect(onProgress.mock.calls.length).toBeLessThanOrEqual(Math.ceil(bytes.length / 16_384) + 3);
    expect(onProgress).toHaveBeenLastCalledWith({ stage: "validating", receivedBytes: bytes.length });
  });

  it("cancels the pending body reader on deadline and stops reporting progress", async () => {
    vi.useFakeTimers();
    const cancelBody = vi.fn();
    const body = new ReadableStream<Uint8Array>({ cancel: cancelBody });
    const onProgress = vi.fn<(value: DesktopUpdateProgress) => void>();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(body, { headers: { "content-type": "application/json" } }));
    const result = checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, onProgress, timeoutMs: 25 });
    const rejected = expect(result).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(25);
    await rejected;
    expect(cancelBody).toHaveBeenCalledTimes(1);
    expect(onProgress.mock.calls.map(([value]) => value.stage)).toEqual(["requesting", "receiving"]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("ignores late metadata and cancels its body when a fetch ignores cancellation", async () => {
    const controller = new AbortController();
    let resolveFetch: (value: Response) => void = () => undefined;
    const fetcher = vi.fn<typeof fetch>(() => new Promise<Response>((resolve) => { resolveFetch = resolve; }));
    const onProgress = vi.fn<(value: DesktopUpdateProgress) => void>();
    const result = checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, onProgress, signal: controller.signal });
    const rejected = expect(result).rejects.toMatchObject({ code: "canceled" });
    controller.abort();
    await rejected;
    const cancelBody = vi.fn();
    resolveFetch(new Response(new ReadableStream({ cancel: cancelBody }), { headers: { "content-type": "application/json" } }));
    await Promise.resolve();
    expect(cancelBody).toHaveBeenCalledTimes(1);
    expect(onProgress.mock.calls.map(([value]) => value.stage)).toEqual(["requesting"]);
  });

  it.each([["3.8.38", "available"], ["3.8.39", "up_to_date"], ["3.8.40", "newer_local"]] as const)("reports %s as %s only after validated Desktop metadata", async (currentVersion, state) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse([release("3.8.39")]));
    await expect(checkDesktopUpdate({ currentVersion, target: mac, fetcher })).resolves.toMatchObject({ state, currentVersion, target: mac });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(DESKTOP_RELEASES_API, expect.objectContaining({ method: "GET", credentials: "omit", redirect: "error", referrerPolicy: "no-referrer", cache: "no-store" }));
  });

  it("does not make a request while offline or with untrusted local identity", async () => {
    const fetcher = vi.fn<typeof fetch>();
    await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, online: false, fetcher })).rejects.toMatchObject({ code: "offline" });
    await expect(checkDesktopUpdate({ currentVersion: "latest", target: mac, fetcher })).rejects.toMatchObject({ code: "invalid_version" });
    await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: { platform: "macos", arch: "unknown" }, fetcher })).rejects.toMatchObject({ code: "unsupported_target" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps failed requests and GitHub rate limits distinct from up-to-date", async () => {
    for (const status of [403, 429, 500]) {
      const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response("untrusted error body", { status }));
      await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher })).rejects.toMatchObject({ code: status === 500 ? "request_failed" : "rate_limited" });
    }
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("secret socket diagnostics"));
    await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher })).rejects.toMatchObject({ code: "request_failed", message: "request_failed" });
  });

  it("enforces declared and streamed response size limits", async () => {
    for (const response of [jsonResponse([], { "content-length": String(MAX_RELEASE_BYTES + 1) }),
      new Response(" ".repeat(MAX_RELEASE_BYTES + 1), { headers: { "content-type": "application/json" } })]) {
      const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response);
      await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher })).rejects.toMatchObject({ code: "invalid_response" });
    }
  });

  it("does not accept HTML, malformed JSON or a Runtime manifest as release metadata", async () => {
    for (const response of [new Response("<html>login</html>", { headers: { "content-type": "text/html" } }),
      new Response("{", { headers: { "content-type": "application/json" } }), jsonResponse({ version: "3.8.39", artifacts: [] })]) {
      const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response);
      await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher })).rejects.toMatchObject({ code: "invalid_response" });
    }
  });

  it("aborts the network on a finite deadline without retrying", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn<typeof fetch>(() => new Promise<Response>(() => undefined));
    const result = checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, timeoutMs: 25 });
    const rejected = expect(result).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(25);
    await rejected;
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });

  it("cancels an in-flight check and refuses a pre-canceled request", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>(() => new Promise<Response>(() => undefined));
    const result = checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, signal: controller.signal });
    const rejected = expect(result).rejects.toMatchObject({ code: "canceled" });
    controller.abort();
    await rejected;
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await expect(checkDesktopUpdate({ currentVersion: "3.8.39", target: mac, fetcher, signal: controller.signal })).rejects.toMatchObject({ code: "canceled" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
