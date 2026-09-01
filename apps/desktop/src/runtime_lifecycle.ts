/** Versioned, redacted lifecycle evidence for the Runtime core installer. */
export const RUNTIME_LIFECYCLE_SCHEMA = 'simplicio.desktop-runtime-lifecycle/v1';

export type RuntimeLifecycleAction = 'install' | 'upgrade' | 'repair' | 'rollback';
export type RuntimeLifecycleStatus = 'installed' | 'already_current' | 'repaired' | 'rolled_back';
export type RuntimeLifecycleState = 'missing' | 'installing' | 'current' | 'upgrading' | 'repairing' | 'rolling_back' | 'blocked';

export interface RuntimeLifecycleReceipt {
  schema: typeof RUNTIME_LIFECYCLE_SCHEMA;
  action: RuntimeLifecycleAction;
  status: RuntimeLifecycleStatus;
  candidate_version: string;
  candidate_digest: string;
  active_version: string;
  active_digest: string;
  previous_version: string | null;
  previous_digest: string | null;
  validated: true;
  atomic_swap: true;
  directory_fsynced: true;
  receipt_durable: true;
  runtime_healthy: true;
  backup_available: boolean;
  plugins_mutated: false;
  rollback_proven: boolean;
}

const ACTIONS: RuntimeLifecycleAction[] = ['install', 'upgrade', 'repair', 'rollback'];
const STATUSES: RuntimeLifecycleStatus[] = ['installed', 'already_current', 'repaired', 'rolled_back'];
const SEMVER = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;
const DIGEST = /^sha256:[a-f0-9]{64}$/;
const SENSITIVE_KEY = /(^|_)(path|cwd|home|argv|prompt|secret|password|credential|authorization|api_key|access_token|refresh_token|raw_payload|raw_output)(_|$)/i;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('runtime_lifecycle_invalid');
  return value as Record<string, unknown>;
}

function rejectSensitiveKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectSensitiveKeys);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (SENSITIVE_KEY.test(key)) throw new Error('runtime_lifecycle_sensitive_field');
    rejectSensitiveKeys(child);
  }
}

function version(value: unknown): string {
  if (typeof value !== 'string' || value.length > 64 || !SEMVER.test(value)) {
    throw new Error('runtime_lifecycle_invalid');
  }
  return value;
}

function digest(value: unknown): string {
  if (typeof value !== 'string' || !DIGEST.test(value)) throw new Error('runtime_lifecycle_invalid');
  return value;
}

function nullableVersion(value: unknown): string | null {
  return value === null ? null : version(value);
}

function nullableDigest(value: unknown): string | null {
  return value === null ? null : digest(value);
}

function boolean(value: unknown, expected: boolean): boolean {
  if (value !== expected) throw new Error('runtime_lifecycle_invalid');
  return expected;
}

function enumValue<T extends string>(value: unknown, values: T[]): T {
  if (typeof value !== 'string' || !values.includes(value as T)) throw new Error('runtime_lifecycle_invalid');
  return value as T;
}

function samePair(leftVersion: string | null, leftDigest: string | null, rightVersion: string, rightDigest: string): boolean {
  return leftVersion === rightVersion && leftDigest === rightDigest;
}

/**
 * Accept only a successful native lifecycle receipt. Unknown fields are discarded
 * so paths, command output, credentials, and backup locations never reach React.
 */
export function parseRuntimeLifecycleReceipt(value: unknown): RuntimeLifecycleReceipt {
  rejectSensitiveKeys(value);
  const raw = record(value);
  const action = enumValue(raw.action, ACTIONS);
  const status = enumValue(raw.status, STATUSES);
  const candidateVersion = version(raw.candidate_version);
  const candidateDigest = digest(raw.candidate_digest);
  const activeVersion = version(raw.active_version);
  const activeDigest = digest(raw.active_digest);
  const previousVersion = nullableVersion(raw.previous_version);
  const previousDigest = nullableDigest(raw.previous_digest);
  if ((previousVersion === null) !== (previousDigest === null)) throw new Error('runtime_lifecycle_invalid');

  const receipt: RuntimeLifecycleReceipt = {
    schema: RUNTIME_LIFECYCLE_SCHEMA,
    action,
    status,
    candidate_version: candidateVersion,
    candidate_digest: candidateDigest,
    active_version: activeVersion,
    active_digest: activeDigest,
    previous_version: previousVersion,
    previous_digest: previousDigest,
    validated: boolean(raw.validated, true),
    atomic_swap: boolean(raw.atomic_swap, true),
    directory_fsynced: boolean(raw.directory_fsynced, true),
    receipt_durable: boolean(raw.receipt_durable, true),
    runtime_healthy: boolean(raw.runtime_healthy, true),
    backup_available: typeof raw.backup_available === 'boolean' ? raw.backup_available : (() => {
      throw new Error('runtime_lifecycle_invalid');
    })(),
    plugins_mutated: boolean(raw.plugins_mutated, false) as false,
    rollback_proven: typeof raw.rollback_proven === 'boolean' ? raw.rollback_proven : (() => {
      throw new Error('runtime_lifecycle_invalid');
    })(),
  };

  if (status === 'rolled_back') {
    if (action !== 'rollback' || previousVersion === null || previousDigest === null
      || !samePair(activeVersion, activeDigest, previousVersion, previousDigest)
      || receipt.backup_available !== true || receipt.rollback_proven !== true) {
      throw new Error('runtime_lifecycle_invalid');
    }
  } else {
    if (action === 'rollback' || !samePair(activeVersion, activeDigest, candidateVersion, candidateDigest)
      || receipt.rollback_proven !== false) {
      throw new Error('runtime_lifecycle_invalid');
    }
    if (status === 'installed' && action !== 'install' && action !== 'upgrade') {
      throw new Error('runtime_lifecycle_invalid');
    }
    if (status === 'already_current' && action !== 'install' && action !== 'upgrade') {
      throw new Error('runtime_lifecycle_invalid');
    }
    if (status === 'repaired' && action !== 'repair') throw new Error('runtime_lifecycle_invalid');
  }
  if (action === 'install' && status === 'repaired') throw new Error('runtime_lifecycle_invalid');
  return receipt;
}

/** A successfully committed or restored receipt leaves the active Runtime current and healthy. */
export function runtimeLifecycleState(value: unknown): RuntimeLifecycleState {
  parseRuntimeLifecycleReceipt(value);
  return 'current';
}
