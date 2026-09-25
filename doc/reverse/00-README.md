# Reverse Engineering Notes

How the endpoint list in [`doc/api/04-api-reference.md`](../api/04-api-reference.md)
was established, and what is still unknown.

**Read this only if you need it.** To use the library, start at
[01-getting-started.md](../api/01-getting-started.md).

| Document | Contents |
|----------|----------|
| [01-capture-approach.md](01-capture-approach.md) | How the traffic was captured, and how to reproduce it |
| [02-app-internals.md](02-app-internals.md) | App structure, endpoints, and what the client does with each |
| [03-protocols.md](03-protocols.md) | Wire formats — REST, STOMP over SockJS, socket.io, AES |
| [04-findings-and-decisions.md](04-findings-and-decisions.md) | What was deliberately changed, and why |
| [05-known-gaps.md](05-known-gaps.md) | 22 known paths that are **not** implemented, and why |
| [06-endpoint-inventory.md](06-endpoint-inventory.md) | Every path seen, implemented or not |
| [07-capture-tool.md](07-capture-tool.md) | The capture script, how to run it |
| [08-live-data-gap.md](08-live-data-gap.md) | The socket.io live tape, and why it is missing |

---

## Scope and standing

* Target: **Finqalab Android v4.0.2**, `com.mobile.finqalab`, `versionCode` 170,
  a Flutter application. Upstream: Next Capital for SECP-regulated brokerage,
  U2 Ventures as publisher.
* Everything here comes from one account, one emulator, one capture run. The API
  is not documented by its owner, so treat every field name here as observed
  rather than specified — it can change without notice.
* **This is not affiliated with, endorsed by, or supported by Next Capital or
  Finqalab.** The AES key and IV shipped in `encryption.py` are their property,
  not this project's, and are disclosed in [`SECURITY.md`](../../SECURITY.md).
* All credentials, JWTs, CNIC and mobile numbers, IBANs, and order numbers found
  during capture were removed from this repository. Raw captures and the APK are
  untracked and never committed. Anything you capture from an account you own is
  your own data — do not publish it.
* Nothing here was obtained by circumventing an authentication control. The
  account was logged into normally, and the network path was observed on a
  device the researcher controlled.

## The one thing worth knowing up front

The app is **Flutter**, and Flutter's `dart:io` networking **ignores the Android
system proxy**. A standard mitmproxy setup captures only analytics noise. The
whole capture hinged on forcing the app's TCP traffic through a reverse proxy
with `iptables` DNAT on a rooted emulator, and on the mitmproxy flag
`connection_strategy=lazy`. Without that flag the proxy fails with
`getaddrinfo failed`. Details in [01-capture-approach.md](01-capture-approach.md).
