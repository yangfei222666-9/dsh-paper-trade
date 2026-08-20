#!/usr/bin/env python3
"""Stdlib-only unit tests for the paper-trade ledger and trade accounting.

Covers: hash-chain append linkage, tamper detection via chain-check, and the
trade accounting rules (cash / fees / positions / rejections).

Zero third-party dependencies: unittest + unittest.mock only.
Run from the repo root:

    python3 -m unittest discover -s tests -v
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paper_trade
import prices  # noqa: F401  (patched in tests; import keeps module identity)

FAKE_PX = {"AAPL": 100.0, "TSM": 200.0}


def fake_latest(sym):
    """Deterministic stand-in for prices.latest (no network in tests)."""
    sym = sym.upper()
    if sym in FAKE_PX:
        return FAKE_PX[sym], "2026-08-20", False
    return None, None, True  # no quote available -> "no data, no trade"


class PaperTradeTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = self._tmp.name
        self._port = os.path.join(base, "portfolio.json")
        self._trades = os.path.join(base, "trades.jsonl")
        self._snap = os.path.join(base, "snapshots")
        # Point the module at isolated paths so tests never touch real state.
        self._patchers = [
            mock.patch.object(paper_trade, "PORT", self._port),
            mock.patch.object(paper_trade, "TRADES", self._trades),
            mock.patch.object(paper_trade, "SNAP", self._snap),
            mock.patch("prices.latest", side_effect=fake_latest),
            # paper_data.refresh() would write a dashboard file next to the
            # real repo; neutralize it in tests.
            mock.patch.object(paper_trade.paper_data, "refresh", return_value=None),
        ]
        for p in self._patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patchers])

    def read_trades(self):
        if not os.path.exists(self._trades):
            return []
        with open(self._trades) as f:
            return [json.loads(line) for line in f if line.strip()]

    def corrupt_line(self, index, mutate):
        rows = self.read_trades()
        mutate(rows[index])
        with open(self._trades, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


class TestDefaults(PaperTradeTestBase):
    def test_fresh_portfolio_starts_with_100k(self):
        self.assertEqual(paper_trade.load_port()["cash"], 100000.0)
        self.assertEqual(paper_trade.load_port()["positions"], {})


class TestChainLedger(PaperTradeTestBase):
    def test_append_links_previous_hash(self):
        h1 = paper_trade.chain_append({"ts": "t1", "action": "buy", "ticker": "AAPL",
                                       "shares": 1, "price": 1.0, "reason": "r1"})
        h2 = paper_trade.chain_append({"ts": "t2", "action": "sell", "ticker": "AAPL",
                                       "shares": 1, "price": 1.0, "reason": "r2"})
        rows = self.read_trades()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["hash"], h1)
        self.assertEqual(rows[1]["prev"], h1)  # second record points at first
        self.assertEqual(rows[1]["hash"], h2)
        # Portfolio head-of-chain matches the latest record.
        self.assertEqual(paper_trade.load_port()["chain"], h2)

    def test_chain_check_passes_when_intact(self):
        paper_trade.chain_append({"ts": "t1", "action": "buy", "ticker": "AAPL",
                                  "shares": 1, "price": 1.0, "reason": "r"})
        out = paper_trade.chain_check()
        self.assertIn("完整", out)
        self.assertIn("1", out)

    def test_chain_check_detects_tampered_record(self):
        paper_trade.chain_append({"ts": "t1", "action": "buy", "ticker": "AAPL",
                                  "shares": 1, "price": 1.0, "reason": "r"})
        self.corrupt_line(0, lambda r: r.update(shares=999))
        out = paper_trade.chain_check()
        self.assertIn("断裂", out)

    def test_chain_check_empty_ledger_is_ok(self):
        out = paper_trade.chain_check()
        self.assertIn("完整", out)
        self.assertIn("0", out)


class TestTradeAccounting(PaperTradeTestBase):
    def test_buy_applies_price_and_fee(self):
        r = paper_trade.do_trade("buy", "AAPL", 10, "test entry")
        self.assertTrue(r["ok"])
        p = paper_trade.load_port()
        # 10 shares @ $100 + $1 fee
        self.assertAlmostEqual(p["cash"], 100000.0 - 1000.0 - 1.0)
        self.assertEqual(p["positions"]["AAPL"]["shares"], 10)
        self.assertAlmostEqual(p["positions"]["AAPL"]["cost"], 1001.0)

    def test_sell_reduces_position_and_returns_cash(self):
        paper_trade.do_trade("buy", "AAPL", 10, "entry")
        r = paper_trade.do_trade("sell", "AAPL", 4, "trim")
        self.assertTrue(r["ok"])
        p = paper_trade.load_port()
        # proceeds 400 - fee 1 added back; avg cost basis reduced by avg*4
        self.assertAlmostEqual(p["cash"], 100000.0 - 1001.0 + 399.0)
        self.assertEqual(p["positions"]["AAPL"]["shares"], 6)
        self.assertAlmostEqual(p["positions"]["AAPL"]["cost"], 1001.0 * 0.6)

    def test_sell_all_removes_position(self):
        paper_trade.do_trade("buy", "TSM", 5, "entry")   # 5 * 200 + 1 = 1001
        r = paper_trade.do_trade("sell", "TSM", 5, "exit")
        self.assertTrue(r["ok"])
        self.assertNotIn("TSM", paper_trade.load_port()["positions"])

    def test_insufficient_cash_rejected_without_state_change(self):
        r = paper_trade.do_trade("buy", "TSM", 100000, "too big")
        self.assertFalse(r["ok"])
        self.assertIn("现金不足", r["error"])
        self.assertEqual(paper_trade.load_port()["cash"], 100000.0)
        self.assertEqual(self.read_trades(), [])  # no ledger entry written

    def test_no_quote_rejected(self):
        r = paper_trade.do_trade("buy", "NODATA", 1, "ghost ticker")
        self.assertFalse(r["ok"])
        self.assertIn("无行情", r["error"])
        self.assertEqual(self.read_trades(), [])

    def test_min_notional_rejected(self):
        r = paper_trade.do_trade("buy", "AAPL", 0, "tiny")  # 0 shares path first
        # 0 shares hits the positive-integer check; use 1 share @100 = 100 >= 20,
        # so exercise min-notional with a cheap fake quote instead.
        with mock.patch("prices.latest", side_effect=lambda sym: (0.5, "2026-08-20", False)):
            r = paper_trade.do_trade("buy", "AAPL", 10, "small")  # notional 5.0 < 20
        self.assertFalse(r["ok"])
        self.assertIn("最小", r["error"])

    def test_nonpositive_shares_rejected(self):
        r = paper_trade.do_trade("buy", "AAPL", 0, "zero")
        self.assertFalse(r["ok"])
        self.assertIn("正整数", r["error"])

    def test_sell_more_than_held_rejected(self):
        paper_trade.do_trade("buy", "AAPL", 2, "entry")
        r = paper_trade.do_trade("sell", "AAPL", 5, "over-sell")
        self.assertFalse(r["ok"])
        self.assertIn("持仓不足", r["error"])

    def test_every_trade_writes_one_ledger_line(self):
        paper_trade.do_trade("buy", "AAPL", 3, "a")
        paper_trade.do_trade("sell", "AAPL", 1, "b")
        rows = self.read_trades()
        self.assertEqual(len(rows), 2)
        self.assertEqual([x["action"] for x in rows], ["buy", "sell"])
        self.assertIn("reason", rows[0])
        self.assertIn("hash", rows[0])
        self.assertIn("prev", rows[1])


if __name__ == "__main__":
    unittest.main()
