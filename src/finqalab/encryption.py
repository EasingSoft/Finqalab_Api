"""AES-256-CBC helpers for the fields the app encrypts.

Several sensitive values are not sent or returned in the clear:

* **Outbound** - the login password is AES-encrypted before it is posted to
  ``/v1/loginV3``.
* **Inbound** - ``trading_pin_code``, ``mobileNo``, ``cnic`` and ``ibn_number``
  come back from the API as base64 ciphertext and the app decrypts them before
  showing them.

The scheme is fixed AES-256-CBC with PKCS7 padding and base64 output:

* key  - 32 bytes, hardcoded in the app
* iv   - 16 bytes, also hardcoded (fixed IV, not per-request)
* out  - ``base64(AES-256-CBC-PKCS7(utf8(plaintext)))``

The constants below are the app's own. Because the scheme is symmetric and the
key is static, *any* ciphertext produced by the app can be decrypted with them,
and vice versa. See ``doc/reverse/02-app-internals.md`` for the full write-up
and ``SECURITY.md`` for the disclosure note.

The trading WebSocket is unaffected: its STOMP ``CONNECT`` frame carries the
password in plaintext (see :mod:`finqalab.stomp`).
"""

from __future__ import annotations

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 32 bytes -> AES-256
KEY = b"58732oc71hdd8d390df44aceaf051056"
# 16 bytes, fixed (not regenerated per request)
IV = b"905820c31fdd8d39"


def encrypt_password(password: str) -> str:
    """Encrypt ``password`` for transport.

    Returns ``base64(AES-256-CBC-PKCS7(utf8(password)))``.
    """
    data = pad(password.encode("utf-8"), AES.block_size)
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return base64.b64encode(cipher.encrypt(data)).decode("ascii")


def decrypt_base64(b64: str) -> bytes:
    """Decrypt a base64 blob back to raw bytes."""
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return unpad(cipher.decrypt(base64.b64decode(b64)), AES.block_size)


def decrypt_text(b64: str) -> str:
    """Decrypt a base64 blob and return the UTF-8 plaintext."""
    return decrypt_base64(b64).decode("utf-8")


def decrypt_field(b64: str) -> str:
    """Alias of :func:`decrypt_text`, kept for readability at call sites."""
    return decrypt_text(b64)
