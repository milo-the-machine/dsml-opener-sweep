
### variant x engine (all depths)

| key | n | tool-call failures | rate | 95% CI |
|---|---:|---:|---:|---|
| clean / high / gb300 | 180 | 0 | 0.0% | 0.0–2.1% |
| clean / high / owen1120 | 180 | 0 | 0.0% | 0.0–2.1% |
| clean / high / sglang | 144 | 0 | 0.0% | 0.0–2.6% |
| clean / max / gb300 | 48 | 0 | 0.0% | 0.0–7.4% |
| clean / max / owen1120 | 48 | 0 | 0.0% | 0.0–7.4% |
| drop / high / gb300 | 192 | 0 | 0.0% | 0.0–2.0% |
| drop / high / owen1120 | 192 | 0 | 0.0% | 0.0–2.0% |
| drop / high / sglang | 192 | 0 | 0.0% | 0.0–2.0% |
| dsmlctx / high / gb300 | 240 | 0 | 0.0% | 0.0–1.6% |
| dsmlctx / high / owen1120 | 240 | 0 | 0.0% | 0.0–1.6% |
| dsmlctx / high / sglang | 48 | 0 | 0.0% | 0.0–7.4% |
| dsmltail / high / gb300 | 240 | 1 | 0.4% | 0.1–2.3% |
| dsmltail / high / owen1120 | 240 | 0 | 0.0% | 0.0–1.6% |
| dsmltail / high / sglang | 48 | 0 | 0.0% | 0.0–7.4% |
| poisoned / high / gb300 | 564 | 20 | 3.5% | 2.3–5.4% |
| poisoned / high / owen1120 | 564 | 14 | 2.5% | 1.5–4.1% |
| poisoned / high / sglang | 432 | 3 | 0.7% | 0.2–2.0% |
| poisoned / max / gb300 | 48 | 3 | 6.2% | 2.1–16.8% |
| poisoned / max / owen1120 | 48 | 4 | 8.3% | 3.3–19.6% |
| poisoned1 / high / gb300 | 192 | 3 | 1.6% | 0.5–4.5% |
| poisoned1 / high / owen1120 | 192 | 3 | 1.6% | 0.5–4.5% |
| poisoned1 / high / sglang | 192 | 1 | 0.5% | 0.1–2.9% |
| poisonedfar / high / gb300 | 288 | 1 | 0.3% | 0.1–1.9% |
| poisonedfar / high / owen1120 | 288 | 4 | 1.4% | 0.5–3.5% |
| poisonedfar / high / sglang | 96 | 0 | 0.0% | 0.0–3.8% |
| repair / high / gb300 | 192 | 0 | 0.0% | 0.0–2.0% |
| repair / high / owen1120 | 192 | 0 | 0.0% | 0.0–2.0% |
| repair / high / sglang | 72 | 0 | 0.0% | 0.0–5.1% |
| strip / high / gb300 | 192 | 10 | 5.2% | 2.9–9.3% |
| strip / high / owen1120 | 192 | 8 | 4.2% | 2.1–8.0% |
| strip / high / sglang | 192 | 4 | 2.1% | 0.8–5.2% |

### variant pooled over engines (all depths)

| key | n | tool-call failures | rate | 95% CI |
|---|---:|---:|---:|---|
| clean / high | 504 | 0 | 0.0% | 0.0–0.8% |
| clean / max | 96 | 0 | 0.0% | 0.0–3.8% |
| drop / high | 576 | 0 | 0.0% | 0.0–0.7% |
| dsmlctx / high | 528 | 0 | 0.0% | 0.0–0.7% |
| dsmltail / high | 528 | 1 | 0.2% | 0.0–1.1% |
| poisoned / high | 1560 | 37 | 2.4% | 1.7–3.3% |
| poisoned / max | 96 | 7 | 7.3% | 3.6–14.3% |
| poisoned1 / high | 576 | 7 | 1.2% | 0.6–2.5% |
| poisonedfar / high | 672 | 5 | 0.7% | 0.3–1.7% |
| repair / high | 456 | 0 | 0.0% | 0.0–0.8% |
| strip / high | 576 | 22 | 3.8% | 2.5–5.7% |

### poisoned/clean by depth band

| key | n | tool-call failures | rate | 95% CI |
|---|---:|---:|---:|---|
| clean / 200K-800K / gb300 | 120 | 0 | 0.0% | 0.0–3.1% |
| clean / 200K-800K / owen1120 | 120 | 0 | 0.0% | 0.0–3.1% |
| clean / 200K-800K / sglang | 96 | 0 | 0.0% | 0.0–3.8% |
| clean / 4K-64K / gb300 | 60 | 0 | 0.0% | 0.0–6.0% |
| clean / 4K-64K / owen1120 | 60 | 0 | 0.0% | 0.0–6.0% |
| clean / 4K-64K / sglang | 48 | 0 | 0.0% | 0.0–7.4% |
| poisoned / 200K-800K / gb300 | 312 | 19 | 6.1% | 3.9–9.3% |
| poisoned / 200K-800K / owen1120 | 312 | 13 | 4.2% | 2.5–7.0% |
| poisoned / 200K-800K / sglang | 288 | 3 | 1.0% | 0.4–3.0% |
| poisoned / 4K-64K / gb300 | 252 | 1 | 0.4% | 0.1–2.2% |
| poisoned / 4K-64K / owen1120 | 252 | 1 | 0.4% | 0.1–2.2% |
| poisoned / 4K-64K / sglang | 144 | 0 | 0.0% | 0.0–2.6% |

### poisoned (broken turns in last ~200 tokens) vs poisonedfar (9-15K tokens of normal turns after them), same depths, pooled

| key | n | tool-call failures | rate | 95% CI |
|---|---:|---:|---:|---|
| poisoned / 200K | 228 | 4 | 1.8% | 0.7–4.4% |
| poisoned / 400K | 228 | 11 | 4.8% | 2.7–8.4% |
| poisoned / 598K | 228 | 9 | 3.9% | 2.1–7.3% |
| poisonedfar / 200K | 192 | 2 | 1.0% | 0.3–3.7% |
| poisonedfar / 400K | 240 | 1 | 0.4% | 0.1–2.3% |
| poisonedfar / 598K | 240 | 2 | 0.8% | 0.2–3.0% |

### failure shapes (all variants)

- 29 × A: params+closers as text, no opener/invoke (new command), real-token DSML in output: 0  ({'gb300': 16, 'owen1120': 13})
- 24 × C: text-only (short tool-announcing line)  ({'gb300': 10, 'owen1120': 9, 'sglang': 5})
- 10 × A: params+closers as text, no opener/invoke (verbatim copy), real-token DSML in output: 0  ({'gb300': 5, 'owen1120': 5})
- 7 × B: real <calls> opener, invoke line missing -> parser drops the call body, client gets the sentence only  ({'gb300': 4, 'owen1120': 3})
- 3 × A: params+closers as text, no opener/invoke (new command), real-token DSML in output: 2  ({'gb300': 2, 'owen1120': 1})
- 2 × EMPTY  ({'owen1120': 2})
- 2 × A: params+closers as text, no opener/invoke (new command)  ({'sglang': 2})
- 1 × CALL_BAD_SHAPE  ({'gb300': 1})
- 1 × A: params+closers as text, no opener/invoke (verbatim copy)  ({'sglang': 1})

excluded as not tool-format failures (honest give-up prose): 4
total requests: 6168  engines: {'gb300': 2376, 'owen1120': 2376, 'sglang': 1416}
