# AGENTS.md — Règles de travail

Contexte : projet de fin d'études. L'utilisateur doit comprendre chaque décision.
On privilégie la pédagogie et la sobriété.

## Communication

- On discute et on valide le plan avant d'écrire du code.
- Langue : discussions et documentation en français ; code, commentaires et
  messages de commit en anglais.
- Si une exigence est ambiguë, poser la question plutôt que deviner.
- Pas d'invention : aucun chiffre, métrique ou référence fabriqué, et pas de
  « ça devrait marcher ». On mesure, ou on dit qu'on ne sait pas.

## Création de fichiers et de scripts

- Ne jamais créer de fichier ni de script sans le demander, **sauf** fichiers
  réellement triviaux : `__init__.py`, `.gitkeep`.
- Ne pas implémenter de fonctionnalité hors du scope du README sans accord préalable.

## Documentation

- `README.md` : présentation générale du projet (vitrine), pas un document
  technique détaillé.
- `docs/` : documents techniques plus précis et focalisés (architecture, modèle
  de données, méthodologie de calibration, décisions d'architecture).
- `reports/` : rapports de milestone, `.md` vivants mis à jour **aux milestones**,
  pas après chaque prompt. Un rapport = un sujet, court et factuel.
- README, `docs/` et `reports/` sont la source de vérité : on les met à jour dès
  qu'une décision d'architecture change, pour éviter la dérive.

## Code

- Python, avec **Poetry** pour la gestion des dépendances.
- Toute nouvelle dépendance est proposée et expliquée avant d'être ajoutée.
- Tests : nécessaires, mais sans excès. On en écrit quand c'est pertinent
  (logique cœur, points de régression), pas systématiquement pendant les
  itérations rapides — à proposer au cas par cas.
- Tout changement de code est exécuté avant d'être annoncé comme terminé.
- Git : l'utilisateur fait les commits ; je propose le contenu du commit
  (message en anglais, un commit logique par étape).

## Cadrage

- On suit le scope du README. Toute nouvelle idée est signalée et discutée avant
  d'élargir le périmètre.
- Les décisions importantes (UI, modèle local, générateur) passent par une
  discussion, pas par un choix unilatéral.
