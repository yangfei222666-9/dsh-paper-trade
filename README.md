# dsh-paper-trade

给 DeepSeek Harness 生态的**零依赖模拟盘工具**:虚拟 $100,000 本金,真实美股日线行情,每一笔交易进**哈希链防篡改账本**——练"下单前写理由、下单后留证据"的肌肉,永不碰真钱。

MIT · 纯 Python 标准库 · 作者:太极鲸 Taiji Whale

## 为什么需要它

DSH 生态里金融工具几乎是空白。多数人一上来就接真券商、烧真钱;这个工具把"证据化交易纪律"做成最小可运行系统:

- **只模拟**:无券商对接、无真实资金,红线写死在设计里;
- **哈希链账本**:每笔交易记录链接上一笔的哈希,`chain-check` 一条命令验证有没有被改过;
- **机器强制的纪律**:现金不足拒单、持仓不足拒单、**无行情拒单**、每笔 $1 虚拟佣金、最小 $20 名义金额;
- **零依赖**:Yahoo 日线免 key 直取(本地缓存兜底),无第三方库。

## 快速开始

```bash
git clone https://github.com/yangfei222666-9/dsh-paper-trade.git
cd dsh-paper-trade
python3 paper_trade.py status          # 初始 $100,000
python3 paper_trade.py quote AAPL      # 查行情
python3 paper_trade.py buy AAPL 10 "理由"   # 买入
python3 paper_trade.py sell AAPL 5 "理由"   # 卖出
python3 paper_trade.py report          # 快照留证
python3 paper_trade.py chain-check     # 账本完整性校验
```

## 命令一览

| 命令 | 作用 |
|---|---|
| `quote SYM` | 最新收盘价(Yahoo,失败走本地缓存) |
| `buy SYM 股数 理由` | 买入(现金校验+佣金) |
| `sell SYM 股数 理由` | 卖出(持仓校验) |
| `status` | 持仓+浮动盈亏 |
| `report` | 生成 JSON 快照(周复盘用) |
| `chain-check` | 哈希链完整性校验 |

## 设计红线(永不可改)

1. 只模拟,永不接真券商、永不代下真实订单;
2. 不承诺任何收益;
3. 数据缺失时拒绝成交,而不是猜一个价格;
4. 账本一旦建立,只有链式追加,没有改写。

## 文件

- `prices.py` — 行情引擎(Yahoo 日线 + CSV 缓存)
- `paper_trade.py` — 交易 CLI + 哈希链账本
- `paper_data.py` — 看板数据生成器
- `watchlist.json` — 观察清单示例

## 与 DSH 的关系

本工具独立于 DSH 运行(任何 Python 3.9+ 环境可用);它最初是 DSH 生态「太极鲸」管家系统的投资线组件,拆出开源以填补 DSH 金融工具空白。后续计划:DSH 插件化面板 + 策略回测层。

## 许可

MIT © Taiji Whale(太极鲸)
