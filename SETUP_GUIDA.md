# TREND RADAR — Guida Setup Completa

## Cosa fa questo script

Pipeline automatica in 3 moduli integrati:

```
KEYWORDS_TO_MONITOR
        │
        ▼
┌───────────────────┐
│  1. GOOGLE TRENDS │  → analizza centinaia di keyword
│     (pytrends)    │  → filtra quelle con crescita > soglia
└────────┬──────────┘
         │ solo keyword "calde"
         ▼
┌───────────────────┐
│  2. AMAZON M&S    │  → scarica Movers & Shakers per categoria
│     (scraper)     │  → verifica se la keyword è già lì
└────────┬──────────┘
         │ segnali confermati da 2 fonti
         ▼
┌───────────────────┐
│  3. TELEGRAM ALERT│  → manda notifica con rank, link, crescita
│     (bot)         │  → salva JSON con storico
└───────────────────┘
```

---

## Installazione

```bash
# 1. Installa Python 3.10+ se non ce l'hai
# https://www.python.org/downloads/

# 2. Installa le dipendenze
pip install pytrends requests beautifulsoup4 schedule

# 3. Scarica lo script
# Metti trend_radar.py in una cartella a tua scelta
```

---

## Configurazione Telegram (5 minuti)

### Crea il bot
1. Apri Telegram, cerca **@BotFather**
2. Scrivi `/newbot`
3. Scegli un nome (es: "Il mio Trend Radar")
4. Copia il **token** che ti dà (formato: `123456:ABC-DEF...`)

### Ottieni il tuo Chat ID
1. Cerca **@userinfobot** su Telegram
2. Scrivi qualsiasi cosa → ti risponde con il tuo ID numerico

### Inserisci nello script
Apri `trend_radar.py` e modifica le righe in cima:
```python
TELEGRAM_BOT_TOKEN = "123456:ABC-DEFghijkl..."  # il tuo token
TELEGRAM_CHAT_ID   = "987654321"                # il tuo ID
```

---

## Come eseguire

### Scansione immediata (test)
```bash
python trend_radar.py now
```

### Modalità automatica (gira in background)
```bash
python trend_radar.py
```
Di default fa la scansione alle **08:00** e alle **20:00** ogni giorno,
più una scansione immediata all'avvio.

### Cambiare gli orari
Nel file, modifica:
```python
SCHEDULE_TIMES = ["08:00", "20:00"]  # aggiungi o cambia
```

---

## Personalizzazione

### Aggiungere keyword
```python
KEYWORDS_TO_MONITOR = [
    "il tuo prodotto",
    "altra keyword",
    # ... aggiungi qui
]
```

### Cambiare la soglia di sensibilità
```python
TRENDS_MIN_GROWTH = 20   # abbassa per più segnali, alza per meno rumore
```

### Monitorare solo alcune categorie Amazon
```python
AMAZON_CATEGORIES = {
    "salute": "health",
    "pet":    "pet-supplies",
    # commenta le categorie che non ti interessano
}
```

---

## Output

### Console
```
08:00:01 │ INFO │ ════════════════════════
08:00:01 │ INFO │ TREND RADAR — Avvio scansione
08:00:05 │ INFO │ [1/3] Analisi Google Trends...
08:00:31 │ INFO │ → 4 keyword sopra soglia (20%)
08:00:31 │ INFO │ [2/3] Costruzione indice Amazon M&S...
08:01:15 │ INFO │ [3/3] Incrocio dati e generazione segnali...
08:01:15 │ INFO │ 🔥 massaggiatore cervicale | +87% Trends | Amazon: #12
08:01:15 │ INFO │ 📈 fontana gatti          | +34% Trends | Amazon: —
```

### Telegram riceve
```
🛰 TREND RADAR — Scansione 01/04/2025 08:00
━━━━━━━━━━━━━━━━━━
Segnali rilevati: 4
Forti: 2 | Medi: 2

#1 MASSAGGIATORE CERVICALE
├ Segnale: 🔥 FORTE
├ Google Trends: +87% (score 82/100)
├ ✅ Su Amazon M&S: #12 — Massaggiatore Collo Elettrico EMS
└ Rilevato: 01/04/2025 08:00
→ Vedi su Amazon
```

### File JSON (storico)
Ogni scansione salva `radar_results_YYYYMMDD_HHMM.json` nella stessa cartella.

---

## Eseguire in background (opzionale)

### Mac / Linux
```bash
nohup python trend_radar.py > radar.log 2>&1 &
```

### Windows (Task Scheduler)
1. Cerca "Utilità di pianificazione" nel menu Start
2. Crea attività → Azione: `python C:\percorso\trend_radar.py`
3. Trigger: all'accensione del PC

### Server VPS (consigliato per uso continuativo)
```bash
# Con screen
screen -S radar
python trend_radar.py
# Ctrl+A, D per staccare (continua in background)
```

---

## Risoluzione problemi

| Problema | Soluzione |
|---|---|
| `ModuleNotFoundError` | `pip install pytrends requests beautifulsoup4 schedule` |
| Google Trends rate limit | Lo script ha pause automatiche, riprova dopo 1h |
| Amazon blocca lo scraper | Cambia `User-Agent` nelle HEADERS, aggiungi pausa più lunga |
| Telegram non invia | Verifica token e chat_id, controlla che il bot sia attivo |
| Nessun segnale trovato | Abbassa `TRENDS_MIN_GROWTH` o aggiungi più keyword |
