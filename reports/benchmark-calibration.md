# Benchmark de calibration du juge

**Date :** 2026-10-29 · **Statut :** méthodologie en place, premiers résultats mesurés, ground truth à valider.

## Objectif

Mesurer l'accord entre un juge LLM (local ou API) et des labels de référence,
pour répondre à deux questions :

1. Quel modèle local est *assez fiable* pour noter des réponses de flashcards ?
2. Comment surveiller cette fiabilité dans le temps (dérive de modèle, de prompt) ?

## Dataset

Fichier : `benchmarks/judge_dataset.yaml`.

- **5 cartes** de fondamentaux Python (2 à 3 critères de rubric chacune).
- **8 types de réponse** par carte = **40 échantillons**.
- Chaque échantillon contient : une réponse d'utilisateur, `expected_met`
  (un booléen par critère, le verdict attendu) et un `kind` (catégorie).

### Catégories et ce qu'elles testent

| Catégorie | Définition | Piège testé |
| --- | --- | --- |
| `perfect` | réponse complète et exacte | noter correctement le sans-faute |
| `paraphrase` | même sens, mots différents | accepter les reformulations |
| `partial` | une partie des critères seulement | détecter le critère **manquant** |
| `negation` | contresens | détecter le faux flagrant |
| `dont_know` | « je ne sais pas » / vide | ne pas inventer de contenu |
| `vague` | dans le thème, aucun critère précis | ne pas créditer le flou |
| `overcomplete` | tous les critères + du hors-sujet | ne pas se laisser distraire |

## Métriques

- **Exact match** : proportion de notes FSRS identiques à l'attendu.
- **Cohen's kappa** (non pondéré) : accord corrigé du hasard.
- **Latence** : moyenne, médiane, p90 par appel de juge.
- **Précision par catégorie** : pour localiser les points faibles.

La note attendue se dérive de `expected_met` via `grade_from_criteria`
(Again / Hard / Good).

## Ground truth

- Les labels `expected_met` actuels ont été **proposés par l'agent, pas encore
  validés par un humain** (au 2026-10-29). À arbitrer avant de figer les chiffres.
- Piste à valider : un modèle fort payant peut être mesuré contre ces labels
  humains pour confirmer son rôle d'oracle de référence.

## Résultats (thinking OFF, 2026-10-29)

| Modèle | Exact match | Kappa | Latence moy. | Verdict |
| --- | --- | --- | --- | --- |
| qwen3.6-35B-MoE (3B actifs) | 95.0 % | 0.924 | 6.2 s | le plus fiable, le plus lent |
| gemma4-e2b (4.6B dense) | 92.5 % | 0.885 | 2.7 s | quasi aussi fiable, 2.3× plus rapide |
| lfm2.5-8B-MoE (1B actif) | 42.5 % | 0.141 | 2.4 s | inutilisable (≈ hasard) |

Point faible commun : la catégorie `partial` (gemma 73 %, qwen 82 %).

### Constats annexes

- **Latence** : sur Ollama via le proxy OpenAI, c'est `reasoning_effort="none"`
  qui coupe le « thinking » (gemma : 19.3 s → 3.0 s, verdict identique). Le
  champ natif `think:false` n'a pas d'effet via `/v1`.
- **Retry** : 2 outputs malformés sur 40 (`met_criteria` booléen au lieu d'une
  liste). Le retry (2 tentatives max) avec message de correction ramène les
  erreurs de parsing à **0**.

## Usage

```bash
poetry run deck-benchmark benchmarks/judge_dataset.yaml
```

Comparaison multi-modèles + graphiques : script ad hoc (voir
`reports/benchmark_results.json`, `reports/benchmark_overview.png`,
`reports/benchmark_per_kind.png`).

## Limites et suite

- Ground truth à valider par un humain.
- 40 échantillons sur un seul thème (Python) : à élargir (plus de sujets,
  cartes à 3+ critères, code).
- Kappa non pondéré : envisager un kappa pondéré (notes ordinales).
- Comparaison formelle thinking ON vs OFF à produire.
