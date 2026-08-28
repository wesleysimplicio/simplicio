# Desktop authentication contract

The primary experience is a system-browser authorization-code flow. The
Desktop never receives an access token in a URL or React state.

1. The Runtime starts `desktop login`, creates the state/PKCE transaction, and
   owns the callback handoff.
2. `apps/desktop/src/auth.ts` defines the browser-side PKCE and deep-link
   validation contract: S256 challenge, one-time state, ten-minute TTL, and
   authorization code only.
3. The Runtime exchanges the code, verifies identity and entitlement, and
   publishes the versioned snapshot. The UI renders only the authoritative
   `active`, `inactive`, `signed_out`, or `unknown` state.
4. Logout invokes the Runtime's `logout --json` action before requesting a new
   snapshot. Paid operations are therefore stopped by the Runtime authority,
   not by a UI-only flag.

Invalid state, replayed callbacks, expired transactions, provider/network
failures, and callbacks containing token-shaped query/hash values fail closed.
The login bridge also has a bounded timeout. The CLI device flow remains a
fallback for headless environments and is not the Desktop's primary UX.
