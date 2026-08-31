export const DESKTOP_UPDATE_EVENT = "simplicio://check-for-updates";
export const DESKTOP_RELEASES_URL = "https://github.com/wesleysimplicio/simplicio/releases";
export const DESKTOP_RELEASES_API = "https://api.github.com/repos/wesleysimplicio/simplicio/releases?per_page=30";
export const MAX_RELEASES = 30;
export const MAX_RELEASE_BYTES = 2 * 1024 * 1024;
const MAX_ASSETS = 128;
const CHECK_TIMEOUT_MS = 15_000;

export type DesktopUpdateTarget = {
  platform: "macos" | "windows" | "linux";
  arch: "arm64" | "x64" | "x86";
};

export type DesktopRelease = {
  version: string;
  tag: string;
  releaseUrl: string;
  assetName: string;
  assetBytes: number;
};

export type DesktopUpdateResult = {
  state: "available" | "up_to_date" | "newer_local";
  currentVersion: string;
  target: DesktopUpdateTarget;
  release: DesktopRelease;
};

export type DesktopUpdateErrorCode = "offline" | "timeout" | "canceled" | "invalid_version" |
  "unsupported_target" | "request_failed" | "rate_limited" | "invalid_response" | "no_compatible_release";

export class DesktopUpdateError extends Error {
  constructor(public readonly code: DesktopUpdateErrorCode) {
    super(code);
    this.name = "DesktopUpdateError";
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function versionParts(value: string): { core: number[]; prerelease: string[] } {
  if (typeof value !== "string" || value.length > 128) throw new DesktopUpdateError("invalid_version");
  const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/.exec(value);
  if (!match || match[0] !== value) throw new DesktopUpdateError("invalid_version");
  const core = match.slice(1, 4).map(Number);
  const prerelease = match[4]?.split(".") ?? [];
  if (core.some((part) => !Number.isSafeInteger(part)) || prerelease.some((part) => /^0\d+$/.test(part))) {
    throw new DesktopUpdateError("invalid_version");
  }
  return { core, prerelease };
}

export function compareVersions(left: string, right: string): -1 | 0 | 1 {
  const a = versionParts(left);
  const b = versionParts(right);
  for (let index = 0; index < 3; index++) {
    if (a.core[index] !== b.core[index]) return a.core[index] > b.core[index] ? 1 : -1;
  }
  if (!a.prerelease.length || !b.prerelease.length) {
    return a.prerelease.length === b.prerelease.length ? 0 : a.prerelease.length ? -1 : 1;
  }
  for (let index = 0; index < Math.max(a.prerelease.length, b.prerelease.length); index++) {
    const x = a.prerelease[index];
    const y = b.prerelease[index];
    if (x === y) continue;
    if (x === undefined || y === undefined) return x === undefined ? -1 : 1;
    const xn = /^\d+$/.test(x);
    const yn = /^\d+$/.test(y);
    if (xn !== yn) return xn ? -1 : 1;
    if (xn && x.length !== y.length) return x.length > y.length ? 1 : -1;
    return x > y ? 1 : -1;
  }
  return 0;
}

export function parseDesktopUpdateTarget(value: unknown): DesktopUpdateTarget {
  if (!record(value) || typeof value.platform !== "string" || typeof value.arch !== "string" ||
    !["macos", "windows", "linux"].includes(value.platform) || !["arm64", "x64", "x86"].includes(value.arch)) {
    throw new DesktopUpdateError("unsupported_target");
  }
  // Return only the native target identity; no client-controlled URL is accepted.
  return { platform: value.platform as DesktopUpdateTarget["platform"], arch: value.arch as DesktopUpdateTarget["arch"] };
}

function desktopAssetRank(name: string, version: string, target: DesktopUpdateTarget): number | null {
  const escapedVersion = version.replaceAll(".", "\\.");
  const arch = target.arch === "arm64" ? "(?:arm64|aarch64)" : target.arch === "x64" ? "(?:x64|x86_64|amd64)" : "(?:x86|i686|i386)";
  // Debian/RPM normalize product names. Keep the historically published macOS ZIP name exact.
  const normalizedName = target.platform === "macos" ? name : name.replace(/^simplicio(?=[_-])/i, "Simplicio");
  let patterns: RegExp[];
  if (target.platform === "macos") {
    const macArch = `(?:${arch}|universal)`;
    patterns = [
      new RegExp(`^Simplicio[-_]${escapedVersion}[-_]${macArch}\\.dmg$`),
      new RegExp(`^Simplicio-${escapedVersion}-${macArch}\\.zip$`),
    ];
  } else if (target.platform === "windows") {
    patterns = [
      new RegExp(`^Simplicio_${escapedVersion}_${arch}-setup\\.exe$`),
      new RegExp(`^Simplicio-${escapedVersion}-windows-${arch}-setup\\.exe$`),
      new RegExp(`^Simplicio_${escapedVersion}_${arch}(?:_[a-z]{2}-[A-Z]{2})?\\.msi$`),
    ];
  } else {
    patterns = [
      new RegExp(`^Simplicio_${escapedVersion}_${arch}\\.AppImage$`),
      new RegExp(`^Simplicio-${escapedVersion}-linux-${arch}\\.AppImage$`),
      new RegExp(`^Simplicio_${escapedVersion}_${arch}\\.deb$`),
      new RegExp(`^Simplicio-${escapedVersion}-[1-9]\\d*\\.${arch}\\.rpm$`),
    ];
  }
  const rank = patterns.findIndex((pattern) => pattern.test(normalizedName));
  return rank < 0 ? null : rank;
}

export function selectDesktopRelease(payload: unknown, target: DesktopUpdateTarget): DesktopRelease {
  const validTarget = parseDesktopUpdateTarget(target);
  if (!Array.isArray(payload) || payload.length > MAX_RELEASES) throw new DesktopUpdateError("invalid_response");
  let latest: DesktopRelease | null = null;
  for (const entry of payload) {
    if (!record(entry) || entry.draft !== false || entry.prerelease !== false || typeof entry.tag_name !== "string" ||
      !/^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(entry.tag_name)) continue;
    const version = entry.tag_name.slice(1);
    try { versionParts(version); } catch { continue; }
    const releaseUrl = `${DESKTOP_RELEASES_URL}/tag/${entry.tag_name}`;
    if (entry.html_url !== releaseUrl || !Array.isArray(entry.assets)) continue;
    if (entry.assets.length > MAX_ASSETS) throw new DesktopUpdateError("invalid_response");
    let selected: { name: string; bytes: number; rank: number } | null = null;
    for (const asset of entry.assets) {
      if (!record(asset) || asset.state !== "uploaded" || typeof asset.name !== "string" || asset.name.length > 180 || /[\u0000-\u001f\u007f]/.test(asset.name) ||
        typeof asset.size !== "number" || !Number.isSafeInteger(asset.size) || asset.size <= 0 || asset.size > 5 * 1024 ** 3) continue;
      const rank = desktopAssetRank(asset.name, version, validTarget);
      if (rank === null || asset.browser_download_url !== `${DESKTOP_RELEASES_URL}/download/${entry.tag_name}/${encodeURIComponent(asset.name)}`) continue;
      if (selected === null || rank < selected.rank) selected = { name: asset.name, bytes: asset.size, rank };
    }
    if (selected && (latest === null || compareVersions(version, latest.version) > 0)) {
      latest = { version, tag: entry.tag_name, releaseUrl, assetName: selected.name, assetBytes: selected.bytes };
    }
  }
  if (!latest) throw new DesktopUpdateError("no_compatible_release");
  return latest;
}

async function readBoundedJson(response: Response): Promise<unknown> {
  const declaredLength = Number(response.headers.get("content-length"));
  if (declaredLength > MAX_RELEASE_BYTES || !response.body ||
    !/^application\/json(?:;|$)/i.test(response.headers.get("content-type") ?? "")) {
    void response.body?.cancel().catch(() => undefined);
    throw new DesktopUpdateError("invalid_response");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let size = 0;
  let text = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_RELEASE_BYTES) {
        void reader.cancel().catch(() => undefined);
        throw new DesktopUpdateError("invalid_response");
      }
      text += decoder.decode(value, { stream: true });
    }
    return JSON.parse(text + decoder.decode()) as unknown;
  } catch (error) {
    if (error instanceof DesktopUpdateError) throw error;
    throw new DesktopUpdateError("invalid_response");
  } finally {
    reader.releaseLock();
  }
}

export async function checkDesktopUpdate(options: {
  currentVersion: string;
  target: unknown;
  signal?: AbortSignal;
  fetcher?: typeof fetch;
  online?: boolean;
  timeoutMs?: number;
}): Promise<DesktopUpdateResult> {
  versionParts(options.currentVersion);
  const target = parseDesktopUpdateTarget(options.target);
  if (options.signal?.aborted) throw new DesktopUpdateError("canceled");
  if (options.online === false) throw new DesktopUpdateError("offline");
  const controller = new AbortController();
  const timeoutMs = typeof options.timeoutMs === "number" && Number.isFinite(options.timeoutMs)
    ? Math.max(1, Math.min(options.timeoutMs, CHECK_TIMEOUT_MS)) : CHECK_TIMEOUT_MS;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancel: () => void = () => undefined;
  const interrupted = new Promise<never>((_, reject) => {
    cancel = () => { controller.abort(); reject(new DesktopUpdateError("canceled")); };
    options.signal?.addEventListener("abort", cancel, { once: true });
    timer = setTimeout(() => { controller.abort(); reject(new DesktopUpdateError("timeout")); }, timeoutMs);
  });
  const request = async (): Promise<DesktopUpdateResult> => {
    const response = await (options.fetcher ?? fetch)(DESKTOP_RELEASES_API, {
      method: "GET", headers: { Accept: "application/vnd.github+json" },
      credentials: "omit", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer", signal: controller.signal,
    });
    if (!response.ok) throw new DesktopUpdateError(response.status === 403 || response.status === 429 ? "rate_limited" : "request_failed");
    const release = selectDesktopRelease(await readBoundedJson(response), target);
    const comparison = compareVersions(options.currentVersion, release.version);
    return { state: comparison < 0 ? "available" : comparison > 0 ? "newer_local" : "up_to_date", currentVersion: options.currentVersion, target, release };
  };
  try {
    return await Promise.race([request(), interrupted]);
  } catch (error) {
    if (error instanceof DesktopUpdateError) throw error;
    throw new DesktopUpdateError("request_failed");
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", cancel);
    controller.abort();
  }
}
