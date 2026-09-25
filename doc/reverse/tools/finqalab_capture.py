"""Finqalab traffic capture - one script, two roles.

As a mitmproxy addon (-s finqalab_capture.py):
    routes upstream TLS by SNI (reverse proxy mode) and records every HTTP
    flow + WebSocket message into SQLite.

As a CLI (python finqalab_capture.py):
    starts mitmdump with this file as addon, installs the iptables DNAT that
    forces the app's :443 traffic through it, relaunches the app, waits, then
    tears everything down.
"""

import argparse
import base64
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    from mitmproxy import http, tls
    from mitmproxy import ctx
except Exception:
    http = tls = ctx = None

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DB = SCRIPT_DIR / "finqalab_capture.db"
DEFAULT_MITMDUMP = r"C:\Users\ali\AppData\Local\Programs\Python\Python312\Scripts\mitmdump.exe"

SNI_ROUTES = {
    "finqalab-oms-prod.finqalab.com": ("finqalab-oms-prod.finqalab.com", 443),
    "live-data.finqalab.com": ("live-data.finqalab.com", 443),
    "cms-prod.finqalab.com": ("cms-prod.finqalab.com", 443),
    "finbot.finqalab.com": ("finbot.finqalab.com", 443),
    "staticapis.nextcapital.com.pk": ("staticapis.nextcapital.com.pk", 443),
    "trade.nextcapital.com.pk": ("trade.nextcapital.com.pk", 443),
    "aof-mobile.nextcapital.com.pk": ("aof-mobile.nextcapital.com.pk", 443),
    "analytics.capitalstake.com": ("analytics.capitalstake.com", 443),
}

ROUTE_SUFFIXES = [
    "finqalab.com",
    "nextcapital.com.pk",
    "capitalstake.com",
    "googleapis.com",
    "google.com",
    "gstatic.com",
    "appmeasurements.com",
]

MAX_BODY = 2_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS http_flows (
    id TEXT PRIMARY KEY,
    run_id INTEGER,
    timestamp TEXT,
    method TEXT,
    scheme TEXT,
    host TEXT,
    port INTEGER,
    path TEXT,
    http_version TEXT,
    tls_version TEXT,
    sni TEXT,
    is_websocket INTEGER DEFAULT 0,
    request_headers TEXT,
    request_body TEXT,
    request_size INTEGER,
    response_status INTEGER,
    response_reason TEXT,
    response_headers TEXT,
    response_body TEXT,
    response_size INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS ws_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    flow_id TEXT,
    timestamp TEXT,
    direction TEXT,
    opcode TEXT,
    content TEXT,
    size INTEGER
);
CREATE INDEX IF NOT EXISTS idx_http_run ON http_flows(run_id);
CREATE INDEX IF NOT EXISTS idx_ws_flow ON ws_messages(flow_id);
"""


def _now(ts=None):
    if ts is None:
        ts = time.time()
    try:
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")
    except Exception:
        return None


def _clip(text):
    if text and len(text) > MAX_BODY:
        return text[:MAX_BODY] + "\n...[truncated]..."
    return text


def _body_text(message):
    try:
        text = message.get_text(strict=False)
        if text is None:
            return "base64:" + base64.b64encode(message.raw_content or b"").decode()
        return _clip(text)
    except Exception:
        return "base64:" + base64.b64encode(message.raw_content or b"").decode()


def _headers_json(headers):
    pairs = []
    for name, value in headers.fields:
        pairs.append((name.decode("latin-1", "replace"), value.decode("latin-1", "replace")))
    return json.dumps(pairs)


class SniRouter:
    def tls_clienthello(self, data: tls.ClientHelloData):
        sni = data.client_hello.sni
        if not sni:
            return
        target = SNI_ROUTES.get(sni)
        if not target:
            for suffix in ROUTE_SUFFIXES:
                if sni.endswith("." + suffix):
                    target = (sni, 443)
                    break
        if target:
            data.context.server.address = target
            data.context.server.sni = sni
            ctx.log.info(f"[sni-route] {sni} -> {target[0]}:{target[1]}")
        else:
            ctx.log.warn(f"[sni-route] NOT ROUTED: {sni}")


class Recorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._conn = None
        self._run_id = None

    @property
    def db_path(self):
        return Path(os.environ.get("FINQALAB_DB", DEFAULT_DB))

    def _ensure(self):
        if self._conn is not None:
            return
        with self._lock:
            if self._conn is not None:
                return
            db = self.db_path
            db.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db), timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            cur = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (_now(),))
            self._run_id = cur.lastrowid
            conn.commit()
            self._conn = conn
            ctx.log.info(f"[finqalab] recording to {db} (run {self._run_id})")

    def _row(self, flow):
        req = flow.request
        host = getattr(req, "pretty_host", None) or req.host
        sc = flow.server_conn
        row = {
            "id": flow.id,
            "run_id": self._run_id,
            "timestamp": _now(getattr(flow, "timestamp_start", None)),
            "method": req.method,
            "scheme": req.scheme,
            "host": host,
            "port": req.port,
            "path": req.path,
            "http_version": getattr(req, "http_version", None),
            "tls_version": sc.tls_version if sc and getattr(sc, "tls_established", False) else None,
            "sni": sc.sni if sc else None,
            "is_websocket": 0,
            "request_headers": _headers_json(req.headers),
            "request_body": _body_text(req),
            "request_size": len(req.raw_content or b""),
            "response_status": None,
            "response_reason": None,
            "response_headers": None,
            "response_body": None,
            "response_size": None,
            "error": flow.error.msg if flow.error else None,
        }
        if flow.response:
            resp = flow.response
            row.update({
                "response_status": resp.status_code,
                "response_reason": resp.reason,
                "response_headers": _headers_json(resp.headers),
                "response_body": _body_text(resp),
                "response_size": len(resp.raw_content or b""),
                "is_websocket": 1 if (resp.headers.get("upgrade", "") or "").strip().lower() == "websocket" else 0,
            })
        return row

    def _upsert(self, row):
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
        sql = f"INSERT INTO http_flows ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}"
        self._conn.execute(sql, [row[c] for c in cols])
        self._conn.commit()

    def request(self, flow: http.HTTPFlow):
        try:
            self._ensure()
            self._upsert(self._row(flow))
        except Exception as e:
            ctx.log.error(f"[finqalab] request: {e}")

    def response(self, flow: http.HTTPFlow):
        try:
            self._ensure()
            self._upsert(self._row(flow))
        except Exception as e:
            ctx.log.error(f"[finqalab] response: {e}")

    def websocket_message(self, flow: http.HTTPFlow):
        try:
            self._ensure()
            ws = flow.websocket
            if not ws or not ws.messages:
                return
            msg = ws.messages[-1]
            if getattr(msg, "_finqalab_captured", False):
                return
            msg._finqalab_captured = True
            if msg.is_text:
                opcode, content = "Text", msg.text or ""
            else:
                opcode = "Binary"
                content = "base64:" + base64.b64encode(msg.content or b"").decode()
            self._conn.execute(
                "INSERT INTO ws_messages (run_id, flow_id, timestamp, direction, opcode, content, size) VALUES (?,?,?,?,?,?,?)",
                (self._run_id, flow.id, _now(getattr(msg, "timestamp", None)),
                 "C->S" if msg.from_client else "S->C", opcode, _clip(content), len(msg.content or b"")),
            )
            self._conn.execute("UPDATE http_flows SET is_websocket=1 WHERE id=?", (flow.id,))
            self._conn.commit()
        except Exception as e:
            ctx.log.error(f"[finqalab] websocket_message: {e}")


addons = []
if http is not None:
    addons = [SniRouter(), Recorder()]


def _run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


ADB_FALLBACKS = [
    r"C:\Program Files\Nox\bin\adb.exe",
    r"C:\Program Files (x86)\Nox\bin\adb.exe",
]


def resolve_adb(adb_bin):
    if Path(adb_bin).is_file():
        return str(Path(adb_bin).resolve())
    which = _run(["where", adb_bin])
    if which.returncode == 0 and which.stdout.strip():
        return which.stdout.strip().splitlines()[0]
    for candidate in ADB_FALLBACKS:
        if Path(candidate).is_file():
            return candidate
    return adb_bin


def adb(cfg, *cmd):
    return _run([cfg.adb, "-s", cfg.device, *cmd])


def adb_shell(cfg, cmd):
    return adb(cfg, "shell", cmd)


def ensure_device(cfg):
    for attempt in range(3):
        out = adb(cfg, "devices").stdout
        if cfg.device in out and "device" in out:
            return True
        if ":" in cfg.device:
            adb(cfg, "connect", cfg.device)
        time.sleep(2)
    return False


def ensure_root(cfg):
    out = adb_shell(cfg, "id")
    if "uid=0" in out.stdout or "root" in out.stdout:
        return True
    adb(cfg, "root")
    time.sleep(2)
    out = adb_shell(cfg, "id")
    return "uid=0" in out.stdout or "root" in out.stdout


def get_device_ips(cfg):
    ips = []
    for line in adb_shell(cfg, "ip -o addr").stdout.splitlines():
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
        if m and not m.group(1).startswith("127."):
            ips.append(m.group(1))
    if not ips:
        for line in adb_shell(cfg, "ifconfig").stdout.splitlines():
            m = re.search(r"inet addr:(\d+\.\d+\.\d+\.\d+)", line)
            if m and not m.group(1).startswith("127."):
                ips.append(m.group(1))
    return ips


def get_gateway(cfg):
    out = adb_shell(cfg, "ip route show table all").stdout
    m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def host_reachable(cfg, host, port):
    r = adb_shell(cfg, f"nc -w 3 {host} {port} </dev/null >/dev/null 2>&1 && echo OK")
    return "OK" in r.stdout


def _ip_int(ip):
    parts = [int(x) for x in ip.split(".")]
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def find_host_ip(device_ip):
    r = _run(["ipconfig"])
    if r.returncode != 0:
        return None
    for block in re.split(r"\r?\n\r?\n", r.stdout):
        ipm = re.search(r"IPv4 Address[^:]*:\s*([\d.]+)", block)
        maskm = re.search(r"Subnet Mask[^:]*:\s*([\d.]+)", block)
        if not ipm or not maskm:
            continue
        host_ip, mask = ipm.group(1), maskm.group(1)
        if (_ip_int(device_ip) & _ip_int(mask)) == (_ip_int(host_ip) & _ip_int(mask)):
            return host_ip
    return None


def dnat_rule(cfg, action):
    return (f"iptables -t nat {action} OUTPUT -p tcp -m owner --uid-owner {cfg.uid} "
            f"--dport 443 -j DNAT --to-destination {cfg.host_ip}:{cfg.port}")


def setup_dnat(cfg):
    adb_shell(cfg, dnat_rule(cfg, "-D"))
    r = adb_shell(cfg, dnat_rule(cfg, "-A"))
    return r.returncode == 0


def clear_dnat(cfg):
    adb_shell(cfg, dnat_rule(cfg, "-D"))


def relaunch_app(cfg):
    adb_shell(cfg, f"am force-stop {cfg.package}")
    time.sleep(1)
    adb_shell(cfg, f"monkey -p {cfg.package} -c android.intent.category.LAUNCHER 1")


def start_proxy(cfg, db_path, script_path):
    log = open(SCRIPT_DIR / "finqalab_capture.log", "w", encoding="utf-8")
    cmd = [
        cfg.mitmdump,
        "--mode", "reverse:https://dummy.invalid",
        "--listen-host", "0.0.0.0",
        "--listen-port", str(cfg.port),
        "--set", "connection_strategy=lazy",
        "-s", str(script_path),
    ]
    if cfg.insecure:
        cmd.append("--ssl-insecure")
    env = dict(os.environ)
    env["FINQALAB_DB"] = str(db_path)
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def wait_port(port, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), 1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def summarize(db_path):
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        flows = conn.execute("SELECT COUNT(*) FROM http_flows").fetchone()[0]
        ws = conn.execute("SELECT COUNT(*) FROM ws_messages").fetchone()[0]
        conn.close()
        return flows, ws
    except Exception:
        return 0, 0


def _poll(stop, db_path):
    last = -1
    while not stop.is_set():
        try:
            flows, ws = summarize(db_path)
            if flows != last:
                print(f"    ... {flows} http flows, {ws} ws messages")
                last = flows
        except Exception:
            pass
        time.sleep(3)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="finqalab_capture.py",
        description="Capture Finqalab app HTTP + WebSocket traffic into SQLite.",
        epilog=(
            "Pipeline: start mitmdump (reverse SNI proxy, connection_strategy=lazy) -> "
            "iptables DNAT the app's :443 traffic to it -> relaunch app -> record -> clean up.\n"
            "Press Enter (or use --duration) to stop.\n"
            "Use --listen-only to run the proxy + recorder without touching the emulator."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--adb", default="adb", help="adb binary (default: adb)")
    p.add_argument("--device", default="127.0.0.1:62001", help="adb device serial (default: 127.0.0.1:62001)")
    p.add_argument("--package", default="com.mobile.finqalab", help="app package (default: com.mobile.finqalab)")
    p.add_argument("--uid", default="10044", help="app uid for iptables owner match (default: 10044)")
    p.add_argument("--host-ip", default=None, help="host IP reachable from the emulator (auto-detected if omitted)")
    p.add_argument("--port", type=int, default=8443, help="local proxy listen port (default: 8443)")
    p.add_argument("--db", default=None, help="sqlite output file (default: finqalab_capture.db next to this script)")
    p.add_argument("--mitmdump", default=DEFAULT_MITMDUMP, help="path to mitmdump")
    p.add_argument("--duration", type=int, default=None, help="stop automatically after N seconds")
    p.add_argument("--listen-only", action="store_true", help="only run proxy + recorder, skip adb/iptables/app")
    p.add_argument("--insecure", action="store_true", help="pass --ssl-insecure to mitmdump")
    return p.parse_args(argv)


def main(argv=None):
    cfg = parse_args(argv)
    cfg.adb = resolve_adb(cfg.adb)
    if not Path(cfg.adb).is_file():
        print(f"[!] adb not found (tried PATH and Nox). Pass --adb <path to adb.exe>")
    script_path = Path(__file__).resolve()
    db_path = Path(cfg.db).resolve() if cfg.db else DEFAULT_DB

    if not Path(cfg.mitmdump).exists():
        print(f"[!] mitmdump not found: {cfg.mitmdump}")

    if not cfg.listen_only:
        print(f"[*] device: {cfg.device}")
        if not ensure_device(cfg):
            print("[!] device not reachable over adb. Is the emulator running? Try:")
            print(f"    {cfg.adb} connect {cfg.device}")
            return 1
        root = ensure_root(cfg)
        print(f"[*] root: {'yes' if root else 'NO - DNAT will likely fail'}")
        if not root:
            print("[!] aborting: iptables DNAT needs root on the device")
            return 1
        dev_ips = get_device_ips(cfg)
        print(f"[*] emulator IPs: {', '.join(dev_ips) if dev_ips else 'none'}")
        if not cfg.host_ip:
            cfg.host_ip = None
            for ip in dev_ips:
                host = find_host_ip(ip)
                if host:
                    cfg.host_ip = host
                    break
            if not cfg.host_ip:
                gw = get_gateway(cfg)
                if gw:
                    cfg.host_ip = gw
                    print("[*] no host subnet match; using device gateway as host target")
            if not cfg.host_ip:
                print("[!] could not determine a host IP reachable from the device")
                print("[!] use --host-ip <ip> or switch the emulator to bridged mode")
                return 1
        print(f"[*] DNAT target: {cfg.host_ip}:{cfg.port}")

    print(f"[*] starting mitmdump -> sqlite: {db_path}")
    proc = start_proxy(cfg, db_path, script_path)
    try:
        if not wait_port(cfg.port):
            print("[!] proxy did not come up; check finqalab_capture.log")
            proc.terminate()
            return 1

        if not cfg.listen_only:
            if not host_reachable(cfg, cfg.host_ip, cfg.port):
                print("[!] the emulator cannot reach host:8443")
                print("[!] check the host firewall allows inbound 8443, e.g.:")
                print('    netsh advfirewall firewall add rule name="mitmproxy8443" dir=in action=allow protocol=TCP localport=8443')
                print("[!] or use --host-ip <ip reachable from the emulator> / bridged network mode")
                proc.terminate()
                return 1
            adb_shell(cfg, "settings put global http_proxy :0")
            if setup_dnat(cfg):
                print("[*] iptables DNAT installed")
            else:
                print("[!] iptables DNAT failed (root?)")
            relaunch_app(cfg)
            print("[*] app relaunched - capturing")

        print("[*] press Enter to stop, or wait for --duration")
        stop = threading.Event()
        t = threading.Thread(target=_poll, args=(stop, db_path), daemon=True)
        t.start()
        try:
            if cfg.duration:
                time.sleep(cfg.duration)
            else:
                input()
        finally:
            stop.set()
            t.join(timeout=2)
    except KeyboardInterrupt:
        pass
    finally:
        if not cfg.listen_only:
            clear_dnat(cfg)
            print("[*] iptables DNAT removed")
        print("[*] stopping mitmdump ...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        flows, ws = summarize(db_path)
        print(f"[*] done. http_flows={flows}, ws_messages={ws}")
        print(f"[*] db: {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
