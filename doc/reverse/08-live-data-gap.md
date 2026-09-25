# The Live Data Gap

Finqalab has a live market tape on `live-data.finqalab.com` over socket.io. It
was never captured, so the client has no live quotes. This is the most visible
missing feature and the one gap that is genuinely unresolved.

---

## What was observed

```
GET https://live-data.finqalab.com/socket.io/?EIO=4&transport=polling&...
```

| | |
|---|---|
| Protocol | socket.io 4 (`EIO=4`) |
| Outcome | **HTTP 503 on every attempt** |
| Frames captured | none |
| Event names | unknown |
| Payload shape | unknown |
| Authentication | unknown |

The request reached the capture. The upstream connection failed. The response
was a 503, not a 200 handshake, so no session was ever established and no event
names or payloads were ever visible.

**This is not a proxy problem that was never diagnosed.** It is a real, recorded
503 from the upstream.

## Why 503 probably isn't a client bug

The likely explanations, in order of probability:

1. **The feed requires something the app supplies that was not present** —
   an auth header on the polling request, a specific origin or referer, or a
   `sid` obtained from another endpoint first.
2. **The service is intermittently or wholly down** — common with a secondary
   market-data feed kept as a nice-to-have while the app falls back to REST.
3. **It is origin-restricted** — only certain client IPs or regions.
4. **It was retired** in a later app version. The capture was v4.0.2; the
   current release may not use it at all.

## How the app works without it

The app does not break when the socket is unavailable. Market data comes from
two polled REST endpoints:

| Endpoint | Refresh | Cost |
|----------|---------|------|
| `GET /v1/marketSnapshot/summaryV2` | On demand | ~425 KB, every symbol |
| `GET /v1/snapshot/index_news` | Periodically | Small, index levels only |

These are snapshots, not a tape. A stock's price in the app updates when the
app re-polls, not tick by tick. The socket, when working, exists to make that
faster.

The client mirrors that: `MarketClient.snapshots()` and
`MarketClient.index_news()`. It polls the same way the app does when the socket
is down.

## What the client does about it

Nothing clever, deliberately.

* **No live-quote method exists.** There is no `live_prices()` to call. An
  endpoint that has never produced a single frame cannot be implemented.
* **`index_news()` does not pretend to be live.** Its `lt` field carries a live
  tick when the server supplies one, but that is a per-request snapshot, not a
  subscription.
* **Nothing is inferred from a 503.** No event names were guessed, no payload
  shape was assumed.

If a future version of the app ships a working tape, or a new version of this
library does, the place to put it is a new module alongside `market.py`, with
the protocol written down in [03-protocols.md](03-protocols.md) first.

## What was tried

| Attempt | Result |
|---------|--------|
| Proxy capture during normal app use | 503 on the handshake |
| Repeated reconnects across sessions | 503 every time |
| Direct host replay to isolate the MITM path | Not reached — the capture attempt was abandoned at this point |

The third line is the honest gap in the investigation. **Replaying the request
from the host, outside the emulator and outside the proxy, was identified as the
next step and not done.** That is what would distinguish explanation 1 from
explanations 2-4, and it is the first thing to try next.

## Next steps, in order

1. **Replay outside the MITM path.** `curl` the handshake from the host with no
   proxy involved. If it also 503s, the service is down or restricted and the
   proxy is exonerated. If it succeeds, the app is sending something the capture
   did not preserve.
2. **Inspect the 503 body and headers.** Was it Cloudflare or the app origin?
   A Cloudflare 503 is a rate or block signal; an origin 503 is the service
   failing. `SELECT response_headers, response_body FROM http_flows WHERE
   response_status = 503;` — the capture already has this.
3. **Diff the request headers** against what the app sends in a plain browser or
   a native socket.io client. Missing `Origin`, `Referer`, or a `t=` auth
   parameter is the usual culprit.
4. **Try a different app version.** If 4.0.2 is old, the current release may
   point at a different host or a different path.
5. **Raw tcpdump on the host interface.** If the proxy is suspected of breaking
   the upgrade, capture the TLS session directly and see whether the 101 ever
   happens.

## Impact on the client

| Need | Workaround |
|------|-----------|
| Current price for a symbol | `market.snapshots()` — one call, every symbol |
| Index levels | `market.index_news()` |
| Price of one instrument | `market.statistics(symbol)` |
| Historical candles | `market.graph(symbol, count, interval)` |
| Alert on a price move | `AlertsClient` — server-side, fires independently |
| Tick-by-tick streaming | **Not available.** Poll on a timer and accept the latency |

For alerts, the server does the watching, so the missing tape costs nothing.
For anything that needs to react within a second of a price move, this is a real
limitation.
