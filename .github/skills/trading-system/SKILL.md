---
name: trading-system
description: "交易数据系统 — 数据获取协议、操作配置、工作流、信号评估。任何需要获取市场数据、执行分析、管理持仓文件的操作必须加载。必须同时加载 livermore-trading 和 livermore-pivotal-points。"
---

# 交易系统 — 数据与执行

<MANDATORY-LOADING>
**本文是利弗莫尔三文件系统的一部分。如果你只读了本文，还需要同时读取：**
1. [livermore-trading/SKILL.md](../livermore-trading/SKILL.md) — 大脑（哲学、铁律、做多做空框架）
2. [livermore-pivotal-points/SKILL.md](../livermore-pivotal-points/SKILL.md) — 关键点（识别、强度、结构速查）

**三个文件必须全部加载后才能开始任何交易判断。**
</MANDATORY-LOADING>

> 利弗莫尔的大脑需要数据。这个系统负责把正确的数据送到大脑面前。

**大脑：** [livermore-trading](../livermore-trading/SKILL.md)（哲学、判断、铁律）
**关键点深度：** [livermore-pivotal-points](../livermore-pivotal-points/SKILL.md)

---

## 数据获取协议

> 利弗莫尔随身携带手写价格记录本，记录几个月甚至几年的价格。他从不凭"印象"判断。AI 必须做同样的事。

### 分析任何股票前，必须获取（缺一不可）

| 数据层 | 内容 | 数据源 |
|--------|------|--------|
| **当日快照** | OHLCV | `cli.py quote {ticker}` |
| **历史价格** | 6-12 月日线 | `cli.py sync {ticker}` → 本地 `data/history/{TICKER}.csv` |
| **关键位坐标** | 52周/3月/1月高低 | `cli.py levels {ticker}` |
| **量价结构** | 上涨日均量 vs 下跌日均量 + 巨量日 | `cli.py volume {ticker}` |
| **摆动高低点** | 收盘价摆动点 + 量比 | `cli.py swings {ticker}` |
| **价格区间** | 同一价位被反复触碰形成的聚集区 | `cli.py zones {ticker}` |
| **摆动序列** | HH/HL/LH/LL 客观记录 | `cli.py sequence {ticker}` |
| **相邻结构** | 低-高-低 / 高-低-高时间叙事 | `cli.py structures {ticker}` |
| **缺口** | 跳空位置 + 回填状态 | `cli.py gaps {ticker}` |
| **姐妹股** | 同板块 3-5 只当日表现 | `cli.py sisters {ticker}` |
| **大盘** | SPY/QQQ + 板块排行 | `cli.py market` / `cli.py sectors` |
| **板块领头羊** | 领涨板块内涨幅前5个股 | `cli.py leaders` / `cli.py leaders {ETF}` |
| **全市场涨跌幅** | 所有板块持仓个股涨跌排名 | `cli.py movers` / `cli.py movers 1mo` |
| **板块多周期强度** | 1d/5d/1mo涨幅+趋势标签 | `cli.py trend` |
| **完整分析** | 以上全部一键获取 | `cli.py analyze {ticker}` |

**历史数据是核心。** 只有52周高低两个数字 = 只知首尾不知中间。必须看到：
- 上升趋势？下降趋势？横盘蓄势？
- 几次关键回调/反弹？幅度多大？在哪企稳？

### 触发词 → 数据需求

| 触发词 | 必须获取 |
|--------|---------|
| 今日分析 | 大盘 + 板块排行 + 板块强度趋势 + 持仓最新价 + 持仓近期历史 |
| 利弗莫尔怎么看 | 领涨领跌板块 + 板块领头羊 + 持仓结构 + 持仓历史（≥3月） |
| 看看 {ticker} | 该股历史（6-12月）+ 当日量价 + 姐妹股对比 |
| 仓位 | portfolio.md + 持仓实时价更新 |
| 分析市场 | 涨跌幅前20 + 板块热力图 + 板块强度趋势 + 大盘量能 + 领涨股历史 + **领跌板块跌落羊** |
| 板块领头羊 | 领涨板块内涨幅前5个股 + 各股历史关键点 |
| 做空机会 | 领跌板块 + 板块内跌幅最大个股 + 各股历史关键点 + 做空可行性 |
| 买入 / 卖出 / 做空 | → 大脑执行三问仪式 → 记录到 trades.md |
| watchlist | → 更新 portfolio.md 关注列表（含做多/做空标注）|
| 复盘 | → 大脑回顾交易 |
| 心法 / 状态 | → 大脑评估心法等级 |

---

## 两层架构

> 纯数据，零判断 — 代码只描述“价格做了什么”，AI 决定“意味着什么”

```
数据源 (market_data.py) → 数据处理 (analysis.py) → AI + SKILL (一切判断)
```

| 层 | 文件 | 职责 | 不做什么 |
|------|------|------|----------|
| **数据源** | market_data.py | 获取原始数据（yfinance、本地CSV、缓存） | 不分析、不判断 |
| **数据处理** | analysis.py | 摆动点、价格区间、相邻结构、缺口、摆动序列、量价多窗口、仓位计算（纯数学） | 不贴标签、不发信号 |
| **判断** | AI + SKILL.md | 突破判断、趋势识别、强弱评估、止损选择、买卖决策 | 不编造数字 |

> 代码负责“看到什么”，AI 负责“意味着什么”。

```yaml
data: src/market_data.py     # 数据源
processing: src/analysis.py  # 数据处理（纯数据 + 仓位计算）
cli: src/cli.py              # 命令行入口
storage:
  history: data/history/{TICKER}.csv  # 本地日线，增量同步
  cache: data/cache/{TICKER}_info.json  # 元数据缓存，7天有效
markets:
  US: yfinance (09:30-16:00 ET)
  CN: xueqiu.com / eastmoney.com (09:30-15:00 CST)  # 待实现
```

---

## 操作配置

```yaml
style: swing_trading  # 数周-数月
capital: <$100K
max_positions: 3-5
single_max: 25%
initial: 10-20%  # 试探仓
stop: pivotal_point (下方 1-2% 缓冲)
trailing: pivotal (跟随延续关键点上移)
```

---

## 每日工作流

1. **大市等级** A/B/C/D + 阻力最小路径 → 用大脑判断
2. **板块轮动** 领涨领跌 + 板块多周期强度（`trend`） + 领头羊识别（`leaders`） + 姐妹股验证
3. **持仓分析** 价格 vs 关键位 + 趋势 + 量能 + 自然回调 or 危险信号 → 操作建议
4. **Watchlist 扫描** → 见下方流程
5. **名言** 与当前状态匹配

---

## Watchlist 扫描

### AI 每日扫描（板块轮动时自动执行）

**做多扫描（大市A/B级）：**
1. 识别当日领涨 2-3 个板块（`trend` 命令确认是新领涨还是持续强势）
2. 每板块取本轮涨幅前 2（`leaders` 命令）→ 领头羊筛选（标准见[大脑](../livermore-trading/SKILL.md)）
3. 候选股获取 6-12 月历史 → 识别关键点（见[关键点 SKILL](../livermore-pivotal-points/SKILL.md)）
4. 有关键点 + 距离 <10% → 加入 watchlist（做多）

**做空扫描（大市C级恶化/D级）：**
1. 识别当日领跌 2-3 个板块（`trend` 命令确认是持续弱势❄️还是短期回调）
2. 每板块取本轮跌幅最大 2 只 → 跌落羊筛选（标准见[大脑](../livermore-trading/SKILL.md)）
3. 候选股获取 6-12 月历史 → 识别下方关键点
4. 有关键点 + 距离 <10% + 市值>$20亿 → 加入 watchlist（做空）

### 用户提名

用户说「看看 XXX」→ 执行完整分析 → 结论：加入 watchlist / 不符合标准 + 原因

### 生命周期

| 阶段 | 触发 |
|------|------|
| **入选** | 关键点已识别 + 距离合理 + 板块/个股条件满足 |
| **跟踪** | 每日更新：价格、距关键点距离、量能状态 |
| **升级 → 交易** | 关键点突破 + 放量 + 三问通过 → 记录到 [trades.md](../livermore-trading/trades.md) |
| **移除** | 关键点失效 / 板块转弱 / 更强领头羊出现 |

> Watchlist 展示在 [portfolio.md](../livermore-trading/portfolio.md)，入选/移除判断标准见[大脑](../livermore-trading/SKILL.md)

---

## 信号评估

**做多条件：** 大盘趋势上 + 板块领涨 + 领头羊 + 突破关键位 + 放量 + 回踩不破

**做空条件：** 大盘趋势下（D级）或恶化中（C→D） + 板块领跌 + 跌落羊 + 跌破关键位 + 放量 + 反弹不过

**信号强度：** ⭐⭐⭐⭐⭐ 多条件共振 → ⭐⭐⭐⭐ 主要满足 → ⭐⭐⭐ 部分满足 → ⭐⭐以下不行动

> 做多和做空使用相同的信号强度标准。方向不同，纪律相同。

---

## 复盘流程

### 单笔复盘（平仓当天）

填写 [trades.md](../livermore-trading/trades.md) 出场复盘模板（入场/持有/出场三阶段审视）

### 周复盘（每周末，用户说「复盘」或 AI 主动提醒）

1. **统计更新** — 胜率、盈亏比、平均持仓天数、本周盈亏
2. **交易审视** — 本周所有操作（入场/加仓/止损/移动止损）是否符合铁律
3. **Watchlist 清理** — 移除失效标的，标记新机会
4. **心法打分** — 本周计划外交易？情绪化操作？止损犹豫？→ 更新 [portfolio.md](../livermore-trading/portfolio.md) 心法等级
5. **下周准备** — 持仓关键位 + watchlist 中最接近触发的标的

### 月复盘（每月末）

1. **绩效统计**

| 指标 | 本月 | 累计 |
|------|------|------|
| 胜率 | | |
| 平均盈亏比 | | |
| 最大单笔盈利/亏损 | | |
| 平均持仓天数 | | |
| 计划外交易 | | |
| 资金曲线 vs 基准(SPY) | | |

2. **模式识别** — 赚钱的交易有什么共同点？亏钱的呢？
3. **铁律遵守率** — 逐条过六大铁律，哪条违反最多？
4. **心法等级评估** — 达到升级门槛了吗？→ 更新 [portfolio.md](../livermore-trading/portfolio.md)
5. **系统调整** — 有没有需要修正的规则？（谨慎，不因一两笔改规则）

> 复盘触发词：「复盘」「本周回顾」「月度总结」→ AI 执行对应流程

---

## 文件系统

| 文件 | 角色 |
|------|------|
| [livermore-trading](../livermore-trading/SKILL.md) | 🧠 大脑：哲学、判断框架、铁律 |
| [livermore-pivotal-points](../livermore-pivotal-points/SKILL.md) | 🎯 关键点：识别、强度、思考框架、常见错误 |
| **本文** | 📡 数据源：数据获取、操作配置、工作流 |
| [portfolio.md](../livermore-trading/portfolio.md) | 📊 仪表盘：账户、持仓、风险 |
| [trades.md](../livermore-trading/trades.md) | 📝 交易日志：入场逻辑、过程、出场复盘 |
