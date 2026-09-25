# Endpoint Inventory

Every path observed, implemented or not. Method in brackets: ✅ implemented,
⚠️ implemented but inferred, ❌ known path, not implemented.

**Base:** `https://staticapis.nextcapital.com.pk` unless noted.

---

## Implemented — 30 REST endpoints

| Path | Method | Wrapped by |
|------|--------|-----------|
| `/v1/appVersion/verify-version` | GET+POST | `FinqalabClient.verify_version` |
| `/v1/loginV3` | ✅ POST | `.login` |
| `/v1/verifyDeviceVerificationOTP` | ✅ POST | `.verify_device_otp` |
| `/v1/userDetailV2` | ✅ GET | `.user_detail` |
| `/v1/portfolio-day-start` | ✅ GET | `.portfolio_day_start` |
| `/v1/multiday-toggle` | ✅ GET | `.multiday_toggle` |
| `/v1/custom_popups` | ✅ GET | `.custom_popups` |
| `/v1/subscription/subscription-detail` | ✅ GET | `.subscription_detail` |
| `/v1/marketSnapshot/summaryV2` | ✅ GET | `MarketClient.summary`, `.snapshots` |
| `/v1/snapshot/index_news` | ✅ GET | `.index_news` |
| `/v1/snapshot/detail/statistics` | ✅ GET | `.statistics` |
| `/v1/snapshot/detail/company` | ✅ GET | `.company` |
| `/v1/snapshot/detail/financial` | ✅ GET | `.financial` |
| `/v1/snapshot/detail/graph` | ✅ GET | `.graph` |
| `/v1/news` | ✅ GET | `.news` |
| `/v1/watchlist/read` | ✅ GET | `WatchlistClient.read` |
| `/v1/watchlist/create` | ✅ POST | `.create` |
| `/v1/alert_permission/byUserId` | ✅ GET | `AlertsClient.by_user_id` |
| `/v1/alert_permission/history` | ✅ GET | `.history` |
| `/v1/alert_permission` | ✅ POST | `.create` |
| `/v1/deposit_amount/usersDepositHistoryV2` | ✅ GET | `PaymentsClient.deposits_history` |
| `/v1/withdrawal` | ✅ GET | `.withdrawal_history` |
| `/v1/withdrawal/getBankCodeList` | ✅ GET | `.get_bank_codes` |
| `/v1/withdrawal/getAllAccounts` | ✅ GET | `.get_accounts` |
| `/v1/generatePeriodicDetailsPDF` | ✅ POST | `.periodic_pdf` (bytes) |
| `/v1/generateCashBookPDF` | ✅ POST | `.cashbook_pdf` (bytes) |
| `/v1/withdrawal` | ⚠️ POST | `.withdrawal` (raw body, unconfirmed) |

## Implemented — 4 WebSocket topics

Host: `wss://trade.nextcapital.com.pk`. Request destination / reply destination.

| Topic | Wrapped by |
|-------|-----------|
| `/app/order-service/portfolio.{code}` | `portfolio.portfolio`, `.holdings`, `.cash_balance` |
| `/app/order-service/order-list.{code}` | `order.order_list`, `.place_and_wait` |
| `/app/order-service/periodicTradeDetailReportRequest.{code}` | `portfolio.trades`, `payments.periodic_details` |
| `/app/order-service.{code}` | `order.buy`, `.sell`, `.modify` ⚠️, `.cancel` ⚠️ |

Reply destinations: `/user/{code}/order-service/{topic}`, and
`/user/{code}/order-service.notify` for order confirmations.

## Implemented — 1 OMS endpoint

| Path | Method | Wrapped by |
|------|--------|-----------|
| `finqalab-oms-prod.finqalab.com/api/trade-intimation` | ⚠️ POST | `oms.trade_intimation` |

---

## Not implemented

See [05-known-gaps.md](05-known-gaps.md) for the full table and the reason each
one is excluded.

| Path | Purpose |
|------|---------|
| `/v1/withdrawalV2` ❌ | Open a withdrawal |
| `/v1/verifyOtpV2` ❌ | Withdrawal OTP |
| `/v1/ibftDepositV2` ❌ | IBFT deposit |
| `/v1/payfastDepositV2` ❌ | PayFast deposit |
| `/v1/ibftDepositDetailV2` ❌ | IBFT deposit status |
| `/v1/withdrawal/beneficiary` ❌ | Add a beneficiary |
| `/v1/subscription/activate` ❌ | Activate a plan |
| `/v1/subscription/plans` ❌ | List plans |
| `/v1/changePassword` ❌ | Change password |
| `/v1/deactivateAccount` ❌ | Deactivate account |
| `/v1/uploadDocument` ❌ | Document upload |
| `/v1/aof/*` (7) ❌ | Account opening — `aof-mobile.nextcapital.com.pk` |
| `/v1/search/*` ❌ | Symbol search |
| `/v1/discover/*` ❌ | Discover feed |
| `/v1/portfolio/alerts` ❌ | Portfolio-wide alerts |
| `/v1/watchlist/reorder` ❌ | Reorder a watchlist |
| `/v1/announcements` ❌ | CMS — `cms-prod.finqalab.com` |
| `/v1/finbot/*` ❌ | FinBot — `finbot.finqalab.com` |
| `live-data.finqalab.com/socket.io/` ❌ | Live tape — 503, see [08](08-live-data-gap.md) |

## Removed from the original draft

Present as speculative code, deleted because the underlying shape was never
captured:

| Removed | Why |
|---------|-----|
| `research.py` | Exploration notes and captured secrets in an importable module |
| `WatchlistClient.symbol_others()` | Unused, request shape never captured |
| `WatchlistClient.custom_sort()` | Would have sent a guessed reorder payload |
| `AlertsClient.by_portfolio()` | Portfolio-wide alerts — path known, shape not |
| `order_list(active_only=...)` | Parameter never existed; raised `TypeError` |

---

## Non-API hosts

| Host | Contents |
|------|----------|
| `staticapis.nextcapital.com.pk` | 26 REST endpoints above |
| `trade.nextcapital.com.pk` | 4 WebSocket topics |
| `finqalab-oms-prod.finqalab.com` | 1 OMS endpoint |
| `live-data.finqalab.com` | socket.io — 503 |
| `cms-prod.finqalab.com` | Announcements, not exercised |
| `finbot.finqalab.com` | Assistant, not exercised |
| `aof-mobile.nextcapital.com.pk` | Account opening, not exercised |
| `analytics.capitalstake.com` | Third-party analytics |
| Firebase / Crashlytics / Mixpanel | Third-party analytics |
