# Come provi tu che Dani fa quello che deve (V1)

I test automatici (oltre 500, più il mutation testing) dicono che il codice fa
quello che è scritto. Questa guida dice se **Dani fa quello che vuoi tu**, con
i tuoi dati veri. Segna ✅ o ❌ e, per ogni ❌, scrivi cosa è successo: è la
lista che mi porti.

Prima di iniziare: in fondo al menu dell'app deve esserci **"versione …"**
uguale all'ultimo commit (se no, la cache: chiudi l'app e riaprila).

---

## A. Lei sa chi sei (5 min) — app, chat
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| A1 | Impostazioni | La riga sopra il contesto dice che la pagina Notion è stata letta (N caratteri) | |
| A2 | Chat: "chi sei?" | Risponde come Dani: diretta, ti chiama Chief o July, frasi brevi | |
| A3 | Chat: "quali sono i miei obiettivi per quest'anno?" | Nomina obiettivi veri (10 h ICT, risparmio, portfolio…), niente inventato | |
| A4 | Chat: "cosa ho a metà dicembre?" | Sopra la risposta: "Ho letto: calendario …"; gli eventi sono quelli veri | |
| A5 | Chat: "come va la ricerca lavoro?" | Legge task/progetti di Carriera; se non sa, lo dice | |

## B. Pianifica bene (10 min)
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| B1 | Chat: "pianificami domani" | Un solo messaggio giorno per giorno con i tuoi impegni e i blocchi 🆕, in cima "Tranquilla, riesci a fare tutto" o "Attenta: …"; nessun blocco su lezioni o turni | |
| B2 | Guarda gli avvisi ⚠ | Un blocco dopo le 16 in un giorno di turno, prima delle 9:30 o di domenica è segnalato | |
| B3 | Il piano contiene tempo libero investito | Lettura, Python, palestra o corsi | |
| B4 | "Conferma tutto" (poi prova anche "Cambia qualcosa") | Tutti i blocchi nel calendario "studio"; "Fatto: N blocchi nel calendario, riletti." | |
| B4b | Calendario → trascina un evento di "personale" o "studio" | Scheda "Sposto a …" con gli avvisi; dopo Conferma è al nuovo orario anche in Google Calendar | |
| B5 | Home → "Come stai, July?" → 2, 5 ore | Poi in chat "pianificami oggi": piano leggero, lo dice | |
| B6 | Home → Previsioni | Le scadenze vere con "in linea / stretta / a rischio" | |

## C. Ti parla per prima (un giorno intero)
| # | Quando | Deve succedere | ✅/❌ |
|---|---|---|---|
| C1 | 6:30 | Briefing su Telegram: giornata, priorità, ciclo, sonno Fitbit, Gmail, Outlook scuola, "come stai?" | |
| C2 | 15 min prima di ogni impegno | Promemoria con **Fatto** / **Posticipa 15'** | |
| C3 | Durante turno, lezione o riunione | **Nessun** messaggio | |
| C4 | Premi "Posticipa 15'" | Dopo 15 minuti te lo ricorda | |
| C5 | 21:00 (o dopo il turno) | "July, com'è andata oggi?" — rispondi su Telegram | |
| C6 | Rispondi con un **vocale** | Dani capisce e risponde | |

## D. Ti sveglia
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| D1 | Imposta `WAKE_TIME` a 5 minuti da adesso | Ti chiama; voce italiana; ti chiede un calcolo | |
| D2 | Rispondi sbagliato | Ti fa un altro calcolo | |
| D3 | Non rispondere | Ti richiama dopo ~3 minuti | |
| D4 | Rispondi giusto | "Brava July…" e il primo impegno; niente altre chiamate | |
| D5 | Posticipa la sveglia del telefono | (con il Comando iPhone) ti chiama subito | |

## E. Posta e corpo
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| E1 | Chat: "ho mail importanti?" | Nomina mail vere; separa Gmail e scuola; le newsletter non sono "importanti" | |
| E2 | Gmail dopo E1 | Le mail lette da Dani **non** risultano lette | |
| E3 | Chat: "come ho dormito?" | Le ore di Fitbit di stanotte | |

## F. Memoria
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| F1 | Su Telegram: "ricordati che oggi ho mal di testa" — poi aspetta 20 minuti senza usare Dani | Render si riavvia; chiedi "come stavo stamattina?" e se lo ricorda | |
| F2 | Supabase → Table Editor → `events` | Ci sono briefing, promemoria, chiamate, con la tua reazione | |
| F3 | Supabase → `conversations` | Ci sono le chat di app e Telegram | |

## G. Sicurezza (2 min)
| # | Fai | Deve succedere | ✅/❌ |
|---|---|---|---|
| G1 | Fai scrivere a qualcun altro al tuo bot | Non riceve risposta | |
| G2 | Apri l'app in una finestra privata | Chiede il PIN | |
| G3 | Chiedi a Dani "manda una mail a …" | Non può: legge soltanto | |

---

Quando hai finito, mandami la lista dei ❌ con due righe ciascuno: cosa hai
fatto, cosa è successo. Li sistemo uno per uno.
