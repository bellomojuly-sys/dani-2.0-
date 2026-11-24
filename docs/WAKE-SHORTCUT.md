# Dani ti sveglia — automazione Comandi su iPhone (D2-067)

Dani sa che hai posticipato la sveglia solo se l'iPhone glielo dice. Lo fa
un'automazione dell'app **Comandi** (Shortcuts), una volta sola.

Serve prima: l'app **ntfy** con il tuo topic (vedi il briefing, D2-061) e
`NTFY_TOPIC` su Render.

## 1. Sveglia posticipata
1. Comandi → **Automazione** → **+** → **Sveglia** → *Quando è posticipata*
   (scegli "Qualsiasi sveglia") → **Esegui immediatamente**.
2. Azione **Ottieni contenuti dell'URL**:
   - URL: `https://dani-2-0.onrender.com/api/wake`
   - Metodo: **POST**
   - Intestazioni: `X-Dani-Pin` = il tuo PIN, `Content-Type` = `application/json`
   - Corpo richiesta: **JSON**, campo `event` = `snoozed`
3. Salva.

## 2. Sveglia fermata
Uguale, con *Quando è fermata* e `event` = `stopped`.

## Cosa succede
- Ogni posticipo: subito una notifica a priorità massima, ogni volta più
  decisa ("Chief. Hai ignorato la sveglia 3 volte. Alzati." dalla terza), con
  il primo impegno della giornata; più due promemoria a +5 e +10 minuti.
- Sveglia fermata dopo un posticipo: "Brava, July".
- I promemoria già programmati non si possono ritirare: dicono "se sei già in
  piedi, ignora".

Limiti: il primo posticipo sveglia anche Render (circa un minuto). Su iPhone
la priorità massima di ntfy è una notifica "urgente" ma non suona come una
chiamata: una vera telefonata richiede un servizio a pagamento (M19,
ask-first).
