# Dani V1 — configurazione dal telefono

Tutto si fa dall'iPhone. Una volta sola, in quest'ordine. Spunta ogni riga.

**Trucco Safari:** per Render, GitHub, Outlook, Fitbit e Twilio usa Safari
(non le app) e tocca **aA → Richiedi sito desktop**.

**Regola d'oro:** chiavi, token e password si incollano **solo su Render**
(o nei secret di GitHub), mai in una chat.

**Su Render:** servizio *dani* → **Environment** → *Add Environment Variable*
→ **Save Changes**. Dopo ogni salvataggio Render riparte da solo (~1,5 min):
conviene aggiungere più variabili insieme e salvare una volta.

---

## 0. Render su `main` (2 min)
Da oggi `main` contiene tutta la V1.
- [ ] Render → servizio *dani* → **Settings** → **Branch** → `main` → salva
      (se il servizio è nato da Blueprint: **Blueprints** → *dani* → Settings → Branch `main`).
- [ ] Aspetta **Live** (Events: "Deploy live").

## 1. Render, pulizia (2 min)
- [ ] Environment: righe con **"Duplicate key"** in rosso → cestino 🗑.
- [ ] Togli `NTFY_TOPIC` (le notifiche ora arrivano su Telegram).
- [ ] C'è `DANI_URL` = `https://dani-2-0.onrender.com`.
- [ ] C'è `PYTHONUNBUFFERED` = `1` (senza, i Logs di Render non mostrano i messaggi di Dani).

## 2. Telegram — Dani come contatto (5 min) · app Telegram
Dettagli in `docs/TELEGRAM.md`.
- [ ] Cerca **@BotFather** → `/newbot` → nome `Dani` → username che finisce in `bot`.
- [ ] Copia il token → Render `TELEGRAM_BOT_TOKEN` → Save.
- [ ] Quando è Live, scrivi **"ciao"** al tuo bot: ti risponde con il tuo chat id.
- [ ] Render `TELEGRAM_CHAT_ID` = quel numero → Save.

## 2b. OpenAI — Whisper, i vocali (3 min) · Safari
Il credito resta sull'account; una chiave si può sempre creare nuova (quella
vecchia non si può più rileggere).
- [ ] Render → Environment: c'è già `OPENAI_API_KEY`? Se sì, salta.
- [ ] Se no: platform.openai.com/api-keys → **Create new secret key** → nome `Dani`
      → copia subito (si vede una volta sola) → Render `OPENAI_API_KEY` → Save.
- [ ] (Controllo credito: platform.openai.com/settings/organization/billing.)

## 3. Il pinger — Dani sempre sveglia (3 min) · Safari
- [ ] cron-job.org → account gratuito.
- [ ] **Create cronjob** → URL `https://dani-2-0.onrender.com/healthz` → ogni **10 minuti** → salva.
      (Senza questo, alle 6:45 Render dorme e la chiamata non parte.)

## 4. GitHub — il briefing delle 6:30 (3 min) · Safari, sito desktop
- [ ] github.com/bellomojuly-sys/dani-2.0-/settings/secrets/actions → *New repository secret*:
  - `DANI_URL` = `https://dani-2-0.onrender.com`
  - `DANI_PIN` = il tuo PIN
- [ ] (Prova) **Actions** → *Morning briefing* → **Run workflow**: il briefing arriva su Telegram.

## 5. Supabase — la memoria (5 min) · Safari
- [ ] supabase.com → accedi (anche con GitHub) → **New project** → nome `dani`,
      password a caso, **Region: Frankfurt (eu-central-1)** → *Create*.
- [ ] Copia lo schema: in un'altra scheda apri
      github.com/bellomojuly-sys/dani-2.0-/blob/main/docs/memory.sql → **Raw** →
      tieni premuto → *Seleziona tutto* → *Copia*.
- [ ] Supabase → **SQL Editor** → *New query* → incolla → **Run** → deve dire *Success*.
- [ ] **Project Settings → API** (o *Data API* / *API Keys*):
  - *Project URL* → Render `SUPABASE_URL`
  - chiave *service_role* (*Reveal*) → Render `SUPABASE_SERVICE_KEY` → Save.

## 6. Gmail — lettura (5 min) · Safari
- [ ] Account Google → **Sicurezza** → **Verifica in due passaggi** attiva.
- [ ] myaccount.google.com/apppasswords → nome `Dani` → *Crea* → copia le 16 lettere (senza spazi).
- [ ] Render: `GMAIL_USER` = il tuo indirizzo Gmail, `GMAIL_APP_PASSWORD` = le 16 lettere → Save.
      (Dani legge soltanto: non segna come lette, non sposta, non cancella, non invia.)

## 7. Outlook scuola → Gmail (3 min) · Safari, sito desktop
- [ ] outlook.office.com → ⚙️ **Impostazioni → Posta → Inoltro** (l'app Outlook non ce l'ha).
- [ ] **Abilita l'inoltro** → il tuo Gmail → *Mantieni una copia* ✅ → Salva.
- [ ] Se è bloccato dalla scuola: dimmelo, c'è un piano B.
- [ ] (Solo se la tua mail di scuola non è `@student.fontys.nl` / `@fontys.nl`)
      Render `SCHOOL_MAIL_MARKERS` = il tuo dominio.

## 8. Fitbit — sonno e attività (10 min) · Safari, sito desktop · dopo Supabase
- [ ] dev.fitbit.com → **Manage → Register An App**:
  - Application Name `Dani` · Website / Organization `https://dani-2-0.onrender.com`
  - **OAuth 2.0 Application Type: Personal**
  - **Redirect URL: `https://dani-2-0.onrender.com/fitbit/callback`**
  - Default Access Type: **Read Only**
- [ ] Render: `FITBIT_CLIENT_ID`, `FITBIT_CLIENT_SECRET` → Save.
- [ ] Quando è Live: `https://dani-2-0.onrender.com/fitbit/connect?key=IL_TUO_PIN`
      → **Consenti** → deve dire *"Fitbit collegato"*.

## 9. Twilio — Dani ti chiama per svegliarti (15 min) · Safari, sito desktop · a pagamento
Costo: un numero europeo (pochi €/mese) + ~0,024 $/min verso un cellulare olandese.
Dettagli in `docs/TWILIO.md`.
- [ ] twilio.com → crea l'account → verifica il tuo cellulare.
- [ ] **Upgrade** + prima ricarica (con l'account di prova la chiamata parte con
      un messaggio di Twilio).
- [ ] **Phone Numbers → Buy a number** → paese europeo (es. Paesi Bassi), capacità **Voice**.
      Se chiede documento o indirizzo (*Regulatory Bundle*), compilalo: può
      richiedere qualche ora/giorno di approvazione.
- [ ] Render:
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — home della console Twilio
  - `TWILIO_FROM` — il numero comprato, formato `+31…`
  - `MY_PHONE` — il tuo cellulare, formato `+31…`
  - `WAKE_TIME` — es. `06:45` (lunedì–sabato; domenica no) → Save.

## 10. iPhone — sveglia posticipata (5 min) · app Comandi
- [ ] Segui `docs/WAKE-SHORTCUT.md`: con Twilio attivo un posticipo fa partire subito la chiamata.

## 11. Notion (10 min) · app Notion
- [ ] Rileggi e correggi le righe **"da confermare"** in "Dani — chi sono e come
      pianifico" e "Dani — chi è Dani".
- [ ] Su Render, se mancano: `NOTION_CONTEXT_PAGE_ID`, `NOTION_PERSONA_PAGE_ID`,
      `NOTION_FOCUS_DB_ID`, `NOTION_MOOD_DB_ID`, `NOTION_USAGE_DB_ID`,
      `NOTION_PROJECTS_DB_ID`, `NOTION_PAGES` (gli ID te li posso preparare io).

## 12. Prova
- [ ] Segui `docs/TEST-GUIDA.md` e segna ✅/❌. Prova veloce della chiamata:
      metti `WAKE_TIME` a 5 minuti da adesso (passo D1), poi rimetti l'ora vera.
