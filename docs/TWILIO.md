# Dani ti chiama per svegliarti (D2-070)

All'ora della sveglia (e subito se la posticipi) Dani ti telefona e ti fa un
calcolo: rispondi a voce o con la tastiera. Giusto → "Brava July" e il primo
impegno. Sbagliato → un altro calcolo. Nessuna risposta → ti richiama ogni 3
minuti, fino a 10 volte, poi ti scrive.

## 1. Account Twilio (10 minuti)
1. Vai su twilio.com e crea un account; verifica il tuo numero di cellulare.
2. Passa a un account a pagamento (Upgrade) e fai la prima ricarica: con l'account di prova
   le chiamate partono con un messaggio di Twilio e vanno solo a numeri verificati.
3. **Compra un numero europeo (EEA)** con capacità *Voice*: le chiamate a un
   cellulare olandese costano ~0,024 $/min da un numero EEA e ~0,28 $/min da un
   numero USA. Alcuni paesi chiedono un documento o un indirizzo (Regulatory Bundle).

## 2. Render → Environment
- `TWILIO_ACCOUNT_SID` e `TWILIO_AUTH_TOKEN` — dalla home della console Twilio
- `TWILIO_FROM` — il numero comprato, formato `+31…` / `+39…`
- `MY_PHONE` — il tuo cellulare, formato `+31…`
- `WAKE_TIME` — l'ora della sveglia, es. `06:45` (lunedì–sabato; domenica no)
- `DANI_URL` — `https://dani-2-0.onrender.com` (se non c'è già)

## 3. Dani sveglia alle 6:45
Render free dorme: serve il pinger gratuito di `docs/TELEGRAM.md` (passo 4,
cron-job.org su `/healthz` ogni 10 minuti), altrimenti alle 6:45 Dani dorme.

## 4. Il Comando iPhone (facoltativo ma utile)
Con l'automazione di `docs/WAKE-SHORTCUT.md` un posticipo fa partire subito la chiamata.

Sicurezza: Dani accetta solo richieste firmate da Twilio (firma
X-Twilio-Signature con il tuo Auth Token): nessun altro può segnarti "sveglia".
