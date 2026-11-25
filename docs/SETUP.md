# Dani — configurazione completa (V1)

Una volta sola, in quest'ordine. Ogni passo dice **dove** cliccare e **cosa
incollare su Render** (Render → servizio *dani-2.0-* → **Environment** →
*Add Environment Variable* → **Save Changes**). Dopo ogni salvataggio Render
riparte da solo (~1 minuto e mezzo).

> Regola d'oro: chiavi e password si incollano **solo su Render**, mai in una
> chat, mai su GitHub.

---

## 1. Render, pulizia (2 min)
1. Render → Environment.
2. Se vedi righe con **"Duplicate key"** in rosso: cestino 🗑 su quelle righe.
3. Togli `NTFY_TOPIC` (con Telegram non serve).
4. Controlla che ci sia `DANI_URL` = `https://dani-2-0.onrender.com`.

## 2. Supabase — la memoria di Dani (5 min)
1. supabase.com → **Start your project** → accedi (anche con GitHub).
2. **New project** → nome `dani` → password a caso (non ti serve) → **Region: Frankfurt (eu-central-1)** → *Create*.
3. A sinistra **SQL Editor** → *New query* → incolla **tutto** il file `docs/memory.sql` → **Run**. Deve dire *Success*.
4. A sinistra **Project Settings → API**:
   - *Project URL* → su Render come `SUPABASE_URL`
   - *service_role* (clic su *Reveal*) → su Render come `SUPABASE_SERVICE_KEY`
5. Per vedere i dati: **Table Editor** (tabelle `conversations`, `events`, `measures`).

## 3. Telegram — Dani come contatto (5 min)
Vedi `docs/TELEGRAM.md`: @BotFather → `/newbot` → `TELEGRAM_BOT_TOKEN` su Render
→ scrivi "ciao" al bot → `TELEGRAM_CHAT_ID` su Render.

## 4. Il pinger — Dani sempre sveglia (3 min)
1. cron-job.org → crea un account gratuito.
2. **Create cronjob** → URL `https://dani-2-0.onrender.com/healthz` → ogni **10 minuti** → salva.

## 5. Gmail — lettura (5 min)
1. Il tuo account Google → **Sicurezza** → attiva la **Verifica in due passaggi** se non c'è.
2. Cerca **"Password per le app"** (myaccount.google.com/apppasswords) → nome `Dani` → *Crea*.
3. Copia le 16 lettere (senza spazi). Su Render:
   - `GMAIL_USER` = il tuo indirizzo Gmail
   - `GMAIL_APP_PASSWORD` = le 16 lettere
4. Dani legge soltanto: non segna come lette, non sposta, non cancella, non invia.

## 6. Outlook scuola → Gmail (3 min)
1. outlook.office.com → ⚙️ **Impostazioni → Posta → Inoltro**.
2. **Abilita l'inoltro** → il tuo indirizzo Gmail → *Mantieni una copia* ✅ → Salva.
3. Se l'opzione non c'è o è bloccata dalla scuola, scrivimelo: c'è un piano B.
4. (Facoltativo) Se il tuo indirizzo di scuola non è `@student.fontys.nl` o
   `@fontys.nl`, metti su Render `SCHOOL_MAIL_MARKERS` = il tuo dominio di scuola.

## 7. Fitbit — sonno e attività (10 min)
1. dev.fitbit.com → **Manage → Register An App**:
   - Application Name: `Dani` · Website / Organization: `https://dani-2-0.onrender.com`
   - **OAuth 2.0 Application Type: Personal**
   - **Redirect URL: `https://dani-2-0.onrender.com/fitbit/callback`**
   - Default Access Type: **Read Only**
2. Salva → copia *OAuth 2.0 Client ID* e *Client Secret*. Su Render:
   `FITBIT_CLIENT_ID`, `FITBIT_CLIENT_SECRET` (serve Supabase già fatto).
3. Quando Render è Live, apri nel browser:
   `https://dani-2-0.onrender.com/fitbit/connect?key=IL_TUO_PIN`
   → **Consenti** → deve dire *"Fitbit collegato"*.

## 8. Twilio — la chiamata sveglia (15 min)
Vedi `docs/TWILIO.md`. In breve: account → Upgrade → **numero europeo** →
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `MY_PHONE`,
`WAKE_TIME` (es. `06:45`) su Render.

## 9. GitHub (3 min)
1. github.com/bellomojuly-sys/dani-2.0-/settings/secrets/actions → *New repository secret*:
   `DANI_URL` = `https://dani-2-0.onrender.com`, `DANI_PIN` = il tuo PIN.
2. Apri la PR #4 → **Merge pull request** → *Confirm merge*.

## 10. iPhone — la sveglia posticipata (5 min)
Vedi `docs/WAKE-SHORTCUT.md`.

## 11. Notion (10 min)
Rileggi e correggi "Dani — chi sono e come pianifico" e "Dani — chi è Dani"
(le righe "da confermare"). Su Render, se mancano:
`NOTION_CONTEXT_PAGE_ID`, `NOTION_PERSONA_PAGE_ID`, `NOTION_FOCUS_DB_ID`,
`NOTION_MOOD_DB_ID`, `NOTION_USAGE_DB_ID`, `NOTION_PROJECTS_DB_ID`, `NOTION_PAGES`.

## 12. Prova
Segui `docs/TEST-GUIDA.md`.
