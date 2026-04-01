"""
╔══════════════════════════════════════════════════════════════════════╗
║              TREND RADAR — Pipeline Automatica Completa             ║
║                                                                      ║
║  Moduli integrati:                                                   ║
║   1. Google Trends  → rileva keyword in crescita (pytrends)         ║
║   2. Amazon Scraper → verifica su Movers & Shakers                  ║
║   3. Telegram Alert → notifica solo i prodotti che passano entrambi ║
║                                                                      ║
║  Installazione dipendenze:                                           ║
║    pip install pytrends requests beautifulsoup4 schedule             ║
║                                                                      ║
║  Modi di utilizzo:                                                   ║
║    python trend_radar.py          → chiede le keyword interattivo   ║
║    python trend_radar.py now      → usa le keyword salvate          ║
║    python trend_radar.py auto     → scheduler automatico            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import time
import json
import logging
import schedule
import requests
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from pytrends.request import TrendReq
from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════════
#  CONFIG — modifica questi valori prima di eseguire
# ══════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = "8225165494:AAG9lDDBCrn3GHVe2UM0N_oa7m07bBJZ7Ho"
TELEGRAM_CHAT_ID   = "8739473584"

# Soglie di filtraggio
TRENDS_MIN_GROWTH     = 5
TRENDS_TIMEFRAME      = "today 3-m"
TRENDS_GEO            = "IT"

# Ore scansione automatica
SCHEDULE_TIMES        = ["08:00", "20:00"]

# Quanti prodotti Amazon per categoria
AMAZON_MAX_PRODUCTS   = 20

# File dove salvare le keyword per le scansioni automatiche
KEYWORDS_FILE         = "keywords.txt"

# Categorie Amazon
AMAZON_CATEGORIES = {
    "salute":        "health",
    "bellezza":      "beauty",
    "casa":          "kitchen",
    "sport":         "sporting-goods",
    "animali":       "pet-supplies",
    "tech":          "electronics",
    "giocattoli":    "toys",
    "abbigliamento": "apparel",
}

# Keyword di default (usate solo se non ne inserisci di nuove)
DEFAULT_KEYWORDS = [
    "massaggiatore cervicale", "fascia postura", "terapia luce led",
    "pistola massaggio", "maschera led viso", "rullo giada",
    "epilatore ipl", "deumidificatore mini", "purificatore aria",
    "cuffie conduzione ossea", "carica wireless", "proiettore mini",
    "fontana gatti", "gps collare cane", "elastici resistenza",
]


# ══════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("TrendRadar")


# ══════════════════════════════════════════════════════════════════════
#  GESTIONE KEYWORD INTERATTIVA
# ══════════════════════════════════════════════════════════════════════

def chiedi_keywords() -> list[str]:
    """
    Chiede all'utente le keyword da cercare.
    Le salva in keywords.txt per le scansioni automatiche future.
    """
    print("\n" + "=" * 60)
    print("  TREND RADAR — Inserimento Keyword")
    print("=" * 60)

    # Mostra keyword esistenti se ci sono
    keywords_esistenti = carica_keywords()
    if keywords_esistenti:
        print(f"\nKeyword salvate ({len(keywords_esistenti)}):")
        for i, kw in enumerate(keywords_esistenti, 1):
            print(f"  {i}. {kw}")
        print()
        scelta = input("Vuoi usare queste keyword? (s/n): ").strip().lower()
        if scelta == "s":
            return keywords_esistenti

    print("\nInserisci le keyword da monitorare.")
    print("Una per riga. Premi INVIO due volte quando hai finito.\n")

    keywords = []
    while True:
        kw = input("  Keyword: ").strip()
        if kw == "":
            if len(keywords) == 0:
                print("  Inserisci almeno una keyword.")
                continue
            break
        keywords.append(kw.lower())
        print(f"  OK: {kw}")

    # Salva per uso futuro
    salva_keywords(keywords)
    print(f"\n{len(keywords)} keyword salvate in '{KEYWORDS_FILE}'")
    print("=" * 60 + "\n")
    return keywords


def salva_keywords(keywords: list[str]) -> None:
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(keywords))


def carica_keywords() -> list[str]:
    if not os.path.exists(KEYWORDS_FILE):
        return []
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    return lines


# ══════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class TrendSignal:
    keyword:        str
    trends_score:   int
    trends_growth:  int
    amazon_rank:    Optional[int]
    amazon_name:    Optional[str]
    amazon_url:     Optional[str]
    sources:        list = field(default_factory=list)
    detected_at:    str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    @property
    def strength(self) -> str:
        score = self.trends_growth + (50 if self.amazon_rank else 0)
        if score >= 100: return "FORTE"
        if score >= 50:  return "MEDIO"
        return "DEBOLE"

    @property
    def summary(self) -> str:
        amazon_info = (
            f"Su Amazon M&S: #{self.amazon_rank} - {self.amazon_name}"
            if self.amazon_rank
            else "Non trovato su Amazon M&S"
        )
        return (
            f"{self.keyword.upper()}\n"
            f"Segnale: {self.strength}\n"
            f"Google Trends: +{self.trends_growth}% (score {self.trends_score}/100)\n"
            f"{amazon_info}\n"
            f"Rilevato: {self.detected_at}"
        )


# ══════════════════════════════════════════════════════════════════════
#  MODULO 1 — GOOGLE TRENDS
# ══════════════════════════════════════════════════════════════════════

class GoogleTrendsModule:

    def __init__(self):
        self.pytrends = TrendReq(
            hl="it-IT",
            tz=60,
            timeout=(15, 30),
            retries=3,
            backoff_factor=1.5,
        )

    def scan(self, keywords: list[str]) -> list[dict]:
        results = []
        groups = [keywords[i:i+5] for i in range(0, len(keywords), 5)]

        for i, group in enumerate(groups):
            log.info(f"[Trends] Batch {i+1}/{len(groups)}: {group}")
            try:
                batch_results = self._scan_batch(group)
                results.extend(batch_results)
            except Exception as e:
                log.warning(f"[Trends] Errore batch {i+1}: {e}")

            # Pausa tra batch per evitare errore 429
            if i < len(groups) - 1:
                log.info("[Trends] Pausa 10s tra batch...")
                time.sleep(10)

        results.sort(key=lambda x: x["growth"], reverse=True)
        log.info(
            f"[Trends] {len(results)} keyword analizzate, "
            f"{sum(1 for r in results if r['growth'] >= TRENDS_MIN_GROWTH)} sopra soglia"
        )
        return results

    def _scan_batch(self, keywords: list[str]) -> list[dict]:
        self.pytrends.build_payload(
            kw_list=keywords,
            timeframe=TRENDS_TIMEFRAME,
            geo=TRENDS_GEO
        )

        iot = self.pytrends.interest_over_time()
        if iot.empty:
            return []

        results = []
        for kw in keywords:
            if kw not in iot.columns:
                continue
            series = iot[kw].dropna()
            if len(series) < 2:
                continue

            current     = int(series.iloc[-1])
            mid         = len(series) // 2
            past_avg    = int(series.iloc[:mid].mean()) or 1
            present_avg = int(series.iloc[mid:].mean())
            growth      = round((present_avg - past_avg) / past_avg * 100)

            results.append({"keyword": kw, "score": current, "growth": growth})

        return results


# ══════════════════════════════════════════════════════════════════════
#  MODULO 2 — AMAZON MOVERS & SHAKERS
# ══════════════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

class AmazonModule:

    BASE_URL = "https://www.amazon.it/gp/movers-and-shakers/{category}"

    def build_index(self) -> dict[str, list[dict]]:
        index = {}
        for label, slug in AMAZON_CATEGORIES.items():
            log.info(f"[Amazon] Scarico M&S: {label}")
            try:
                products = self._scrape_category(slug)
                index[label] = products
                log.info(f"[Amazon] {label}: {len(products)} prodotti trovati")
                time.sleep(4)
            except Exception as e:
                log.warning(f"[Amazon] Errore categoria {label}: {e}")
                index[label] = []
        return index

    def find_keyword(self, keyword: str, index: dict) -> Optional[dict]:
        kw_lower = keyword.lower()
        tokens = [t for t in kw_lower.split() if len(t) > 3]

        for category, products in index.items():
            for product in products:
                name_lower = product["name"].lower()
                matches = sum(1 for t in tokens if t in name_lower)
                if matches >= max(1, len(tokens) // 2):
                    return {
                        "rank":     product["rank"],
                        "name":     product["name"],
                        "url":      product["url"],
                        "category": category,
                    }
        return None

    def _scrape_category(self, slug: str) -> list[dict]:
        url = self.BASE_URL.format(category=slug)
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        products = []

        # Prova più selettori — Amazon aggiorna spesso la struttura HTML
        selectors = [
            "li.zg-item-immersion",
            "div.zg-item-immersion",
            "div[class*='zg_item']",
            "li[class*='zg-item']",
            ".p13n-desktop-grid li",
            "div.a-cardui div[data-index]",
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)[:AMAZON_MAX_PRODUCTS]
            if items:
                log.info(f"[Amazon] Selettore: '{selector}' ({len(items)} items)")
                break

        for item in items:
            rank_el = (
                item.select_one(".zg-badge-text") or
                item.select_one("span.zg-bdg-text") or
                item.select_one("[class*='badge']")
            )
            name_el = (
                item.select_one(".p13n-sc-truncate") or
                item.select_one(".p13n-sc-line-clamp-1") or
                item.select_one("._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y") or
                item.select_one("a span") or
                item.select_one(".a-size-small.a-color-base")
            )
            link_el = item.select_one("a.a-link-normal")

            if not (rank_el and name_el):
                continue

            rank_text = rank_el.get_text(strip=True).replace("#", "").replace(",", "").replace(".", "")
            try:
                rank = int(rank_text)
            except ValueError:
                continue

            name = name_el.get_text(strip=True)
            url  = ("https://www.amazon.it" + link_el["href"]) if link_el else ""
            products.append({"rank": rank, "name": name, "url": url})

        return products


# ══════════════════════════════════════════════════════════════════════
#  MODULO 3 — TELEGRAM ALERTS
# ══════════════════════════════════════════════════════════════════════

class TelegramModule:

    @property
    def api_url(self):
        return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def send(self, message: str) -> bool:
        payload = {
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(self.api_url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error(f"[Telegram] Errore invio: {e}")
            return False

    def send_report(self, signals: list[TrendSignal], keywords_usate: list[str]) -> None:
        if not signals:
            self.send(
                "TREND RADAR - Nessun segnale sopra soglia.\n"
                f"Keyword monitorate: {', '.join(keywords_usate)}"
            )
            return

        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        header = (
            f"TREND RADAR - Scansione {now}\n"
            f"------------------------\n"
            f"Keyword monitorate: {len(keywords_usate)}\n"
            f"Segnali rilevati: {len(signals)}\n"
            f"Forti: {sum(1 for s in signals if s.strength == 'FORTE')} | "
            f"Medi: {sum(1 for s in signals if s.strength == 'MEDIO')}\n"
        )
        self.send(header)

        for i, signal in enumerate(signals[:10], 1):
            msg = f"#{i} {signal.summary}"
            if signal.amazon_url:
                msg += f"\nLink Amazon: {signal.amazon_url}"
            self.send(msg)
            time.sleep(0.5)

        self.send(
            "------------------------\n"
            "Dati: Google Trends + Amazon Movers & Shakers"
        )


# ══════════════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════

class TrendRadarPipeline:

    def __init__(self):
        self.trends   = GoogleTrendsModule()
        self.amazon   = AmazonModule()
        self.telegram = TelegramModule()

    def run(self, keywords: list[str]) -> list[TrendSignal]:
        log.info("=" * 60)
        log.info(f"TREND RADAR — Avvio scansione ({len(keywords)} keyword)")
        log.info("=" * 60)
        start = time.time()

        # STEP 1: Google Trends
        log.info("[1/3] Analisi Google Trends...")
        trends_data = self.trends.scan(keywords)

        hot_keywords = [t for t in trends_data if t["growth"] >= TRENDS_MIN_GROWTH]
        log.info(f"      -> {len(hot_keywords)} keyword sopra soglia ({TRENDS_MIN_GROWTH}%)")

        if not hot_keywords:
            log.info("      Nessun segnale rilevante. Fine scansione.")
            self.telegram.send_report([], keywords)
            return []

        # STEP 2: Amazon Movers & Shakers
        log.info("[2/3] Costruzione indice Amazon M&S...")
        amazon_index = self.amazon.build_index()

        # STEP 3: Incrocia i dati
        log.info("[3/3] Incrocio dati e generazione segnali...")
        signals: list[TrendSignal] = []

        for trend in hot_keywords:
            amazon_match = self.amazon.find_keyword(trend["keyword"], amazon_index)
            sources = ["Google Trends"]
            if amazon_match:
                sources.append("Amazon M&S")

            signal = TrendSignal(
                keyword       = trend["keyword"],
                trends_score  = trend["score"],
                trends_growth = trend["growth"],
                amazon_rank   = amazon_match["rank"] if amazon_match else None,
                amazon_name   = amazon_match["name"] if amazon_match else None,
                amazon_url    = amazon_match["url"]  if amazon_match else None,
                sources       = sources,
            )
            signals.append(signal)

            indicator = "FORTE" if amazon_match else "TREND"
            log.info(
                f"      [{indicator}] {signal.keyword} | "
                f"+{signal.trends_growth}% Trends | "
                f"Amazon: {'#' + str(signal.amazon_rank) if signal.amazon_rank else '---'}"
            )

        signals.sort(key=lambda s: (-(s.amazon_rank is not None), -s.trends_growth))

        # STEP 4: Alert Telegram
        log.info(f"[4/3] Invio report Telegram — {len(signals)} segnali...")
        self.telegram.send_report(signals, keywords)

        elapsed = round(time.time() - start, 1)
        log.info(f"=== Scansione completata in {elapsed}s ===\n")

        self._save_results(signals, keywords)
        return signals

    def _save_results(self, signals: list[TrendSignal], keywords: list[str]) -> None:
        filename = f"radar_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        data = {
            "scan_date":     datetime.now().strftime("%d/%m/%Y %H:%M"),
            "keywords_used": keywords,
            "signals": [
                {
                    "keyword":       s.keyword,
                    "trends_score":  s.trends_score,
                    "trends_growth": s.trends_growth,
                    "amazon_rank":   s.amazon_rank,
                    "amazon_name":   s.amazon_name,
                    "amazon_url":    s.amazon_url,
                    "sources":       s.sources,
                    "strength":      s.strength,
                    "detected_at":   s.detected_at,
                }
                for s in signals
            ]
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"[Save] Risultati salvati in {filename}")


# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def run_with_keywords(keywords: list[str]):
    try:
        pipeline = TrendRadarPipeline()
        pipeline.run(keywords)
    except Exception as e:
        log.error(f"Errore durante la scansione: {e}", exc_info=True)


if __name__ == "__main__":
    import sys

    # python trend_radar.py auto  →  scheduler automatico
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        keywords = carica_keywords() or DEFAULT_KEYWORDS
        log.info("=" * 60)
        log.info("TREND RADAR — Modalita Scheduler Automatica")
        log.info(f"Keyword caricate: {len(keywords)}")
        log.info(f"Scansioni: {', '.join(SCHEDULE_TIMES)}")
        log.info("=" * 60)

        for t in SCHEDULE_TIMES:
            schedule.every().day.at(t).do(run_with_keywords, keywords=keywords)
            log.info(f"  Schedulata alle {t}")

        log.info("\nEseguo prima scansione subito...")
        run_with_keywords(keywords)

        while True:
            schedule.run_pending()
            time.sleep(30)

    # python trend_radar.py now  →  usa keyword salvate, scansione immediata
    elif len(sys.argv) > 1 and sys.argv[1] == "now":
        keywords = carica_keywords() or DEFAULT_KEYWORDS
        log.info(f"Modalita immediata — {len(keywords)} keyword caricate")
        run_with_keywords(keywords)

    # python trend_radar.py  →  chiede keyword interattivo
    else:
        keywords = chiedi_keywords()
        run_with_keywords(keywords)
