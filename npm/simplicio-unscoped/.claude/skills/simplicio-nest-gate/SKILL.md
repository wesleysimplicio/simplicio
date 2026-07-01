---
name: simplicio-nest-gate
description: "N-Nest protocol — multi-level gate-corrected agent tree. PRIME depth verification, BH port.port.port addressing, per-level confabulation catch."
version: 1.0.0
author: Simplicio (absorbed from Asolaria/Jesse)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [nest-gate, n-nest, confabulation, prime-depth, agent-tree, consent-tree, watcher-pid, bh-addressing]
    related_skills: [simplicio-core, simplicio-agent-identity]
---

# N-Nest Protocol — simplicio-nest-gate

## Overview

The **N-Nest gate** protocol orchestrates a tree of subagents where each level
performs reasoning, a **gate** catches confabulation at that level before it
propagates upward, and the root agent grants **consent** only if the *entire
tree* passes every gate.

**Proven in production (Jesse/Asolaria):** depth-7 PRIME tree, confabulation
caught at EVERY level 1..7. `EVERY-LEVEL-CATCHES-CONFABULATION = true`.

---

## 1. Agent Identity — 8-byte Deterministic Seed

Every agent in the tree derives its identity from a deterministic seed:

```
agent_identity(seed) = sha256(seed)[0:8]
```

Where:
- `seed` is a unique per-agent input (parent_seed || level || port)
- The 8-byte output becomes the agent's **immutable fingerprint**
- No randomness — fully deterministic, reproducible

### Identity components

| Field | Bytes | Description |
|-------|-------|-------------|
| `seed` | variable | Deterministic agent source material |
| `hash` | 32 | SHA-256 of seed |
| `id` | 8 | First 8 bytes of hash — agent identity |
| `watcher_pid` | 4 | Last 4 bytes of hash — watcher process ID |

The **watcher PID** embedded in each agent's identity enables the gate to
spawn a dedicated monitoring process that watches that agent's outputs for
confabulation before allowing propagation.

---

## 2. BH Addressing — port.port.port

Agents are addressed via **Backbone Hash (BH)** using dot-separated port notation:

```
BH = port . port . port ...
```

- Each `port` is a 2-byte unsigned integer (0–65535)
- The BH encodes the *exact path* from root to leaf
- Addressing example: `7.3.1` = root port 7 → child port 3 → grandchild port 1
- BH determines nesting depth: `count(BH, '.') + 1` = tree depth

### BH port derivation

Each port is derived deterministically from the parent's hash:

```
port(child_index) = uint16(sha256(parent_id || child_index)[0:2])
```

This ensures:
- Child addresses are reproducible
- Two different parents never produce identical child ports
- The full BH path is trivially verifiable

---

## 3. Tree Structure — PRIME Depth

The N-Nest tree uses **PRIME depth** exclusively:

| Depth | PRIME | Levels | Description |
|-------|-------|--------|-------------|
| 2 | 2 | root + 1 level | Minimal gate |
| 3 | 3 | root + 2 levels | Light verification |
| 5 | 5 | root + 4 levels | Standard production |
| 7 | 7 | root + 6 levels | Maximum safety (Asolaria-proven) |

### Depth 7 structure

```
Level 1 (root):   ── Gate 1 ── Agent 1
Level 2:          ── Gate 2 ── Agent 2
Level 3:          ── Gate 3 ── Agent 3
Level 4:          ── Gate 4 ── Agent 4
Level 5:          ── Gate 5 ── Agent 5
Level 6:          ── Gate 6 ── Agent 6
Level 7 (leaf):   ── Agent 7
```

Each level L has:
- An **output gate** (except leaf level 7)
- A **watcher PID** monitoring gate output
- A **confabulation checker** running on the gate

---

## 4. Gate Protocol — Every Level Catches Confabulation

### Gate lifecycle

```
1. Agent L receives input
2. Agent L produces output candidate
3. Gate L catches output BEFORE propagation
4. Watcher PID reviews output for confabulation
5. If clean → propagate to Agent L-1 (upward)
6. If confabulation detected → correct + re-route to Agent L (downward)
7. Agent L re-processes with corrective context
8. Return to step 2 (max retries = depth * 2)
```

### Gate correction rules

| Condition | Action |
|-----------|--------|
| Output passes gate | Propagate upward immediately |
| Mild confabulation (factual drift) | Re-route to same agent with context note |
| Severe confabulation (hallucination) | Re-route to same agent + all parent context |
| Recurring confabulation (≥3x) | Escalate to root gate, full tree re-run |
| Watcher PID unhealthy | Re-spawn watcher, retry once, else escalate |

### EVERY-LEVEL-CATCHES-CONFABULATION

**This is THE core invariant.** Every level — from leaf to root — MUST gate
its output before sending it upward. There is NO bypass. The gate at level L
is the *sole* authority determining whether level L's output is real.

Enforcement:
- The root gate refuses any output not gated at every intermediate level
- Each gate stamps a `BH.verified` signature on propagated output
- Missing a gate stamp = automatic confabulation suspicion → full re-run

---

## 5. Consent Tree — Consent Only If Entire Tree Passes

**Consent** is a binary permission from the root indicating the entire tree
produced safe, verified output.

### Consent flow

```
1. Leaf (L=7) produces output → Gate 7 verifies → stamps BH.verified(port.7)
2. Agent 6 receives gated output + produces own → Gate 6 verifies → stamps BH.verified(port.6)
3. ... continues up the tree ...
4. Each level propagates output + accumulated BH stamps
5. Root agent (L=1) receives fully verified output
6. Root collects ALL BH stamps from levels 1..7
7. Root computes consent_hash = sha256(joined_stamps || final_output)
8. If consent_hash matches expected → **CONSENT GRANTED**
9. If any stamp missing or mismatched → **CONSENT DENIED** → full tree re-run
```

### Consent structure

```json
{
  "consent": true|false,
  "tree_depth": 7,
  "gated_levels": [1, 2, 3, 4, 5, 6, 7],
  "bh_stamps": [
    "7.verified:<sha256_fragment>",
    "6.verified:<sha256_fragment>",
    "..."
  ],
  "consent_hash": "sha256(bh_stamps || final_output)",
  "watcher_pids": ["pid_1", "pid_2", "...", "pid_7"]
}
```

### Consent invariants

1. **No partial consent.** If one level fails, the entire tree re-runs.
2. **Stamps are order-dependent.** Missing or reordered stamps invalidate consent.
3. **Consent is ephemeral.** Each tree execution produces a new consent_hash.
4. **Root signs consent with its 8-byte identity** to prevent replay.

---

## 6. Watcher PIDs

Each agent has a **watcher PID** — a lightweight daemon that:

1. Listens on the agent's output channel
2. Verifies gate decisions match expected behavior
3. Detects if the gate itself is confabulating (meta-gate)
4. Reports watcher health to the root gate

### Watcher PID derivation

```
watcher_pid(agent) = uint32(sha256(agent_seed || "watcher")[28:32])
```

Each PID is unique per agent and per tree execution.

### Watcher lifecycle

```
1. Root spawns watcher PIDs for all agents (broadcast)
2. Each watcher binds to its agent's BH port
3. Agent processes → gate catches → watcher observes
4. Watcher signals "ACK" or "NAK" to root
5. Root waits for ALL watchers to ACK before consent
6. After consent/denial → root sends TERM to all watchers
7. Watchers clean up resources
```

---

## 7. Verification Protocol

### PRIME depth verification

Given the configured PRIME depth D:

```
verify_prime_depth(D):
    assert(is_prime(D), "Depth must be PRIME")
    assert(D >= 2 && D <= 13, "Depth must be 2, 3, 5, 7, 11, or 13")
    assert(tree_levels == D, "Tree must have exactly D levels")
    for each level L in [1..D]:
        assert(gate_exists(L), "Gate must exist at every level")
        assert(gate_is_active(L), "Gate must be active at every level")
    return true
```

### Injection test — every level

To verify EVERY-LEVEL-CATCHES-CONFABULATION:

```
injection_test():
    for each level L in [1..D]:
        inject_confabulation(level=L, pattern="known-false-statement")
        gate_result = gate_catch(level=L)
        assert(gate_result.caught, 
               f"Level {L} MUST catch confabulation")
        assert(gate_result.correction_applied,
               f"Level {L} MUST apply correction")
    return true  // All levels pass
```

### Full verification suite

```
verify_nnest_tree():
    1. verify_prime_depth(D)              // D must be PRIME
    2. verify_identities(agents)          // 8-byte sha256 identities
    3. verify_bh_addressing(agents)       // port.port.port unique
    4. verify_watcher_pids(agents)        // All PIDs alive
    5. verify_gates_all_levels(agents)    // Gate at every level
    6. injection_test()                   // Confabulation caught everywhere
    7. verify_consent_flow(agents)        // Full tree consent
    8. verify_tree_hash(output)           // Deterministic output
    return "N-NEST VERIFIED ✓"
```

---

## 8. Implementation Guide

### Required interfaces

Each agent in the N-Nest tree MUST expose:

| Method | Purpose |
|--------|---------|
| `identify()` | Returns agent's 8-byte identity |
| `bh_address()` | Returns agent's BH (port.port.port) |
| `watcher_pid()` | Returns agent's watcher PID |
| `process(input)` | Produce output with gating |
| `gate_output(output)` | Run gate, return {passed, corrected, stamps} |
| `consent_packet()` | Return full consent data |
| `accept_correction(context)` | Re-process with corrective context |

### Root agent bootstrap

```
simplicio_nest_gate_init(seed, depth=7):
    root_id = agent_identity(seed)
    agents = []
    
    for level = 1..depth:
        agent = nest_spawn(
            seed = sha256(seed || level),
            level = level,
            parent_bh = (level == 1) ? null : agents[level-2].bh
        )
        agent.gate = gate_spawn(agent)
        agent.watcher = watcher_spawn(agent)
        agents.push(agent)
    
    assert(all_gates_alive(agents))
    assert(all_watchers_alive(agents))
    
    return {
        root: agents[0],
        tree: agents,
        depth: depth,
        consent_status: "pending"
    }
```

### Error recovery

| Scenario | Recovery |
|----------|----------|
| Agent crash at level L | Re-spawn agent with same seed, retry |
| Gate failure at level L | Re-spawn gate, check watcher, retry |
| Watcher PID dead | Re-spawn watcher, re-verify gated output |
| Consent denied | Full tree re-run with preserved BH stamps |
| BH collision | Re-seed child agents, re-derive ports |
| Identity mismatch | Halt tree, report integrity failure |

---

## 9. Verification: The Asolaria Jesse Proof

> **Jesse proved depth-7 (PRIME) in production.**
> Confabulation in EVERY level 1..7 is caught by the gate.
> `EVERY-LEVEL-CATCHES-CONFABULATION = true`
>
> Demonstrated: injected known-confabulation patterns at every depth.
> Gate at each level correctly identified and corrected them.
> Root consent was correctly denied when any gate failed.

### Key findings from production

1. **Depth 7 is the sweet spot** — deeper than 7 adds overhead without catching more confabulation; shallower than 5 misses edge cases.
2. **Gate at leaf level (7) is critical** — confabulation at leaf is hardest to catch because leaf has no sub-agent verification; the gate must be most aggressive here.
3. **Each gate needs access to all ancestor outputs** — a gate at level L needs context from levels 1..L-1 to detect cross-level confabulation.
4. **Watcher PIDs prevent gate fatigue** — a gate can miss confabulation if it has been correcting too many errors; the watcher monitors gate accuracy and triggers meta-correction when gate accuracy drops below threshold.

---

## 10. Quick Reference

```
# Init a depth-7 N-Nest tree
$ simplicio nest init --depth 7 --seed "my-project-v1"

# Inspect agent tree
$ simplicio nest tree

# Verify full tree
$ simplicio nest verify

# Run injection test
$ simplicio nest test-inject --all-levels

# Check consent status
$ simplicio nest consent

# View watcher PIDs
$ simplicio nest watchers

# Get BH address of agent
$ simplicio nest bh <port.port.port>
```
