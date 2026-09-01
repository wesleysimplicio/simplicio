import { describe, expect, it } from 'vitest';
import {
  parseRuntimeLifecycleReceipt,
  runtimeLifecycleState,
  type RuntimeLifecycleReceipt,
} from './runtime_lifecycle';

const digestA = 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const digestB = 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

function validReceipt(): RuntimeLifecycleReceipt {
  return {
    schema: 'simplicio.desktop-runtime-lifecycle/v1',
    action: 'upgrade',
    status: 'installed',
    candidate_version: '3.8.40',
    candidate_digest: digestA,
    active_version: '3.8.40',
    active_digest: digestA,
    previous_version: '3.8.39',
    previous_digest: digestB,
    validated: true,
    atomic_swap: true,
    directory_fsynced: true,
    receipt_durable: true,
    runtime_healthy: true,
    backup_available: true,
    plugins_mutated: false,
    rollback_proven: false,
  };
}

describe('Runtime lifecycle receipt contract', () => {
  it('accepts an atomic validated upgrade and exposes only safe fields', () => {
    const parsed = parseRuntimeLifecycleReceipt({
      ...validReceipt(),
      targetPath: '/private/user/.simplicio/bin/simplicio',
      rawOutput: 'secret-token',
    });
    expect(parsed).toEqual(validReceipt());
    expect(runtimeLifecycleState(parsed)).toBe('current');
    expect(JSON.stringify(parsed)).not.toMatch(/private|rawOutput|secret-token/);
  });

  it('accepts idempotent install and explicit repair receipts', () => {
    const current = {
      ...validReceipt(),
      action: 'install' as const,
      status: 'already_current' as const,
      previous_version: null,
      previous_digest: null,
      backup_available: false,
    };
    const repaired = {
      ...validReceipt(),
      action: 'repair' as const,
      status: 'repaired' as const,
      previous_version: null,
      previous_digest: null,
    };
    expect(parseRuntimeLifecycleReceipt(current).status).toBe('already_current');
    expect(parseRuntimeLifecycleReceipt(repaired).status).toBe('repaired');
  });

  it('accepts rollback only when the prior verified target is active', () => {
    const rolledBack = {
      ...validReceipt(),
      action: 'rollback' as const,
      status: 'rolled_back' as const,
      active_version: '3.8.39',
      active_digest: digestB,
      rollback_proven: true,
    };
    expect(parseRuntimeLifecycleReceipt(rolledBack).status).toBe('rolled_back');
  });

  it('fails closed for unverified, non-atomic, plugin-mutating, and inconsistent receipts', () => {
    const invalid = [
      { ...validReceipt(), validated: false },
      { ...validReceipt(), atomic_swap: false },
      { ...validReceipt(), directory_fsynced: false },
      { ...validReceipt(), receipt_durable: false },
      { ...validReceipt(), runtime_healthy: false },
      { ...validReceipt(), plugins_mutated: true },
      { ...validReceipt(), active_digest: digestB },
      { ...validReceipt(), action: 'rollback' as const },
      { ...validReceipt(), path: '/private/user/.simplicio/bin/simplicio' },
    ];
    for (const receipt of invalid) {
      expect(() => parseRuntimeLifecycleReceipt(receipt)).toThrow();
    }
  });
});
