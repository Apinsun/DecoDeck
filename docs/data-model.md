# Modèle de données — Decks

Document de référence pour le format des decks. **Statut : décidé (M1).**

## Principe

- Un deck = **un fichier YAML** dans `decks/`, versionné sur Git.
- Chaque carte est un objet structuré, prêt à être consommé par le juge local
  (M2) et par le moteur FSRS.
- YAML a été préféré à JSONL (illisible à la main) et à Markdown (schéma peu
  contraignant) : c'est le meilleur compromis entre lisible par un humain et
  parsable par une machine.

## Structure d'un fichier de deck

| Champ | Type | Obligatoire | Description |
| --- | --- | --- | --- |
| `id` | string | oui | Identifiant du deck (slug, ex. `fastapi-internals`) |
| `title` | string | oui | Titre lisible |
| `cards` | liste | oui | Les cartes du deck |

## Structure d'une carte

| Champ | Type | Obligatoire | Description |
| --- | --- | --- | --- |
| `id` | string | oui | Identifiant unique de la carte, **global au projet** (future clé SQLite). Convention : `<deck-id>-<slug>` |
| `question` | string | oui | Question atomique (une seule notion) |
| `reference_answer` | string | oui | Réponse de référence, concise (2-3 phrases) |
| `grading_rubric` | liste de string | oui | 2 à 3 critères vérifiables et indépendants |
| `source_anchor` | string | non | Pointeur vers la source (fichier + lignes, ou section) |

## Règles de validation

- `id` de carte **unique sur tout le projet**, format `[a-z0-9-]+`.
- `grading_rubric` : 2 à 3 critères. Assez pour discriminer une réponse
  partielle d'une réponse complète, assez peu pour rester fiable avec un petit
  modèle local.
- Un critère est une phrase courte et vérifiable indépendamment
  (« mentionner X », « préciser Y »), pas une question.
- `question` et `reference_answer` non vides.

Ces règles seront appliquées par un loader Python au chargement (M2).

## Chaînes multi-lignes

En YAML, `|` (bloc littéral) préserve les retours à la ligne, `>` les replie en
espaces. Pour questions/réponses multi-lignes ou contenant du code, on utilise `|`.

## Exemple

```yaml
# decks/fastapi-internals.yaml
id: fastapi-internals
title: "FastAPI — internals"
cards:
  - id: fastapi-dep-01
    source_anchor: "fastapi/routing.py:L210-245"
    question: |
      Comment FastAPI résout-il une sous-dépendance déclarée avec Depends(),
      et comment évite-t-il de l'exécuter deux fois dans la même requête ?
    reference_answer: |
      Il construit un arbre de dépendances (Dependant), résolu récursivement
      par solve_dependencies, et stocke les résultats dans un cache par requête.
    grading_rubric:
      - "Résolution récursive de l'arbre de dépendances"
      - "Cache par requête, pas de double exécution"
```

## Évolution prévue

- **M2** : un loader Python validera ces règles et exposera les cartes au moteur
  de révision.
- **M3** : `grading_rubric` pourrait devenir une liste d'objets
  `{criterion, hint}` pour produire des indices socratiques ciblés. Décision
  repoussée — une liste de chaînes suffit pour l'instant.
