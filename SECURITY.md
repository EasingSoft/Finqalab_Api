# Security Policy

## Supported versions

Only the latest released version receives fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x | yes |

## Reporting a vulnerability

Open a GitHub issue on
[EasingSoft/Finqalab_Api](https://github.com/EasingSoft/Finqalab_Api/issues)
for anything that affects account safety. Please do not include live tokens,
client codes, passwords, or account numbers in the report.

---

## Disclosure: encryption keys are in this repository

This project implements the app's authentication scheme, which means it ships
constants that are **secrets belonging to Next Capital / U2 Ventures** rather
than to this project:

| Constant | File | What it is |
|----------|------|------------|
| `KEY` | `src/finqalab/encryption.py` | Static 32-byte AES-256 key the app uses for password, trading PIN, CNIC, and mobile fields |
| `IV` | `src/finqalab/encryption.py` | Static 16-byte IV for the same |

Because the scheme is symmetric with a fixed key and a fixed IV, these are not
a security measure — anyone holding them can encrypt or decrypt these fields.
They are published here so the client works out of the box.

Consequences worth being explicit about:

* **Do not treat this transport as confidential.** Passwords travel as
  AES-CBC under a public key. The protection in transit is TLS, and only TLS.
* **A fixed IV is cryptographically weak.** Identical plaintexts produce
  identical ciphertexts. Do not reuse this construction for anything of your
  own.
* **Anything encrypted with this key is effectively public.** Never paste a
  ciphertext produced by the app into a public issue, a log, or a screenshot.

If you are the rights holder for this scheme and want it removed, open an
issue or email the maintainers and it will be taken out.

## Credential hygiene

* Keep credentials in environment variables or a secret manager. Never commit
  them, and never pass them on a command line where they land in shell history.
* This repository's `.gitignore` excludes `*.db`, `*.apk`, `*.pptx`, images,
  `.env`, and `.finqalab_token`. Raw traffic captures and app binaries are
  deliberately untracked — they contain live tokens, CNIC and mobile numbers,
  IBANs, and plaintext passwords. Keep them out of version control.
* `~/.finqalab_token` holds a 28-day JWT. Delete it when you are done:
  `FinqalabClient(user_id="...").clear_token()`.
* Rotate any password that has ever been pasted into a file, a chat, or a
  commit.

## Trading risk

`finqalab.order` sends real orders to the exchange. There is no paper-trading
mode and no test environment. Validate on small size first, and treat any
order-placement automation you build as production software.
