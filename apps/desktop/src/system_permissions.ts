import { invoke } from "@tauri-apps/api/core";
export const permissionIds = ["microphone", "camera", "screen", "accessibility", "files", "automation", "network", "devices"] as const;
export type PermissionId = typeof permissionIds[number];
export type PermissionStatus = "unknown" | "not_determined" | "restricted" | "denied" | "granted" | "not_granted";
export type PermissionRow = { id: PermissionId; status: PermissionStatus; canOpenSettings: boolean };
export function parsePermissions(value: unknown): PermissionRow[] {
  const data = value as { schema?: unknown; source?: unknown; rows?: unknown };
  if (!data || data.schema !== "simplicio.desktop-permissions/v1" || data.source !== "operating_system" || !Array.isArray(data.rows) || data.rows.length !== permissionIds.length) throw new Error("permissions_invalid");
  return permissionIds.map(id => {
    const matches = (data.rows as PermissionRow[]).filter(row => row && row.id === id);
    const row = matches[0];
    if (matches.length !== 1 || !["unknown", "not_determined", "restricted", "denied", "granted", "not_granted"].includes(row.status) || typeof row.canOpenSettings !== "boolean") throw new Error("permissions_invalid");
    return { id, status: row.status, canOpenSettings: row.canOpenSettings };
  });
}
async function bounded<T>(promise: Promise<T>, timeout = 5000): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  try { return await Promise.race([promise, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error("permissions_timeout")), timeout); })]); }
  finally { clearTimeout(timer!); }
}
export async function requestMediaPermission(permission: PermissionId) {
  if (!["microphone", "camera"].includes(permission)) throw new Error("permission_invalid");
  return parsePermissions(await bounded(invoke("desktop_request_media_permission", { permission }), 65_000));
}
export async function revealPermissionApp() { await bounded(invoke("desktop_reveal_permission_app")); }
export async function readPermissions() { return parsePermissions(await bounded(invoke("desktop_permissions"))); }
export async function openPermissionSettings(permission: PermissionId) {
  if (!permissionIds.includes(permission)) throw new Error("permission_invalid");
  await bounded(invoke("desktop_open_permission_settings", { permission }));
}
