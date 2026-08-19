#!/usr/bin/env python3
# 模拟盘交易 CLI v1:虚拟 10 万刀,全记账、哈希链防篡改、零真钱、绝不接真券商
# 用法:
#   python3 paper_trade.py quote AAPL
#   python3 paper_trade.py buy AAPL 10 "理由"
#   python3 paper_trade.py sell AAPL 5 "理由"
#   python3 paper_trade.py status
#   python3 paper_trade.py report          # 周报快照(留证)
#   python3 paper_trade.py chain-check     # 校验回执链完整性
import hashlib, json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = os.path.join(BASE, "portfolio.json")
TRADES = os.path.join(BASE, "trades.jsonl")
SNAP = os.path.join(BASE, "snapshots")
sys.path.insert(0, BASE)
import prices
import paper_data

FEE = 1.0          # 虚拟佣金,每笔 1 刀(模拟真实摩擦)
MIN_NOTIONAL = 20  # 最小名义金额,防碎单

def load_port():
    if not os.path.exists(PORT):
        return {"cash": 100000.0, "positions": {}, "chain": ""}
    return json.load(open(PORT))

def save_port(p):
    json.dump(p, open(PORT, "w"), indent=2, ensure_ascii=False)

def chain_append(record):
    p = load_port()
    prev = p["chain"] or ""
    record["prev"] = prev[:16]
    body = json.dumps(record, sort_keys=True, ensure_ascii=False)
    record["hash"] = hashlib.sha1(body.encode()).hexdigest()[:16]
    p["chain"] = record["hash"]
    save_port(p)
    with open(TRADES, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record["hash"]

def do_trade(action, sym, shares, reason):
    sym = sym.upper()
    shares = int(shares)
    if shares <= 0:
        return {"ok": False, "error": "股数必须为正整数"}
    px, date, stale = prices.latest(sym)
    if px is None:
        return {"ok": False, "error": f"{sym} 无行情,拒绝成交(数据缺失不开单)"}
    notional = px * shares
    if notional < MIN_NOTIONAL:
        return {"ok": False, "error": f"名义金额 ${notional:.2f} 小于最小 ${MIN_NOTIONAL},拒绝"}
    p = load_port()
    if action == "buy":
        cost = notional + FEE
        if cost > p["cash"]:
            return {"ok": False, "error": f"现金不足:需 ${cost:.2f},仅有 ${p['cash']:.2f}"}
        p["cash"] -= cost
        pos = p["positions"].get(sym, {"shares": 0, "cost": 0.0})
        pos["cost"] += cost
        pos["shares"] += shares
        p["positions"][sym] = pos
    else:
        pos = p["positions"].get(sym, {"shares": 0, "cost": 0.0})
        if pos["shares"] < shares:
            return {"ok": False, "error": f"{sym} 持仓不足:{pos['shares']} < {shares}"}
        avg = pos["cost"] / pos["shares"]
        pos["shares"] -= shares
        pos["cost"] -= avg * shares
        if pos["shares"] == 0:
            del p["positions"][sym]
        p["cash"] += notional - FEE
    save_port(p)
    h = chain_append({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action,
                      "ticker": sym, "shares": shares, "price": px, "px_date": date,
                      "fee": FEE, "reason": reason, "stale": stale})
    paper_data.refresh()
    return {"ok": True, "hash": h, "price": px, "date": date,
            "cash_left": round(p["cash"], 2)}

def status():
    p = load_port()
    lines = [f"现金:${p['cash']:,.2f}"]
    total_mv = p["cash"]
    for sym, pos in sorted(p["positions"].items()):
        px, date, _ = prices.latest(sym)
        if px is None:
            lines.append(f"{sym}: {pos['shares']} 股(无行情)")
            continue
        mv = px * pos["shares"]
        pnl = mv - pos["cost"]
        total_mv += mv
        lines.append(f"{sym}: {pos['shares']} 股 @ 成本${pos['cost']/pos['shares']:.2f} | 现价 ${px:.2f}({date}) | 浮动 ${pnl:+,.2f}")
    lines.append(f"总资产:${total_mv:,.2f} (起始 $100,000 | 累计 {total_mv-100000:+,.2f})")
    return "\n".join(lines)

def report():
    os.makedirs(SNAP, exist_ok=True)
    p = load_port()
    px_map = {}
    total_mv = p["cash"]
    for sym, pos in p["positions"].items():
        px, date, _ = prices.latest(sym)
        px_map[sym] = px
        if px is not None:
            total_mv += px * pos["shares"]
    snap = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cash": p["cash"],
            "positions": p["positions"], "prices": px_map, "total": total_mv,
            "pnl": total_mv - 100000.0, "chain": p["chain"]}
    fn = os.path.join(SNAP, time.strftime("%Y%m%d-%H%M%S") + "-report.json")
    json.dump(snap, open(fn, "w"), indent=2, ensure_ascii=False)
    return f"快照已留证:{fn}\n{status()}"

def chain_check():
    rows = [json.loads(l) for l in open(TRADES) if l.strip()] if os.path.exists(TRADES) else []
    prev = ""
    for r in rows:
        body = json.dumps({k: v for k, v in r.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
        if hashlib.sha1(body.encode()).hexdigest()[:16] != r.get("hash"):
            return f"❌ 回执链在 {r.get('ts')} 处断裂!"
        prev = r["hash"]
    return f"✅ 回执链完整:{len(rows)} 笔交易,末链 {prev[:16]}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "quote":
        sym = sys.argv[2].upper() if len(sys.argv) > 2 else "AAPL"
        px, date, stale = prices.latest(sym)
        print(f"{sym}: {date} close ${px}" + ("(缓存,拉取失败)" if stale else ""))
    elif cmd in ("buy", "sell"):
        if len(sys.argv) < 4:
            print("用法: buy/sell <代码> <股数> [理由]")
            sys.exit(1)
        r = do_trade(cmd, sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]) or "-")
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif cmd == "status":
        print(status())
    elif cmd == "report":
        print(report())
    elif cmd == "chain-check":
        print(chain_check())
    else:
        print(__doc__)
