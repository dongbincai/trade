"""
利弗莫尔交易系统 — 数据引擎

职责：把正确的数据送到利弗莫尔大脑面前。
架构：
  - 本地存储：历史日线 OHLCV (data/history/{TICKER}.csv)，每日增量同步
  - 本地缓存：股票元数据/板块分类 (data/cache/)，每周更新
  - 实时 API：当日报价、板块排行，按需获取
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

# ──────────────────────────────────────────
# 时区
# ──────────────────────────────────────────
_ET = ZoneInfo("America/New_York")


def _us_market_date() -> datetime.date.__class__:
    """当前美东日期。用于判断"今天的交易日"是否已收盘。"""
    return datetime.now(_ET).date()


def _is_market_closed() -> bool:
    """美股是否已收盘（16:00 ET 后 + 30 分钟数据结算缓冲）。"""
    now_et = datetime.now(_ET)
    # 周末
    if now_et.weekday() >= 5:
        return True
    # 16:30 ET 后视为已收盘（给 30 分钟数据结算）
    return now_et.hour > 16 or (now_et.hour == 16 and now_et.minute >= 30)

# ──────────────────────────────────────────
# 路径
# ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
CACHE_DIR = DATA_DIR / "cache"

for d in [HISTORY_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────
# 1. 历史数据（本地存储 + 增量同步）
# ──────────────────────────────────────────

def sync_history(ticker: str, months: int = 36) -> pd.DataFrame:
    """
    同步历史日线数据。本地有则增量追加，无则全量拉取。
    **只保留已收盘的完整交易日。** 当天盘中数据不写入 CSV。
    返回完整 DataFrame (Date, Open, High, Low, Close, Volume)。
    """
    path = HISTORY_DIR / f"{ticker.upper()}.csv"
    today = datetime.now().date()
    us_today = _us_market_date()

    if path.exists():
        df = pd.read_csv(path, parse_dates=["Date"])
        last_date = df["Date"].max().date()

        # 修复：如果 CSV 最后一行是今天的美股交易日且盘未收，
        # 说明之前写入了未收盘数据，删掉它。
        if last_date >= us_today and not _is_market_closed():
            df = df[df["Date"].dt.date < us_today].reset_index(drop=True)
            df.to_csv(path, index=False)
            last_date = df["Date"].max().date() if not df.empty else today - timedelta(days=365)

        # 如果已收盘且 CSV 已含今天数据，无需更新
        if last_date >= us_today and _is_market_closed():
            return df
        # 如果数据已经是昨天且盘还没收，也无需更新（等收盘再写）
        if last_date >= us_today - timedelta(days=1) and not _is_market_closed():
            return df

        # 增量：从 last_date + 1 天开始
        start = last_date + timedelta(days=1)
        end = today + timedelta(days=1)  # yfinance end 是 exclusive
        new = _fetch_history(ticker, start=start.isoformat(), end=end.isoformat())
        if new is not None and not new.empty:
            # 丢弃当前交易日的未收盘数据
            if not _is_market_closed():
                new = new[new["Date"].dt.date < us_today]
            df = pd.concat([df, new], ignore_index=True).drop_duplicates(subset=["Date"])
            df = df.sort_values("Date").reset_index(drop=True)
            df.to_csv(path, index=False)
        return df
    else:
        # 全量拉取
        start = (today - timedelta(days=months * 30)).isoformat()
        end = (today + timedelta(days=1)).isoformat()
        df = _fetch_history(ticker, start=start, end=end)
        if df is not None and not df.empty:
            # 丢弃当前交易日的未收盘数据
            if not _is_market_closed():
                df = df[df["Date"].dt.date < us_today]
            if not df.empty:
                df.to_csv(path, index=False)
            return df
        return pd.DataFrame()


def _fetch_history(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    """从 yfinance 拉取日线数据，标准化列名。"""
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start, end=end, auto_adjust=True)
        if df.empty:
            return None
        df = df.reset_index()
        df = df.rename(columns={"index": "Date"})
        # 确保 Date 列存在且标准化
        if "Date" not in df.columns and "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        # 只保留需要的列
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in cols if c in df.columns]]
        return df
    except Exception as e:
        print(f"[ERROR] 获取 {ticker} 历史数据失败: {e}")
        return None


# ──────────────────────────────────────────
# 2. 实时报价（带缓存）
# ──────────────────────────────────────────

# 报价缓存：同一分析会话内，多个函数调用只打一次 API。
# TTL 30 秒 — 足够一次完整分析，不会拿到过期数据。
_quote_cache: dict[str, tuple[float, dict]] = {}  # ticker -> (timestamp, data)
_QUOTE_TTL = 30  # 秒


def _get_cached_quote(ticker: str) -> dict | None:
    """返回缓存中未过期的报价，或 None。"""
    key = ticker.upper()
    if key in _quote_cache:
        ts, data = _quote_cache[key]
        if (datetime.now().timestamp() - ts) < _QUOTE_TTL:
            return data
    return None


def invalidate_quote_cache(ticker: str | None = None):
    """手动清除报价缓存。传 None 清全部。"""
    if ticker is None:
        _quote_cache.clear()
    else:
        _quote_cache.pop(ticker.upper(), None)


def get_quote(ticker: str, use_cache: bool = True) -> dict:
    """
    获取当前报价快照。
    use_cache=True 时 30 秒内重复调用返回缓存值（默认）。
    """
    key = ticker.upper()

    if use_cache:
        cached = _get_cached_quote(key)
        if cached:
            return cached

    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        volume = int(info.last_volume) if info.last_volume else None

        # 量比：今日量 / 近20日均量（需要历史数据）
        vol_ratio = None
        if volume:
            path = HISTORY_DIR / f"{ticker.upper()}.csv"
            if path.exists():
                df = pd.read_csv(path)
                if len(df) >= 20:
                    avg_vol = df["Volume"].tail(20).mean()
                    if avg_vol > 0:
                        vol_ratio = round(volume / avg_vol, 2)

        result = {
            "ticker": key,
            "price": round(info.last_price, 2) if info.last_price else None,
            "open": round(info.open, 2) if info.open else None,
            "high": round(info.day_high, 2) if info.day_high else None,
            "low": round(info.day_low, 2) if info.day_low else None,
            "volume": volume,
            "vol_ratio": vol_ratio,  # 量比：>1.5 放量, <0.5 缩量
            "prev_close": round(info.previous_close, 2) if info.previous_close else None,
            "market_cap": info.market_cap if info.market_cap else None,
            "change_pct": round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            ) if info.last_price and info.previous_close else None,
        }
        # 写入缓存
        _quote_cache[key] = (datetime.now().timestamp(), result)
        return result
    except Exception as e:
        print(f"[ERROR] 获取 {ticker} 报价失败: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}


def get_quotes(tickers: list[str]) -> list[dict]:
    """批量获取报价。"""
    return [get_quote(t) for t in tickers]


# ──────────────────────────────────────────
# 2b. 实时 K 线 + 完整历史
# ──────────────────────────────────────────

def get_live_bar(ticker: str) -> dict | None:
    """
    用实时 API 构建当前交易日的 K 线。
    如果美股已收盘，返回 None（当天数据应在 sync_history 中）。
    """
    q = get_quote(ticker)
    if not q or "error" in q:
        return None
    if q["open"] is None:
        return None
    return {
        "date": _us_market_date().isoformat(),
        "open": q["open"],
        "high": q["high"],
        "low": q["low"],
        "close": q["price"],  # 最新价即实时收盘
        "volume": q["volume"],
        "is_live": True,
    }


def get_full_history(ticker: str) -> pd.DataFrame:
    """
    已收盘历史 + 当日实时 K 线。分析函数应使用此接口。

    规则：
      - sync_history() 只含已收盘的完整日线
      - 如果盘中，追加 get_live_bar() 作为当天的行
      - 如果已收盘，sync_history 已包含当天，不重复追加
    """
    df = sync_history(ticker)
    # 如果盘中（未收盘），追加实时 bar
    if not _is_market_closed():
        bar = get_live_bar(ticker)
        if bar:
            live_date = pd.Timestamp(bar["date"])
            # 确保不重复
            if df.empty or live_date not in df["Date"].values:
                live_row = pd.DataFrame([{
                    "Date": live_date,
                    "Open": bar["open"],
                    "High": bar["high"],
                    "Low": bar["low"],
                    "Close": bar["close"],
                    "Volume": bar["volume"],
                }])
                df = pd.concat([df, live_row], ignore_index=True)
    return df


# ──────────────────────────────────────────
# 3. 股票元数据（本地缓存）
# ──────────────────────────────────────────

def get_stock_info(ticker: str, force_refresh: bool = False) -> dict:
    """获取股票基本信息（板块、行业、市值等），缓存到本地。"""
    cache_path = CACHE_DIR / f"{ticker.upper()}_info.json"

    if cache_path.exists() and not force_refresh:
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        if age < 7 * 86400:  # 7 天内有效
            with open(cache_path) as f:
                return json.load(f)

    try:
        t = yf.Ticker(ticker)
        info = t.info
        result = {
            "ticker": ticker.upper(),
            "name": info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap", 0),
            "exchange": info.get("exchange", ""),
            "updated": datetime.now().isoformat(),
        }
        with open(cache_path, "w") as f:
            json.dump(result, f, indent=2)
        return result
    except Exception as e:
        print(f"[ERROR] 获取 {ticker} 信息失败: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}


# ──────────────────────────────────────────
# 4. 板块/大盘分析
# ──────────────────────────────────────────

# 主要板块 ETF — 用于板块轮动扫描
SECTOR_ETFS = {
    "XLK": "科技",
    "XLF": "金融",
    "XLE": "能源",
    "XLV": "医疗",
    "XLI": "工业",
    "XLY": "消费",
    "XLP": "必需消费",
    "XLU": "公用事业",
    "XLB": "材料",
    "XLRE": "地产",
    "XLC": "通信",
}


def get_sector_performance() -> list[dict]:
    """获取板块 ETF 当日表现，按涨跌幅排序。"""
    results = []
    for etf, name in SECTOR_ETFS.items():
        q = get_quote(etf)
        if "error" not in q:
            results.append({
                "etf": etf,
                "sector": name,
                "change_pct": q.get("change_pct", 0),
                "volume": q.get("volume", 0),
            })
    results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    return results


def get_market_overview() -> dict:
    """大盘概览：SPY + QQQ + 板块排行。"""
    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    sectors = get_sector_performance()
    return {
        "spy": spy,
        "qqq": qqq,
        "sectors": sectors,
        "leading": sectors[:3] if sectors else [],
        "lagging": sectors[-3:] if sectors else [],
    }


def get_etf_holdings(etf: str, top_n: int = 15) -> list[str]:
    """获取 ETF 的前 N 大持仓 ticker。"""
    try:
        t = yf.Ticker(etf)
        holdings = t.funds_data.top_holdings
        if holdings is None or holdings.empty:
            return []
        tickers = holdings.index.tolist()[:top_n]
        return tickers
    except Exception as e:
        print(f"[ERROR] 获取 {etf} 持仓失败: {e}")
        return []


def get_sector_leaders(etf: str = None, top_n: int = 5, period: str = "1mo") -> list[dict]:
    """
    获取板块内领涨个股。

    参数:
        etf: 板块 ETF（如 'XLK'），为 None 时自动取当日领涨前 3 板块
        top_n: 每个板块返回前 N 只领涨股
        period: 计算涨幅的时间窗口（'5d' / '1mo' / '3mo'）

    返回:
        [{"sector": "科技", "etf": "XLK", "leaders": [
            {"ticker": "NVDA", "name": "...", "change_pct": 12.5, "price": 130.5, "holding_pct": 0.15},
            ...
        ]}, ...]
    """
    if etf:
        etfs_to_scan = [(etf.upper(), SECTOR_ETFS.get(etf.upper(), etf.upper()))]
    else:
        # 自动取领涨前 3 板块
        sectors = get_sector_performance()
        etfs_to_scan = [(s["etf"], s["sector"]) for s in sectors[:3]]

    results = []
    for etf_ticker, sector_name in etfs_to_scan:
        holdings = get_etf_holdings(etf_ticker)
        if not holdings:
            results.append({"sector": sector_name, "etf": etf_ticker, "leaders": [], "error": "无法获取持仓"})
            continue

        # 批量获取近期价格
        try:
            data = yf.download(holdings, period=period, progress=False, threads=True)
            if data.empty:
                continue
            close = data["Close"] if len(holdings) > 1 else data[["Close"]].rename(columns={"Close": holdings[0]})
            first = close.iloc[0]
            last = close.iloc[-1]
            chg = ((last - first) / first * 100).dropna().sort_values(ascending=False)

            leaders = []
            for ticker in chg.index[:top_n]:
                leaders.append({
                    "ticker": ticker,
                    "price": round(float(last[ticker]), 2),
                    "change_pct": round(float(chg[ticker]), 2),
                    "period": period,
                })
            results.append({"sector": sector_name, "etf": etf_ticker, "leaders": leaders})
        except Exception as e:
            print(f"[ERROR] 板块 {etf_ticker} 领涨计算失败: {e}")
            results.append({"sector": sector_name, "etf": etf_ticker, "leaders": [], "error": str(e)})

    return results


def get_top_movers(top_n: int = 20, period: str = "1d") -> dict:
    """
    全市场涨跌幅筛选 — 从所有板块 ETF 持仓中汇总。

    参数:
        top_n: 返回前/后 N 只
        period: '1d' 当日, '5d' 一周, '1mo' 一月

    返回:
        {"gainers": [...], "losers": [...]}
    """
    # 收集所有板块 ETF 的持仓
    all_tickers = set()
    for etf in SECTOR_ETFS:
        holdings = get_etf_holdings(etf, top_n=10)
        all_tickers.update(holdings)

    if not all_tickers:
        return {"gainers": [], "losers": []}

    all_tickers = list(all_tickers)
    try:
        # '1d' period 只返回 1 行无法计算涨跌幅，改用 '2d' 取前后两天对比
        dl_period = "2d" if period == "1d" else period
        data = yf.download(all_tickers, period=dl_period, progress=False, threads=True)
        if data.empty:
            return {"gainers": [], "losers": []}

        close = data["Close"]
        if len(close) < 2:
            return {"gainers": [], "losers": []}

        first = close.iloc[0]
        last = close.iloc[-1]
        chg = ((last - first) / first * 100).dropna().sort_values(ascending=False)

        def _build_list(tickers):
            result = []
            for t in tickers:
                result.append({
                    "ticker": t,
                    "price": round(float(last[t]), 2),
                    "change_pct": round(float(chg[t]), 2),
                    "period": period,
                })
            return result

        return {
            "gainers": _build_list(chg.index[:top_n]),
            "losers": _build_list(chg.index[-top_n:][::-1]),
        }
    except Exception as e:
        print(f"[ERROR] 全市场筛选失败: {e}")
        return {"gainers": [], "losers": [], "error": str(e)}


def get_sector_history(days: int = 30) -> list[dict]:
    """
    板块历史强度 — 各板块 ETF 多时间窗口涨跌幅，判断新领涨 vs 老强势。

    返回每个板块的 1d / 5d / 1mo 涨幅，按1月涨幅排序。
    """
    etf_list = list(SECTOR_ETFS.keys())
    try:
        data = yf.download(etf_list, period=f"{days + 5}d", progress=False, threads=True)
        if data.empty:
            return []

        close = data["Close"]
        results = []
        for etf in etf_list:
            if etf not in close.columns:
                continue
            col = close[etf].dropna()
            if len(col) < 2:
                continue

            last_price = col.iloc[-1]
            chg_1d = _safe_pct(col, 1)
            chg_5d = _safe_pct(col, 5)
            chg_1mo = _safe_pct(col, 21)

            # 判断趋势标签
            if chg_1mo is not None and chg_5d is not None:
                if chg_1mo > 3 and chg_5d > 1:
                    trend = "🔥 持续强势"
                elif chg_1mo < -3 and chg_5d > 2:
                    trend = "🔄 反弹中"
                elif chg_1mo > 3 and chg_5d < -1:
                    trend = "⚠️ 回调中"
                elif chg_5d > 2 and (chg_1mo is None or abs(chg_1mo) < 3):
                    trend = "🆕 新领涨"
                elif chg_1mo < -3 and chg_5d < -1:
                    trend = "❄️ 持续弱势"
                else:
                    trend = "➡️ 震荡"
            else:
                trend = "➡️ 数据不足"

            results.append({
                "etf": etf,
                "sector": SECTOR_ETFS[etf],
                "price": round(float(last_price), 2),
                "chg_1d": chg_1d,
                "chg_5d": chg_5d,
                "chg_1mo": chg_1mo,
                "trend": trend,
            })

        # 按 1 月涨幅降序
        results.sort(key=lambda x: x.get("chg_1mo") or 0, reverse=True)
        return results
    except Exception as e:
        print(f"[ERROR] 板块历史强度获取失败: {e}")
        return []


def _safe_pct(series: pd.Series, lookback: int) -> float | None:
    """安全计算 N 日涨跌幅。"""
    if len(series) <= lookback:
        return None
    old = series.iloc[-(lookback + 1)]
    new = series.iloc[-1]
    if old == 0:
        return None
    return round(float((new - old) / old * 100), 2)


# ──────────────────────────────────────────
# 5. 姐妹股发现
# ──────────────────────────────────────────

# 常见板块成员映射（可扩展）
SECTOR_MEMBERS = {
    "自动驾驶": ["PONY", "WRD", "TSLA", "GOOGL", "GM", "MBLY"],
    "AI/半导体": ["NVDA", "AMD", "AVGO", "TSM", "INTC", "QCOM"],
    "中概": ["BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI"],
    "能源": ["XOM", "CVX", "COP", "OXY", "SLB", "EOG"],
    "金融": ["JPM", "BAC", "GS", "MS", "WFC", "C"],
}


def find_sisters(ticker: str) -> list[str]:
    """找到同板块姐妹股。先查本地映射，再查 yfinance 行业。"""
    ticker = ticker.upper()
    # 先查本地映射
    for sector, members in SECTOR_MEMBERS.items():
        if ticker in members:
            return [m for m in members if m != ticker]

    # 再查 yfinance 行业
    info = get_stock_info(ticker)
    industry = info.get("industry", "")
    if not industry:
        return []

    # 搜索缓存中同行业的
    sisters = []
    for cache_file in CACHE_DIR.glob("*_info.json"):
        with open(cache_file) as f:
            cached = json.load(f)
        if cached.get("industry") == industry and cached["ticker"] != ticker:
            sisters.append(cached["ticker"])
    return sisters[:5]


def get_sister_comparison(ticker: str) -> list[dict]:
    """姐妹股对比：当日表现。"""
    sisters = find_sisters(ticker)
    if not sisters:
        return []
    return get_quotes(sisters)


# ──────────────────────────────────────────
# 6. 利弗莫尔数据处理（委托给 analysis.py）
# ──────────────────────────────────────────
# analysis.py 只输出纯数据，零判断。这里保留薄包装供 CLI 调用。
# 所有函数用 get_full_history()：已收盘历史 + 当日实时 bar。

import analysis as _analysis


def compute_key_levels(ticker: str) -> dict:
    """52w/3m/1m 高低点坐标。"""
    df = get_full_history(ticker)
    if df.empty:
        return {}
    return _analysis.compute_key_levels(df)


def compute_volume_profile(ticker: str, **kwargs) -> dict:
    """多窗口量价数据。"""
    df = get_full_history(ticker)
    if df.empty:
        return {}
    return _analysis.compute_volume_profile(df, **kwargs)


def find_swing_points(ticker: str, window: int = 5) -> dict:
    """摆动高/低点。"""
    df = get_full_history(ticker)
    if df.empty:
        return {"highs": [], "lows": []}
    return _analysis.find_swing_points(df, window=window)


def find_price_zones(ticker: str, **kwargs) -> dict:
    """价格区间——同一价位被反复触碰的聚集区。"""
    df = get_full_history(ticker)
    if df.empty:
        return {"current_price": None, "zones": []}
    return _analysis.find_price_zones(df, **kwargs)


def find_adjacent_structures(ticker: str, **kwargs) -> list[dict]:
    """相邻结构——低-高-低、高-低-高的时间叙事。"""
    df = get_full_history(ticker)
    if df.empty:
        return []
    return _analysis.find_adjacent_structures(df, **kwargs)


def find_gaps(ticker: str, **kwargs) -> list[dict]:
    """缺口——跳空在哪里，是否已回填。"""
    df = get_full_history(ticker)
    if df.empty:
        return []
    return _analysis.find_gaps(df, **kwargs)


def build_swing_sequence(ticker: str, **kwargs) -> dict:
    """HH/HL/LH/LL 摆动序列。"""
    df = get_full_history(ticker)
    if df.empty:
        return {"current_price": None, "sequence": [], "highs": [], "lows": [],
                "last_swing_high": None, "last_swing_low": None}
    return _analysis.build_swing_sequence(df, **kwargs)


# ──────────────────────────────────────────
# 7. 综合分析（利弗莫尔全套数据）
# ──────────────────────────────────────────

def full_analysis(ticker: str) -> dict:
    """
    利弗莫尔的价格记录本——一只股票的全部结构化数据。
    纯数据，零判断。

    数据来源：
      - 历史 K 线：sync_history()（已收盘日）
      - 当日 K 线：get_live_bar()（盘中实时）
      - 实时报价：get_quote()（最新价、量比）
    """
    df = get_full_history(ticker)
    if df.empty:
        return {}

    data_as_of = str(pd.Timestamp(df["Date"].iloc[-1]).date()) if not df.empty else None
    live = get_live_bar(ticker) if not _is_market_closed() else None

    return {
        "quote": get_quote(ticker),
        "info": get_stock_info(ticker),
        "data_as_of": data_as_of,
        "is_live": live is not None,
        "key_levels": _analysis.compute_key_levels(df),
        "volume_profile": _analysis.compute_volume_profile(df),
        "recent_bars": _analysis.get_recent_bars(df),
        "swing_sequence": _analysis.build_swing_sequence(df),
        "price_zones": _analysis.find_price_zones(df),
        "adjacent_structures": _analysis.find_adjacent_structures(df),
        "gaps": _analysis.find_gaps(df),
        "sisters": get_sister_comparison(ticker),
        "market": {
            "spy": get_quote("SPY"),
            "qqq": get_quote("QQQ"),
        },
    }
