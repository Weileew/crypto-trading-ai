## CG Rate Limit Management

All CoinGecko API calls in the TOK system go through a **single, centralized rate limiter** in `scripts/free_data.py`.

### Architecture

```
free_data._get_cg()  ← shared by all scripts
  ├── 6s min spacing between CG calls (CG free tier limit)
  ├── exponential backoff on 429 (3s × attempt)
  ├── automatic call counter (reports/cg_call_count.json)
  └── 90% threshold warning
```

### Where CG calls come from

| Script | Endpoint | Calls per run | Schedule |
|---|---|---|---|
| `free_data._get_cg()` | CG `/simple/price` | 1 | M2M cron (every 10m), paper_trader |
| `free_data.fetch_coingecko_market_chart()` | CG `/coins/{id}/market_chart` | 1 per signal | signal_validator (on demand) |
| `briefing.py._get_cg()` | CG `/coins/markets` + `/coins/list` + `/simple/price` + `/global` | 6 | Morning/afternoon briefings |

### Daily budget

- **CG free tier**: ~10 req/min = ~14,400/day
- **Safety threshold** (`_CG_MAX_DAILY`): 500 (warns at 90%+)
- **Actual daily usage**: ~160 calls/day (M2M 144 + briefings 12 + validator on-demand)

### Rules for future development

1. **Always use `_get_cg()` for CG endpoints**, never `_get()` or raw `urlopen`.
2. `_get_cg()` is imported from `free_data` in all consumer scripts.
3. Do NOT define a separate `_get()` for CG in any new script.
4. If adding a new CG-heavy job, update cron-schedule.md and verify no collision with existing jobs.
5. Monitor `reports/cg_call_count.json` — it logs warning at 90% of threshold.

### What was centralized

- `signal_validator.py`: removed its own `_get()` + `_throttle()` — imports `_get_cg` from free_data
- `paper_trader.py`: removed its own `_get()` — imports `_get_cg` from free_data
- `free_data.py`: added `_get_cg()` with 6s spacing, counter, backoff
