# Capture Tool

`finqalab_capture.py` — a mitmproxy addon and a CLI in one file. It captures
Finqalab HTTP and WebSocket traffic into SQLite.

Source: [`tools/finqalab_capture.py`](tools/finqalab_capture.py) · Tool notes:
[`tools/README.md`](tools/README.md) · Why the obvious approach fails:
[01-capture-approach.md](01-capture-approach.md)

> ⚠️ **The database this writes contains live credentials, JWTs, CNIC and mobile
> numbers, IBANs, and order numbers.** `.gitignore` excludes `*.db`, but keep the
> output outside the repository. Delete it when you are done and change any
> password that landed in it.
>
> Only capture an account you own, on a device you control.

---

## Requirements

| Need | Why |
|------|-----|
| Rooted Android 7+ emulator | `iptables` DNAT needs root; API 24+ ignores user-installed CAs |
| **Bridged** network mode | The device must reach the host IP directly, with no NAT layer |
| mitmproxy 11+ | `connection_strategy=lazy` and the `tls_clienthello` hook API |
| adb on `PATH`, or Nox's | Device control |
| The app installed | Traffic source |
| An account you own | Yours to risk, not the library's |

## Running it

```bash
# Full pipeline: proxy + DNAT + app relaunch + record + teardown
python doc/reverse/tools/finqalab_capture.py --duration 300

# Keep the database outside the repository
set FINQALAB_DB=D:\captures\finqalab.db
python doc/reverse/tools/finqalab_capture.py --duration 300
```

Then walk the app while it records: log in, open the watchlist, open a stock,
open portfolio, place a small order. Every screen is a different set of
endpoints.

## Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--duration N` | — | Stop after N seconds. Default waits for Enter |
| `--device` | `127.0.0.1:62001` | ADB serial |
| `--adb` | `adb` | adb binary; falls back to Nox's copy |
| `--package` | `com.mobile.finqalab` | App package |
| `--uid` | `10044` | App UID for the DNAT owner match |
| `--host-ip` | auto-detected | Host IP reachable from the emulator |
| `--port` | `8443` | Proxy listen port |
| `--db` | `finqalab_capture.db` | SQLite output path |
| `--mitmdump` | auto-detected | Path to `mitmdump` |
| `--listen-only` | off | Proxy + recorder only; no adb, no DNAT |
| `--insecure` | off | Pass `--ssl-insecure` to mitmdump |

`--listen-only` is for a device you have already configured by hand — it starts
mitmdump and the recorder and leaves the emulator alone.

## What it does

1. Resolves adb, checks the device is reachable and rooted.
2. Reads the emulator IPs and finds a host IP on the same subnet, falling back
   to the gateway.
3. Starts `mitmdump` in reverse mode on `dummy.invalid` with
   `connection_strategy=lazy`, using itself as the addon.
4. Waits for the port, then checks the emulator can actually reach it — the
   Windows firewall is the usual culprit.
5. Clears the Android system proxy and force-stops any competing VPN
   interceptor, which would otherwise fight the DNAT.
6. Installs the iptables DNAT rule scoped to the app's UID, verifies
   reachability, relaunches the app.
7. Records until Enter or `--duration`, printing progress every 3 seconds.
8. Removes the DNAT rule and stops mitmdump.

Teardown is in a `finally` block, so a crash or Ctrl-C does not leave a
redirect rule behind on the device.

## Database

`FINQALAB_DB` or `--db` sets the path. Three tables:

```sql
runs(id, started_at, ended_at)

http_flows(id, run_id, timestamp, method, scheme, host, port, path,
           http_version, tls_version, sni, is_websocket,
           request_headers, request_body, request_size,
           response_status, response_reason, response_headers,
           response_body, response_size, error)

ws_messages(id, run_id, flow_id, timestamp, direction, opcode, content, size)
```

`http_flows` upserts on request and again on response, so an interrupted flow
still has its request half. `ws_messages.direction` is `C->S` or `S->C`.

Bodies are clipped at 2 MB. Binary bodies are stored as `base64:<data>` rather
than mangled into invalid text.

## Querying

```sql
-- Every request in order
SELECT timestamp, method, host, path, response_status
FROM http_flows ORDER BY timestamp;

-- Just the broker API
SELECT method, path, response_status, response_size
FROM http_flows WHERE host LIKE '%nextcapital%' ORDER BY timestamp;

-- WebSocket frames
SELECT timestamp, direction, content FROM ws_messages ORDER BY timestamp;

-- The STOMP CONNECT frame -- shows the auth mechanism
SELECT content FROM ws_messages WHERE content LIKE '%CONNECT%';

-- Flows that got no response -- where the 503s live
SELECT host, path, response_status, error FROM http_flows
WHERE response_status IS NULL;
```

From the shell:

```bash
sqlite3 finqalab_capture.db "SELECT method, path, response_status FROM http_flows;"
```

`mitmdump -nr flows.mitm` also works if you saved one with `-w`, but SQLite is
better: it is queryable, and the WebSocket frames are already split out by
direction.

## As a bare addon

Same file, against a device you have already DNAT'd:

```bash
mitmdump --mode reverse:https://dummy.invalid \
         --listen-host 0.0.0.0 --listen-port 8443 \
         --set connection_strategy=lazy \
         -s doc/reverse/tools/finqalab_capture.py
```

The SNI router uses a hardcoded `SNI_ROUTES` dict plus suffix matching on
`finqalab.com`, `nextcapital.com.pk`, and `capitalstake.com`. Unrouted hosts log
`[sni-route] NOT ROUTED` — add them to the dict.

## Troubleshooting

| Message | Cause and fix |
|---------|---------------|
| `device not reachable over adb` | Emulator not running, or `adb connect 127.0.0.1:62001` |
| `aborting: iptables DNAT needs root` | `adb root` failed — the image is not rooted the way this needs |
| `the emulator cannot reach host:8443` | Windows firewall. See below, or switch to bridged mode and pass `--host-ip` |
| `could not determine a host IP` | Same-subnet detection failed. Pass `--host-ip` |
| `proxy did not come up` | Check `finqalab_capture.log` next to the script. Usually a bad `--mitmdump` path |
| `getaddrinfo failed` on every connection | `connection_strategy=lazy` missing. The script sets it; do not forget it when running mitmdump by hand |
| `[sni-route] NOT ROUTED` | A new host. Add it to `SNI_ROUTES` |
| Capture is full of analytics, no API | DNAT is not matching. Check the packet counter grows, and force-stop the app so it opens fresh connections |
| Nothing after an emulator reboot | Nox wipes NAT rules on reboot. Re-run |

Firewall:

```powershell
netsh advfirewall firewall add rule name="mitmproxy8443" dir=in action=allow protocol=TCP localport=8443
```

## Safety

* Only on an account you own, on a device you control. Nothing here circumvents
  an access control — the account is logged into normally and the network path
  is observed.
* Captures contain live credentials and personal data. Store them outside the
  repository, delete them when done, and rotate any password that appears.
* Placing a real order to observe the trading flow is **your** decision, on
  **your** account, at **your** risk. The tool does not place orders itself.

Next: [08-live-data-gap.md](08-live-data-gap.md)
