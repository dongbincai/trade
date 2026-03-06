#!/usr/bin/env python3
"""
利弗莫尔交易系统 — CLI

用法：
  python src/cli.py quote PONY WRD          # 实时报价
  python src/cli.py sync PONY WRD           # 同步历史数据到本地
  python src/cli.py levels PONY             # 关键位坐标
  python src/cli.py volume PONY             # 量价数据
  python src/cli.py swings PONY             # 摆动高低点
  python src/cli.py zones PONY              # 价格区间（同一价位反复触碰）
  python src/cli.py sequence PONY           # 摆动序列（HH/HL/LH/LL）
  python src/cli.py structures PONY         # 相邻结构（低-高-低 / 高-低-高）
  python src/cli.py gaps PONY               # 缺口（跳空 + 回填状态）
  python src/cli.py sisters PONY            # 姐妹股对比
  python src/cli.py sectors                 # 板块排行（当日）
  python src/cli.py market                  # 大盘概览
  python src/cli.py leaders                 # 领涨板块内的领头羊（自动取前3板块）
  python src/cli.py leaders XLK             # 指定板块内领头羊
  python src/cli.py movers                  # 全市场今日涨跌幅前20
  python src/cli.py movers 1mo             # 全市场近1月涨跌幅前20
  python src/cli.py trend                   # 板块多周期强度（1d/5d/1mo）
  python src/cli.py analyze PONY            # 完整分析（利弗莫尔价格记录本）
  python src/cli.py brief PONY WRD           # ⭐ 利弗莫尔简报（市场+个股一次性获取）
  python src/cli.py brief PONY --no-market   # 简报（跳过市场层数据）
  python src/cli.py watch                   # 盯盘模式（所有已同步股票，30s刷新）
  python src/cli.py watch PONY WRD          # 盯盘指定股票
  python src/cli.py watch PONY 10           # 指定刷新间隔（秒）
"""

import json
import sys
from datetime import datetime

from market_data import (
    build_swing_sequence,
    compute_key_levels,
    compute_volume_profile,
    find_adjacent_structures,
    find_gaps,
    find_price_zones,
    find_swing_points,
    full_analysis,
    get_live_bar,
    get_market_overview,
    get_quote,
    get_sector_leaders,
    get_sector_history,
    get_sector_performance,
    get_sister_comparison,
    get_top_movers,
    invalidate_quote_cache,
    livermore_briefing,
    sync_history,
)


def fmt(data) -> str:
    """Pretty-print JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _fmt_vol(v):
    """格式化成交量：1234567 → 123.5万 or 1.2亿"""
    if v is None:
        return "N/A"
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.0f}万"
    return str(v)


def _fmt_vol_ratio(vr):
    """量比标签"""
    if vr is None:
        return ""
    if vr >= 2.0:
        return f" 🔴量比{vr:.1f}"
    if vr >= 1.5:
        return f" 🟡量比{vr:.1f}"
    if vr <= 0.5:
        return f" ⚪量比{vr:.1f}"
    return f" 量比{vr:.1f}"


def cmd_quote(tickers):
    for t in tickers:
        print(fmt(get_quote(t)))


def cmd_sync(tickers):
    for t in tickers:
        df = sync_history(t)
        if df.empty:
            print(f"[WARN] {t}: 无数据")
        else:
            print(f"✅ {t}: {len(df)} 条已收盘日线, {df['Date'].min().date()} → {df['Date'].max().date()}")
            bar = get_live_bar(t)
            if bar:
                print(f"   📡 当日实时: {bar['date']}  O:{bar['open']}  H:{bar['high']}  L:{bar['low']}  C:{bar['close']}  V:{_fmt_vol(bar['volume'])}")


def cmd_levels(tickers):
    for t in tickers:
        print(f"── {t} 关键位 ──")
        print(fmt(compute_key_levels(t)))


def cmd_volume(tickers):
    for t in tickers:
        data = compute_volume_profile(t)
        print(f"\n── {t} 量价数据 ──")

        windows = data.get("windows", {})
        if windows:
            print(f"  {'窗口':>6s}  {'涨日':>4s}  {'跌日':>4s}  {'涨均量':>10s}  {'跌均量':>10s}  {'涨/跌':>6s}  {'均量':>10s}")
            for key in sorted(windows.keys(), key=lambda k: int(k.replace('d', ''))):
                w = windows[key]
                ratio_str = f"{w['up_down_ratio']:.2f}" if w.get('up_down_ratio') else "N/A"
                print(f"  {key:>6s}  {w['up_days']:>4d}  {w['down_days']:>4d}  {_fmt_vol(w['up_avg_vol']):>10s}  {_fmt_vol(w['down_avg_vol']):>10s}  {ratio_str:>6s}  {_fmt_vol(w['avg_vol']):>10s}")

        heavy = data.get("heavy_volume_days", [])
        if heavy:
            print(f"\n  巨量日（>2x均量）:")
            for d in heavy:
                vr = f"量比{d['vol_ratio']}" if d.get('vol_ratio') else ""
                print(f"    {d['date']}  ${d['close']}  {d['change']:+.2f}  Vol:{_fmt_vol(d['volume'])}  {vr}")


def cmd_swings(tickers):
    for t in tickers:
        data = find_swing_points(t)
        print(f"── {t} 摆动高点 ──")
        for h in data.get("highs", [])[-10:]:
            vr = f"  Vol:{h['vol_ratio']:.1f}x" if h.get('vol_ratio') else ""
            print(f"  {h['date']}  ${h['price']}{vr}")
        print(f"── {t} 摆动低点 ──")
        for l in data.get("lows", [])[-10:]:
            vr = f"  Vol:{l['vol_ratio']:.1f}x" if l.get('vol_ratio') else ""
            print(f"  {l['date']}  ${l['price']}{vr}")


def cmd_zones(tickers):
    for t in tickers:
        data = find_price_zones(t)
        print(f"\n{'=' * 50}")
        print(f"  {t} 价格区间  当前 ${data.get('current_price', '?')}")
        print(f"{'=' * 50}")

        for z in data.get("zones", []):
            vr_tag = f"  最大量比{z['max_vol_ratio']}" if z.get('max_vol_ratio') else ""
            print(
                f"\n  ${z['low']}-${z['high']}  ({z['tests']}次触碰  跨{z['span_days']}天  "
                f"距{z['distance_pct']:+.1f}%{vr_tag})"
            )
            for pt in z.get("points", []):
                pt_vr = f"  量比{pt['vol_ratio']:.1f}" if pt.get('vol_ratio') else ""
                print(f"    {pt['date']}  ${pt['price']}  [{pt['type']}]{pt_vr}")


def cmd_sequence(tickers):
    for t in tickers:
        data = build_swing_sequence(t)
        print(f"\n{'=' * 50}")
        print(f"  {t} 摆动序列  当前 ${data.get('current_price', '?')}")
        print(f"{'=' * 50}")

        lsh = data.get("last_swing_high")
        lsl = data.get("last_swing_low")
        if lsh:
            print(f"  最近摆动高: ${lsh['price']}  {lsh['date']}")
        if lsl:
            print(f"  最近摆动低: ${lsl['price']}  {lsl['date']}")

        seq = data.get("sequence", [])[-12:]
        if seq:
            print(f"\n── 序列 ──")
            for s in seq:
                arrow = "↑" if s["type"] in ("HH", "HL") else "↓"
                print(f"  {arrow} {s['type']}  {s['date']}  ${s['price']}  (前值${s['prev_price']}  {s['change']:+.2f})")


def cmd_structures(tickers):
    for t in tickers:
        data = find_adjacent_structures(t)
        print(f"\n{'=' * 50}")
        print(f"  {t} 相邻结构（低-高-低 / 高-低-高）")
        print(f"{'=' * 50}")

        if not data:
            print("  无相邻结构")
            continue

        for s in data:
            if s["type"] == "low-high-low":
                print(f"\n  低-高-低  两底差{s['bottom_spread_pct']}%  峰高{s['peak_height_pct']}%")
                print(f"    左低: {s['left']['date']}  ${s['left']['price']}")
                print(f"    峰值: {s['peak']['date']}  ${s['peak']['price']}")
                print(f"    右低: {s['right']['date']}  ${s['right']['price']}")
            else:
                print(f"\n  高-低-高  两顶差{s['top_spread_pct']}%  谷深{s['valley_depth_pct']}%")
                print(f"    左高: {s['left']['date']}  ${s['left']['price']}")
                print(f"    谷底: {s['valley']['date']}  ${s['valley']['price']}")
                print(f"    右高: {s['right']['date']}  ${s['right']['price']}")


def cmd_gaps(tickers):
    for t in tickers:
        data = find_gaps(t)
        print(f"\n{'=' * 50}")
        print(f"  {t} 缺口")
        print(f"{'=' * 50}")

        if not data:
            print("  无缺口")
            continue

        for g in data:
            direction = "↑上跳" if g["direction"] == "up" else "↓下跳"
            filled = "已回填" if g["filled"] else "未回填"
            fill_info = f" ({g['fill_date']})" if g.get("fill_date") else ""
            vr = f"  量比{g['vol_ratio']}" if g.get("vol_ratio") else ""
            print(f"  {g['date']}  {direction} {g['gap_pct']}%  ${g['gap_bottom']}-${g['gap_top']}  {filled}{fill_info}{vr}")


def cmd_sisters(tickers):
    for t in tickers:
        print(f"── {t} 姐妹股 ──")
        sisters = get_sister_comparison(t)
        for s in sisters:
            chg = s.get("change_pct", "N/A")
            vol = _fmt_vol(s.get("volume"))
            vr = _fmt_vol_ratio(s.get("vol_ratio"))
            if isinstance(chg, (int, float)):
                print(f"  {s['ticker']:6s}  ${s.get('price', 'N/A')}  ({chg:+.2f}%)  Vol:{vol}{vr}")
            else:
                print(f"  {s['ticker']:6s}  error")


def cmd_sectors():
    sectors = get_sector_performance()
    print("── 板块排行 ──")
    for s in sectors:
        chg = s.get("change_pct", 0)
        bar = "🟢" if chg > 0 else "🔴"
        vol = _fmt_vol(s.get("volume"))
        print(f"  {bar} {s['sector']:6s} ({s['etf']})  {chg:+.2f}%  Vol:{vol}")


def cmd_market():
    data = get_market_overview()
    spy = data["spy"]
    qqq = data["qqq"]
    spy_vol = _fmt_vol(spy.get("volume"))
    qqq_vol = _fmt_vol(qqq.get("volume"))
    spy_vr = _fmt_vol_ratio(spy.get("vol_ratio"))
    qqq_vr = _fmt_vol_ratio(qqq.get("vol_ratio"))
    print(f"SPY  ${spy.get('price', 'N/A')}  ({spy.get('change_pct', 0):+.2f}%)  Vol:{spy_vol}{spy_vr}")
    print(f"QQQ  ${qqq.get('price', 'N/A')}  ({qqq.get('change_pct', 0):+.2f}%)  Vol:{qqq_vol}{qqq_vr}")
    print()
    print("领涨:")
    for s in data["leading"]:
        vol = _fmt_vol(s.get("volume"))
        print(f"  🟢 {s['sector']} ({s['etf']})  {s.get('change_pct', 0):+.2f}%  Vol:{vol}")
    print("领跌:")
    for s in data["lagging"]:
        vol = _fmt_vol(s.get("volume"))
        print(f"  🔴 {s['sector']} ({s['etf']})  {s.get('change_pct', 0):+.2f}%  Vol:{vol}")


def cmd_leaders(args):
    etf = args[0] if args else None
    results = get_sector_leaders(etf=etf)
    for sector_data in results:
        print(f"\n── {sector_data['sector']} ({sector_data['etf']}) 领头羊 ──")
        if sector_data.get("error"):
            print(f"  ⚠️ {sector_data['error']}")
            continue
        for i, s in enumerate(sector_data["leaders"], 1):
            chg = s.get("change_pct", 0)
            bar = "🟢" if chg > 0 else "🔴"
            print(f"  {i}. {bar} {s['ticker']:6s}  ${s['price']}  ({chg:+.2f}% / {s['period']})")


def cmd_movers(args):
    period = args[0].lower() if args else "1d"
    data = get_top_movers(top_n=20, period=period)
    print(f"\n── 全市场涨幅前20 ({period}) ──")
    for i, s in enumerate(data.get("gainers", []), 1):
        chg = s['change_pct']
        bar = "🟢" if chg > 0 else "🔴"
        print(f"  {i:2d}. {bar} {s['ticker']:6s}  ${s['price']}  ({chg:+.2f}%)")
    print(f"\n── 全市场跌幅前20 ({period}) ──")
    for i, s in enumerate(data.get("losers", []), 1):
        chg = s['change_pct']
        bar = "🟢" if chg > 0 else "🔴"
        print(f"  {i:2d}. {bar} {s['ticker']:6s}  ${s['price']}  ({chg:+.2f}%)")


def cmd_trend():
    results = get_sector_history()
    print(f"\n── 板块多周期强度 ──")
    print(f"  {'板块':8s} {'ETF':5s} {'1日':>7s} {'5日':>7s} {'1月':>7s}  趋势")
    print(f"  {'─' * 55}")
    for s in results:
        d1 = f"{s['chg_1d']:+.2f}%" if s['chg_1d'] is not None else "  N/A"
        d5 = f"{s['chg_5d']:+.2f}%" if s['chg_5d'] is not None else "  N/A"
        m1 = f"{s['chg_1mo']:+.2f}%" if s['chg_1mo'] is not None else "  N/A"
        print(f"  {s['sector']:8s} {s['etf']:5s} {d1:>7s} {d5:>7s} {m1:>7s}  {s['trend']}")


def cmd_analyze(tickers):
    for t in tickers:
        print(f"{'=' * 50}")
        print(f"  利弗莫尔完整分析: {t}")
        print(f"{'=' * 50}")
        print(fmt(full_analysis(t)))


def cmd_brief(raw_args):
    """
    ⭐ 利弗莫尔简报 — 一次性获取市场全景 + 个股全套数据。
    AI 的主入口：调用一次，获得利弗莫尔分析所需的一切。
    """
    tickers = []
    include_market = True
    for a in raw_args:
        if a.upper() in ("--NO-MARKET", "-NM"):
            include_market = False
        else:
            tickers.append(a)

    if not tickers:
        print("用法: brief TICKER [TICKER ...] [--no-market]")
        print("  一次性获取利弗莫尔分析所需的所有数据：")
        print("    市场层: SPY/QQQ + 板块排行 + 多周期强度 + 领头羊")
        print("    个股层: 报价 + 关键位 + 量价 + 摆动点 + 序列 + 区间 + 结构 + 缺口 + 姐妹股")
        return

    market_tag = "含市场全景" if include_market else "仅个股"
    print(f"⭐ 利弗莫尔简报 | {', '.join(tickers)} | {market_tag}")
    print(f"{'=' * 60}")

    data = livermore_briefing(tickers, include_market=include_market)
    print(fmt(data))


def cmd_watch(tickers, interval=30):
    """
    盯盘模式：每 interval 秒刷新一次持仓/关注股票的实时报价。
    Ctrl+C 退出。
    """
    import time

    if not tickers:
        # 默认监控已有 CSV 的所有股票
        from market_data import HISTORY_DIR
        tickers = [f.stem for f in HISTORY_DIR.glob("*.csv")]
    if not tickers:
        print("没有可监控的股票。请先 sync 或指定 ticker。")
        return

    print(f"📡 盯盘模式 | {', '.join(tickers)} | 每 {interval}s 刷新 | Ctrl+C 退出")
    print()

    try:
        while True:
            invalidate_quote_cache()  # 强制刷新
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\033[2K── {now} ──")
            print(f"\033[2K  {'股票':6s} {'价格':>8s} {'涨跌%':>8s} {'成交量':>10s} {'量比':>6s}  {'日内高':>7s} {'日内低':>7s}")

            for t in tickers:
                q = get_quote(t, use_cache=False)
                if "error" in q:
                    print(f"\033[2K  {t:6s}  [错误: {q['error'][:30]}]")
                    continue
                price = q.get("price", 0) or 0
                chg = q.get("change_pct", 0) or 0
                vol = q.get("volume", 0) or 0
                vr = q.get("vol_ratio")
                hi = q.get("high", 0) or 0
                lo = q.get("low", 0) or 0

                icon = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
                vr_str = f"{vr:.2f}" if vr else "N/A"
                print(f"\033[2K  {icon} {t:5s} ${price:>7.2f} {chg:>+7.2f}% {_fmt_vol(vol):>10s} {vr_str:>6s}  ${hi:>6.2f} ${lo:>6.2f}")

            print()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n⏹  盯盘结束")





def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    args = [a.upper() for a in sys.argv[2:]]

    def _dispatch_watch(raw_args):
        """解析 watch 参数：ticker... [interval]"""
        tickers = []
        interval = 30
        for a in raw_args:
            if a.isdigit():
                interval = max(int(a), 5)  # 最少 5 秒
            else:
                tickers.append(a)
        cmd_watch(tickers, interval)

    commands = {
        "quote": lambda: cmd_quote(args),
        "sync": lambda: cmd_sync(args),
        "levels": lambda: cmd_levels(args),
        "volume": lambda: cmd_volume(args),
        "swings": lambda: cmd_swings(args),
        "zones": lambda: cmd_zones(args),
        "sequence": lambda: cmd_sequence(args),
        "structures": lambda: cmd_structures(args),
        "gaps": lambda: cmd_gaps(args),
        "sisters": lambda: cmd_sisters(args),
        "sectors": lambda: cmd_sectors(),
        "market": lambda: cmd_market(),
        "leaders": lambda: cmd_leaders(args),
        "movers": lambda: cmd_movers(args),
        "trend": lambda: cmd_trend(),
        "analyze": lambda: cmd_analyze(args),
        "brief": lambda: cmd_brief(sys.argv[2:]),  # 保留原始大小写（--no-market 参数）
        "watch": lambda: _dispatch_watch(args),
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
