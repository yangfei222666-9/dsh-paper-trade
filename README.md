# dsh-paper-trade

A **zero-dependency paper-trading CLI** for the DeepSeek Harness ecosystem: a virtual **$100,000** account, real daily stock quotes, and every trade recorded in a **hash-chained, tamper-evident ledger**. It exists to train one discipline — *write the reason before the order, leave the evidence after the fill* — without ever touching real money.

MIT · pure Python standard library · by Taiji Whale (太极鲸)

## Why it exists

The DSH ecosystem has almost no financial tooling. Most people jump straight to a real brokerage and burn real money. This tool turns "evidence-based trading discipline" into the smallest runnable system:

- **Paper only** — no brokerage integration, no real funds. The red line is baked into the design.
- **Hash-chained ledger** — every trade record carries the hash of the previous record; one command verifies nothing was altered.
- **Machine-enforced discipline** — reject on insufficient cash, reject on insufficient position, **reject when no quote exists**, $1 virtual commission per trade, $20 minimum notional.
- **Zero dependencies** — free Yahoo daily bars with a local CSV cache fallback. No third-party libraries.

## Install

```bash
git clone https://github.com/yangfei222666-9/dsh-paper-trade.git
cd dsh-paper-trade
python3 paper_trade.py status
```

Requires Python 3.9+. No `pip install` step: the entire codebase uses only the standard library.

## Usage

```bash
python3 paper_trade.py quote AAPL            # latest close (Yahoo; cached fallback)
python3 paper_trade.py buy AAPL 10 "reason"  # buy: cash check + commission
python3 paper_trade.py sell AAPL 5 "reason"  # sell: position check
python3 paper_trade.py status                # positions + unrealized P/L
python3 paper_trade.py report                # JSON snapshot (weekly review)
python3 paper_trade.py chain-check           # verify ledger integrity
```

| Command | Purpose |
|---|---|
| `quote SYM` | Latest close for a ticker |
| `buy SYM <shares> <reason>` | Buy (cash validation + $1 fee) |
| `sell SYM <shares> <reason>` | Sell (position validation + $1 fee) |
| `status` | Cash, positions, unrealized P/L, total assets |
| `report` | Timestamped JSON snapshot under `snapshots/` |
| `chain-check` | Hash-chain integrity verification |

The `reason` argument is not optional decoration — the ledger records it with the trade. If you cannot state a reason, the trade should not happen.

## The hash-chained ledger

Every trade appends one line to `trades.jsonl`:

```json
{"ts": "2026-08-20 09:15:00", "action": "buy", "ticker": "AAPL", "shares": 10,
 "price": 100.0, "px_date": "2026-08-19", "fee": 1.0, "reason": "…",
 "prev": "<first 16 hex of previous hash>", "hash": "<sha1[:16] of this record>"}
```

- Each record's `hash` is `sha1` over its own canonical body (sorted keys, excluding `hash`).
- Each record's `prev` links to the previous record's hash; the head hash is stored in `portfolio.json` as `chain`.
- `chain-check` recomputes every hash from the file and reports the first break point.

**Ledger rules:** append-only; never rewritten; tampering is detectable, not preventable — the goal is *evidence*, and the evidence must survive a casual edit.

## Design red lines (never change)

1. **Paper only.** Never connect a real brokerage, never place a real order.
2. No return promises. This is a discipline trainer, not an advisor.
3. **No data, no trade.** A missing quote rejects the order instead of guessing a price.
4. The ledger is append-only. Established records are never rewritten.

## Tests

Stdlib-only unit tests (hash-chain integrity, tamper detection, trade accounting):

```bash
python3 -m unittest discover -s tests -v
```

CI runs the same suite on Python 3.9–3.13 (see `.github/workflows/ci.yml`).

## Files

- `prices.py` — quote engine (Yahoo daily bars + CSV cache)
- `paper_trade.py` — trading CLI + hash-chained ledger
- `paper_data.py` — dashboard data generator
- `watchlist.json` — example watchlist
- `tests/` — stdlib unit tests

## Relationship to DeepSeek Harness

The tool runs independently of DSH (any Python 3.9+ environment works). It originated as the investing lane of the "Taiji Whale" butler system inside the DSH ecosystem, and was split out to fill the financial-tooling gap. Roadmap: a DSH plugin panel and a strategy backtest layer.

## License

MIT © Taiji Whale (太极鲸)
