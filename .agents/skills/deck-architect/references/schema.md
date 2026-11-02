# Schéma d'un deck (condensé)

Schéma canonique : `docs/data-model.md`. Résumé pour la génération.

## Un fichier par thème : `decks/<theme>.yaml`

```yaml
id: <slug-kebab-case>          # identifiant du deck
title: "<titre lisible>"
cards:
  - id: <deck>-<slug>          # unique sur TOUT le projet
    question: "..."            # atomique (une notion)
    reference_answer: "..."    # 2-3 phrases max
    grading_rubric:            # 2 à 3 critères, courts et vérifiables
      - "..."
      - "..."
    source_anchor: "..."       # optionnel : fichier.py:Ldébut-fin ou section
    explanation: "..."        # optionnel : explication didactique post-révision
```

## Règles de validation (appliquées par `deck-lint`)

- `id` : `[a-z0-9-]+` (mots en minuscules séparés par des tirets simples),
  unique sur tout le projet.
- `grading_rubric` : entre 2 et 3 critères.
- `source_anchor` au format `fichier:Ldébut-fin` → le fichier doit exister
  (sinon erreur). Autre format (URL, section) → simple avertissement.
- `explanation` (optionnel) : 3-5 phrases didactiques qui expliquent le
  « pourquoi » — affichées après la révision, surtout en cas d'échec.
- Chaînes multi-lignes : utiliser `|` (bloc littéral, préserve les retours).
