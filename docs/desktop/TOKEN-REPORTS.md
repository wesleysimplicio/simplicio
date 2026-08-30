# Token Reports

`insights.tokens/v1` is a read-only projection of savings, cost and cache
receipts. It preserves evidence labels (`measured`, `estimated`, `replayed`,
`mixed` or `unavailable`) and never computes a provider cache hit locally.

The Desktop shows a dash when the Runtime did not provide proof. Raw prompts,
ledgers and credentials are not included in the projection.
