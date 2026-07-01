# Delivery Preferences — Cron Notifications to User

Established during the 2026-06-29 cron job triage. These rules govern what trading-advisor cron jobs should and shouldn't deliver as Telegram messages.

## Delivery Taxonomy

| Deliver | Examples | Rationale |
|---------|----------|-----------|
| ✅ **Always deliver** | Morning/afternoon briefings, orchestrator digest, weekly review, M2M position closes | Trading signals and trend summaries are core value |
| 🔇 **Do NOT deliver** | Research enrichment "new papers" summaries, optimizer sweep results | Infrastructure noise — consumed by the pipeline, not the user |
| ❌ **Fix or remove broken delivery** | Reports that exceed Telegram's 4,096-char limit | A failed delivery wastes the run |
| 🔕 **Silent until events** | M2M ticks with no position closes | No news is good news — only notify on actions (close, error) |

## Guidelines for New Cron Jobs

1. If another job already surfaces the same data (e.g., orchestrator digest shows optimizer findings), deliver the new job **locally** — don't send a duplicate Telegram message.
2. If the output is consumed by a script downstream (e.g., research digest → briefing citation pipeline), the Telegram message is just a notification. Consider **local delivery** — the pipeline works without it.
3. Jobs that run more than once daily should almost never deliver to `origin` unless something meaningfully changed since the last run.
4. When in doubt, start with `deliver: local`. Users can switch to `origin` if they want to see it.
5. A job that **never successfully delivered** (e.g., message too long for Telegram) should be removed, not kept running in a broken state.

## Rationale

The user wants to see:
- Actionable trading information (signals, trends, position closes)
- Summaries they act on (briefings, weekly reviews)
- Errors (M2M failures)

The user does NOT want to see:
- Pipeline status updates ("papers collected", "optimizer ran")
- Data that's already shown in another message
- Broken messages that truncate mid-delivery
