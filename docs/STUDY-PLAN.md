# Piano di studio — Dani e AMEXIO

Copia nella repo del documento "Piano di studio — Dani e AMEXIO" (Claude Docs,
16 ottobre 2026). È lo stesso file nelle repo `dani-2.0-` e
`amexio-ai-data-generetor-`. Se cambia, va cambiato in entrambe e nel documento
originale.

## Come funziona

Ogni milestone delle due roadmap è un obiettivo didattico: **la microfase si
chiude quando il codice funziona, l'obiettivo si chiude solo quando Giulia
supera la prova orale.**

Il ciclo per ogni obiettivo:

1. **Teoria.** Claude spiega l'argomento intero, non solo il pezzo che serve al progetto.
2. **Appunti.** Giulia scrive sul quaderno la logica di base con parole sue, senza copiare.
3. **Pratica.** Si fanno le microfasi della roadmap. Prima di chiedere all'AI, Giulia scrive cosa si aspetta che faccia la soluzione.
4. **Correzione.** Si rivedono insieme codice e test; ogni riga che non sa spiegare torna indietro.
5. **Prova.** Giulia risponde alle domande d'esame senza guardare gli appunti, comprese quelle su cose che il progetto non usa. Solo allora si passa avanti.

Regole:

- **Il confine del sapere** è l'argomento come lo conosce chi lavora in quel tipo di progetto. Se il teacher chiede di un tipo di test non usato, Giulia sa dire cos'è e perché non l'ha usato.
- **Gli argomenti comuni si studiano una volta** (Fondamenta) e valgono per entrambi i progetti.
- **Le parti già fatte vanno recuperate.** Le milestone chiuse senza aver capito (AMEXIO M00–M03, Dani M01–M03) hanno un ripasso con la stessa prova.
- **Il codice generato dall'AI si accetta solo dopo averlo giudicato:** cosa fa, perché così, come si rompe.
- Ogni obiettivo superato diventa un Decision Log o un'evidence taggata nel portfolio MA-AAI.
- Se una settimana salta, si sposta l'obiettivo intero, non si accorcia la prova.

## Ordine di marcia

Si parte mercoledì 21 ottobre dal testing, perché entrambe le roadmap sono
ferme lì: D2-020a blocca M04 di Dani e AX-018a viene prima di AX-019. Poi i
ripassi delle parti già fatte, poi il calendario degli sprint.

| Periodo | Fondamenta | Dani | AMEXIO |
|---|---|---|---|
| 21–23 ott | F1 Testing; ripasso F2 e F3 | D2-020a; ripasso D-A (M01–M03) | AX-018a, AX-019, AX-020; ripasso A-A (M00–M03) |
| Sprint 3 (26 ott–13 nov) | F4 Persistenza, F6 Osservabilità ed evals, F8 Design e contratti | D-B (M05–M06), D-C (M12), D-D (M13), F6 su M04 | A-B (M04), A-C (M05), F4 su M06, A-E (M07), A-F (M08) |
| Sprint 4 (16–27 nov) | F5 Errori e affidabilità | D-E MCP (M16–M17) | A-F (M09), A-E (M10–M11) |
| Sprint 5 (30 nov–18 dic) | F7 Git, CI e collaborazione | D-E (M18), D-F (M19–M20) | A-G (M12–M13), A-H (M14) |
| Sprint 6 (4–15 gen) | Ripasso generale per la valutazione | Prove orali dei gate | A-H (M15) |

## Stato degli obiettivi

Aggiornato dall'agente quando Giulia supera una prova (mai prima).

| Obiettivo | Stato |
|---|---|
| F1 Testing | in corso |
| F2, F3 | ripasso da fare |
| D-A (Dani M01–M03) | ripasso da fare |
| A-A (AMEXIO M00–M03) | ripasso da fare |
| Tutti gli altri | non iniziati |

## Fondamenta comuni

### F1 — Testing

**Teoria:** a cosa serve un test e cosa lo rende buono (fallisce per il motivo giusto, controlla una cosa, è deterministico e indipendente). Piramide dei test: unitari, di integrazione, end-to-end. Test di regressione, di contratto, property-based, mutation testing. Struttura Arrange–Act–Assert. Coverage contro qualità. In pytest: fixture, `parametrize`, `pytest.raises`, `conftest.py`. Come si testa codice che chiama un LLM: mock del modello per la logica, evals per il comportamento.
**Pratica:** D2-020a, AX-018a, AX-019; poi D2-025 e ogni test nuovo.
**Prova:**
- Per ogni test del progetto, cosa dimostra in una frase?
- Rompo il codice in un punto a scelta del teacher: quale test deve fallire, e fallisce davvero?
- Differenza tra test unitario, di integrazione ed end-to-end, con un esempio da ciascun progetto.
- Cos'è il mutation testing e perché il 100% di coverage non basta?
- Come testi una funzione che chiama un LLM senza pagare né dipendere dalla risposta del modello?

### F2 — Modellazione dei dati e validazione

**Teoria:** entità, attributi, relazioni e cardinalità (1:1, 1:N, N:M). Integrità referenziale e ID stabili. Riferimenti invece di copie, normalizzazione contro dati annidati. Type hints. Pydantic: tipi, vincoli, `Enum`, validatori di campo e di modello, serializzazione, JSON Schema. Date in ISO 8601, soldi come `Decimal` più valuta e perché non `float`.
**Pratica:** ripasso di AMEXIO M00–M02 e Dani D2-010; poi D2-027, D2-028, D2-031.
**Prova:**
- Disegna a mano il modello del dossier 100101 con le cardinalità.
- Perché un documento contiene l'ID di una persona e non il suo nome?
- Differenza tra validatore di campo e di modello, con un esempio di vincolo tra due campi.
- Perché un importo non va salvato come `float`?

### F3 — LLM via API e output strutturati

**Teoria:** come funziona una chiamata (messaggi system/user/assistant, token, contesto, temperatura). JSON mode, structured outputs e tool calling a confronto. Validare l'output e gestire il rifiuto (retry, errore esplicito). Costi, limiti di rate, gestione delle chiavi.
**Pratica:** ripasso di Dani M01 (D2-006–D2-010); in AMEXIO, la regola "l'AI scrive, il codice tiene i fatti".
**Prova:**
- Cosa succede, passo per passo, tra `main.py` e la risposta del modello?
- Perché il modello può restituire JSON valido ma sbagliato, e come te ne accorgi?
- Perché in AMEXIO gli ID non li genera mai l'LLM?

### F4 — Persistenza e riproducibilità

**Teoria:** serializzazione in JSON, versione dello schema e migrazioni, salvataggio deterministico. Scritture atomiche, rilettura dopo la scrittura, idempotenza.
**Pratica:** AMEXIO AX-018 (ripasso) e M06; Dani M05.
**Prova:**
- Perché salvare due volte lo stesso caso deve dare file identici?
- Cosa fai se domani lo schema cambia e devi caricare un run vecchio?
- Cos'è un'operazione idempotente? Un esempio da ciascun progetto.

### F5 — Errori e affidabilità

**Teoria:** eccezioni in Python, fallire forte contro fallire in silenzio, errori strutturati, timeout, retry con backoff, degrado controllato.
**Pratica:** Dani D2-011a, D2-020, D2-089; AMEXIO AX-024, M13.
**Prova:**
- Perché un placeholder non risolto deve fermare il run invece di lasciare uno spazio vuoto?
- Quando un retry è pericoloso?
- Come distingue il client un errore di dominio da un guasto tecnico?

### F6 — Osservabilità ed evals

**Teoria:** log, tracce e run ID; oscuramento dei dati sensibili; dataset di valutazione; differenza tra test ed eval; regressioni su sistemi non deterministici.
**Pratica:** Dani M04; AMEXIO AX-030 (change log) e M12.
**Prova:**
- Ricostruisci un run di Dani solo dalla traccia.
- Perché per un agente non bastano i test unitari?
- Come misuri se una modifica al prompt ha peggiorato il sistema?

### F7 — Git, CI e collaborazione

**Teoria:** branch, commit atomici, pull request e code review, tag e versioni semantiche, integrazione continua con GitHub Actions.
**Pratica:** AMEXIO AX-019 (test a ogni push), AX-020 (tag v1), AX-075; tutti i commit di Dani.
**Prova:**
- Cosa succede tecnicamente quando faccio push e parte la CI?
- Perché il case model cambia solo con una nuova versione concordata?

### F8 — Design del software e contratti

**Teoria:** separazione delle responsabilità, interfacce e contratti tra moduli, configurazione come dati, dipendenze, principio del minimo privilegio.
**Pratica:** AMEXIO AX-005 (ripasso), AX-042, M07, M10; Dani M17.
**Prova:**
- Cosa promette il contratto del case model agli altri moduli?
- Perché la review UI non può scrivere file direttamente?
- Quando una regola va nel codice e quando nella configurazione?

## Dani

M07–M11 e M14–M15 restano fuori da dicembre come nella roadmap.

### D-A — Il loop dell'agente e il tool calling (M01–M03, ripasso)

**Teoria:** agente contro singola chiamata. Function calling: schema del tool in JSON Schema, richiesta del modello, dispatch, risultato restituito. Loop limitato e condizioni di uscita. Skill e istruzioni per gruppi di tool. Errori tipici: tool inventato, argomenti sbagliati, risultato inventato. Pattern noti (ReAct, plan-and-execute) e quando servono.
**Pratica:** ripasso di D2-011–D2-020 e D2-017a.
**Prova:**
- Racconta il giro completo LLM → funzione → LLM sulla traccia di un run vero (Gate M02).
- Perché la validazione sta dentro la funzione del tool e non solo nello schema?
- Cosa succede se il modello chiama un tool che non esiste? Fammelo vedere.
- Perché serve un limite di iterazioni?

### D-B — Stato, dipendenze e grafi (M05–M06)

**Teoria:** macchine a stati e transizioni lecite. Grafi diretti, rilevamento dei cicli (DFS), ordinamento topologico. Come si deriva il prossimo task disponibile.
**Pratica:** D2-026–D2-035, D2-030a, D2-030b.
**Prova:**
- Disegna a mano il grafo di un progetto e trova un ciclo con l'algoritmo, non a occhio.
- Perché lo stato deve sopravvivere al riavvio, e come lo dimostri?
- Perché il tool store può scrivere solo in un documento pre-registrato?

### D-C — Tempo e calendari (M12)

**Teoria:** fusi orari e ora legale, datetime naive e aware, intervalli, fusione di intervalli sovrapposti, calcolo degli slot liberi.
**Pratica:** D2-061–D2-064.
**Prova:**
- Perché un evento alle 2:30 del 25 ottobre 2026 è un problema ad Amsterdam?
- Calcola a mano gli slot liberi di una giornata con tre eventi sovrapposti.

### D-D — Pianificazione con vincoli (M13)

**Teoria:** vincoli rigidi e flessibili, blocchi fissi e spostabili, greedy contro solver, ripianificazione che tocca solo il necessario, spiegare un piano a partire dal diff.
**Pratica:** D2-066–D2-070.
**Prova:**
- Quando un approccio greedy dà un piano sbagliato? Un esempio.
- Come dimostri che una ripianificazione non ha perso niente?

### D-E — MCP e supervisor (M16–M18)

**Teoria:** host, client e server; JSON-RPC; trasporti stdio e HTTP; tool, resource e prompt. Function calling contro MCP. Separare lettura, proposta e scrittura; autorizzazioni e minimo privilegio. Il supervisor come unico punto di decisione.
**Pratica:** D2-081–D2-095.
**Prova:**
- Dove gira il modello e dove gira il tool? (Gate M16)
- Cosa cambia passando a MCP e cosa non deve cambiare? (Gate M17)
- Perché uno specialista non può autorizzarsi da solo?

### D-F — Integrazioni con API esterne (M19–M20)

**Teoria:** API REST, OAuth e scope, paginazione e limiti di rate, fixture offline, mappatura verso i modelli di dominio, idempotenza, rilettura dopo la scrittura, freschezza dei dati.
**Pratica:** D2-096–D2-105.
**Prova:**
- Perché un token in sola lettura viene prima di uno in scrittura?
- Come eviti che un retry crei due pagine Notion o due eventi?
- Quando un dato del calendario è troppo vecchio per agire?

## AMEXIO

Otto obiettivi propri sul modulo di Giulia (case model, configurazione, review).

### A-A — Il case model (M00–M03, ripasso)

**Teoria:** F2 applicata al dossier HR: persona, organizzazione, impiego, evento, documento, fatti del dossier, contenitore Case. Pattern degli ID, rifiuto degli ID in ingresso, fixture di riferimento.
**Pratica:** ripasso di AX-001–AX-018, in particolare AX-008 e i test scritti da Claude in AX-007; poi AX-018a, AX-019, AX-020.
**Prova:**
- Spiega ogni campo del modello Document e perché c'è.
- Perché un ID scritto dall'LLM viene rifiutato?
- Cosa garantisce il test di regressione sul dossier 100101, e cosa no?

### A-B — Template e risoluzione dei fatti (M04)

**Teoria:** motori di template (Jinja2), risoluzione per percorso, valori mancanti (`StrictUndefined`). Separare il dato salvato dalla sua formattazione; date e importi per lingua (locale).
**Pratica:** AX-021–AX-025.
**Prova:**
- Perché la data si formatta solo quando il testo viene riempito?
- Cosa succede con un placeholder sbagliato, e perché è meglio di uno spazio vuoto?

### A-C — Dipendenze tra dati e propagazione delle modifiche (M05)

**Teoria:** indice inverso (fatto → documenti che lo usano), un solo punto di scrittura, registro delle modifiche, idea di base dell'event sourcing.
**Pratica:** AX-026–AX-030.
**Prova:**
- Correggo lo stipendio lordo: quali documenti cambiano e come lo sai senza aprirli?
- Perché tutte le modifiche passano da una sola funzione?

### A-D — Versioni e riproducibilità dei run (M06)

**Teoria:** F4 applicata ai run: cartella per run, versione nello schema, salvataggio deterministico, test congiunto con l'export.
**Pratica:** AX-031–AX-035.
**Prova:**
- Come dimostri che un run di un mese fa produce lo stesso XML di allora?

### A-E — Configurazione e domini (M07, M10–M11)

**Teoria:** configurazione come dati e il suo schema, confine tra dominio e scenario, regole di coerenza come dati, architettura a plugin: aggiungere un dominio senza toccare il core.
**Pratica:** AX-036–AX-040, AX-051–AX-060.
**Prova:**
- Dove passa la linea tra dominio e scenario? Classifica tre esempi nuovi.
- Come verifichi che nel core non resta nessuna parola HR?
- Scrivi a mano una regola di coerenza come dato.

### A-F — Interfaccia di review e human-in-the-loop (M08–M09)

**Teoria:** opzioni per l'interfaccia (web app, notebook, riga di comando) e criteri per sceglierle. Strato API tra interfaccia e dati. Read-only prima, modifica poi. Punti di revisione umana in una pipeline.
**Pratica:** AX-041–AX-050.
**Prova:**
- Quali opzioni hai scartato per la review e perché?
- Perché la pipeline si ferma dopo le persone e dopo la storyline, e non alla fine?

### A-G — Volume e casi limite (M12–M13)

**Teoria:** misurare le prestazioni (tempo, memoria), unicità in un batch, integrità referenziale alla cancellazione, messaggi d'errore utili.
**Pratica:** AX-061–AX-070.
**Prova:**
- Due persone con lo stesso nome: come restano distinte in ogni documento?
- Cosa succede se cancello una persona ancora citata?
- Quanto ci mettono 100 dossier, e come l'hai misurato?

### A-H — Usabilità, documentazione e consegna (M14–M15)

**Teoria:** test di usabilità con un utente esterno, priorità tra i problemi trovati, documentazione per chi estende il modulo, script di demo.
**Pratica:** AX-071–AX-080.
**Prova:**
- Un compagno aggiunge un dominio giocattolo solo con la tua guida (Gate M15).
- Fai la demo: cambi un fatto e i documenti seguono.
