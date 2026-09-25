"""Market data: the full PSX snapshot, index levels, news, and one stock.

All of this needs only a valid token - no trading credentials.

Run:

    export FQ_USER_ID=00000
    export FQ_PASSWORD='your-password'
    python examples/02_market_data.py
"""

import os
import sys

from finqalab import FinqalabClient, LoginRequired, MarketClient


def login() -> str:
    client = FinqalabClient(
        user_id=os.environ["FQ_USER_ID"], password=os.environ["FQ_PASSWORD"]
    )
    try:
        client.login()
    except LoginRequired:
        client.verify_device_otp(input("enter the OTP from your email: ").strip())
        client.login()
    return client.token


def main() -> int:
    if not os.environ.get("FQ_USER_ID") or not os.environ.get("FQ_PASSWORD"):
        print("Set FQ_USER_ID and FQ_PASSWORD first.")
        return 1

    token = login()
    market = MarketClient(token=token)

    # ------------------------------------------------------------- indices
    print("=" * 62)
    print("INDEX LEVELS  (GET /v1/snapshot/index_news)")
    print("=" * 62)
    print(f"{'index':<12}{'open':>13}{'high':>13}{'low':>13}{'close':>13}")
    for row in market.index_news().get("data", {}).get("index", []):
        print(
            f"{row.get('symbol',''):<12}"
            f"{row.get('open',''):>13}{row.get('high',''):>13}"
            f"{row.get('low',''):>13}{row.get('close',''):>13}"
        )

    # ------------------------------------------------- full market summary
    # One call returns every listed symbol (~870 rows, a few hundred KB).
    print()
    print("=" * 62)
    print("MARKET SUMMARY  (GET /v1/marketSnapshot/summaryV2)")
    print("=" * 62)
    snapshots = market.snapshots()
    print(f"{len(snapshots)} symbols returned. First 10:\n")
    print(f"{'symbol':<10}{'name':<34}{'price':>10}{'chg%':>9}")
    for s in snapshots[:10]:
        pct = s.percent_change
        pct_s = f"{pct * 100:.2f}" if isinstance(pct, (int, float)) else (pct or "")
        print(f"{s.symbol or '':<10}{(s.name or '')[:32]:<34}{str(s.price or ''):>10}{pct_s:>9}")

    # ---------------------------------------------------- one stock in depth
    symbol = snapshots[0].symbol if snapshots else "OGDC"
    print()
    print("=" * 62)
    print(f"STATISTICS for {symbol}  (GET /v1/snapshot/detail/statistics)")
    print("=" * 62)
    stats = market.statistics(symbol)
    fundamentals = (stats.get("data") or {}).get("statistics") or {}
    for key in ("avgDailyVolume", "marketCap", "earningsPerShare",
                "PE_Ratio", "bookValueShare", "dividendPerShare"):
        if key in fundamentals:
            print(f"  {key:<20}{fundamentals[key]}")

    company = (market.company(symbol).get("data") or {})
    print(f"\n  company description: {(company.get('description') or '')[:150]}...")

    financials = market.financial(symbol).get("data") or {}
    periods = (financials.get("annually") or {}).get("periods") or []
    print(f"  annual periods available: {periods}")

    graph = market.graph(symbol, count=5, interval="d").get("data") or []
    print(f"  last {len(graph)} daily candles:")
    for candle in graph[-5:]:
        print(f"    {candle.get('Date')}  O={candle.get('Open')} "
              f"H={candle.get('High')} L={candle.get('Low')} C={candle.get('Price')}")

    # ----------------------------------------------------------------- news
    print()
    print("=" * 62)
    print("NEWS  (GET /v1/news?page=0&type=0)")
    print("=" * 62)
    for item in market.news(page=0, news_type=0)[:5]:
        print(f"  [{item.source or 'news'}] {(item.heading or '')[:70]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
