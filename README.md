# AmataShield

A digital **dairy transaction trust and evidence-management** platform for Rwanda's dairy value chain.
Farmers, buyers and drivers record the agreement, quantity, price, delivery, quality evidence, payment status and
disputes of a milk deal in one shared, time-stamped record.

**What it is not:** AmataShield does not guarantee milk quality, does not guarantee payment, does not hold or move money
(no escrow) and its AI never certifies milk or confirms a payment. Payment status is a *record* that both parties confirm.

## Quick start (Windows, macOS, Linux)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # Windows: copy .env.example .env   (then edit .env)
python -m backend.seed                # optional: fictional demo data
python run.py                         # open http://localhost:5000
```

Demo password for all seeded accounts: `Demo1234`
(phones: farmer 0788100001, buyer 0788200001, driver 0788300001, cooperative admin 0788000002, admin 0788000001).

To test on an Android phone on the same Wi-Fi, open `http://<your-computer-IP>:5000`.
Browsers only allow the camera on HTTPS or `localhost`; for phone camera tests use an HTTPS tunnel or deploy with HTTPS
(the "Choose file" button, which opens the phone camera app, works without HTTPS).

## Gemini AI
Put your key in `.env` as `GEMINI_API_KEY`. The key stays on the server. Without a key the AI buttons are hidden and
the rest of the app works normally.

## Run the tests
```bash
python -m unittest discover -s tests -v
```
The tests replace the Gemini network call with a fake, so they check AmataShield's rules, not Google's service.

## Project layout
```
backend/   app.py (factory) routes.py (all API rules) auth.py schemas.py database.py config.py seed.py ai/(gemini.py prompts.py)
frontend/  index.html css/style.css js/app.js assets/logo.svg      (single-page app, no build step)
database/  schema.sql  sample_data.sql
tests/     test_api.py
documentation/  API.md  ROADMAP.md  TEAM_TASKS.md
```

## Roles
| Role | Can do |
|---|---|
| Farmer | Post milk for sale, answer buy requests, add evidence, confirm payment received, open disputes |
| Buyer | Post purchase requests, accept sale posts, hire driver, accept delivery, report payment, open disputes |
| Driver | See agreed jobs, apply with a fee, add evidence, record pickup and arrival |
| Cooperative admin | Same-district oversight, mediation, record dispute outcome (created by a system admin) |
| System admin | Users, system statistics, mediation |

## Implemented vs proposed
Implemented: accounts and roles, marketplace with filters, two-party acceptance with terms fingerprint, driver applications,
evidence upload with SHA-256, pickup/arrival/receipt steps, payment *records*, disputes with proposals and agreement,
dashboards, Gemini drafts with mandatory human review, audit history, automated tests.
Proposed (not built): SMS/USSD, WhatsApp, in-app chat, GPS distance and routing, real mobile-money integration, escrow,
Kinyarwanda voice, offline mode, push notifications, PostgreSQL deployment, formal security audit.

## Known limitations
Login throttling is in memory (resets on restart). Files are stored on local disk. SQLite suits a pilot, not national scale.
The "1-minute booking window" idea from the notebook is not implemented. Distance filtering is by district only.
See `documentation/ROADMAP.md`.
