"""
利弗莫尔交易系统 — 数据处理层

职责：把原始 K 线处理成利弗莫尔能读懂的结构化数据。
原则：
  - 输入：DataFrame (Date, Open, High, Low, Close, Volume)
  - 输出：结构化 dict，每个数字都有来源（日期+价格+成交量）
  - 只描述"价格做了什么"，不说"意味着什么"
  - 不贴标签（强/弱/确认/失败）——那是利弗莫尔大脑的活
  - 不画均线，不算指标——只看价格在哪里停下来了

五大模块：
  1. 摆动高低点 — 价格在哪里掉头了
  2. 价格区间   — 同一价位被反复触碰形成的聚集区
  3. 相邻结构   — 低-高-低、高-低-高的时间叙事
  4. 缺口       — 跳空在哪里，是否已回填
  5. 摆动序列   — HH/HL/LH/LL 的客观记录
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


# ══════════════════════════════════════════
# 1. 摆动高低点 — "价格在哪里掉头了"
# ══════════════════════════════════════════

def find_swing_points(
    df: pd.DataFrame,
    window: int = 5,
    use_close: bool = True,
) -> dict:
    """
    识别摆动高/低点。

    利弗莫尔用收盘价——收盘是一天交战后的终审判决。

    返回:
        {"highs": [...], "lows": [...]}
        每个元素: {"date": "2025-10-08", "price": 671.13,
                   "volume": 12345678, "vol_ratio": 1.2}
    """
    if df.empty or len(df) < window * 2 + 1:
        return {"highs": [], "lows": []}

    df = df.sort_values("Date").reset_index(drop=True)
    col = "Close" if use_close else ("High", "Low")
    highs_col = col if isinstance(col, str) else col[0]
    lows_col = col if isinstance(col, str) else col[1]

    highs_vals = df[highs_col].values
    lows_vals = df[lows_col].values
    volumes = df["Volume"].values
    dates = df["Date"].values

    vol_ma20 = df["Volume"].rolling(20).mean().values

    highs, lows = [], []

    for i in range(window, len(df) - window):
        if highs_vals[i] == max(highs_vals[i - window : i + window + 1]):
            vr = round(volumes[i] / vol_ma20[i], 2) if vol_ma20[i] and vol_ma20[i] > 0 else None
            highs.append({
                "date": str(pd.Timestamp(dates[i]).date()),
                "price": round(float(highs_vals[i]), 2),
                "volume": int(volumes[i]),
                "vol_ratio": vr,
            })

        if lows_vals[i] == min(lows_vals[i - window : i + window + 1]):
            vr = round(volumes[i] / vol_ma20[i], 2) if vol_ma20[i] and vol_ma20[i] > 0 else None
            lows.append({
                "date": str(pd.Timestamp(dates[i]).date()),
                "price": round(float(lows_vals[i]), 2),
                "volume": int(volumes[i]),
                "vol_ratio": vr,
            })

    return {"highs": highs, "lows": lows}


# ══════════════════════════════════════════
# 2. 价格区间 — "同一价位被反复触碰"
# ══════════════════════════════════════════

def find_price_zones(
    df: pd.DataFrame,
    cluster_pct: float = 2.0,
    min_tests: int = 2,
    lookback_months: int = 12,
) -> dict:
    """
    把摆动点按价格聚类成区间。

    纯客观：只回答"哪些价位被反复触碰了，各碰了几次"。
    不说"支撑""阻力"——当前价以下的是不是支撑，那是利弗莫尔判断的。

    返回:
        {
            "current_price": 12.93,
            "zones": [
                {"price": 13.06, "low": 13.04, "high": 13.08,
                 "tests": 2, "dates": [...],
                 "first_test": "2025-08-01", "last_test": "2026-02-05",
                 "span_days": 188, "avg_volume": 3780700,
                 "max_vol_ratio": 1.5,
                 "distance_pct": -1.0,
                 "points": [{"date":.., "price":.., "volume":.., "type":"low"}, ...]
                },
            ],
        }
    """
    if df.empty:
        return {"current_price": None, "zones": []}

    df = df.sort_values("Date").reset_index(drop=True)

    cutoff = datetime.now() - timedelta(days=lookback_months * 30)
    df_window = df[pd.to_datetime(df["Date"]) >= cutoff].copy()
    if len(df_window) < 20:
        df_window = df.copy()

    current_price = round(float(df_window["Close"].iloc[-1]), 2)

    # 两种窗口取摆动点，合并去重
    sw5 = find_swing_points(df_window, window=5)
    sw10 = find_swing_points(df_window, window=10)

    all_highs = _merge_points(sw5["highs"], sw10["highs"])
    all_lows = _merge_points(sw5["lows"], sw10["lows"])

    # 给每个点标注类型，合到一起
    all_points = []
    for h in all_highs:
        all_points.append({**h, "point_type": "high"})
    for lo in all_lows:
        all_points.append({**lo, "point_type": "low"})

    # 按价格聚类
    zones = _cluster_points(all_points, cluster_pct)

    # 过滤：至少 min_tests 次
    zones = [z for z in zones if z["tests"] >= min_tests]

    # 加距离，按距当前价排序
    for z in zones:
        z["distance_pct"] = round((current_price - z["price"]) / z["price"] * 100, 2)
    zones.sort(key=lambda x: abs(x["distance_pct"]))

    return {"current_price": current_price, "zones": zones}


def _merge_points(list_a: list[dict], list_b: list[dict]) -> list[dict]:
    """合并两组摆动点，去除价格和日期都接近的重复。"""
    merged = list(list_a)
    for b in list_b:
        is_dup = False
        for a in merged:
            if a["date"] == b["date"]:
                is_dup = True
                break
            if abs(a["price"] - b["price"]) / max(a["price"], 0.01) < 0.005:
                days_apart = abs((pd.Timestamp(a["date"]) - pd.Timestamp(b["date"])).days)
                if days_apart <= 5:
                    is_dup = True
                    break
        if not is_dup:
            merged.append(b)
    return sorted(merged, key=lambda x: x["date"])


def _cluster_points(points: list[dict], cluster_pct: float) -> list[dict]:
    """把价格接近的点聚成区间。纯数学操作。"""
    if not points:
        return []

    sorted_pts = sorted(points, key=lambda x: x["price"])
    clusters = []
    used = set()

    for i, pt in enumerate(sorted_pts):
        if i in used:
            continue

        members = [pt]
        used.add(i)

        for j in range(i + 1, len(sorted_pts)):
            if j in used:
                continue
            center = sum(m["price"] for m in members) / len(members)
            if abs(sorted_pts[j]["price"] - center) / center * 100 <= cluster_pct:
                members.append(sorted_pts[j])
                used.add(j)

        prices = [m["price"] for m in members]
        volumes = [m["volume"] for m in members if m.get("volume")]
        vol_ratios = [m["vol_ratio"] for m in members if m.get("vol_ratio")]
        dates = sorted([m["date"] for m in members])

        span_days = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days if len(dates) > 1 else 0

        clusters.append({
            "price": round(sum(prices) / len(prices), 2),
            "low": round(min(prices), 2),
            "high": round(max(prices), 2),
            "tests": len(members),
            "dates": dates,
            "first_test": dates[0],
            "last_test": dates[-1],
            "span_days": span_days,
            "avg_volume": int(sum(volumes) / len(volumes)) if volumes else 0,
            "max_vol_ratio": round(max(vol_ratios), 2) if vol_ratios else None,
            "points": [
                {"date": m["date"], "price": m["price"],
                 "volume": m.get("volume"), "vol_ratio": m.get("vol_ratio"),
                 "type": m.get("point_type", "unknown")}
                for m in sorted(members, key=lambda x: x["date"])
            ],
        })

    return clusters


# ══════════════════════════════════════════
# 3. 相邻结构 — "低-高-低、高-低-高的叙事"
# ══════════════════════════════════════════

def find_adjacent_structures(
    df: pd.DataFrame,
    lookback_months: int = 6,
    max_structures: int = 8,
) -> list[dict]:
    """
    在摆动点序列中找出相邻的 低-高-低 和 高-低-高。

    这就是利弗莫尔翻价格记录本的方式：
    "跌到 13 → 反弹到 14.8 → 又跌回 13 附近"
    代码只描述这个事实。"这是不是双底"——利弗莫尔自己判断。

    返回:
        [
            {"type": "low-high-low",
             "left": {"date":.., "price":.., "volume":.., "vol_ratio":..},
             "peak": {"date":.., "price":.., "volume":.., "vol_ratio":..},
             "right": {"date":.., "price":.., "volume":.., "vol_ratio":..},
             "bottom_spread_pct": 0.3,
             "peak_height_pct": 9.7},
            {"type": "high-low-high",
             "left": {"date":.., "price":.., ...},
             "valley": {"date":.., "price":.., ...},
             "right": {"date":.., "price":.., ...},
             "top_spread_pct": 2.1,
             "valley_depth_pct": 8.3},
        ]
    """
    if df.empty:
        return []

    df = df.sort_values("Date").reset_index(drop=True)
    cutoff = datetime.now() - timedelta(days=lookback_months * 30)
    df_window = df[pd.to_datetime(df["Date"]) >= cutoff].copy()
    if len(df_window) < 20:
        df_window = df.copy()

    swings = find_swing_points(df_window, window=5)

    # 按时间合并成交替序列
    merged = []
    for h in swings["highs"]:
        merged.append({**h, "swing": "high"})
    for lo in swings["lows"]:
        merged.append({**lo, "swing": "low"})
    merged.sort(key=lambda x: x["date"])

    # 去除连续同向（保留最极端的）
    cleaned = []
    for pt in merged:
        if not cleaned or cleaned[-1]["swing"] != pt["swing"]:
            cleaned.append(pt)
        else:
            if pt["swing"] == "high" and pt["price"] > cleaned[-1]["price"]:
                cleaned[-1] = pt
            elif pt["swing"] == "low" and pt["price"] < cleaned[-1]["price"]:
                cleaned[-1] = pt

    structures = []

    for i in range(len(cleaned) - 2):
        a, b, c = cleaned[i], cleaned[i + 1], cleaned[i + 2]

        if a["swing"] == "low" and b["swing"] == "high" and c["swing"] == "low":
            spread = abs(a["price"] - c["price"]) / min(a["price"], c["price"]) * 100
            peak_h = (b["price"] - min(a["price"], c["price"])) / min(a["price"], c["price"]) * 100
            structures.append({
                "type": "low-high-low",
                "left": _pt(a),
                "peak": _pt(b),
                "right": _pt(c),
                "bottom_spread_pct": round(spread, 1),
                "peak_height_pct": round(peak_h, 1),
            })

        elif a["swing"] == "high" and b["swing"] == "low" and c["swing"] == "high":
            spread = abs(a["price"] - c["price"]) / min(a["price"], c["price"]) * 100
            valley_d = (max(a["price"], c["price"]) - b["price"]) / b["price"] * 100
            structures.append({
                "type": "high-low-high",
                "left": _pt(a),
                "valley": _pt(b),
                "right": _pt(c),
                "top_spread_pct": round(spread, 1),
                "valley_depth_pct": round(valley_d, 1),
            })

    # 只保留最近 max_structures 个（利弗莫尔关心当前周围的结构，不翻远古历史）
    if max_structures and len(structures) > max_structures:
        structures = structures[-max_structures:]

    return structures


def _pt(p: dict) -> dict:
    """提取摆动点核心字段。"""
    return {
        "date": p["date"],
        "price": p["price"],
        "volume": p.get("volume"),
        "vol_ratio": p.get("vol_ratio"),
    }


# ══════════════════════════════════════════
# 4. 缺口 — "跳空在哪里"
# ══════════════════════════════════════════

def find_gaps(
    df: pd.DataFrame,
    min_gap_pct: float = 1.0,
    lookback_months: int = 6,
) -> list[dict]:
    """
    检测跳空缺口。

    缺口 = 今日最低 > 昨日最高（向上跳空）
           或 今日最高 < 昨日最低（向下跳空）

    返回:
        [{"date": "2025-11-04", "direction": "down",
          "gap_top": 17.73, "gap_bottom": 16.80, "gap_pct": 5.2,
          "volume": 9130100, "vol_ratio": 2.1,
          "filled": False, "fill_date": None}]
    """
    if df.empty or len(df) < 2:
        return []

    df = df.sort_values("Date").reset_index(drop=True)
    cutoff = datetime.now() - timedelta(days=lookback_months * 30)
    df_window = df[pd.to_datetime(df["Date"]) >= cutoff].copy().reset_index(drop=True)
    if len(df_window) < 2:
        df_window = df.copy().reset_index(drop=True)

    vol_ma20 = df_window["Volume"].rolling(20).mean()
    gaps = []

    for i in range(1, len(df_window)):
        prev = df_window.iloc[i - 1]
        curr = df_window.iloc[i]

        # 向上跳空
        if curr["Low"] > prev["High"]:
            gap_pct = (curr["Low"] - prev["High"]) / prev["High"] * 100
            if gap_pct >= min_gap_pct:
                vr = round(curr["Volume"] / vol_ma20.iloc[i], 2) if pd.notna(vol_ma20.iloc[i]) and vol_ma20.iloc[i] > 0 else None
                gaps.append({
                    "date": str(pd.Timestamp(curr["Date"]).date()),
                    "direction": "up",
                    "gap_top": round(float(curr["Low"]), 2),
                    "gap_bottom": round(float(prev["High"]), 2),
                    "gap_pct": round(gap_pct, 1),
                    "volume": int(curr["Volume"]),
                    "vol_ratio": vr,
                })

        # 向下跳空
        elif curr["High"] < prev["Low"]:
            gap_pct = (prev["Low"] - curr["High"]) / prev["Low"] * 100
            if gap_pct >= min_gap_pct:
                vr = round(curr["Volume"] / vol_ma20.iloc[i], 2) if pd.notna(vol_ma20.iloc[i]) and vol_ma20.iloc[i] > 0 else None
                gaps.append({
                    "date": str(pd.Timestamp(curr["Date"]).date()),
                    "direction": "down",
                    "gap_top": round(float(prev["Low"]), 2),
                    "gap_bottom": round(float(curr["High"]), 2),
                    "gap_pct": round(gap_pct, 1),
                    "volume": int(curr["Volume"]),
                    "vol_ratio": vr,
                })

    # 检查缺口是否被回填
    for gap in gaps:
        gap_date = pd.Timestamp(gap["date"])
        subsequent = df_window[pd.to_datetime(df_window["Date"]) > gap_date]
        gap["filled"] = False
        gap["fill_date"] = None
        for _, row in subsequent.iterrows():
            if gap["direction"] == "up" and row["Low"] <= gap["gap_bottom"]:
                gap["filled"] = True
                gap["fill_date"] = str(pd.Timestamp(row["Date"]).date())
                break
            elif gap["direction"] == "down" and row["High"] >= gap["gap_top"]:
                gap["filled"] = True
                gap["fill_date"] = str(pd.Timestamp(row["Date"]).date())
                break

    return gaps


# ══════════════════════════════════════════
# 5. 摆动序列 — "HH/HL/LH/LL 的客观记录"
# ══════════════════════════════════════════

def build_swing_sequence(
    df: pd.DataFrame,
    lookback_months: int = 6,
) -> dict:
    """
    构建摆动高低点的 HH/HL/LH/LL 序列。

    纯客观记录：只标注每个高/低是比前一个高了还是低了。
    不说"上升趋势""下降趋势"——那是利弗莫尔的判断。

    返回:
        {
            "current_price": 12.93,
            "sequence": [{"type": "HH", "date": ..., "price": ...,
                          "prev_price": ..., "change": +0.90}, ...],
            "highs": [...],
            "lows": [...],
            "last_swing_high": {...},
            "last_swing_low": {...},
        }
    """
    if df.empty:
        return {"current_price": None, "sequence": [], "highs": [], "lows": [],
                "last_swing_high": None, "last_swing_low": None}

    df = df.sort_values("Date").reset_index(drop=True)
    cutoff = datetime.now() - timedelta(days=lookback_months * 30)
    df_window = df[pd.to_datetime(df["Date"]) >= cutoff].copy()
    if len(df_window) < 20:
        df_window = df.copy()

    swings = find_swing_points(df_window, window=5)

    # 去重：连续同价保留第一个（修复如 $17.91 连续两天被标为摆动低的脏数据）
    all_highs = _dedup_swing_list(swings["highs"])
    all_lows = _dedup_swing_list(swings["lows"])

    current_price = round(float(df_window["Close"].iloc[-1]), 2)

    sequence = []

    for i in range(1, len(all_highs)):
        prev, curr = all_highs[i - 1], all_highs[i]
        seq_type = "HH" if curr["price"] > prev["price"] else "LH"
        sequence.append({
            "type": seq_type,
            "date": curr["date"],
            "price": curr["price"],
            "prev_price": prev["price"],
            "change": round(curr["price"] - prev["price"], 2),
        })

    for i in range(1, len(all_lows)):
        prev, curr = all_lows[i - 1], all_lows[i]
        seq_type = "HL" if curr["price"] > prev["price"] else "LL"
        sequence.append({
            "type": seq_type,
            "date": curr["date"],
            "price": curr["price"],
            "prev_price": prev["price"],
            "change": round(curr["price"] - prev["price"], 2),
        })

    sequence.sort(key=lambda x: x["date"])

    return {
        "current_price": current_price,
        "sequence": sequence,
        "highs": all_highs,
        "lows": all_lows,
        "last_swing_high": all_highs[-1] if all_highs else None,
        "last_swing_low": all_lows[-1] if all_lows else None,
    }


def _dedup_swing_list(points: list[dict]) -> list[dict]:
    """去除连续同价摆动点，保留第一个。"""
    if not points:
        return []
    deduped = [points[0]]
    for pt in points[1:]:
        if pt["price"] != deduped[-1]["price"]:
            deduped.append(pt)
    return deduped


# ══════════════════════════════════════════
# 6. 量价数据
# ══════════════════════════════════════════

def compute_volume_profile(df: pd.DataFrame, periods: list[int] | None = None) -> dict:
    """
    多窗口量价对比 + 巨量日。

    利弗莫尔不只看"现在多少量"，他看"量在往哪个方向走"。
    5天 vs 20天 vs 60天，收缩还是扩张一目了然。
    """
    if periods is None:
        periods = [5, 20, 60]

    if df.empty or len(df) < min(periods):
        return {}

    vol_ma20 = df["Volume"].rolling(20).mean()

    windows = {}
    for days in periods:
        if len(df) < days:
            continue
        recent = df.tail(days).copy()
        recent["change"] = recent["Close"].diff()
        up = recent[recent["change"] > 0]
        down = recent[recent["change"] < 0]

        up_avg = int(up["Volume"].mean()) if not up.empty else 0
        down_avg = int(down["Volume"].mean()) if not down.empty else 0
        ratio = round(up_avg / down_avg, 2) if down_avg > 0 else None
        avg_vol = int(recent["Volume"].mean())

        windows[f"{days}d"] = {
            "period_days": days,
            "up_days": len(up),
            "down_days": len(down),
            "up_avg_vol": up_avg,
            "down_avg_vol": down_avg,
            "up_down_ratio": ratio,
            "avg_vol": avg_vol,
        }

    # 巨量日（近20天内 >2x 20日均量）
    tail20 = df.tail(20).copy()
    tail20["change"] = tail20["Close"].diff()
    tail20["vol_ma20"] = vol_ma20.tail(20).values
    heavy = tail20[tail20["Volume"] > tail20["vol_ma20"] * 2]

    heavy_volume_days = []
    for _, row in heavy.iterrows():
        heavy_volume_days.append({
            "date": str(pd.Timestamp(row["Date"]).date()),
            "close": round(row["Close"], 2),
            "change": round(row["change"], 2) if pd.notna(row["change"]) else 0,
            "volume": int(row["Volume"]),
            "vol_ratio": round(row["Volume"] / row["vol_ma20"], 1) if pd.notna(row["vol_ma20"]) and row["vol_ma20"] > 0 else None,
        })

    return {
        "windows": windows,
        "heavy_volume_days": heavy_volume_days,
    }


# ══════════════════════════════════════════
# 7. 关键位坐标
# ══════════════════════════════════════════

def compute_key_levels(df: pd.DataFrame) -> dict:
    """52周/3月/1月的高低点。纯数据。"""
    if df.empty:
        return {}

    now = datetime.now()
    result = {}

    for label, days in [("52w", 365), ("3m", 90), ("1m", 30)]:
        window = df[pd.to_datetime(df["Date"]) >= (now - timedelta(days=days))]
        if not window.empty:
            result[f"{label}_high"] = round(float(window["High"].max()), 2)
            result[f"{label}_low"] = round(float(window["Low"].min()), 2)

    return result


# ══════════════════════════════════════════
# 8. 综合数据包
# ══════════════════════════════════════════

def get_recent_bars(df: pd.DataFrame, n: int = 10) -> list[dict]:
    """最近 N 个交易日的逐日 OHLCV + 量比。利弗莫尔翻记录本最后几页。"""
    if df.empty:
        return []

    vol_ma20 = df["Volume"].rolling(20).mean()
    tail = df.tail(n).copy()
    tail["vol_ma20"] = vol_ma20.tail(n).values
    tail["change"] = tail["Close"].diff()

    bars = []
    for _, row in tail.iterrows():
        vr = round(row["Volume"] / row["vol_ma20"], 2) if pd.notna(row["vol_ma20"]) and row["vol_ma20"] > 0 else None
        bars.append({
            "date": str(pd.Timestamp(row["Date"]).date()),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
            "vol_ratio": vr,
            "change": round(row["change"], 2) if pd.notna(row["change"]) else None,
        })
    return bars


# ══════════════════════════════════════════
# 工具函数 — 纯数学，无判断
# ══════════════════════════════════════════

def compute_position_size(
    account_size: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_price: float,
    max_position_pct: float = 25.0,
) -> dict:
    """
    根据止损距离和风险预算计算仓位（纯数学）。

    返回:
        {"shares": 162, "cost": 2187.0, "dollar_risk": 80.46,
         "risk_pct": 0.9, "position_pct": 24.4, "warning": None}
    """
    if entry_price <= 0 or stop_price <= 0:
        return {"error": "价格无效"}

    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share == 0:
        return {"error": "入场价等于止损价"}

    max_risk_dollar = account_size * (risk_per_trade_pct / 100)
    shares_by_risk = int(max_risk_dollar / risk_per_share)

    max_cost = account_size * (max_position_pct / 100)
    shares_by_position = int(max_cost / entry_price)

    shares = min(shares_by_risk, shares_by_position)
    cost = round(shares * entry_price, 2)
    dollar_risk = round(shares * risk_per_share, 2)
    risk_pct = round(dollar_risk / account_size * 100, 2)
    position_pct = round(cost / account_size * 100, 2)

    warning = None
    if shares == shares_by_position and shares < shares_by_risk:
        warning = f"仓位受限于 {max_position_pct}% 上限（{position_pct}%），风险 {risk_pct}% 低于预算 {risk_per_trade_pct}%"

    return {
        "shares": shares,
        "cost": cost,
        "dollar_risk": dollar_risk,
        "risk_pct": risk_pct,
        "position_pct": position_pct,
        "risk_per_share": round(risk_per_share, 2),
        "warning": warning,
    }


# ══════════════════════════════════════════
# 完整分析 — 一键获取所有数据
# ══════════════════════════════════════════

def full_analysis(df: pd.DataFrame, ticker: str = "") -> dict:
    """利弗莫尔的价格记录本——一只股票的全部结构化数据。"""
    data_as_of = str(pd.Timestamp(df["Date"].iloc[-1]).date()) if not df.empty else None

    return {
        "ticker": ticker,
        "data_as_of": data_as_of,
        "key_levels": compute_key_levels(df),
        "volume_profile": compute_volume_profile(df),
        "recent_bars": get_recent_bars(df),
        "swing_points": find_swing_points(df),
        "swing_sequence": build_swing_sequence(df),
        "price_zones": find_price_zones(df),
        "adjacent_structures": find_adjacent_structures(df),
        "gaps": find_gaps(df),
    }
