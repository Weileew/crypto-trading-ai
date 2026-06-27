# TokoCrypto Liquidity Reference

Requires browser automation because TokoCrypto only exposes this via issued frontends / Yokwe endpoints, or theTokocrypto dashboard and spot orderbook page.

## Files Generated
- `tokocrypto_snapshot_{symbol}.json`
- latest snapshot symlink: `tokocrypto_snapshot_latest.json`

## Procedure
1. Open TokoCrypto spot market for target coin pair in a browser-capable state.
2. Wait for orderbook to stabilize.
3. Extract:
   - best bid / best ask
   - sizes and cumulative depth within 1%
   - recent fills quantity range
   - spread basis points
4. Persist the result in JSON inside report workdir.
5. Compare previous snapshot to current to detect liquidity changes.

## Notes
- Do NOT treat unfilled depth as available capital; execution risk is high on thin orderbooks.
- Negative mark if best bid size < 0.1% of notional you would reasonably trade at once.
- Do NOT trade if spread > 0.5% unless there is an overwhelming trend reason and wide stop.
