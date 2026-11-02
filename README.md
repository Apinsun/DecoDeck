# DecoDeck

Système de révision par répétition espacée, assisté par un évaluateur LLM local,
pour s'approprier des cours et des codebases avec un *active recall* honnête.

Projet de fin d'études. L'objectif premier est un outil que j'utilise réellement,
développé de façon propre et présentable à des recruteurs. Ce n'est ni un produit
commercial, ni une tentative de concurrencer l'écosystème Anki.

## Problème

Les outils de flashcards classiques reposent sur l'auto-évaluation : on juge
soi-même sa réponse (« Good » / « Again »). Deux biais en découlent :

1. **Illusion de compétence** — on valide des cartes qu'on ne maîtrise qu'en surface,
   sans jamais formuler la réponse.
2. **Effet perroquet** — on mémorise la formulation exacte du verso plutôt que le concept.

DecoDeck force une réponse écrite, la fait évaluer par un modèle local contre une
grille de correction explicite, et guide par une relance ciblée quand la réponse
est partielle — plutôt que de révéler immédiatement la solution.

## Fonctionnalités

- **Génération de decks** : un skill Pi (`deck-architect`) produit un fichier YAML
  par thème depuis un cours ou une codebase. Chaque carte : `question` atomique,
  `reference_answer` concise, `grading_rubric` (2-3 critères vérifiables),
  `source_anchor` (pointeur vers la source) et `explanation` (explication didactique).
- **Révision (web + CLI)** : question → réponse écrite → juge LLM local → note FSRS
  (`Again` / `Hard` / `Good` / `Easy`).
- **Relance socratique** : si la réponse est partielle, un indice ciblé est généré ;
  la note est alors plafonnée à `Hard`.
- **Chat de clarification** : après la révision, un espace pour poser des questions
  au LLM sur la notion (thinking activé pour la qualité des réponses).
- **Benchmark de calibration** : mesure de l'accord juge ↔ labels humains (exact
  match + Kappa de Cohen), pour choisir le modèle le plus fiable au coût le plus bas.

## Architecture

- **Génération** : skill Pi `deck-architect` → `decks/*.yaml` (versionnés) → `deck-lint`.
- **Révision** : juge LLM (tout backend OpenAI-compatible : Ollama, vLLM, API…) +
  `py-fsrs` + SQLite.
- **UI** : FastAPI + Jinja2 (web) ; un CLI (`deck-review`) pour le terminal.
- **Évaluation** : `deck-benchmark` + dataset de 40 échantillons + graphiques matplotlib.

## Stack

- Python + Poetry · PyYAML · SQLite (stdlib)
- `openai` — client pour tout backend OpenAI-compatible (Ollama en local)
- `fsrs` (py-fsrs) — algorithme de répétition espacée, pas de réimplémentation
- FastAPI + Jinja2 — interface web
- matplotlib — graphiques du benchmark
- pytest — 38 tests

## Lancer

```bash
poetry install
poetry run deck-web                                          # web → http://127.0.0.1:8000
poetry run deck-review decks/python-fundamentals.yaml        # révision en CLI
poetry run deck-lint decks/python-fundamentals.yaml          # valider un deck
poetry run deck-benchmark benchmarks/judge_dataset.yaml      # benchmark du juge
poetry run pytest                                            # tests
```

## Documentation

- `README.md` — présentation générale (ce fichier)
- `docs/` — documents techniques (`docs/data-model.md`)
- `reports/` — rapports de milestone (`reports/benchmark-calibration.md`)
- `AGENTS.md` — règles de travail avec l'agent

## Critères de succès

- Le juge local atteint un accord mesurable avec des labels humains. Premiers
  chiffres : gemma4-e2b à 92,5 % d'exact match (Kappa 0,885) — labels humains
  encore à arbitrer avant de figer les chiffres.
- J'utilise réellement l'outil pour réviser mes cours ou des codebases.
- La démo d'entretien montre le circuit complet, sans dépendre du réseau.

## Risques et choix

- **Fiabilité du juge** : mesurée — le modèle à 1B actif est inutilisable
  (Kappa 0,14) ; le seuil de fiabilité se situe au-dessus (4,6B dense OK).
- **Latence** : mesurée — juge ~2,7 s (thinking off), chat ~15-30 s (thinking on).
- **LangGraph écarté** : la relance socratique est un flux à 2 tours ; un simple
  state machine suffit (choix assumé : pas de sur-ingénierie).

## Jalons

- [x] **M0 — Cadrage** : README + AGENTS.md + repo
- [x] **M1 — Format de deck + générateur** : YAML, `deck-lint`, skill `deck-architect`
- [x] **M2 — Boucle de révision** : juge + FSRS + SQLite (web + CLI)
- [x] **M3 — Relance socratique** : indice ciblé + plafonnement de note
- [x] **M4 — Calibration** : benchmark 40 échantillons, Kappa, rapport
- [x] **M5 — UI** : FastAPI + Jinja2 (reste : polish de démo)
