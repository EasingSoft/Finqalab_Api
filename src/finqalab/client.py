"""REST API client (``staticapis.nextcapital.com.pk``).

Auth flow (mirrors ``helpers/api_manager.dart`` + ``helpers/auth_controller.dart``):

1. ``POST /v1/appVersion/verify-version``  (form ``app_build=170``)
2. ``POST /v1/loginV3`` with ``password`` AES-encrypted
   * HTTP 207 ``{"msg":"Unauthorized"}``  -> device not verified; OTP email sent
   * ``verifyDeviceVerificationOTP`` then login again
   * HTTP 200 -> full profile + JWT ``token`` (``x-auth-token`` header)
3. Every authenticated call sends ``x-auth-token: <JWT>``.

The login password must be AES-encrypted with the app's fixed key (see
:mod:`finqalab.encryption`). If you already hold a valid JWT you can bypass
login entirely via ``FinqalabClient(token=...)``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

from .config import ACCEPT, API, API_BASE, APP_BUILD, CONTENT_TYPE, USER_AGENT
from .encryption import encrypt_password
from .utils import random_device_id, TokenStore, DEFAULT_TOKEN_PATH


class FinqalabError(Exception):
    pass


class LoginRequired(FinqalabError):
    """Login needs the device OTP (HTTP 207)."""


class FinqalabClient:
    def __init__(
        self,
        user_id: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        device_id: Optional[str] = None,
        session: Optional[requests.Session] = None,
        token_path: Optional[str] = DEFAULT_TOKEN_PATH,
    ):
        self.user_id = user_id
        self.password = password
        self.device_id = device_id or random_device_id()
        self.profile: Dict[str, Any] = {}
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "user-agent": USER_AGENT,
                "accept": ACCEPT,
                "accept-encoding": "gzip",
            }
        )
        self._store = TokenStore(token_path)

        if token is not None:
            self._token = token
        else:
            self._token = self._store.load()

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    # ----------------------------------------------------------- token disk
    def save_token(self) -> None:
        """Persist the current token to disk."""
        self._store.save(self._token, self.user_id)

    def clear_token(self) -> None:
        """Remove the saved token from disk."""
        self._token = None
        self._store.clear()

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {}
        if self._token:
            headers["x-auth-token"] = self._token
            headers["cookie"] = f"xauth={self._token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self, method: str, path: str, *, params=None, json_body=None,
        data=None, auth: bool = False, extra_headers: Optional[dict] = None
    ) -> requests.Response:
        url = API_BASE + path
        headers = {}
        if json_body is not None:
            headers["content-type"] = CONTENT_TYPE
        if auth:
            headers.update(self._headers())
        if extra_headers:
            headers.update(extra_headers)
        return self.session.request(
            method, url, params=params, json=json_body, data=data, headers=headers
        )

    # ------------------------------------------------------------------ auth
    def verify_version(self, app_build: int = APP_BUILD) -> Dict[str, Any]:
        resp = self._request(
            "POST", API["verify_version"], data={"app_build": app_build},
            extra_headers={"content-type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()

    def _encrypt_password(self) -> str:
        if not self.password:
            raise FinqalabError("no password set")
        return encrypt_password(self.password)

    def login(self, password: Optional[str] = None) -> Dict[str, Any]:
        """Full login. Raises :class:`LoginRequired` if the device is new and
        an OTP was emailed; call :meth:`verify_device_otp` then login again."""
        if password is not None:
            self.password = password
        body = {
            "id": self.user_id,
            "password": self._encrypt_password(),
            "device_token": "",
            "device_id": self.device_id,
            "os": "Android",
        }
        resp = self._request("POST", API["login_v3"], json_body=body)
        if resp.status_code == 207:
            raise LoginRequired(resp.json())
        resp.raise_for_status()
        data = resp.json()
        self.profile = data
        self._token = data.get("token")
        self.save_token()
        return data

    def verify_device_otp(self, otp: str, *, auth: bool = False) -> Dict[str, Any]:
        if not self.user_id:
            raise FinqalabError("user_id is required")
        body = {"user_id": self.user_id, "otp": otp, "device_id": self.device_id}
        resp = self._request("POST", API["verify_device_otp"], json_body=body, auth=auth)
        try:
            data = resp.json()
        except ValueError:
            data = {"_status": resp.status_code, "_text": resp.text}
        if resp.status_code >= 400:
            raise FinqalabError(f"OTP verify failed ({resp.status_code}): {data}")
        return data

    def user_detail(self) -> Dict[str, Any]:
        resp = self._request("GET", API["user_detail"], auth=True)
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------- misc
    def portfolio_day_start(self) -> Dict[str, Any]:
        resp = self._request("GET", API["portfolio_day_start"], auth=True)
        resp.raise_for_status()
        return resp.json()

    def multiday_toggle(self) -> bool:
        resp = self._request("GET", API["multiday_toggle"], auth=True)
        resp.raise_for_status()
        data = resp.json()
        return bool(data.get("data", {}).get("isMultidayToggle"))

    def custom_popups(self) -> Dict[str, Any]:
        resp = self._request("GET", API["custom_popups"], auth=True)
        resp.raise_for_status()
        return resp.json()

    def subscription_detail(self) -> Dict[str, Any]:
        resp = self._request("GET", API["subscription_detail"], auth=True)
        resp.raise_for_status()
        return resp.json()
