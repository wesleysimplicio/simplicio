const GOOGLE_LOGIN_URL = "https://simpleti.com.br/simplicio/login";
const TOKEN_QUERY_KEYS = ["access_token", "id_token", "refresh_token", "token"];

export interface PkceTransaction {
  state: string;
  verifier: string;
  challenge: string;
  createdAt: number;
}

export interface AuthorizationCallback {
  code: string;
  state: string;
}

export class AuthCallbackError extends Error {
  constructor(public readonly code: "invalid_state" | "expired" | "replayed" | "invalid_callback") {
    super(`OAuth callback rejected: ${code}`);
    this.name = "AuthCallbackError";
  }
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function randomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  if (!globalThis.crypto?.getRandomValues) throw new Error("Secure randomness is unavailable");
  return globalThis.crypto.getRandomValues(bytes);
}

export async function createPkceTransaction(
  now = Date.now(),
  getRandomBytes: (length: number) => Uint8Array = randomBytes,
): Promise<PkceTransaction> {
  const verifierBytes = getRandomBytes(32);
  const stateBytes = getRandomBytes(24);
  const verifier = base64Url(verifierBytes);
  const state = base64Url(stateBytes);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return { state, verifier, challenge: base64Url(new Uint8Array(digest)), createdAt: now };
}

export function buildGoogleAuthorizationUrl(options: {
  clientId: string;
  redirectUri: string;
  transaction: PkceTransaction;
  endpoint?: string;
}): string {
  const url = new URL(options.endpoint ?? GOOGLE_LOGIN_URL);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: options.clientId,
    redirect_uri: options.redirectUri,
    code_challenge: options.transaction.challenge,
    code_challenge_method: "S256",
    state: options.transaction.state,
  }).toString();
  return url.toString();
}

export class AuthTransactionStore {
  private readonly transactions = new Map<string, PkceTransaction>();
  private readonly usedStates = new Set<string>();

  constructor(private readonly getRandomBytes: (length: number) => Uint8Array = randomBytes) {}

  async begin(now = Date.now()): Promise<PkceTransaction> {
    const transaction = await createPkceTransaction(now, this.getRandomBytes);
    this.transactions.set(transaction.state, transaction);
    return transaction;
  }

  consume(callbackUrl: string, now = Date.now(), maxAgeMs = 10 * 60 * 1000): AuthorizationCallback {
    let url: URL;
    try {
      url = new URL(callbackUrl);
    } catch {
      throw new AuthCallbackError("invalid_callback");
    }

    if (TOKEN_QUERY_KEYS.some((key) => url.searchParams.has(key)) || TOKEN_QUERY_KEYS.some((key) => url.hash.includes(key))) {
      throw new AuthCallbackError("invalid_callback");
    }

    const state = url.searchParams.get("state");
    const transaction = state ? this.transactions.get(state) : undefined;
    if (!state || this.usedStates.has(state) || !transaction) throw new AuthCallbackError("invalid_state");
    if (now - transaction.createdAt > maxAgeMs || now < transaction.createdAt) {
      this.transactions.delete(state);
      throw new AuthCallbackError("expired");
    }

    const code = url.searchParams.get("code");
    if (!code || url.searchParams.has("error")) throw new AuthCallbackError("invalid_callback");

    this.transactions.delete(state);
    this.usedStates.add(state);
    return { code, state };
  }
}
