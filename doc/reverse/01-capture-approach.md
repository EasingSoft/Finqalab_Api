# Capture Approach

How the Finqalab traffic was intercepted, and how to reproduce it. This is the
single most useful file in this directory — the obvious method does not work.

> **Legal note.** Intercept traffic from an account you own, on a device you
> control. Nothing here circumvents an access control; the account is logged
> into normally. Captures contain your own credentials and personal data —
> never commit them.

---

## Why the obvious method fails

Finqalab is a **Flutter** app. Flutter's `dart:io` HTTP and WebSocket clients
**bypass the Android system proxy** (`settings put global http_proxy`).

The observed symptom: with mitmproxy on `:8080` and the system proxy pointed at
it, the capture filled up with Firebase, Crashlytics, Mixpanel, and Google
traffic — and **zero Finqalab API calls**. Anyone trying this will conclude the
API is unreachable, or that the app uses certificate pinning. Neither is true.
The traffic simply never touched the proxy.

Certificate pinning is a real possibility with Flutter's BoringSSL stack and
should be assumed, but it is not the first obstacle. The proxy is.

## Environment that worked

| Item | Value |
|------|-------|
| Emulator | Nox Player, Android 7.0 / SDK 25, **rooted** |
| ADB serial | `127.0.0.1:62001` |
| Network mode | **Bridged** — device and host on the same subnet |
| Host tools | mitmproxy 11.1.0 (`mitmdump`), Python 3.12, adb |
| App | `com.mobile.finqalab` v4.0.2, UID **10044** |
| Proxy port | `8443` (host side) |

**Bridged mode is important.** The device must be able to reach the host IP
directly, with no extra NAT layer in between, so the DNAT redirect resolves
cleanly. Nox's default NAT mode can work but needs more fighting.

Android 7.0 matters for the certificate: **apps ignore user-installed CAs** on
API 24+. The mitmproxy CA must be installed as a *system* cert. Rooting the
emulator and remounting `/system` is what makes that possible.

## The pipeline

```
app :443
  │  (iproute2 DNAT, filtered on --uid-owner 10044)
  ▼
host:8443  mitmdump, reverse mode, dummy.invalid
  │  (tls_clienthello hook: read SNI, set real upstream)
  ▼
staticapis.nextcapital.com.pk:443  (real TLS, MITM CA trusted)
```

Three parts, each of which was the thing that broke first.

---

## Step 1 — verify the environment

```bash
adb devices                                        # 127.0.0.1:62001 present
adb -s 127.0.0.1:62001 shell "su -c id"            # uid=0
adb -s 127.0.0.1:62001 shell getprop ro.product.cpu.abi
adb -s 127.0.0.1:62001 shell "dumpsys package com.mobile.finqalab | grep -iE 'versionName|versionCode'"
adb -s 127.0.0.1:62001 shell "dumpsys package com.mobile.finqalab | grep userId"
```

The **UID is the key number** — the DNAT rule filters on it, so the app's
traffic is redirected and everything else on the emulator is untouched. Get it
from `dumpsys`, do not guess it.

## Step 2 — install the mitmproxy CA as a system certificate

```bash
openssl x509 -inform PEM -subject_hash_old \
  -in ~/.mitmproxy/mitmproxy-ca-cert.pem -noout
# -> c8750f0d
```

Android names system CAs by the **first 4 hex digits of the SHA-1 fingerprint,
with `.0` appended** — the legacy `subject_hash_old` format. That is what the
`c8750f0d` output is for.

```bash
adb -s 127.0.0.1:62001 root
adb -s 127.0.0.1:62001 remount
adb -s 127.0.0.1:62001 push mitmproxy-ca-cert.pem \
  /system/etc/security/cacerts/c8750f0d.0
adb -s 127.0.0.1:62001 shell chmod 644 /system/etc/security/cacerts/c8750f0d.0
```

Verify: `adb shell ls /system/etc/security/cacerts/ | grep c8750f0d`.

If `remount` fails, the emulator image is not rooted the way you need — this is
the step most likely to need a different emulator.

## Step 3 — the SNI routing addon

mitmproxy reverse mode needs a target, but the app connects to six different
hostnames. Since the DNAT rewrites the destination to `host:8443`, mitmproxy
cannot tell them apart from the address — **only the SNI carries the real
hostname**. An addon reads the ClientHello and sets the upstream:

```python
from mitmproxy import tls, ctx

ROUTES = {
    "finqalab-oms-prod.finqalab.com": ("finqalab-oms-prod.finqalab.com", 443),
    "live-data.finqalab.com":           ("live-data.finqalab.com", 443),
    "cms-prod.finqalab.com":            ("cms-prod.finqalab.com", 443),
    "finbot.finqalab.com":              ("finbot.finqalab.com", 443),
    "staticapis.nextcapital.com.pk":    ("staticapis.nextcapital.com.pk", 443),
    "trade.nextcapital.com.pk":         ("trade.nextcapital.com.pk", 443),
    "aof-mobile.nextcapital.com.pk":    ("aof-mobile.nextcapital.com.pk", 443),
    "analytics.capitalstake.com":       ("analytics.capitalstake.com", 443),
}

def tls_clienthello(data: tls.ClientHelloData):
    sni = data.client_hello.sni
    if not sni:
        return
    target = ROUTES.get(sni)
    if not target:
        for suffix in ("finqalab.com", "nextcapital.com.pk", "capitalstake.com"):
            if sni.endswith("." + suffix):     # catch the rest by suffix
                target = (sni, 443)
                break
    if target:
        data.context.server.address = target
        data.context.server.sni = sni
    else:
        ctx.log.warn(f"[sni-route] NOT ROUTED: {sni}")
```

Routing by suffix matters. A hardcoded dictionary misses the next host the app
adds, and an unrouted host fails silently with an error rather than being
captured.

## Step 4 — start mitmdump with `connection_strategy=lazy`

**This flag is the whole trick.**

```bash
mitmdump \
  --mode reverse:https://dummy.invalid \
  --listen-host 0.0.0.0 --listen-port 8443 \
  --set connection_strategy=lazy \
  -s sni_routes.py
```

`dummy.invalid` is a deliberately unresolvable placeholder. In mitmproxy 11's
default `eager` mode, mitmproxy tries to resolve and connect **upstream before
the ClientHello arrives**. The SNI hook has not run yet, so the target is still
`dummy.invalid`, and every connection dies with:

```
[Errno 11001] getaddrinfo failed
```

`connection_strategy=lazy` defers the upstream connect until after the
ClientHello, so the hook has a chance to set the real destination. Without it
this whole approach does not work, and the error message gives no hint why.

Start it **detached**. A normal `Start-Process` with output redirection gets
killed when the shell times out:

```powershell
$r = ([wmiclass]"\\.\root\cimv2:Win32_Process").Create(
  'cmd.exe /c ""...\mitmdump.exe"
   --mode reverse:https://dummy.invalid
   --listen-host 0.0.0.0 --listen-port 8443
   --set connection_strategy=lazy
   -s C:\...\sni_routes.py
   -w C:\...\flows.mitm
   > C:\...\rp8443.log 2>&1"')
$r.ReturnValue     # 0 = ok
```

## Step 5 — DNAT the app's :443 traffic

```bash
adb -s 127.0.0.1:62001 shell "iptables -t nat -A OUTPUT -p tcp \
  -m owner --uid-owner 10044 --dport 443 \
  -j DNAT --to-destination 172.22.207.203:8443"
```

Verify the counter moves — this is the check that tells you the rule is live:

```bash
adb -s 127.0.0.1:62001 shell "iptables -t nat -L OUTPUT -n -v | grep 10044"
```

A zero packet count means the app has not made a new connection yet. Force one
by restarting the app.

`-m owner --uid-owner` is what keeps this surgical: only the Finqalab process
is redirected, so nothing else on the emulator is affected.

The host firewall also has to allow inbound 8443:

```powershell
netsh advfirewall firewall add rule name="mitmproxy8443" dir=in action=allow protocol=TCP localport=8443
```

## Step 6 — remove competing interceptors

Two things will fight the DNAT if left in place:

```bash
adb -s 127.0.0.1:62001 shell "settings put global http_proxy :0"
adb -s 127.0.0.1:62001 shell "am force-stop tech.httptoolkit.android.v1"
```

* The **Android system proxy** must be off. Native SDKs inside the app split
  traffic between the old proxy and the DNAT path, and you get a partial,
  confusing capture.
* **HTTP Toolkit** and similar VPN-based interceptors create a `tun0` device
  that hijacks the same packets. Two interceptors at once means neither works.

HTTP Toolkit alone *does* work for this app — its VPN mode intercepts Flutter
traffic without DNAT. It was not used here only because it is GUI-driven and
awkward to script flow extraction from.

## Step 7 — relaunch and interact

```bash
adb -s 127.0.0.1:62001 shell "am force-stop com.mobile.finqalab"
adb -s 127.0.0.1:62001 shell "monkey -p com.mobile.finqalab -c android.intent.category.LAUNCHER 1"
```

Long-lived connections (the trading socket) are established at launch, so a
force-stop is **required** after installing the DNAT rule — otherwise the app
keeps using its existing direct connections and nothing is captured.

Then walk the app: log in, open the watchlist, open a stock, open portfolio,
place a small order. Each screen is a different set of endpoints.

## Step 8 — read the capture

Everything is automated by [`finqalab_capture.py`](tools/finqalab_capture.py),
which does all of the above and writes SQLite. See
[07-capture-tool.md](07-capture-tool.md).

Ad-hoc read:

```bash
mitmdump -nr flows.mitm | tail -40
```

---

## What got captured

**HTTP — fully decrypted, 200 OK, with request and response bodies:**

* `POST /v1/appVersion/verify-version`
* `POST /v1/loginV3` — AES-encrypted password, and the 207 OTP branch
* `POST /v1/verifyDeviceVerificationOTP`
* `GET /v1/userDetailV2` — profile, `x-auth-token`, encrypted PIN/CNIC/mobile/IBAN
* `GET /v1/subscription/subscription-detail`
* `GET /v1/multiday-toggle`, `/v1/custom_popups`, `/v1/portfolio-day-start`
* `GET /v1/marketSnapshot/summaryV2` — 425 KB, every symbol
* `GET /v1/snapshot/index_news`
* `GET /v1/snapshot/detail/{statistics,company,financial,graph}`
* `GET /v1/news?page=0&type=N`
* `GET /v1/watchlist/read?sortBy=custom` — 50.6 KB
* `GET /v1/watchlist/create`
* `GET /v1/alert_permission/{byUserId,history}`, `POST /v1/alert_permission`
* `GET /v1/deposit_amount/usersDepositHistoryV2`, `GET /v1/withdrawal`
* `GET /v1/withdrawal/{getBankCodeList,getAllAccounts}`
* `POST /v1/generate{PeriodicDetails,CashBook}PDF`
* `POST` `finqalab-oms-prod.finqalab.com/api/trade-intimation`
* `wss://trade.nextcapital.com.pk/order-dispatch-websocket/...` — **STOMP frames,
  fully readable**, including the `CONNECT` frame with the plaintext password

**Not captured:** the socket.io live tape on `live-data.finqalab.com` — see
[08-live-data-gap.md](08-live-data-gap.md).

The trading socket being readable is the significant result. It gave the STOMP
topic structure, the order body shape, and the confirmation format directly
rather than by inference.

---

## Gotchas

1. **Flutter ignores the system proxy.** The headline. Everything else is
   downstream of this.
2. **`connection_strategy=lazy` is mandatory** in mitmproxy 11 reverse mode with
   SNI routing, or everything fails with a misleading DNS error.
3. **Never run two interceptors.** DNAT and a VPN-based tool will fight.
4. **Nox reboots wipe the iptables NAT rules** and kill frida-server. Re-add the
   DNAT rule after every reboot.
5. **Force-stop the app after installing the rule.** Long-lived sockets are
   established at launch and will not be re-resolved otherwise.
6. **A frida-based BoringSSL hook was abandoned** — it crashed the emulator.
   The MITM CA route needs no runtime patching.
7. **MitmCA trust is a system-cert problem, not a pinning problem.** On API 24+,
   user CAs are ignored by apps; install to `/system` as above.
8. **Bridged networking, not NAT.** The device must reach the host IP directly.

## Reproducing from scratch

You need: a rooted Android 7+ emulator, mitmproxy 11+, the app, and an account
you own. Then:

```bash
python doc/reverse/tools/finqalab_capture.py --duration 300
```

It handles the CA check, the proxy, the DNAT, the app relaunch, recording, and
teardown. Set `FINQALAB_DB` to control the output path — and keep the output
out of version control. `.gitignore` excludes `*.db`.
