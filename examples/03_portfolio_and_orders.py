"""Portfolio, order list, and (optionally) order placement over the trading socket.

The trading WebSocket authenticates differently from the REST API: the STOMP
CONNECT frame carries your client code and your password in plaintext, so
`nostr` here is just your FQ_PASSWORD.

READ-ONLY BY DEFAULT. Placing an order sends a real order to the exchange
matching engine, so it needs the explicit --place flag plus an interactive
confirmation.

Run:

    export FQ_USER_ID=00000
    export FQ_PASSWORD='your-password'
    python examples/03_portfolio_and_orders.py
    python examples/03_portfolio_and_orders.py --place OGDC 1 137.50
"""

import getpass
import os
import sys
from typing import Tuple

from finqalab import FinqalabClient, LoginRequired, order, portfolio


def get_credentials() -> Tuple[str, str]:
    user_id = os.environ.get("FQ_USER_ID")
    password = os.environ.get("FQ_PASSWORD")
    if not user_id or not password:
        print("Set FQ_USER_ID and FQ_PASSWORD first.")
        sys.exit(1)

    # Log in over REST once. This validates the password and stores the JWT;
    # the socket then reuses the same client code + password.
    client = FinqalabClient(user_id=user_id, password=password)
    try:
        client.login()
    except LoginRequired:
        client.verify_device_otp(input("enter the OTP from your email: ").strip())
        client.login()
    return user_id, password


def is_cash_row(row) -> bool:
    """The money row is a holding like any other - exclude it from stock value."""
    if "cashBalance" in row.raw or "CashBalance" in row.raw:
        return True
    return "Money" in str(row.security or "")


def show_portfolio(code: str, nostr: str) -> None:
    print("=" * 74)
    print("PORTFOLIO  (STOMP order-service/portfolio)")
    print("=" * 74)
    rows = portfolio.holdings(code, nostr)
    if not rows:
        print("  no holdings returned")
        return

    print(f"{'security':<24}{'qty':>10}{'avg cost':>13}{'last':>12}{'value':>16}")
    stock_value = 0.0
    cash = 0.0
    for row in rows:
        value = row.current_value
        if isinstance(value, (int, float)):
            if is_cash_row(row):
                cash += value
            else:
                stock_value += value
        print(
            f"{(row.security or '')[:22]:<24}"
            f"{str(row.quantity or ''):>10}"
            f"{str(row.cost_per_unit or ''):>13}"
            f"{str(row.current_price or ''):>12}"
            f"{str(value or ''):>16}"
        )

    print()
    print(f"{'stock value (cash row excluded)':<64}{stock_value:>10,.2f}")
    print(f"{'cash (the money row)':<64}{cash:>10,.2f}")
    print(f"{'total':<64}{stock_value + cash:>10,.2f}")

    print("\nThe row whose security contains 'Money' is your cash balance:")
    print(" ", portfolio.cash_balance(code, nostr))


def show_orders(code: str, nostr: str) -> None:
    print()
    print("=" * 74)
    print("ORDER LIST  (STOMP order-service/order-list)")
    print("=" * 74)
    rows = order.order_list(code, nostr, page_size=1, from_index=0, to_index=50)
    if not rows:
        print("  no orders today")
        return
    print(f"{'order no':<14}{'symbol':<10}{'side':<7}{'qty':>8}{'price':>11}  {'status':<12}{'time'}")
    for o in rows:
        print(
            f"{str(o.order_number or ''):<14}{(o.symbol or ''):<10}"
            f"{(o.side or ''):<7}{str(o.volume or ''):>8}{str(o.price or ''):>11}"
            f"  {str(o.order_status or ''):<12}{o.order_date_time or ''}"
        )


def place_order(code: str, nostr: str, symbol: str, volume: int, price: float) -> None:
    print()
    print("=" * 74)
    print("PLACE ORDER  (STOMP order-service)")
    print("=" * 74)
    print(f"  BUY {volume} {symbol} @ {price}")

    # The STOMP socket authenticates independently of the REST session.
    if not nostr:
        nostr = getpass.getpass("trading password: ")

    answer = input("\n  This sends a REAL order to the exchange. Type 'yes' to proceed: ")
    if answer.strip().lower() != "yes":
        print("  cancelled - nothing was sent")
        return

    session = order.OrderSession(code, nostr, timeout=15.0)
    try:
        result = session.place(symbol=symbol, side="Buy", volume=volume, price=price)
    finally:
        session.close()

    print("\n ", result)
    if result.success:
        print("  accepted, order no:", result.order_no)


def main() -> int:
    code, nostr = get_credentials()

    if len(sys.argv) == 1:
        show_portfolio(code, nostr)
        show_orders(code, nostr)
        print()
        print("To place an order:")
        print("  python examples/03_portfolio_and_orders.py --place OGDC 1 137.50")
        return 0

    if sys.argv[1] == "--place" and len(sys.argv) == 5:
        place_order(code, nostr, sys.argv[2], int(sys.argv[3]), float(sys.argv[4]))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
