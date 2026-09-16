<div align="center">

# ⚖️ THEMIS Monitor

**Free, local-first monitoring of Brazilian court cases — straight from the official CNJ data source, without leaving your computer.**

[![CI](https://github.com/Dramorimrodrigues/themis-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Dramorimrodrigues/themis-monitor/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-c9a440.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3d1a6e.svg)](https://www.python.org/downloads/)
[![Source: DataJud/CNJ](https://img.shields.io/badge/source-DataJud%20%2F%20CNJ-1a8a5a.svg)](https://datajud-wiki.cnj.jus.br/api-publica/)
[![Windows · macOS · Linux](https://img.shields.io/badge/runs%20on-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-555.svg)](#install-in-3-steps)

</div>

> ### 🇧🇷 Não lê inglês? Sem problema.
> **Clique com o botão direito nesta página → "Traduzir para português"** (Chrome, Edge e Safari fazem isso na hora).
> Ou leia a **versão completa em português: [README.pt-BR.md](README.pt-BR.md)** — e a interface do programa é toda em português.

<div align="center">
<img src="docs/screenshots/painel.png" alt="THEMIS Monitor dashboard" width="880">
</div>

---

## Why THEMIS exists

Every Brazilian lawyer knows the ritual: open three court portals, solve CAPTCHAs, check case by case, hope nothing slipped through. Or pay R$ 80–300 a month for a service that does it for you — and keeps your clients' data on someone else's server.

THEMIS does the boring part for free, with official data, **on your own machine**:

| | THEMIS | Paid services | Manual lookup |
|---|:---:|:---:|:---:|
| Cost | **R$ 0** | R$ 80–300 / month | your time |
| Data source | official CNJ API | varies | court portals |
| Where your data lives | **your PC** | their cloud | — |
| Detects new filings | ✅ | ✅ | 👀 |
| Urgency alerts (seizure, injunction, arrest warrant…) | ✅ | depends | ❌ |
| Estimated deadlines from filings | ✅ | ✅ | ❌ |
| E-mail / WhatsApp notifications | ✅ | ✅ | ❌ |
| Open source, auditable | ✅ | ❌ | — |

## What it does

- 🔎 **Queries every case** on your list against the [DataJud public API](https://datajud-wiki.cnj.jus.br/api-publica/) of the National Council of Justice (CNJ) — the same database behind Brazil's official judicial statistics.
- 🆕 **Spots what's new** by diffing against the last run and highlights it.
- 🚨 **Flags urgency** with keyword detection on filings: *penhora* (seizure), *bloqueio* (asset freeze), *liminar* (injunction), *mandado de prisão* (arrest warrant), *leilão* (auction)… turn red.
- ⏱ **Estimates deadlines**: a summons automatically becomes "estimated deadline in 15 days".
- 💤 **Highlights stalled cases** with no activity for 30+ days (configurable).
- 📊 **Generates a polished HTML report** with search and filters, plus **CSV spreadsheets** that open in Excel.
- 🖥 **Local web dashboard** to look up any case number instantly and bulk-import cases.
- 📧 **Notifies via e-mail or WhatsApp** when something changes (optional).
- 🔒 **Everything stays local**: one SQLite file in your folder. No sign-up, no cloud, no subscription.

<div align="center">
<img src="docs/screenshots/demo.gif" alt="Demo: double-click monitorar.bat and the report opens in the browser" width="720">
</div>

## What it does NOT do (read before relying on it)

> **THEMIS does not replace PJe Push, the Official Gazette or electronic service of process for counting hard deadlines.**

- DataJud usually reflects court activity **24–48 hours later** — sometimes more, depending on the court.
- Due to data-protection rules (LGPD), DataJud **does not expose party or attorney names**. You provide the case numbers; it cannot discover them from your bar number alone (the dashboard includes a guided helper for the court portals).
- Cases under **judicial secrecy** don't appear.
- "Estimated deadlines" are a **simple calendar-day count** from the filing date — a reminder, not a procedural computation.

Use THEMIS as your daily radar. For deadlines, always confirm with the official source.

## Install in 3 steps

### Windows

1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/) — tick **"Add Python to PATH"** on the first screen.
2. **Download THEMIS**: green **Code → Download ZIP** button above, unzip anywhere.
3. **Double-click `instalar.bat`**. Done.

Then open `config.ini` (your name and bar number), paste your cases into `processos.txt` and double-click **`monitorar.bat`**.

### macOS / Linux

```bash
git clone https://github.com/Dramorimrodrigues/themis-monitor.git
cd themis-monitor
./themis.sh instalar
./themis.sh monitorar
```

## Day-to-day use

| I want to… | Windows | macOS / Linux |
|---|---|---|
| Monitor all my cases | `monitorar.bat` | `./themis.sh monitorar` |
| Open the interactive dashboard | `painel.bat` | `./themis.sh painel` |
| Look up a single case | `consultar.bat` | `./themis.sh consultar 0000000-00.0000.0.00.0000` |
| Test the DataJud connection | `testar.bat` | `./themis.sh testar` |
| Find my cases by bar number | `buscar-oab.bat` | `./themis.sh oab` |

### The `processos.txt` file

One case per line. The number alone is enough; the rest is optional:

```
0000001-05.2025.8.26.0100
0000001-05.2025.8.26.0100 | Case nickname
0000001-05.2025.8.26.0100 | Case nickname | Client name | Civil
```

THEMIS **identifies the court from the number** and **validates the CNJ check digit** — a typo is caught before any query is made.

### Run automatically every day

**Windows:** Task Scheduler → Create Basic Task → Daily 07:00 → Start a program → `monitorar.bat`.
**macOS/Linux:** `crontab -e` and add `0 7 * * * /path/to/themis-monitor/themis.sh monitorar --sem-navegador`.

### Notifications (optional)

Edit the `[notificacoes]` section of `config.ini`:

- **E-mail (Gmail):** enable 2-step verification, create an [app password](https://myaccount.google.com/apppasswords), set `email_ativo = sim`, sender, password and recipient.
- **WhatsApp (CallMeBot, free):** follow the instructions inside `config.ini`.

## Supported courts

Every court exposed by DataJud — **92 courts**: STF, STJ, TST, TSE, STM, all 6 Federal Regional Courts (TRF), all 24 Labor Regional Courts (TRT), all 27 State Courts (TJ), all 27 Electoral Regional Courts (TRE) and the 3 State Military Courts (TJM). The court is inferred automatically from the CNJ case number.

## Security & privacy

- The dashboard server binds **only to 127.0.0.1** and rejects requests that don't originate from the dashboard itself.
- The only key in the code is the **official public key** the CNJ publishes for the DataJud API — none of your credentials live in the repository.
- HTTPS **always verified**; parameterized SQL; every string from the court is escaped before becoming HTML; CSV cells are protected against formula injection.
- `config.ini`, `processos.txt` and the database are git-ignored.

Details and how to report issues: [SECURITY.md](SECURITY.md).

## Under the hood

```
themis.py                ← entry point (monitorar | painel | consultar | testar | oab)
themis/
  cnj.py                 ← clean, format, check digit, court identification
  constantes.py          ← court catalogue, keywords, deadline table
  analise.py             ← urgency, estimated deadlines, formatting
  config.py              ← config.ini, processos.txt
  banco.py               ← SQLite: persistence, diffing, backups
  datajud.py             ← HTTP client for the CNJ API
  notificacoes.py        ← e-mail and WhatsApp
  relatorio.py           ← HTML and CSV
  painel.py              ← local web server
  descoberta_oab.py      ← bar-number discovery guide
tests/                   ← pytest, no network access
```

Pure Python: the only dependencies are `requests` and `truststore`. Tests run on Windows and Linux on every commit.

## Roadmap

- [ ] Edit nickname/client/area from the dashboard
- [ ] "Refresh now" button in the dashboard
- [ ] PDF export
- [ ] `.exe` installer with no Python required
- [ ] Automatic discovery by bar number (blocked on court portals offering CAPTCHA-free APIs)
- [ ] Multi-user edition for law firms

Want to help? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author & license

Created by **Márcio Luis Amorim**, a practicing lawyer (OAB/RJ) and member of the Artificial Intelligence Committee of the Rio de Janeiro Bar Association, from a tool originally built for his own firm. Developed with AI assistance (Claude, Anthropic).

Licensed under **MIT** — use, modify and redistribute freely, keeping the copyright notice:

```
Copyright (c) 2026 Márcio Luis Amorim
```

If THEMIS saved you an hour on court portals, leave a ⭐ — it helps other lawyers find the project.

---

<div align="center">
<sub>THEMIS Monitor is not affiliated with the CNJ or any court. DataJud is a public service of Brazil's National Council of Justice.</sub>
</div>
