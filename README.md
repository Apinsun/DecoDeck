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

L'idée est de forcer une réponse écrite, de la faire évaluer par un modèle local
contre une grille de correction explicite, et de guider par une relance ciblée
quand la réponse est partielle — plutôt que de révéler immédiatement la solution.

## Scope

### In scope (MVP)

- **Génération de cartes** à partir d'un cours (PDF/Markdown) ou d'une codebase.
  Chaque carte contient :
  - `question` — question atomique ;
  - `reference_answer` — réponse de référence concise ;
  - `grading_rubric` — 2 à 3 critères vérifiables ;
  - `source_anchor` — pointeur vers la source (ex. `src/auth.py:L40-65`).
- **Révision locale** : question → réponse écrite → évaluation par LLM local contre
  la rubric → note FSRS (`Again` / `Hard` / `Good` / `Easy`).
- **Relance socratique** : si la réponse est partielle, un indice ciblé est proposé
  avant de révéler la réponse ; dans ce cas la note est plafonnée à `Hard`
  (règle de design, pas une contrainte de FSRS).
- **Planification** via `py-fsrs`, état de révision stocké en SQLite.
- **Rapport de calibration** : mesure de l'accord entre le juge local et des notes
  humaines (Kappa de Cohen / corrélation de Spearman).

### Out of scope (assumé, par réalisme)

- Pas d'application mobile ni de synchronisation multi-appareils.
- Pas d'intégration Anki/AnkiConnect (à reconsidérer seulement si besoin réel).
- Pas de multi-utilisateur, pas de cloud, pas de SaaS.
- Pas de génération massive de cartes : la qualité des cartes prime sur le volume.

## Architecture (proposée, à valider)

- **Génération** : modèle API (skill Pi ou script CLI) → fichiers de deck versionnés
  (YAML ou JSONL).
- **Révision** : LangGraph (orchestration + `interrupt` pour la relance) + LLM local
  (Ollama ou vLLM) + `py-fsrs` + SQLite.
- **UI** : à décider (Streamlit / Textual / CLI).
- **Métriques** : scripts et rapports dans `reports/`.

## Stack

- Python + Poetry (dépendances) + ruff (lint)
- `py-fsrs` — algorithme FSRS, pas de réimplémentation
- LangGraph — orchestration de la boucle de révision
- Ollama ou vLLM — inférence locale
- SQLite — état de révision + checkpoints LangGraph
- UI à confirmer

## Documentation

- `README.md` — présentation générale (ce fichier)
- `docs/` — documents techniques focalisés (architecture, calibration, décisions)
- `reports/` — rapports de milestone

## Critères de succès

- Le juge local atteint un accord mesurable et documenté avec mes notes humaines
  (seuil cible à définir lors du milestone calibration).
- J'utilise réellement l'outil pour réviser mes cours ou des codebases.
- La démo d'entretien montre le circuit complet, sans dépendre du réseau.

## Risques principaux

- **Fiabilité du juge local** : produire une évaluation stable et un JSON strict
  avec un petit modèle. C'est le risque central, mesuré par le benchmark de calibration.
- **Qualité des rubrics** : une mauvaise grille rend l'évaluation inutile quelle que
  soit la qualité du juge.
- **Latence** : dépend du GPU local et du modèle choisi ; à mesurer, pas à supposer.

## Décisions ouvertes

- [ ] UI : Streamlit vs Textual vs CLI
- [ ] Modèle local : lequel, à quelle taille (selon le GPU disponible)
- [ ] Générateur : skill Pi vs script CLI autonome
- [ ] Design du benchmark de calibration (taille, répartition des cas)

## Jalons

- [x] **M0 — Cadrage** : README + AGENTS.md + repo initialisé
- [ ] **M1 — Format de deck + générateur** : quelques cartes, d'abord à la main
- [ ] **M2 — Boucle de révision** : évaluation + FSRS + SQLite
- [ ] **M3 — Relance socratique** : `interrupt` LangGraph + plafonnement de note
- [ ] **M4 — Calibration** : benchmark, métriques, rapport dans `reports/`
- [ ] **M5 — UI + démo d'entretien**
