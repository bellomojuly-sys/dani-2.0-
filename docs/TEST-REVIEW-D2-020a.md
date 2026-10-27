# D2-020a — Revisione critica di tutti i test (nota di lavoro)

Obiettivo di studio **F1 Testing**. Questo file è la mappa per la *Correzione*
e la *Prova* orale di F1. Stato: **in lavorazione** (non ancora chiuso).

## Il metro di giudizio (F1)

Un test è buono quando:

1. **Fallisce per il motivo giusto** — se rompo il codice nel punto che il test
   copre, quel test diventa rosso (mutation testing).
2. **Controlla una cosa sola** — un motivo di fallimento, non tre.
3. **È deterministico e indipendente** — stesso risultato ogni volta, non dipende
   da altri test, dalla rete o dal modello vero.

La domanda della Prova: *«per ogni test, cosa dimostra in una frase?»* e *«rompo
il codice in un punto a scelta: quale test deve fallire, e fallisce davvero?»*.

> Le frasi "cosa dimostra" qui sotto sono la **chiave di correzione**: all'esame
> le devi dire con parole tue, non leggerle.

## Inventario — 40 test

### `test_answer.py` (3) — validazione della risposta del modello

| Test | Cosa dimostra | Giudizio |
|---|---|---|
| `test_valid_response_is_accepted` | Un JSON con `answer` e `reason` diventa un `DaniAnswer` e `.answer` è leggibile | ⚠️ controlla solo `.answer`, mai `.reason` |
| `test_missing_field_fails` | Se manca `reason`, `parse_answer` alza `ValueError`, non accetta a metà | ✅ |
| `test_plain_text_fails` | Testo libero (non-JSON) alza `ValueError` | ✅ |

### `test_skill.py` (3) — la policy testuale del toolbox

| Test | Cosa dimostra | Giudizio |
|---|---|---|
| `test_skill_names_the_three_tools_in_the_right_order` | I tre nomi dei tool compaiono nel testo della skill nell'ordine read→prioritize→validate | ✅ (test di contratto sul testo) |
| `test_tool_order_covers_exactly_the_registered_tools` | `TOOL_ORDER` e i tool registrati sono lo stesso insieme: la policy non cita tool fantasma né ne dimentica | ✅ (bel test di contratto) |
| `test_skill_forbids_inventing_tasks` | Il testo contiene il divieto "never invent" | ⚠️ cerca una stringa esatta: fragile, dimostra un testo, non un comportamento |

### `test_tools.py` (20) — le tre funzioni-tool e i loro schemi

| Test | Cosa dimostra | Giudizio |
|---|---|---|
| `test_read_tasks_returns_three_tasks` | `read_tasks()` restituisce 3 task | ✅ |
| `test_read_tasks_accepts_empty_arguments` | "Nessun argomento" = `None` o `{}`, entrambi accettati | ✅ |
| `test_read_tasks_rejects_unexpected_arguments_with_structured_error` | Un dict inatteso torna `{"error": ...}` | ✅ (rifiuto) |
| `test_read_tasks_rejects_non_dict_arguments_with_structured_error` | Un argomento non-dict (`"oops"`) torna errore strutturato | ✅ (rifiuto) |
| `test_wrong_arguments_do_not_return_an_invented_task_list` | Su argomenti sbagliati NON torna comunque la lista: niente risultato inventato | ✅ (proprietà chiave) |
| `test_every_task_has_id_and_title` | Ogni task ha `id` e `title` | ✅ |
| `test_task_ids_are_unique` | Gli `id` dei task sono unici | ✅ |
| `test_read_tasks_schema_describes_a_function_with_no_arguments` | Lo schema dichiara nome `read_tasks` e zero parametri | ✅ (contratto schema↔funzione) |
| `test_every_schema_name_has_a_matching_callable_in_the_toolbox` | Ogni schema inviato al modello ha una funzione reale eseguibile | ✅ (contratto) |
| `test_prioritize_tasks_returns_numbered_order` | Aggiunge rank 1,2,3 nell'ordine ricevuto | ✅ |
| `test_prioritize_tasks_keeps_the_order_the_llm_decided` | NON riordina: tiene l'ordine deciso dal modello | ✅ (proprietà chiave) |
| `test_prioritize_tasks_rejects_missing_order` | Senza chiave `order` torna errore | ✅ (rifiuto) |
| `test_prioritize_tasks_rejects_empty_order` | `order` vuota torna errore | ✅ (rifiuto) |
| `test_prioritize_tasks_rejects_item_without_reason` | Un item senza `reason` torna errore | ✅ (rifiuto) |
| `test_bad_order_does_not_return_a_priority_list` | Su input sbagliato non compare `priority`: niente risultato a metà | ✅ |
| `test_prioritize_tasks_schema_has_an_order_parameter` | Lo schema espone il parametro `order` | ✅ (contratto) |
| `test_validate_priority_result_accepts_a_complete_report` | Report completo e corretto → `{"valid": True}` | ✅ |
| `test_validate_priority_result_rejects_a_missing_id` | Un id reale mancante → `valid False`, errore "missing" | ✅ (rifiuto) |
| `test_validate_priority_result_rejects_a_duplicate_id` | Un id ripetuto → `valid False`, errore "duplicate" | ✅ (rifiuto) |
| `test_validate_priority_result_rejects_an_invented_id` | Un id non nella lista → `valid False`, errore "unknown" | ✅ (rifiuto) |
| `test_validate_priority_result_rejects_a_malformed_call` | Chiamata malformata (manca `known_ids`) → `error`, senza `valid` | ✅ (distingue call storta da report sbagliato) |
| `test_validate_priority_result_schema_has_priority_and_known_ids` | Lo schema espone `priority` e `known_ids` | ✅ (contratto) |

*(21 righe in tabella = 20 test + la riga `_valid_order` è solo un helper, non un test.)*

### `test_agent.py` (12) — lettura chiamate, dispatch, loop, esito

| Test | Cosa dimostra | Giudizio |
|---|---|---|
| `test_read_tool_calls_names_the_requested_tool` | Da un messaggio SDK estrae nome e argomenti del tool richiesto | ✅ |
| `test_read_tool_calls_is_empty_when_no_tool_requested` | Nessun tool richiesto → lista vuota | ✅ |
| `test_run_tool_call_executes_the_tool_exactly_once` | Esegue il tool **una sola volta** (spy conta 1) | ✅ (proprietà chiave) |
| `test_run_tool_call_runs_the_real_read_tasks_tool` | Il dispatch chiama davvero `read_tasks` reale (3 task) | ✅ |
| `test_run_tool_call_rejects_unknown_tool_with_structured_error` | Un tool sconosciuto (`delete_everything`) torna errore, non crash | ✅ (rifiuto) |
| `test_tool_result_message_carries_the_three_real_titles` | Il messaggio-risultato porta i 3 titoli REALI di `read_tasks` | ✅ (proprietà chiave) |
| `test_tool_result_message_does_not_contain_an_invented_title` | Il contenuto non contiene `"Buy a yacht"` | ⚠️ **debole**: nega una sola stringa a caso; resta verde anche se il contenuto è vuoto o sbagliato |
| `test_run_tool_loop_records_the_call_trace_in_order` | La traccia registra i tool nell'ordine read→prioritize→validate e lo stato è `answered` | ✅ (cuore del loop) |
| `test_run_tool_loop_stops_at_the_iteration_limit` | Se il modello non smette mai, il loop si ferma al cap (`stopped`, traccia lunga 3) | ✅ (proprietà chiave: niente loop infinito) |
| `test_full_run_covers_every_source_id_exactly_once` | Run completo end-to-end: ogni id reale compare esattamente una volta | ✅ (end-to-end) |
| `test_honest_failure_when_the_task_source_fails` | Se `read_tasks` fallisce, l'esito è `ok False`, nessuna priorità | ✅ (D2-020) |
| `test_no_fabricated_priority_after_a_source_failure` | Anche se dopo il guasto il modello inventa e una validazione finta passa, l'esito rifiuta la priorità | ✅ (D2-020, forte) |

## Prove di rottura deliberata (mutation testing) — fatte il 27 ott

| Mutazione | Test che diventa rosso | Letto come |
|---|---|---|
| `prioritize_tasks` riordina con `sorted()` | `test_prioritize_tasks_keeps_the_order_the_llm_decided` | ✅ il test giusto, e uno solo |
| `read_tasks` restituisce 2 task | `..._returns_three_tasks`, `..._accepts_empty_arguments`, `run_tool_call_runs_the_real_read_tasks_tool`, `full_run...` | ✅ più test, tutti legittimi |
| `build_tool_result_message` restituisce `[]` (perde i task) | **FORTE** `..._carries_the_three_real_titles` → rosso · **DEBOLE** `..._does_not_contain_an_invented_title` → resta **verde** | la prova che il test "yacht" è cieco |

## Giudizio: deboli da sistemare

1. **`test_tool_result_message_does_not_contain_an_invented_title`** — negare una
   stringa a caso non prova nulla (mutazione 3). Va trasformato in una proprietà
   positiva: il contenuto contiene *solo* gli id/titoli reali di `read_tasks`.
2. **`test_valid_response_is_accepted`** — non verifica mai `.reason`. Un bug che
   perde `reason` non verrebbe visto da questo test.
3. **`test_skill_forbids_inventing_tasks`** — dipende dalla stringa esatta
   "never invent"; riscrivere la frase (stesso senso) lo romperebbe a torto.
   Da discutere: è un test di comportamento o solo di testo?

## Giudizio: cosa manca (da decidere insieme)

- **`read_tool_calls` con più tool in un messaggio**: testato solo con un tool.
- **`read_tool_calls` con JSON argomenti malformato**: `json.loads` potrebbe
  sollevare un'eccezione non gestita (possibile crash non coperto).
- **`prioritize_tasks` con `order` non-lista** (es. stringa) e **item non-dict**:
  rami di codice esistenti ma non testati.
- **`validate_priority_result` con `priority`/`known_ids` non-liste** e **riga
  senza `id` stringa**: rami di `else`/errore non coperti.
- **`final_outcome` quando `validate` non è mai stato chiamato** o manca
  `prioritize`: percorso non testato direttamente.
- **Divergenza test/produzione**: `build_tool_result_message` è testata ma il
  `run_tool_loop` reale ricostruisce il messaggio a mano (agent.py:89-94). Il
  messaggio che gira davvero non è testato in isolamento. Scelta di design da
  annotare (forse un Decision Log).

## Da fare per chiudere D2-020a

- [ ] Giulia dice, per ogni test, cosa dimostra (con parole sue).
- [ ] Sistemare i 3 test deboli (dopo che Giulia ha capito perché).
- [ ] Aggiungere i test mancanti concordati.
- [ ] `python3 -m pytest -v` verde + ogni nuovo test fallisce per il motivo giusto.
