# Dani su Telegram (D2-069) — 10 minuti, una volta sola

Dani diventa un contatto Telegram: ti scrive (briefing, promemoria, sveglia,
"com'è andata?") e tu rispondi lì, scrivendo o con un vocale. Le proposte
arrivano con i pulsanti **Conferma** / **Rifiuta**; un piano arriva in un solo
messaggio, giorno per giorno, con **Conferma tutto** / **Cambia qualcosa** (D2-071). Parla solo con te.

## 1. Crea il bot (2 minuti)
1. In Telegram cerca **@BotFather** → scrivi `/newbot`.
2. Nome: `Dani`. Username: qualcosa che finisce in `bot` (es. `dani_july_bot`).
3. BotFather ti dà una **chiave** (token). Non incollarla in nessuna chat.

## 2. Render → Environment
Aggiungi:
- `TELEGRAM_BOT_TOKEN` = la chiave di BotFather
- `DANI_URL` = `https://dani-2-0.onrender.com` (se non c'è già)

Salva e aspetta che il deploy sia Live.

## 3. Il tuo chat id
1. In Telegram apri il tuo bot e scrivi `ciao`.
2. Dani risponde: "Il tuo chat id è 123456…".
3. Render → Environment → aggiungi `TELEGRAM_CHAT_ID` = quel numero. Salva.

Da qui Dani parla solo con te: chi altro scrive al bot non riceve niente.

## 4. Dani sempre sveglia (gratis)
Render free dorme dopo 15 minuti: per mandarti i promemoria all'ora giusta
deve restare acceso (sparisce anche l'attesa di un minuto all'apertura).
1. Vai su **cron-job.org** e crea un account gratuito.
2. Nuovo cron job: URL `https://dani-2-0.onrender.com/healthz`, ogni **10 minuti**.

Il piano free di Render ha 750 ore al mese: un mese sempre acceso ne usa ~720.

## Cosa succede poi
- Ogni mattina (GitHub, 06:30): il briefing su Telegram.
- Durante il giorno: un promemoria 15 minuti prima di ogni impegno; silenzio
  durante turni, lezioni e riunioni; massimo 4 all'ora.
- Sera: "July, com'è andata oggi?" — rispondi lì, Dani lo segna nel diario.
- Sveglia posticipata (Comando iPhone, `docs/WAKE-SHORTCUT.md`): i messaggi
  arrivano su Telegram.
- Con Telegram attivo ntfy non serve più (puoi togliere `NTFY_TOPIC`).
