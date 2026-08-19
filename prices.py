#!/usr/bin/env python3
# 模拟盘行情引擎 v2:Yahoo 日线为主(免key),Nasdaq 实时为辅,stdlib only,本地缓存
# 用法: python3 prices.py AAPL   → 打印最近日线
#        python3 prices.py AAPL 5 → 最近5日
import csv, io, json, os, sys, time, urllib.request, datetime

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices-cache")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")

def fetch_yahoo(sym, days="10d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={days}&interval=1d"
    d = json.loads(_get(url))
    r = d["chart"]["result"][0]
    ts = r.get("timestamp") or []
    closes = (r.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    rows = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        date = datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d")
        rows.append({"Date": date, "Close": f"{c:.4f}"})
    return rows

def load_rows(sym):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{sym}.csv")
    merged = {}
    if os.path.exists(path):
        with open(path) as f:
            for row in csv.DictReader(f):
                merged[row["Date"]] = row["Close"]
    try:
        for row in fetch_yahoo(sym):
            merged[row["Date"]] = row["Close"]
    except Exception:
        pass  # 拉取失败:用缓存兜底
    rows = [{"Date": d, "Close": merged[d]} for d in sorted(merged)]
    if rows:
        with open(path, "w") as f:
            w = csv.DictWriter(f, fieldnames=["Date", "Close"])
            w.writeheader()
            w.writerows(rows)
    return rows

def latest(sym):
    rows = load_rows(sym)
    if not rows:
        return None, None, True
    return float(rows[-1]["Close"]), rows[-1]["Date"], False

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rows = load_rows(sym)
    if not rows:
        print(f"{sym}: 无行情数据")
        sys.exit(1)
    for r in rows[-n:]:
        print(r["Date"], "close=", r["Close"])
