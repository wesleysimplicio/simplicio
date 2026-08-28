import { describe, expect, it } from "vitest";
import { AuthCallbackError, AuthTransactionStore, buildGoogleAuthorizationUrl, createPkceTransaction } from "./auth";

const bytes = (length: number) => new Uint8Array(length).fill(7);

describe("browser auth contract", () => {
  it("builds an authorization-code PKCE URL without tokens", async () => {
    const transaction = await createPkceTransaction(1_000, bytes);
    const url = new URL(buildGoogleAuthorizationUrl({
      clientId: "desktop-test",
      redirectUri: "simplicio://oauth/callback",
      transaction,
      endpoint: "https://simpleti.test/login",
    }));
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("state")).toBe(transaction.state);
    expect(url.searchParams.has("access_token")).toBe(false);
    expect(url.hash).toBe("");
  });

  it("rejects state mismatch, expiry, and replay", async () => {
    const store = new AuthTransactionStore(bytes);
    expect(() => store.consume("simplicio://oauth/callback?code=c&state=mismatch", 1_001)).toThrowError(AuthCallbackError);

    const active = await store.begin(1_000);
    expect(() => store.consume(`simplicio://oauth/callback?code=c&state=${active.state}`, 601_001)).toThrowError("expired");
    const fresh = await store.begin(2_000);
    expect(store.consume(`simplicio://oauth/callback?code=c&state=${fresh.state}`, 2_001)).toEqual({ code: "c", state: fresh.state });
    expect(() => store.consume(`simplicio://oauth/callback?code=c&state=${fresh.state}`, 2_002)).toThrowError("invalid_state");
  });

  it("fails closed when the callback contains a token or missing code", async () => {
    const store = new AuthTransactionStore();
    const transaction = await store.begin(1_000);
    expect(() => store.consume(`simplicio://oauth/callback?state=${transaction.state}&access_token=secret`, 1_001)).toThrowError("invalid_callback");
    expect(() => store.consume(`simplicio://oauth/callback?state=${transaction.state}`, 1_001)).toThrowError("invalid_callback");
  });
});
