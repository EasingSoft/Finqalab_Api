# Known Gaps

22 endpoints whose paths are known but whose request and response shapes were
**never captured**. They are not implemented, and this file is the record of why.

**The rule:** no captured shape, no wrapper. A plausible-looking guess would be
worse than an honest gap — it fails mid-withdrawal and looks like a server error
rather than the guess it is.

## Inventory

| # | Path | Purpose | Blocker |
|---|------|---------|---------|
| 1 | `POST /v1/withdrawalV2` | Open a withdrawal | Needs an OTP first |
| 2 | `POST /v1/verifyOtpV2` | Withdrawal OTP | Body never seen |
| 3 | `POST /v1/ibftDepositV2` | IBFT bank transfer deposit | Body never seen |
| 4 | `POST /v1/payfastDepositV2` | PayFast card deposit | Body never seen |
| 5 | `GET /v1/ibftDepositDetailV2` | IBFT deposit status | Query shape unknown |
| 6 | `POST /v1/withdrawal/beneficiary` | Add a bank beneficiary | Body never seen |
| 7 | `POST /v1/subscription/activate` | Activate a plan | Body never seen |
| 8 | `GET /v1/subscription/plans` | List plans | Not exercised |
| 9 | `POST /v1/changePassword` | Change password | Body never seen |
| 10 | `POST /v1/deactivateAccount` | Deactivate account | Body never seen |
| 11 | `POST /v1/uploadDocument` | Document upload | Multipart shape unknown |
| 12 | `GET /v1/aof/*` (7 paths) | Account opening form | On `aof-mobile.nextcapital.com.pk`, not exercised |
| 13 | `GET /v1/search/*` | Symbol search | Query shape unknown |
| 14 | `GET /v1/discover/*` | Discover feed | Not exercised |
| 15 | `GET /v1/portfolio/alerts` | Portfolio-wide alerts | Path only |
| 16 | `POST /v1/watchlist/reorder` | Reorder a watchlist | Body never seen |
| 17 | `GET /v1/announcements` | CMS announcements | On `cms-prod.finqalab.com` |
| 18 | `GET /v1/finbot/*` | FinBot assistant | On `finbot.finqalab.com` |
| 19 | `live-data.finqalab.com/socket.io/` | Live market tape | 503 on every attempt |

> Path prefixes are as observed. Some are versioned (`V2`) and some are not;
> treat the exact strings as approximate where noted.

---

## The ones that matter

### 1-2 · Withdrawal V2 and its OTP

**The most consequential gap.** Deposits and withdrawal history are readable,
but **money cannot leave the account** through this client.

The flow requires an OTP to a registered bank account before the withdrawal is
accepted. Neither request body was captured — exercising it would have moved real
money, which is a decision for the account owner, not for reverse engineering.

`PaymentsClient.withdrawal(body)` is a raw passthrough, so the request plumbing
is there if you have the shape. Everything else is missing.

### 3-4 · Deposit flows

IBFT and PayFast deposits are deposit *initiations*. Both would move real money
into the account. Not exercised.

`deposits_history()` reads what has already happened, which is safe.

### 6 · Beneficiary accounts

`getAllAccounts` reads registered beneficiaries. Adding one is not implemented —
that would change account state.

### 12 · Account opening

Seven AOF paths on `aof-mobile.nextcapital.com.pk`, plus document upload. Not
exercised, and not relevant to using the client: this is broker onboarding, not
trading.

### 15-16 · Portfolio alerts and watchlist reorder

Both exist in the app UI. Both are cosmetic or low-value:

* Portfolio-wide alert settings duplicate per-symbol alerts, which **are**
  implemented via `AlertsClient`.
* Watchlist reorder changes display order only. The original draft had
  `custom_sort()`, which would have sent a guessed payload; it was deleted rather
  than shipped broken.

### 19 · Live market data

The socket.io feed returned **503** on every attempt. Event names, payload shape,
and auth are all unknown. Not implemented — there is nothing to implement against.

The client uses polled REST snapshots instead. Full investigation in
[08-live-data-gap.md](08-live-data-gap.md).

---

## Why not just try them

Each of these would need either real money moving or a guess at the body.

* **Withdrawal, deposits** — real money. Yours to risk, not the library's to
  assume.
* **Change password, deactivate account** — changes account state, and a
  malformed request could lock someone out.
* **AOF, document upload** — a different broker workflow entirely, unrelated to
  the client.
* **Search, discover, announcements, FinBot** — read-only, so they could have
  been captured. They were not exercised during the session, so the response
  shapes are unknown. Lower risk to add later.

The last group is the realistic next step. A few hours with the capture tool and
a screen-by-screen walk would close most of them.

---

## Adding one

1. Exercise the screen in the app with the capture tool running
   ([07-capture-tool.md](07-capture-tool.md)).
2. Get the request **and** response from SQLite.
3. Add the path to `config.py`.
4. Add a method to the relevant client. Unwrap the envelope like the others.
5. **Document whether it is verified or inferred.** If you inferred it, say so
   in the docstring and the API reference. See
   [04-findings-and-decisions.md](04-findings-and-decisions.md).

Step 5 is the one that gets skipped. It is the one that matters — an unlabelled
guess reads as a guarantee.

```bash
sqlite3 finqalab_capture.db \
  "SELECT method, path, response_status FROM http_flows ORDER BY timestamp;"
```

---

## What is implemented

Everything with a captured shape. Full table in
[`doc/api/04-api-reference.md`](../api/04-api-reference.md) — 30 REST endpoints,
4 WebSocket topics, 1 OMS endpoint.
