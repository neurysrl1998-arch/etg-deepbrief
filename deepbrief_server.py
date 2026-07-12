# -*- coding: utf-8 -*-
"""
ETG DEEPBRIEF — El periódico del trading en vivo
Agente investigador: noticias geopolíticas + mercados + calendario + alertas de impacto.
Nada habla. Todo visual. Todo local.
"""
import os, re, sys, json, time, base64, hashlib, threading, traceback, subprocess, webbrowser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET

import requests, feedparser
from flask import Flask, jsonify, request, send_from_directory

# ------------------------------------------------------------------ config
if getattr(sys, "frozen", False):          # corriendo como .exe (PyInstaller)
    APP_DIR  = sys._MEIPASS                 # recursos empaquetados (dashboard.html)
    DATA_DIR = os.path.dirname(sys.executable)  # settings junto al .exe
else:
    APP_DIR  = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = APP_DIR
PORT      = 8765
NY        = ZoneInfo("America/New_York")
UTC       = timezone.utc
UA        = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

POLL_NEWS_SEC   = 45     # ciclo de investigación de noticias
POLL_QUOTES_SEC = 20     # ciclo de futuros
POLL_META_SEC   = 300    # calendario + fear&greed
MAX_ITEMS       = 900
KEEP_HOURS      = 48

APP_VERSION = "3.3.0"
GH_REPO     = "neurysrl1998-arch/etg-deepbrief"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{GH_REPO}/main/version.json"

def ver_tuple(v):
    try:
        return tuple(int(x) for x in re.findall(r'\d+', str(v))[:3])
    except Exception:
        return (0,)

def gnews(q):
    from urllib.parse import quote
    return f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en"

# (id, nombre, url, categoría_por_defecto, peso_fuente)
FEEDS = [
    ("gn_iran",    "Google News · Irán",      gnews('Iran when:1d'),                          "geo",     8),
    ("gn_mideast", "Google News · M.Oriente", gnews('Israel OR Hormuz OR Tehran when:1d'),    "geo",     6),
    ("gn_trump",   "Google News · Trump",     gnews('"Donald Trump" when:1d'),                "trump",   7),
    ("gn_fed",     "Google News · Fed",       gnews('"Federal Reserve" OR Powell OR FOMC when:1d'), "fed", 7),
    ("gn_futures", "Google News · Futuros",   gnews('"stock futures" OR Nasdaq when:1d'),     "markets", 6),
    ("gn_oil",     "Google News · Energía",   gnews('"oil prices" OR OPEC when:1d'),          "energy",  5),
    ("aljazeera",  "Al Jazeera",              "https://www.aljazeera.com/xml/rss/all.xml",    "geo",     6),
    ("bbc",        "BBC World",               "https://feeds.bbci.co.uk/news/world/rss.xml",  "geo",     6),
    ("cnbc",       "CNBC",                    "https://www.cnbc.com/id/100003114/device/rss/rss.html", "markets", 7),
    ("mw",         "MarketWatch RT",          "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/", "markets", 7),
    ("zh",         "ZeroHedge",               "https://feeds.feedburner.com/zerohedge/feed",  "markets", 5),
    ("fxstreet",   "FXStreet",                "https://www.fxstreet.com/rss/news",            "fed",     4),
    ("reddit",     "Reddit r/worldnews",      "https://www.reddit.com/r/worldnews/new/.rss",  "geo",     5),
]

QUOTE_SYMBOLS = [
    ("NQ=F",     "NASDAQ",   "NQ"),
    ("ES=F",     "S&P 500",  "ES"),
    ("YM=F",     "DOW",      "YM"),
    ("GC=F",     "ORO",      "GC"),
    ("CL=F",     "PETRÓLEO", "CL"),
    ("SI=F",     "PLATA",    "SI"),
    ("^VXN",     "VXN N-100","VXN"),
    ("DX-Y.NYB", "DXY",      "DXY"),
    ("^TNX",     "10Y",      "10Y"),
    ("BTC-USD",  "BITCOIN",  "BTC"),
    ("EURUSD=X", "EUR/USD",  "EUR"),
]

# ------------------------------------------------------------------ scoring
GEO_ACTORS  = re.compile(r'\b(iran|iranian|tehran|israel|israeli|hormuz|khamenei|hezbollah|houthi|gaza|russia|ukraine|china|taiwan|north korea|middle east)\b', re.I)
GEO_ACTION  = re.compile(r'\b(strike|strikes|struck|attack|attacks|attacked|missile|missiles|drone|bomb|bombing|bombed|explosion|nuclear|war|invasion|invades|retaliat|assassinat|killed|casualties|escalat|mobiliz|troops|warship|sanction|closure|closes?|closed|blockade|blocks?|shut|seiz\w*|threat\w*|ultimatum|evacuat\w*)\b', re.I)
FED_WORDS   = re.compile(r'\b(fed|fomc|powell|federal reserve|rate cut|rate hike|interest rate|cpi|inflation|nfp|payrolls|jobs report|pce|gdp|treasury|yields?)\b', re.I)
TRUMP_WORDS = re.compile(r'\b(trump|white house|tariff|tariffs|truth social|executive order)\b', re.I)
ENERGY_WORDS= re.compile(r'\b(oil|crude|brent|wti|opec|natural gas|gasoline)\b', re.I)
CRYPTO_WORDS= re.compile(r'\b(bitcoin|btc|ethereum|crypto|binance|coinbase)\b', re.I)
MARKET_WORDS= re.compile(r'\b(nasdaq|s&p|dow|futures|stocks?|wall street|earnings|sell-?off|rally|correction|bear market|bull market)\b', re.I)
URGENT      = re.compile(r'\b(breaking|urgent|just in|alert|emergency|halt|halted|crash|plunge|soar|record high|record low)\b', re.I)
SEVERE      = re.compile(r'\b(declares? war|state of emergency|nuclear weapon|direct attack|major escalation|circuit breaker|market halt|assassination)\b', re.I)

def classify(title, default_cat):
    t = title or ""
    score, cat = 0, default_cat
    geo_a, geo_x = bool(GEO_ACTORS.search(t)), bool(GEO_ACTION.search(t))
    if geo_a and geo_x: score += 60; cat = "geo"
    elif geo_a:         score += 18; cat = "geo"
    elif geo_x:         score += 10
    if TRUMP_WORDS.search(t):
        score += 20; cat = "trump" if cat not in ("geo",) else cat
        if geo_x or URGENT.search(t): score += 20
    if FED_WORDS.search(t):
        score += 22
        if cat not in ("geo", "trump"): cat = "fed"
    if ENERGY_WORDS.search(t):
        score += 12
        if cat == default_cat and cat not in ("geo",): cat = "energy"
    if CRYPTO_WORDS.search(t) and cat == default_cat: cat = "crypto"; score += 8
    if MARKET_WORDS.search(t):
        score += 10
        if cat == default_cat: cat = "markets"
    if URGENT.search(t): score += 25
    if SEVERE.search(t): score += 45
    if score >= 70: level = "CRITICO"
    elif score >= 45: level = "ALTO"
    elif score >= 22: level = "MEDIO"
    else: level = "BAJO"
    return cat, score, level

# ------------------------------------------------------------------ state
LOCK = threading.Lock()
ITEMS = []            # lista de dicts
SEEN  = set()         # hashes de títulos
QUOTES = {}
CALENDAR = []
FNG = {"score": None, "rating": ""}
SOURCE_STATUS = {}
STARTED = time.time()

def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s = json.load(f)
            s.setdefault("watch", []); s.setdefault("lang", "en")
            s.setdefault("win_toast", True); s.setdefault("llama_url", "")
            return s
    except Exception:
        return {"watch": [], "lang": "en", "win_toast": True, "llama_url": ""}
SETTINGS = load_settings()
TRANS = {}   # caché de traducciones id -> título en español

def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(SETTINGS, f, ensure_ascii=False, indent=1)
    except Exception: pass

def norm_key(title):
    t = re.sub(r'[^a-z0-9 ]', '', (title or '').lower())
    return hashlib.md5(t[:70].encode()).hexdigest()

def add_item(title, link, source, default_cat, weight, published_ts):
    if not title: return
    key = norm_key(title)
    with LOCK:
        if key in SEEN: return
        SEEN.add(key)
    cat, score, level = classify(title, default_cat)
    score += weight
    item = {
        "id": key, "title": title.strip(), "link": link or "", "source": source,
        "cat": cat, "score": score, "level": level,
        "ts": published_ts or time.time(), "fetched": time.time(),
    }
    # 📸 sello de precio: fotografía del mercado al momento de la noticia importante
    if level in ("CRITICO", "ALTO") and (time.time() - item["ts"]) < 1800:
        snap = {k: QUOTES[k]["price"] for k in ("NQ", "ES", "GC", "CL", "VXN") if k in QUOTES}
        if snap: item["snap"] = snap
    with LOCK:
        ITEMS.append(item)

def prune():
    cutoff = time.time() - KEEP_HOURS * 3600
    with LOCK:
        ITEMS.sort(key=lambda x: x["ts"], reverse=True)
        alive = [i for i in ITEMS if i["ts"] > cutoff][:MAX_ITEMS]
        dead_keys = {i["id"] for i in ITEMS} - {i["id"] for i in alive}
        ITEMS[:] = alive
        SEEN.difference_update(dead_keys)

# ------------------------------------------------------------------ fetchers
def fetch_feed(fid, name, url, cat, weight):
    try:
        r = requests.get(url, headers=UA, timeout=10)
        fp = feedparser.parse(r.content)
        n = 0
        for e in fp.entries[:30]:
            ts = None
            for k in ("published_parsed", "updated_parsed"):
                v = e.get(k)
                if v: ts = time.mktime(v) - time.timezone if False else datetime(*v[:6], tzinfo=UTC).timestamp(); break
            title = re.sub(r'\s+', ' ', e.get("title", ""))
            # Google News añade " - Fuente" al final: úsalo como fuente real
            src = name
            m = re.match(r'^(.*)\s-\s([^-]{2,40})$', title)
            if fid.startswith("gn") and m:
                title, src = m.group(1), m.group(2)
            add_item(title, e.get("link", ""), src, cat, weight, ts)
            n += 1
        SOURCE_STATUS[fid] = {"name": name, "ok": True, "n": n, "t": time.time()}
    except Exception as ex:
        SOURCE_STATUS[fid] = {"name": name, "ok": False, "err": str(ex)[:120], "t": time.time()}

def fetch_reddit():
    try:
        r = requests.get(REDDIT_URL, headers=UA, timeout=10)
        for c in r.json()["data"]["children"][:25]:
            d = c["data"]
            add_item(d.get("title"), "https://reddit.com" + d.get("permalink", ""), "r/worldnews", "geo", 5, d.get("created_utc"))
        SOURCE_STATUS["reddit"] = {"name": "Reddit r/worldnews", "ok": True, "t": time.time()}
    except Exception as ex:
        SOURCE_STATUS["reddit"] = {"name": "Reddit r/worldnews", "ok": False, "err": str(ex)[:120], "t": time.time()}

def news_loop():
    while True:
        try:
            feeds = list(FEEDS) + [("watch_" + re.sub(r'\W', '', w)[:20], f"Vigilancia · {w}", gnews(f'"{w}" when:1d'), "watch", 6) for w in SETTINGS.get("watch", [])]
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = [ex.submit(fetch_feed, *f) for f in feeds]
                futs.append(ex.submit(fetch_reddit))
                for f in as_completed(futs, timeout=40): pass
        except Exception:
            traceback.print_exc()
        prune()
        try:
            recluster()
            notify_new_criticals()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_NEWS_SEC)

def fetch_quote(sym, name, short):
    for host in ("query1", "query2"):
        try:
            u = f"https://{host}.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}?interval=1m&range=1d"
            j = requests.get(u, headers=UA, timeout=8).json()
            res  = j["chart"]["result"][0]
            meta = res["meta"]
            price = meta.get("regularMarketPrice")
            prev  = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None or not prev: continue
            pct = (price - prev) / prev * 100
            # 📉 sparkline: serie del día comprimida a ~40 puntos
            closes = [c for c in (res.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if c is not None]
            if len(closes) < 10:   # fin de semana / sin sesión: usa los últimos días
                try:
                    u5 = f"https://{host}.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}?interval=15m&range=5d"
                    r5 = requests.get(u5, headers=UA, timeout=8).json()["chart"]["result"][0]
                    closes = [c for c in (r5.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if c is not None][-120:]
                except Exception:
                    pass
            spark = []
            if len(closes) > 10:
                src = closes[-300:]
                step = max(1, len(src) // 40)
                spark = [round(src[k], 4) for k in range(0, len(src), step)][-40:] + [round(closes[-1], 4)]
            # ⚡ velocímetro: movimiento de los últimos 5 min vs lo típico del día
            vel = vel_delta = None
            if len(closes) >= 40:
                d5 = [abs(closes[k] - closes[k - 5]) for k in range(5, len(closes), 5)]
                if len(d5) >= 6:
                    import statistics
                    base = statistics.median(d5[:-1])
                    last = abs(closes[-1] - closes[-6])
                    if base > 0:
                        vel = round(last / base, 2)
                        vel_delta = round(closes[-1] - closes[-6], 2)
            QUOTES[short] = {"name": name, "price": price, "pct": round(pct, 2),
                             "spark": spark, "vel": vel, "vel_delta": vel_delta, "t": time.time()}
            return
        except Exception:
            continue

def quotes_loop():
    while True:
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(lambda s: fetch_quote(*s), QUOTE_SYMBOLS))
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_QUOTES_SEC)

def fetch_calendar():
    global CALENDAR
    try:
        out = []
        for wk in ("thisweek", "nextweek"):
            try:
                r = requests.get(f"https://nfs.faireconomy.media/ff_calendar_{wk}.xml", headers=UA, timeout=12)
                root = ET.fromstring(r.content)
            except Exception:
                continue
            for ev in root.iter("event"):
                g = lambda k: (ev.findtext(k) or "").strip()
                date_s, time_s = g("date"), g("time")
                if not date_s: continue
                try:
                    if time_s and re.match(r'^\d', time_s):
                        dt = datetime.strptime(f"{date_s} {time_s}", "%m-%d-%Y %I:%M%p").replace(tzinfo=UTC)
                        dt_ny = dt.astimezone(NY)
                        tlabel = dt_ny.strftime("%H:%M")
                    else:
                        dt = datetime.strptime(date_s, "%m-%d-%Y").replace(tzinfo=UTC)
                        dt_ny = dt.astimezone(NY); tlabel = time_s or "—"
                except Exception:
                    continue
                out.append({"title": g("title"), "country": g("country"), "impact": g("impact"),
                            "forecast": g("forecast"), "previous": g("previous"),
                            "ts": dt.timestamp(), "time_ny": tlabel, "date_ny": dt_ny.strftime("%Y-%m-%d")})
        CALENDAR = out
    except Exception as ex:
        SOURCE_STATUS["calendar"] = {"name": "ForexFactory", "ok": False, "err": str(ex)[:120], "t": time.time()}
        return
    SOURCE_STATUS["calendar"] = {"name": "ForexFactory", "ok": True, "n": len(CALENDAR), "t": time.time()}

def fetch_fng():
    global FNG
    try:
        j = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                         headers={**UA, "Referer": "https://edition.cnn.com/"}, timeout=10).json()
        FNG = {"score": round(j["fear_and_greed"]["score"]), "rating": j["fear_and_greed"]["rating"]}
        SOURCE_STATUS["fng"] = {"name": "Fear&Greed CNN", "ok": True, "t": time.time()}
    except Exception as ex:
        SOURCE_STATUS["fng"] = {"name": "Fear&Greed CNN", "ok": False, "err": str(ex)[:120], "t": time.time()}

def meta_loop():
    while True:
        fetch_calendar(); fetch_fng()
        time.sleep(POLL_META_SEC)

# ------------------------------------------------------------------ traducción EN→ES
def translate_batch(texts):
    """Traduce una lista de titulares con el endpoint gratuito de Google (gtx)."""
    SEP = " ||| "
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": "en", "tl": "es", "dt": "t", "q": SEP.join(texts)},
                         headers=UA, timeout=12)
        segs = r.json()[0]
        full = "".join(s[0] for s in segs if s and s[0])
        parts = [p.strip() for p in re.split(r'\s*\|\s*\|\s*\|\s*', full)]
        if len(parts) == len(texts):
            return parts
    except Exception:
        pass
    return None

def translate_pending(limit=60):
    with LOCK:
        pend = [i for i in ITEMS if i["id"] not in TRANS][:limit]
    for j in range(0, len(pend), 10):
        chunk = pend[j:j + 10]
        res = translate_batch([c["title"] for c in chunk])
        if res:
            for c, t in zip(chunk, res): TRANS[c["id"]] = t
        else:  # el separador se rompió: uno a uno
            for c in chunk:
                r1 = translate_batch([c["title"]])
                if r1: TRANS[c["id"]] = r1[0]
        time.sleep(0.3)

def translate_loop():
    while True:
        try:
            if SETTINGS.get("lang") == "es":
                translate_pending(80)
        except Exception:
            pass
        time.sleep(8)

def with_es(items):
    if SETTINGS.get("lang") != "es":
        return items
    return [{**i, "title_es": TRANS.get(i["id"])} for i in items]

# ------------------------------------------------------------------ 🔗 clusters (confirmación multi-fuente)
STOPWORDS = set(("the a an of to in on for and or with as at by from over after amid says said say news live update "
                 "updates report reports breaking is are was were be been has have had will would could should new "
                 "his her its their this that these those about into during between against more most other some what "
                 "when where which while than then also just been being before under above").split())

def title_sig(title):
    return {w for w in re.findall(r'[a-z]{4,}', (title or '').lower()) if w not in STOPWORDS}

def recluster():
    cutoff = time.time() - 12 * 3600
    with LOCK:
        items = [i for i in ITEMS if i["ts"] > cutoff][:500]
    sigs = [title_sig(i["title"]) for i in items]
    parent = list(range(len(items)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a in range(len(items)):
        if not sigs[a]: continue
        for b in range(a + 1, len(items)):
            if not sigs[b]: continue
            inter = len(sigs[a] & sigs[b])
            if inter >= 3 and inter / len(sigs[a] | sigs[b]) >= 0.42:
                ra, rb = find(a), find(b)
                if ra != rb: parent[ra] = rb
    groups = {}
    for k, i in enumerate(items):
        groups.setdefault(find(k), []).append(i)
    with LOCK:
        for i in ITEMS: i["cluster"] = 1
        for g in groups.values():
            n = len({x["source"] for x in g})
            if n > 1:
                for x in g: x["cluster"] = n

# ------------------------------------------------------------------ 🧠 analista (heurístico + Llama opcional)
AI_CACHE = {}

def analyze(i):
    t = (i["title"] or "").lower()
    bias, up, dn, notes = None, [], [], []
    if re.search(r'hormuz|strait', t) and re.search(r'clos|block|attack|seiz|mine|shut', t):
        bias = "RISK-OFF FUERTE"; up = ["CL", "GC", "VXN"]; dn = ["NQ", "ES"]
        notes.append("Shock petrolero en juego: prima de riesgo en crudo/oro y presión sobre índices.")
    elif i["cat"] == "geo" and GEO_ACTION.search(i["title"] or ""):
        bias = "RISK-OFF"; up = ["GC", "CL", "VXN"]; dn = ["NQ", "ES"]
        notes.append("Escalada geopolítica: flujo a refugio (oro) y cautela en índices.")
    if re.search(r'tariff', t):
        bias = bias or "RISK-OFF"; dn = sorted(set(dn + ["NQ", "ES"]))
        notes.append("Aranceles: presión sobre índices y cadenas de suministro.")
    if re.search(r'rate cut|dovish|inflation (cool|slow|fall|eas)|cpi (below|cool)', t):
        bias = "RISK-ON"; up = sorted(set(up + ["NQ", "ES"]))
        notes.append("Sesgo dovish: alivio para tecnología e índices.")
    if re.search(r'rate hike|hawkish|hot inflation|cpi (above|hot|rise)|yields? (surge|spike|jump)', t):
        bias = "RISK-OFF"; dn = sorted(set(dn + ["NQ", "ES"]))
        notes.append("Sesgo hawkish: presión sobre el NQ y activos de duración larga.")
    if re.search(r'opec|(supply|production|output) cut', t):
        up = sorted(set(up + ["CL"])); bias = bias or "NEUTRO"
        notes.append("Recorte de oferta: soporte estructural para el crudo.")
    if bias is None:
        bias = "NEUTRO"; notes.append("Impacto direccional limitado: deja que el precio confirme.")
    if datetime.now(NY).weekday() >= 5 and (up or dn):
        notes.append("Mercado cerrado: riesgo de GAP en la apertura del domingo 18:00 NY.")
    inst = (("▲ " + ", ".join(up)) if up else "") + ((" · ▼ " + ", ".join(dn)) if dn else "")
    return {"bias": bias, "inst": inst.strip(), "note": " ".join(notes)[:230]}

def llama_on():
    return bool((SETTINGS.get("llama_url") or "").strip())

def llama_chat(messages, max_tokens=220, temperature=0.4, timeout=90):
    """Llama al servidor local (API compatible con OpenAI). Devuelve texto o None."""
    url = (SETTINGS.get("llama_url") or "").strip()
    if not url:
        return None
    try:
        r = requests.post(url.rstrip("/") + "/v1/chat/completions", json={
            "model": "local", "temperature": temperature, "max_tokens": max_tokens,
            "messages": messages}, timeout=timeout).json()
        return (r["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return None

def headline_context(n=14, hours=14):
    cutoff = time.time() - hours * 3600
    with LOCK:
        items = [i for i in ITEMS if i["ts"] > cutoff]
    items.sort(key=lambda x: (x.get("cluster", 1), x["score"]), reverse=True)
    return "\n".join(f"- [{i['level']}·{i['cat']}] {i['title']} ({i['source']})" for i in items[:n])

def llama_loop():
    """Análisis IA por titular (2 frases) para los CRÍTICOS/ALTOS."""
    while True:
        try:
            if llama_on():
                with LOCK:
                    cand = [i for i in ITEMS if i["level"] in ("CRITICO", "ALTO")
                            and time.time() - i["ts"] < 3 * 3600 and i["id"] not in AI_CACHE][:3]
                for i in cand:
                    txt = llama_chat([
                        {"role": "system", "content": "Eres analista de futuros (NQ=Nasdaq, ES=S&P, GC=oro, CL=petróleo). Responde en español en máximo 2 frases: sesgo (RISK-ON/RISK-OFF/NEUTRO), instrumentos afectados con ▲/▼ y un consejo operativo concreto. No des consejo financiero personalizado ni cifras inventadas."},
                        {"role": "user", "content": i["title"]}], max_tokens=120, temperature=0.3, timeout=60)
                    if txt: AI_CACHE[i["id"]] = {"bias": "🤖 IA", "inst": "", "note": txt[:320]}
        except Exception:
            pass
        time.sleep(10)

# ------------------------------------------------------------------ 🧠 #1 EDITORIAL redactado por IA
EDITORIAL = {"text": "", "generated": 0, "lang": None, "busy": False}

def generate_editorial(force=False):
    if EDITORIAL["busy"] or not llama_on():
        return
    lang = SETTINGS.get("lang", "en")
    if not force and EDITORIAL["text"] and EDITORIAL["lang"] == lang and time.time() - EDITORIAL["generated"] < 720:
        return
    ctx = headline_context(14, 14)
    if not ctx:
        return
    EDITORIAL["busy"] = True
    try:
        sys_p = ("Eres el editor jefe de un periódico de trading para un trader de futuros "
                 "(NQ=Nasdaq, ES=S&P 500, GC=oro, CL=petróleo). Escribe SIEMPRE en español neutro, "
                 "en 2 párrafos cortos (máximo 110 palabras en total). Resume el panorama, indica el sesgo "
                 "de riesgo (risk-on / risk-off / mixto), los riesgos clave y qué debe vigilar hoy. "
                 "Tono profesional y directo, como un briefing de apertura. No inventes cifras que no estén "
                 "en los titulares y no des consejo financiero personalizado.")
        txt = llama_chat([{"role": "system", "content": sys_p},
                          {"role": "user", "content": "Titulares recientes:\n" + ctx + "\n\nEscribe el editorial de hoy."}],
                         max_tokens=280, temperature=0.5, timeout=120)
        if txt:
            EDITORIAL.update(text=txt, generated=time.time(), lang=lang)
    finally:
        EDITORIAL["busy"] = False

def editorial_loop():
    while True:
        try:
            generate_editorial(False)
        except Exception:
            pass
        time.sleep(20)

# ------------------------------------------------------------------ 🔔 notificaciones nativas de Windows
WIN_NOTIFIED = set()

def notify_windows(title, msg):
    t = (title or "").replace("'", "’")[:100]
    m = (msg or "").replace("'", "’")[:160]
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
          "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
          "$t=$x.GetElementsByTagName('text');"
          f"$t.Item(0).AppendChild($x.CreateTextNode('{t}')) | Out-Null;"
          f"$t.Item(1).AppendChild($x.CreateTextNode('{m}')) | Out-Null;"
          "$n=[Windows.UI.Notifications.ToastNotification]::new($x);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ETG DeepBrief').Show($n)")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=0x08000000)
    except Exception:
        pass

def notify_new_criticals():
    if not SETTINGS.get("win_toast", True): return
    if time.time() - STARTED < 90: return   # no bombardear con el backlog inicial
    now = time.time()
    with LOCK:
        fresh = [i for i in ITEMS if i["level"] == "CRITICO" and now - i["ts"] < 1800
                 and i["id"] not in WIN_NOTIFIED]
    for i in fresh[:2]:
        WIN_NOTIFIED.add(i["id"])
        notify_windows("🚨 ETG DeepBrief — NOTICIA CRÍTICA", i["title"][:150])

# ------------------------------------------------------------------ tensión geopolítica
def tension():
    cutoff = time.time() - 3 * 3600
    with LOCK:
        geo = [i for i in ITEMS if i["cat"] == "geo" and i["ts"] > cutoff]
    crit = sum(1 for i in geo if i["level"] == "CRITICO")
    alto = sum(1 for i in geo if i["level"] == "ALTO")
    med  = sum(1 for i in geo if i["level"] == "MEDIO")
    val = min(100, crit * 16 + alto * 6 + med * 1)
    if val >= 70: label = "CRÍTICA"
    elif val >= 45: label = "ALTA"
    elif val >= 22: label = "ELEVADA"
    else: label = "NORMAL"
    return {"value": val, "label": label, "criticos": crit, "altos": alto}

# ------------------------------------------------------------------ flask
app = Flask(__name__, static_folder=None)

@app.get("/")
def index():
    return send_from_directory(APP_DIR, "dashboard.html")

@app.get("/api/items")
def api_items():
    cat = request.args.get("cat", "")
    q   = request.args.get("q", "").lower()
    with LOCK:
        data = list(ITEMS)
    if cat and cat != "all":
        data = [i for i in data if i["cat"] == cat]
    if q:
        data = [i for i in data if q in i["title"].lower()]
    data.sort(key=lambda x: x["ts"], reverse=True)
    out = []
    now = time.time()
    for i in with_es(data[:220]):
        i = dict(i)
        if i.get("snap"):   # 📸 qué ha hecho el mercado desde esta noticia
            since = []
            for k, v in i["snap"].items():
                q = QUOTES.get(k)
                if q and v:
                    since.append({"sym": k, "pct": round((q["price"] - v) / v * 100, 2)})
            since.sort(key=lambda s: abs(s["pct"]), reverse=True)
            i["since"] = since[:4]
        if i["level"] == "CRITICO" or (i["level"] == "ALTO" and now - i["ts"] < 3 * 3600):
            i["ai"] = AI_CACHE.get(i["id"]) or analyze(i)   # 🧠 análisis
        out.append(i)
    return jsonify(out)

@app.get("/api/quotes")
def api_quotes():
    order = [s[2] for s in QUOTE_SYMBOLS]
    return jsonify([{**QUOTES[k], "sym": k} for k in order if k in QUOTES])

@app.get("/api/meta")
def api_meta():
    now_ny = datetime.now(NY)
    today = now_ny.strftime("%Y-%m-%d")
    cal_today = sorted([c for c in CALENDAR if c["date_ny"] == today], key=lambda x: x["ts"])
    cal_label = "HOY"
    if not cal_today:
        future = sorted([c for c in CALENDAR if c["date_ny"] > today], key=lambda x: x["ts"])
        if future:
            nxt_day = future[0]["date_ny"]
            cal_today = [c for c in future if c["date_ny"] == nxt_day]
            try:
                cal_label = datetime.strptime(nxt_day, "%Y-%m-%d").strftime("%a %d/%m").upper()
            except Exception:
                cal_label = nxt_day
    with LOCK:
        total = len(ITEMS)
    ok = sum(1 for s in SOURCE_STATUS.values() if s.get("ok"))
    return jsonify({
        "tension": tension(), "fng": FNG, "calendar": cal_today, "cal_label": cal_label,
        "lang": SETTINGS.get("lang", "en"),
        "win_toast": SETTINGS.get("win_toast", True),
        "llama_on": llama_on(),
        "llama_url": SETTINGS.get("llama_url", ""),
        "version": APP_VERSION,
        "watch": SETTINGS.get("watch", []),
        "status": {"total_items": total, "sources_ok": ok, "sources_total": len(SOURCE_STATUS),
                   "uptime": int(time.time() - STARTED)},
        "sources": SOURCE_STATUS,
        "now_ny": now_ny.strftime("%H:%M:%S"), "date_ny": now_ny.strftime("%A %d %B %Y"),
    })

@app.get("/api/brief")
def api_brief():
    """Portada: lo más relevante de las últimas 14 horas, agrupado."""
    cutoff = time.time() - 14 * 3600
    with LOCK:
        recent = [i for i in ITEMS if i["ts"] > cutoff]
    recent.sort(key=lambda x: (x["score"], x["ts"]), reverse=True)
    top = recent[:6]
    groups = {}
    for i in recent:
        groups.setdefault(i["cat"], []).append(i)
    sections = []
    for cat in ("geo", "trump", "fed", "markets", "energy", "crypto", "watch"):
        if cat in groups:
            sections.append({"cat": cat, "items": with_es(groups[cat][:4])})
    return jsonify({"top": with_es(top), "sections": sections, "generated": time.time()})

@app.get("/cinta")
def cinta():
    return send_from_directory(APP_DIR, "cinta.html")

@app.get("/api/gapreport")
def api_gapreport():
    """🌅 Informe Pre-Apertura: todo lo que pasó desde el cierre del viernes."""
    now_ny = datetime.now(NY)
    days_back = (now_ny.weekday() - 4) % 7
    fri = (now_ny - timedelta(days=days_back)).replace(hour=17, minute=0, second=0, microsecond=0)
    if fri > now_ny: fri -= timedelta(days=7)
    cutoff = fri.timestamp()
    with LOCK:
        wk = [i for i in ITEMS if i["ts"] >= cutoff and i["level"] in ("CRITICO", "ALTO")]
    wk.sort(key=lambda x: (x.get("cluster", 1), x["score"]), reverse=True)
    top = []
    for i in with_es(wk[:10]):
        i = dict(i); i["ai"] = AI_CACHE.get(i["id"]) or analyze(i)
        top.append(i)
    horizon = time.time() + 60 * 3600
    ev = [c for c in CALENDAR if time.time() < c["ts"] < horizon and c["impact"] == "High"][:8]
    return jsonify({"since": fri.strftime("%A %d · %H:%M NY"), "top": top, "tension": tension(),
                    "events": ev, "fng": FNG,
                    "quotes": [{**QUOTES[k], "sym": k} for k in ("NQ", "ES", "GC", "CL", "VXN") if k in QUOTES]})

@app.get("/api/editorial")
def api_editorial():
    return jsonify({"on": llama_on(), "text": EDITORIAL["text"],
                    "generated": EDITORIAL["generated"], "busy": EDITORIAL["busy"]})

@app.post("/api/editorial")
def api_editorial_refresh():
    if not llama_on():
        return jsonify({"ok": False, "err": "Conecta tu modelo Llama en ⚙️"})
    threading.Thread(target=generate_editorial, args=(True,), daemon=True).start()
    return jsonify({"ok": True})

@app.post("/api/ask")
def api_ask():
    q = ((request.json or {}).get("q") or "").strip()[:400]
    if not q:
        return jsonify({"ok": False, "err": "Pregunta vacía"})
    if not llama_on():
        return jsonify({"ok": False, "err": "Conecta tu modelo Llama local en ⚙️ para usar el chat."})
    ctx = headline_context(18, 24)
    sys_p = ("Eres un analista de mercados que conversa con un trader de futuros (NQ=Nasdaq, ES=S&P, "
             "GC=oro, CL=petróleo, VXN=volatilidad Nasdaq). Responde SIEMPRE en español, claro y conciso "
             "(máximo 130 palabras). Usa los titulares recientes como contexto cuando sean relevantes; "
             "si no hay información suficiente, dilo con honestidad. Explica implicaciones para el mercado, "
             "pero NO des consejo financiero personalizado ni inventes cifras.")
    ans = llama_chat([{"role": "system", "content": sys_p},
                      {"role": "user", "content": "Titulares recientes (contexto):\n" + ctx + "\n\nPregunta del trader: " + q}],
                     max_tokens=340, temperature=0.4, timeout=120)
    if not ans:
        return jsonify({"ok": False, "err": "El modelo no respondió. ¿Está corriendo el servidor Llama en esa URL?"})
    return jsonify({"ok": True, "answer": ans})

UPDATE_CACHE = {"data": None, "t": 0}

def check_update(force=False):
    if not force and UPDATE_CACHE["data"] and time.time() - UPDATE_CACHE["t"] < 1800:
        return UPDATE_CACHE["data"]
    out = {"current": APP_VERSION, "latest": None, "update_available": False,
           "notes": "", "exe_url": "", "frozen": bool(getattr(sys, "frozen", False))}
    try:
        j = requests.get(RAW_VERSION_URL, headers=UA, timeout=10).json()
        out["latest"] = j.get("version", "")
        out["notes"]  = j.get("notes", "")
        out["exe_url"] = j.get("exe_url", "")
        out["update_available"] = ver_tuple(out["latest"]) > ver_tuple(APP_VERSION)
    except Exception as ex:
        out["err"] = str(ex)[:140]
    UPDATE_CACHE.update(data=out, t=time.time())
    return out

@app.get("/api/update")
def api_update():
    return jsonify(check_update(request.args.get("force") == "1"))

@app.post("/api/update/apply")
def api_update_apply():
    info = check_update(True)
    if not info.get("update_available"):
        return jsonify({"ok": False, "err": "Ya tienes la última versión."})
    if not getattr(sys, "frozen", False):
        return jsonify({"ok": False, "err": "La versión de código se actualiza con 'git pull' (usa actualizar.bat)."})
    url = info.get("exe_url")
    if not url:
        return jsonify({"ok": False, "err": "No hay instalador .exe publicado para esta versión."})
    try:
        cur = sys.executable
        newexe = os.path.join(DATA_DIR, "ETG DeepBrief.new.exe")
        with requests.get(url, headers=UA, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(newexe, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
        if os.path.getsize(newexe) < 1_000_000:
            os.remove(newexe); return jsonify({"ok": False, "err": "La descarga falló (archivo incompleto)."})
        bat = os.path.join(DATA_DIR, "_update.bat")
        with open(bat, "w", encoding="ascii", errors="ignore") as f:
            f.write("@echo off\r\nchcp 65001 >nul\r\nping 127.0.0.1 -n 3 >nul\r\n"
                    f'del "{cur}"\r\n'
                    f'move "{newexe}" "{cur}"\r\n'
                    f'start "" "{cur}"\r\n'
                    'del "%~f0"\r\n')
        subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
        threading.Thread(target=lambda: (time.sleep(1.5), os._exit(0)), daemon=True).start()
        return jsonify({"ok": True})
    except Exception as ex:
        return jsonify({"ok": False, "err": str(ex)[:160]})

@app.post("/api/config")
def api_config():
    j = request.json or {}
    if "win_toast" in j: SETTINGS["win_toast"] = bool(j["win_toast"])
    if "llama_url" in j: SETTINGS["llama_url"] = str(j["llama_url"]).strip()
    save_settings()
    return jsonify({"win_toast": SETTINGS.get("win_toast", True), "llama_url": SETTINGS.get("llama_url", "")})

@app.post("/api/lang")
def api_lang():
    lang = (request.json or {}).get("lang", "en")
    SETTINGS["lang"] = "es" if lang == "es" else "en"
    save_settings()
    if SETTINGS["lang"] == "es":
        # traduce de inmediato lo más reciente para que el cambio se sienta al instante
        threading.Thread(target=translate_pending, args=(40,), daemon=True).start()
    return jsonify({"lang": SETTINGS["lang"]})

@app.post("/api/watch")
def api_watch():
    term = (request.json or {}).get("term", "").strip()
    remove = (request.json or {}).get("remove", "").strip()
    w = SETTINGS.setdefault("watch", [])
    if term and term.lower() not in [x.lower() for x in w] and len(w) < 8:
        w.append(term)
    if remove:
        SETTINGS["watch"] = [x for x in w if x.lower() != remove.lower()]
    save_settings()
    return jsonify({"watch": SETTINGS["watch"]})

# ------------------------------------------------------------------ 🖱️ icono de bandeja (junto al reloj)
def tray_icon():
    try:
        import pystray
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (64, 64), (10, 10, 8))
        d = ImageDraw.Draw(img)
        d.ellipse([6, 6, 58, 58], fill=(212, 175, 55))
        d.ellipse([18, 18, 46, 46], fill=(10, 10, 8))
        d.ellipse([26, 26, 38, 38], fill=(212, 175, 55))
        def open_panel(icon, item): webbrowser.open(f"http://127.0.0.1:{PORT}")
        def open_cinta(icon, item): webbrowser.open(f"http://127.0.0.1:{PORT}/cinta")
        def quit_app(icon, item):
            icon.stop(); os._exit(0)
        icon = pystray.Icon("ETGDeepBrief", img, "ETG DeepBrief — vigilando el mercado",
                            menu=pystray.Menu(
                                pystray.MenuItem("📰 Abrir panel", open_panel, default=True),
                                pystray.MenuItem("🖥️ Abrir Modo Cinta", open_cinta),
                                pystray.MenuItem("❌ Salir del todo", quit_app)))
        icon.run()
    except Exception:
        pass

# ------------------------------------------------------------------ main
def open_browser():
    time.sleep(1.5)
    url = f"http://127.0.0.1:{PORT}"
    for exe in (os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
        if os.path.exists(exe):
            subprocess.Popen([exe, f"--app={url}", "--window-size=1600,950"]); return
    webbrowser.open(url)

if __name__ == "__main__":
    threading.Thread(target=news_loop,     daemon=True).start()
    threading.Thread(target=quotes_loop,   daemon=True).start()
    threading.Thread(target=meta_loop,     daemon=True).start()
    threading.Thread(target=translate_loop, daemon=True).start()
    threading.Thread(target=llama_loop,     daemon=True).start()
    threading.Thread(target=editorial_loop, daemon=True).start()
    threading.Thread(target=tray_icon,      daemon=True).start()
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()
    print(f"ETG DEEPBRIEF corriendo en http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
