#!/usr/bin/env python3
# 模拟盘看板数据生成器:portfolio+行情+交易+链状态 → dashboard/paper-data.json(voice-page 静态引用一份)
import hashlib, json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))          # finance/paper
sys.path.insert(0, BASE)
import prices

PORT = os.path.join(BASE, "portfolio.json")
TRADES = os.path.join(BASE, "trades.jsonl")
OUT = os.path.join(BASE, "dashboard", "paper-data.json")

def refresh():
    p = json.load(open(PORT))
    positions = []
    total = p["cash"]
    for sym in sorted(p["positions"]):
        pos = p["positions"][sym]
        px, date, _ = prices.latest(sym)
        mv = (px * pos["shares"]) if px is not None else None
        avg = pos["cost"] / pos["shares"] if pos["shares"] else 0
        if mv is not None:
            total += mv
        positions.append({
            "sym": sym, "shares": pos["shares"], "avg": round(avg, 2),
            "px": px, "date": date,
            "mv": round(mv, 2) if mv is not None else None,
            "pnl": round(mv - pos["cost"], 2) if mv is not None else None})
    trades = []
    if os.path.exists(TRADES):
        rows = [json.loads(l) for l in open(TRADES) if l.strip()]
        for r in rows[-10:]:
            trades.append({"ts": r["ts"], "action": r["action"], "sym": r["ticker"],
                           "shares": r["shares"], "px": r["price"], "reason": (r.get("reason") or "-")[:24]})
    chain_ok = True
    if trades:
        prev = ""
        ok = True
        for r in [json.loads(l) for l in open(TRADES) if l.strip()]:
            body = json.dumps({k: v for k, v in r.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
            if hashlib.sha1(body.encode()).hexdigest()[:16] != r.get("hash"):
                ok = False
                break
        chain_ok = ok
    watch = []
    try:
        wl = json.load(open(os.path.join(BASE, "watchlist.json")))
        for it in wl.get("items", []):
            px, date, _ = prices.latest(it["sym"])
            watch.append({"sym": it["sym"], "note": it.get("note", ""), "px": px, "date": date})
    except Exception:
        pass
    data = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cash": round(p["cash"], 2),
            "total": round(total, 2), "pnl": round(total - 100000.0, 2),
            "positions": positions, "watchlist": watch, "trades": trades, "chain_ok": chain_ok,
            "n_trades": sum(1 for _ in open(TRADES)) if os.path.exists(TRADES) else 0}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), ensure_ascii=False)
    return data
