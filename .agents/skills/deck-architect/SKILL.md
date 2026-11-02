---
name: deck-architect
description: Generate a spaced-repetition deck (YAML) from a codebase or a course document. Use when the user wants to create flashcards to learn or review code, architecture, or study material.
---

# Deck architect

Crée un deck de révision DecoDeck — **un fichier YAML par thème** — à partir
d'une codebase ou d'un document de cours.

## Avant de commencer

Lis `references/schema.md` (schéma condensé) et `assets/example-deck.yaml`
(exemples de cartes bien formées). Le schéma canonique est dans
`docs/data-model.md`.

## Méthode

1. **Explore la source** avec les outils disponibles (read, grep, glob) :
   codebase → lis le README, repère les modules centraux, les flux de données
   et les abstractions clés ; cours → repère les notions structurantes.
2. **Sélectionne 5 à 10 concepts** qui sont à la fois : centraux, faciles à
   oublier, et répondables en 2-3 phrases. Une carte = une notion.
   Si le périmètre est flou (combien de cartes, quels modules), demande avant
   de générer.
3. **Écris le deck** dans `decks/<theme>.yaml` (slug kebab-case).
4. **Valide** : `poetry run deck-lint decks/<theme>.yaml`, et corrige jusqu'à
   ce qu'il n'y ait plus d'erreur.

## Règles absolues

- **Jamais de `source_anchor` inventé** : vérifie que le fichier et les lignes
  existent réellement (le linter le vérifie aussi).
- **Une carte = une notion.** Découpe plutôt que d'empiler.
- **Rubric discriminante** : 2-3 critères indépendants, qui permettent de juger
  une réponse *partielle*. Pas un seul gros critère.
- **Réponse de référence concise** : 2-3 phrases, pas un pavé.
- Questions et réponses en **français**.
