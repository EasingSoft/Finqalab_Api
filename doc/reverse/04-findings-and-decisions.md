# Findings and Decisions

What was learned, what was changed as a result, and what was left alone on
purpose. Each entry says the evidence.

---

## Confirmed by capture

Solid. Implemented, tested, documented.

| Finding | Evidence |
|---------|----------|
| Main API is REST + JWT on `staticapis.nextcapital.com.pk` | Full request and response bodies, 200 OK |
| JWT auth via `x-auth-token` header **and** `xauth` cookie | Both present on every authenticated call |
| Token is a 28-day standard JWT | `exp` claim decodes |
| First login on a new device returns **HTTP 207** and emails an OTP | Captured 207, then the verify call, then 200 |
| Device OTP is mixed-case alphanumeric | Captured `Ab3xY9`; uppercase rejected |
| `device_id` is locally generated, not fingerprinted | 8 random bytes hex; no IMEI or Android ID anywhere in the login body |
| Watchlist read is `GET` with `?sortBy=custom`, not POST | Captured |
| Watchlist `status` is an add/remove switch | Captured `status:false` on a remove action |
| Watchlist `watchlist` is a string 1-5 | Captured `"1"` |
| Alert `title` is server-generated — do not send one | Server returned `"Rises over 15"` for a request with no title |
| `alertType` 2 is a percentage move, `target` the threshold | Captured create with `target:"15"` |
| `summaryV2` is ~425 KB, every symbol, under `message` | Captured, 425k |
| `statistics()` wants `DD-MM-YYYY`, `graph()` wants `YYYY-MM-DD` | Both captured with dates |
| `sector` is a numeric PSX code | `0824` in the snapshot |
| `index_news`'s `lt` is JSON inside JSON | Captured escaped object |
| Trading socket is STOMP 1.2 over SockJS | Frames readable, full topic structure visible |
| SockJS client frames are `json.dumps([frame])` | Exactly as the capture shows |
| Topic naming is asymmetric: `/app/…/{topic}.{code}` vs `/user/{code}/…` | Both forms captured |
| STOMP `CONNECT` carries `id`=client code, `nostr`=**plaintext password** | Frame captured verbatim |
| Order confirmation arrives on a different destination than the request | Request to `/app/order-service.{code}`, reply on `/user/{code}/order-service.notify` |
| `VLD` means validated, not filled | Status field in the confirmation |
| Portfolio and order-list responses are bare JSON arrays | No envelope in either |
| Cash arrives as a portfolio row | `security` containing `"Money"`, with `cashBalance` |
| Payments `createdAt` is epoch **milliseconds** | Value was ~13 digits, not 10 |
| `periodicTradeDetailReportRequest` ignores the date range | Full history returned regardless of `fromDate`/`toDate` |
| `app_build` is not enforced | Wrong values return 200 and login proceeds |
| PDF endpoints return bytes, not JSON | `application/pdf` responses |

---

## Inferred, not observed

Implemented but explicitly marked unproven. Each carries the same warning in
the docstrings and the API docs.

### `modify()` and `cancel()`

**Evidence:** no modify or cancel frame exists in the capture. Reconstructed
from the OMS trade-intimation payload (`orderNo`, `symbol`, `side`, `volume`,
`price`) plus the `neworder` body shape, assuming `actionType` is what changes.

**Confidence: low.** The `actionType` mechanism itself was never observed
changing — only `neworder` was ever seen. Both functions exist because the
capability is obviously real, not because it was verified.

**Consequence:** for a live account, cancel in the app and place a new order.

### Live socket.io feed

**Evidence:** a 503 on every handshake attempt. No frames, no event names, no
auth.

**Decision:** not implemented at all. Nothing to implement against. The REST
snapshots stand in. See [08-live-data-gap.md](08-live-data-gap.md).

### OMS trade-intimation schema

**Evidence:** the endpoint was called and the payload inspected, but the
response carried nothing meaningful — it echoes what was sent.

**Decision:** implemented as a raw passthrough (`oms.trade_intimation(payload)`),
documented as inferred, no typed model.

### WebSocket `oms_user_id` and `session_token`

**Evidence:** both appear as literal path segments in the app and in captured
handshake URLs. `291` and `4rjrnta5`.

**Note:** these are **not per-user credentials.** They are shared, fixed
identifiers present in every client's URL. The STOMP `CONNECT` frame carries the
real authentication. They have been stable for years.

**Decision:** ship as defaults in `config.py`, overridable via the
`oms_user_id` / `session_token` arguments. Not a security decision, just a
practical one.

---

## Deliberately not implemented

22 known paths. Full inventory in [05-known-gaps.md](05-known-gaps.md), reason in
one line each: **no captured request or response, so no way to know the body.**

The principle: an endpoint whose shape was never observed does not get a typed
wrapper. A plausible-looking guess would be worse than an honest gap, because
it fails at the worst moment — mid-withdrawal — and looks like a server error
rather than a guess.

The one exception is `PaymentsClient.withdrawal(body)`, a raw passthrough, kept
because it costs nothing and someone who has already worked out the shape
should not have to write the request plumbing.

---

## Code changes from the original draft

### Removed `research.py`

It contained exploration notes, endpoint paths, and captured values mixed into
an importable module. Wrong place for any of it: the notes belong in this
directory, the secrets should not be in the repository at all. The reference
material moved to [05-known-gaps.md](05-known-gaps.md) and
[06-endpoint-inventory.md](06-endpoint-inventory.md); the secrets were deleted.

### Fixed `order_list.place_and_wait()`

It called `order_list(..., active_only=True)`. No such parameter exists — it
would have raised `TypeError` on every call. Removed.

### Removed `symbol_others()` and `custom_sort()`

Neither was ever used, and neither could work: both call watchlist endpoints with
request shapes that were never captured. `custom_sort` in particular would have
sent a guessed reorder payload. Deleting them is more honest than shipping code
that cannot work.

### Made `APP_BUILD` configurable

```python
APP_BUILD = int(os.environ.get("FQ_APP_BUILD", "170"))
```

It was a module constant. The server does not enforce it, so this is for
matching a different app build, not for bypassing anything.

### Rewrote `AlertsClient.create()`

The original sent a `title`. The server generates it and rejects requests that
include one. Corrected against the capture.

### Removed a live password and ciphertext from `encryption.py`

A real account password and its ciphertext were in the module docstring as an
example. Replaced with a placeholder. Same fix applied to every other captured
value in `src/`.

### Rewrote the `withdrawal()` docstring

It pointed at `research.py`, which no longer exists. Now points at
[05-known-gaps.md](05-known-gaps.md) and states that the body is unconfirmed.

---

## Security decisions

### Kept the AES key and IV in the repository

They are in `src/finqalab/encryption.py`, published.

**Reasoning:** the login is rejected without them, so removing them would break
the library. But shipping them silently would be dishonest — the obvious
impression is that the password is protected in transit, and it is not.

**Compromise:** keep them, and state plainly in `SECURITY.md` that this is
symmetric with a static key, that the fixed IV leaks equality, that TLS is the
only real protection, and that anything encrypted with it is effectively public.

**If the rights holder asks,** they come out. `SECURITY.md` says so.

### Kept the WebSocket path constants

`291` and `4rjrnta5` are not secrets — they are in every client's URL. Documented
as constants with an override.

### Removed every captured credential

Client code, password, username, email, CNIC, mobile, IBAN, trading PIN, live
JWT, and order numbers. `.gitignore` excludes `*.db`, `*.apk`, `*.pptx`, images,
`.env`, and `.finqalab_token` so raw artefacts stay out by default.

**Rotation:** any password that has been written into a file, a chat, or a commit
should be changed. A leaked one stays leaked.

### No tests, no CI

Deliberate. The library talks to a live broker account; a test suite would
either need real credentials or become a pile of mocks that assert nothing. There
is no mock market, no paper-trading mode, and no way to test order placement
without sending real orders. Verification was import checks, an AES roundtrip,
and STOMP frame parse/connect — all of which are safe.
