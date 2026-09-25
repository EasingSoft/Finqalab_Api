"""Quickstart: log in, handle the email OTP, and read your profile.

Run:

    export FQ_USER_ID=00000
    export FQ_PASSWORD='your-password'
    python examples/01_quickstart.py

The first login from a new machine gets HTTP 207 and an OTP by email. The
script pauses so you can paste the code, then retries.
"""

import os
import sys

from finqalab import FinqalabClient, LoginRequired, decrypt_text


def main() -> int:
    user_id = os.environ.get("FQ_USER_ID")
    password = os.environ.get("FQ_PASSWORD")

    if not user_id or not password:
        print("Set FQ_USER_ID and FQ_PASSWORD first.")
        print("  Windows:  set FQ_USER_ID=00000 && set FQ_PASSWORD=your-password")
        print("  Linux/Mac: export FQ_USER_ID=00000 FQ_PASSWORD=your-password")
        return 1

    client = FinqalabClient(user_id=user_id, password=password)

    # 1. App-build handshake. The server accepts the default, so a failure here
    #    is not fatal - it is logged and we carry on.
    print("> verifying app version")
    try:
        print("  ", client.verify_version())
    except Exception as exc:
        print("   skipped:", type(exc).__name__)

    # 2. Log in. A brand-new device gets 207 + an email OTP instead of a token.
    print("> logging in")
    try:
        client.login()
    except LoginRequired:
        print("   new device detected - an OTP was emailed to you")
        otp = input("   enter the OTP from your email: ").strip()
        print("  ", client.verify_device_otp(otp))
        print("> logging in again")
        client.login()

    print("   token stored at ~/.finqalab_token\n")

    # 3. The login response is the full profile.
    profile = client.profile
    print("Logged in")
    print("  client code :", profile.get("id"))
    print("  username    :", profile.get("username"))
    print("  email       :", profile.get("email"))
    print("  account     :", profile.get("account_status"))
    print("  can trade   :", profile.get("trade"))
    print("  tax rate    :", profile.get("tax_rate"))

    # 4. Sensitive fields arrive AES-encrypted; decrypt_text handles them.
    mobile = profile.get("mobileNo")
    if mobile:
        print("  mobile      :", decrypt_text(mobile))

    # 5. Any authenticated call works from here.
    detail = client.user_detail()
    print("\nVerified via GET /v1/userDetailV2")
    print("  status      :", detail.get("message", detail.get("status")))
    print("  otp verified:", detail.get("otp_is_verified"))

    print("\nNext: 02_market_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
