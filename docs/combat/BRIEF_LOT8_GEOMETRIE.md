# Cadrage lot 8 — géométrie de combat (moteur + API)

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** — mainteneur 2026-08-13 |
| **Date** | 2026-08-13 (acceptation arbitrages §7) |
| **Prérequis** | Lot 7 MVP combat jouable ✅ (`ROADMAP.md`) ; **1002** tests verts |
| **Successeur consommateur** | Lot 6 front — map tactique (`web/`, WebSocket) — **après** ce lot |
| **Hors périmètre de ce document** | Implémentation, découpage commits, rendu Svelte, WebSocket |

**Décisions actées (2026-08-13)** :

- Lot **moteur + API** d'abord, lot **6 front** ensuite — aucun rendu carte dans ce lot.
- Grille dans l'**état de combat** (`grid: { width, height }`), défaut **20×20** à l'`activate` — pas de constante de module.
- Budget mouvement : **`movement_remaining_ft` uniquement** — retrait de `has_movement` ; bump `COMBAT_STATE_VERSION` **sans** reconstruction des blobs antérieurs.
- Positions **non filtrées** par `viewer` — brouillard de guerre reporté au lot terrain (avec LoS).
- Distance Chebyshev × 5 ft : **conforme SRD** (variante mouvement grille par défaut), pas une approximation à « corriger » plus tard.

---

## 1. Mission

Introduire un **modèle de position discrète** par combattant, des **primitives de distance/portée**, la **consommation réelle du budget mouvement**, et la **validation spatiale** des attaques et sorts — le tout comme **API moteur pure** (fonctions déterministes + événements), consommable ensuite par le lot 6.

**Principe directeur** (VISION D3/D4, `AGENTS.md` §6) :

| Priorité | Règle |
|---|---|
| 1 | Moteur pur — zéro Svelte, zéro Discord, zéro embed |
| 2 | Enregistrement d'état — pas de simulation de trajectoire |
| 3 | Placeholders explicites pour ce qui dépend du terrain (LoS) |
| 4 | Contrat API documenté dans `docs/api/CONTRAT.md` (section dédiée post-implémentation) |

---

## 2. Réserves mainteneur (non négociables)

### 2.1 Ligne de vue — **hors lot 8**

La **line of sight (LoS)** dépend d'obstacles, donc d'un **modèle de terrain** inexistant aujourd'hui. Un « MVP simplifié » du type « toujours vrai » n'est **pas** une simplification : c'est une **absence déguisée** qui se paiera à l'ajout des murs.

| Attendu lot 8 | Interdit lot 8 |
|---|---|
| Aucune validation LoS dans le moteur | `has_line_of_sight = True` silencieux |
| Placeholder API **explicite** si un champ doit exister côté contrat | Filtrage de cibles « visible » pour sorts |
| Référence lot futur **9+** (terrain + LoS) | Règles `frightened` SRD complètes (ADR-004 dette) |

Si le contrat HTTP doit anticiper LoS : champ du type `"line_of_sight": null` avec sémantique documentée **« non implémenté — lot terrain »**, jamais interprété comme `true`.

### 2.2 Mouvement — enregistrement d'état, **pas pathfinding**

`POST /v1/combats/{id}/move` **valide** qu'un déplacement est légal et **met à jour** la position. Il ne **calcule pas** de chemin.

| Inclus | Exclu (lots ultérieurs) |
|---|---|
| Budget mouvement suffisant (pieds restants) | Pathfinding / trajectoire multi-cases |
| Case destination libre (une seule occupante) | Terrain difficile (coût ×2) |
| Destination dans les bornes de la grille | Attaques d'opportunité |
| Distance **directe** case départ → case arrivée ≤ pieds restants | Règle diagonale alternée 5/10 ft en chemin |

**Garde-fou de périmètre** : si l'implémentation commence à raisonner en graphe, segments ou coût cumulé le long d'un chemin, le lot **déborde** — s'arrêter et remonter.

---

## 3. État réel du code (référence factuelle, 2026-08-13)

### 3.1 Absences mesurées

| Domaine | État |
|---|---|
| `Combatant` (`jdr_engine/domain/combat/combatant.py`) | Pas de position (x/y/grille) |
| `CombatState` | Pas de dimensions de carte ni de grille |
| Distance / portée spatiale | **Inexistant** — portée attaque = flags `melee_weapon` / `ranged_weapon` uniquement |
| Budget `movement` (`action_budget.py`) | Flag booléen `has_movement` — **inerte** (ADR-004 § dette C4) |
| `WeaponProfile` (`rules/combat/weapons.py`) | Pas de `range_ft` — table transitoire 4 armes |
| Sorts compendium | `mechanics.range` = libellés i18n (`"120 feet"`) — **pas** de champ mécanique `range_ft` |
| API combat | `create`, `activate`, `attack`, `cast`, `heal`, `advance-turn`, `close`, `events` — **aucun** `move` |
| `GET /v1/combats/{id}` | `combatants{}` sans position |

### 3.2 Ressources réutilisables

| Élément | Fichier | Usage lot 8 |
|---|---|---|
| Vitesse dérivée | `CharacterSheet.speed` via `build_character_sheet()` | Budget mouvement au `TurnStarted` |
| Budget d'actions | `ActionBudget`, `ActionConsumed` | Étendre mouvement en **pieds restants** |
| Portée attaque sort | `SpellAttackRange` (`melee` / `ranged`) | Brancher sur `in_range` |
| Sérialisation API | `combat_state_to_dict` (`output_serializers.py`) | Exposer `position` par combattant |
| Tests API | `tests/unit/test_api_v1_combat.py` | Étendre parcours contrat |
| Version blob | `COMBAT_STATE_VERSION = 2` | Incrément **obligatoire** si schéma position / budget change |

---

## 4. Périmètre fonctionnel

### 4.1 Modèle de position et grille

- Coordonnées **entières** en **cases** ; **1 case = 5 ft** (grille discrète SRD).
- Position par combattant : `{ "x": int, "y": int }` — persistée dans le blob combat.
- Dimensions de grille dans **`CombatState`** : `grid: { "width": int, "height": int }` — **pas** de constante en dur dans un module. Initialisées à **`activate`** (défaut **20×20** si le body ne précise rien). Body optionnel sur `activate` : `{ "grid": { "width", "height" }, "placements": { … } }`.
- Bornes inclusives : `[0, width-1]` × `[0, height-1]`. Validation de `POST …/move` et placement contre **`state.grid`**, jamais contre une constante de module.
- **Unicité** : deux combattants actifs ne partagent pas la même case.

### 4.2 Primitives moteur (`jdr_engine/rules/combat/` — module dédié)

| Primitive | Signature indicative | Rôle |
|---|---|---|
| `grid_distance_ft` | `(a, b) → int` | Distance en pieds entre deux cases **sans obstacle** |
| `in_range` | `(origin, target, range_ft) → bool` | Cible à portée |
| `is_cell_free` | `(state, x, y, *, ignore_combatant_id?) → bool` | Case libre |
| `movement_cost_ft` | `(from, to) → int` | Coût du **saut** direct (lot 8 = même formule que `grid_distance_ft`) |

**Règle de distance lot 8 — conforme SRD** : distance Chebyshev × 5 ft — `max(|Δx|, |Δy|) × 5`. Correspond à la **variante de mouvement par défaut** du SRD 5.1 2014 sur grille (1 case diagonale = 5 ft). Documenter comme **conforme SRD**, pas comme approximation — évite une « correction » euclidienne ultérieure. Les règles de **comptage de cases avec obstacles** viendront avec le lot terrain.

### 4.3 Budget mouvement

- **Remplacer** le booléen `has_movement` par **`movement_remaining_ft: int`** — **une seule source de vérité** ; ne pas conserver les deux champs (divergence au premier bug).
- Réinitialisation à **`CharacterSheet.speed`** au `TurnStarted` du combattant.
- `POST …/move` déduit `movement_cost_ft` de `movement_remaining_ft`.
- `movement_remaining_ft == 0` ⇒ mouvement indisponible pour le tour.
- Publier `ActionConsumed(action_kind="movement")` **ou** événement dédié `PositionChanged` — choix implémentation ; le journal API doit refléter le déplacement.

**Bump `COMBAT_STATE_VERSION`** : incrément obligatoire. Au rechargement d'un blob antérieur, lever **`CombatStateVersionError`** — **aucune** tentative de reconstruction depuis `has_movement: false` (impossible de distinguer « 0 ft restants » de « 15 ft restants puis tout consommé »).

**Dette ADR-004** : la dette « movement inerte » est **soldée** par ce lot pour la consommation en pieds ; les règles avancées (difficult, OA) restent ouvertes.

### 4.4 Validation de portée — attaques et sorts

Brancher **avant** résolution :

| Action | Règle lot 8 |
|---|---|
| Attaque arme mêlée | `in_range(attacker, target, 5)` |
| Attaque arme distance | `in_range` avec `normal_range_ft` ajouté à `WeaponProfile` (table transitoire — même pattern que lot 2) |
| Attaque de sort `melee` | 5 ft |
| Attaque de sort `ranged` | `range_ft` mécanique du sort |
| Sorts sans jet vs CA (save, heal, buff…) | `range_ft` si cible requise ; sorts « self » / « touch » : règles dédiées documentées |

**Erreur moteur** : code stable type `OUT_OF_RANGE` → `409` API (aligné `NOT_COMBATANT_TURN`, `ACTION_BUDGET_EXHAUSTED`).

**Portée des sorts — dette compendium** : les 42 sorts curated n'ont pas de `range_ft` structuré. Lot 8 autorise une **table transitoire** `spell_id → range_ft` côté moteur (miroir `weapons.py`), **référencée dans le brief de commit**, avec issue ouverte vers extension schéma YAML — **sans** parser fragile de chaînes i18n en production.

### 4.5 Positions dès l'activation (**critère de done explicite**)

Les positions doivent être **présentes dans la réponse de `GET /v1/combats/{id}` dès la fin de `POST …/activate`**, pas seulement après un premier `move`.

**Placement initial** :

- Body **optionnel** sur `activate` : `{ "grid": { "width", "height" }, "placements": { "<combatant_id>": { "x", "y" }, … } }`.
- Grille absente du body ⇒ **20×20** par défaut.
- Placements absents ⇒ algorithme moteur déterministe (ex. ligne horizontale espacée, y constant, x croissant selon `initiative_order`).
- Validation : cases libres, dans les bornes de `state.grid`, une position par combattant actif.

État `preparing` : positions **absentes** ou `null` — acceptable tant que le combat n'est pas actif.

### 4.6 API HTTP

| Route | Statut lot 8 |
|---|---|
| `GET /v1/combats/{id}` | `grid`, combattants avec `position: { x, y }` si combat actif ; `movement_remaining_ft` dans le budget |
| `POST /v1/combats/{id}/activate` | Accepte `grid` et `placements` optionnels ; réponse avec grille et positions résolues |
| `POST /v1/combats/{id}/move` | **Nouveau** — body `{ combatant_id, x, y }` |
| `POST …/attack`, `POST …/cast` | Rejet `409 OUT_OF_RANGE` si hors portée spatiale |

Politique `viewer` : positions **exposées sans filtrage** pour tous les combattants — même règle que l'absence de LoS (§2.1). Le **brouillard de guerre** dépend du lot terrain : filtrer maintenant imposerait une règle de visibilité provisoire à défaire plus tard.

### 4.7 Événements

Minimum :

- Mise à jour position + budget après `move`.
- Option recommandée : `PositionChanged(combatant_id, from, to, cost_ft)` pour le journal et le futur WebSocket lot 6.

---

## 5. Hors périmètre (volontaire)

| Item | Lot cible |
|---|---|
| Ligne de vue / couvert / obscurci | **9+** avec modèle terrain |
| Brouillard de guerre / filtrage positions par `viewer` | Lot terrain (avec LoS) |
| Pathfinding, terrain difficile, diagonales alternées en chemin | Lots séparés post-terrain |
| Attaques d'opportunité | Lot dédié |
| Rendu carte, jetons, WebSocket | **Lot 6 front** |
| Compendium armes complet | Existant transitoire suffit pour parcours tests |
| Extension schéma YAML `range_ft` sorts | Souhaitable post-lot 8 ; table transitoire acceptable ici |
| `frightened` : impossibilité d'approche | Lié movement + LoS — post-terrain |
| Discord, nouvelles commandes joueur | Interdit (`AGENTS.md` D2) |

---

## 6. Critères de done

Ne pas clôturer le lot sans **tous** les points suivants :

1. **Tests** : `python -m unittest discover -s tests -p "test_*.py" -q` — `Ran N tests` + `OK` ; delta N documenté vs **1002** baseline `ROADMAP.md`.
2. **Positions à l'activation** : test API (ou moteur + serializer) prouvant `GET` post-`activate` contient `position` pour **chaque** combattant actif.
3. **`POST /move`** : cas heureux + rejets (`NOT_COMBATANT_TURN`, budget insuffisant, case occupée, hors bornes, coût > restant).
4. **Portée** : au moins un test attaque mêlée hors portée + un test sort `ranged` hors portée → `OUT_OF_RANGE`.
5. **Budget mouvement** : consommation partielle (deux `move` qui épuisent la vitesse) + reset au tour suivant.
6. **`COMBAT_STATE_VERSION`** incrémentée ; blob antérieur ⇒ **`CombatStateVersionError`** explicite — **aucune** reconstruction depuis `has_movement` ; politique = recréer la rencontre.
7. **Aucun fichier** sous `web/` modifié pour la fonctionnalité (placeholders lot 4 inchangés).
8. **Contrat** : section lot 8 ajoutée à `docs/api/CONTRAT.md` (routes, codes erreur, forme JSON).
9. **LoS** : aucune validation silencieuse ; placeholder documenté si champ présent.
10. **Pathfinding** : aucune fonction de recherche de chemin dans `jdr_engine/`.

---

## 7. Arbitrages actés (2026-08-13)

### 7.1 Dimensions de grille et placement — **accepté**

**Décision** : `grid: { width, height }` **persisté dans `CombatState`**, initialisé à l'`activate`. Défaut **20×20** si le body ne précise rien ; surcharge optionnelle via body `activate`. Placements optionnels sur le même body.

**Rejeté** : constante de module (20×20 en dur) — les tests, bornes et placement auto supposeraient une valeur implicite difficile à faire évoluer (ex. rencontre 30×40).

### 7.2 Budget mouvement — **accepté**

**Décision** : **`movement_remaining_ft` remplace `has_movement`** — breaking assumé avant le lot 6 front (contrat non consommé). Bump `COMBAT_STATE_VERSION` ; **refus explicite** des blobs antérieurs — pas de migration ni reconstruction (`has_movement: false` ne permet pas de deviner 0 vs 15 ft restants).

**Rejeté** : conserver les deux champs (double source de vérité).

---

## 8. Ordre d'implémentation proposé

1. **Domaine** — type `GridPosition`, extension `Combatant` / `CombatState`, bump version blob.
2. **Règles** — `grid_geometry.py` (distance, in_range, validation case).
3. **Moteur** — placement à `activate`, `move_combatant`, hook portée dans `resolve_attack_roll` / `cast_spell_*`.
4. **Budget** — `movement_remaining_ft`, reset `TurnStarted`.
5. **DTO / API** — serializer, route `move`, codes erreur.
6. **Tests** — `tests/unit/test_combat_geometry.py` (nouveau) + extensions `test_api_v1_combat.py`.
7. **Contrat** — `docs/api/CONTRAT.md`.

**Ordre validé** : géométrie moteur → API consommateur → (plus tard) lot 6 front.

---

## 9. Fichiers touchés (indicatif)

| Zone | Fichiers probables |
|---|---|
| Domaine | `combatant.py`, `combat_state.py`, `action_budget.py` |
| Règles | `rules/combat/grid_geometry.py` (nouveau), `weapons.py`, `spell_resolution.py` |
| Game | `combat_manager.py` |
| Events | `combat_events.py` |
| Application | `output_serializers.py` |
| API | `combat_routes.py`, `errors.py` |
| Tests | `test_combat_geometry.py`, `test_api_v1_combat.py`, parcours moteur existants |
| Doc | `docs/api/CONTRAT.md` |

---

## 10. Références

| Document | Rôle |
|---|---|
| [`VISION.md`](../../VISION.md) §5 | Combat Engine API pure |
| [`ROADMAP.md`](../../ROADMAP.md) | Lot 7 ✅ ; lot 6 front après lot 8 |
| [`docs/adr/ADR-004-modele-combat.md`](../adr/ADR-004-modele-combat.md) | Dette movement inerte §C4 |
| [`docs/api/CONTRAT.md`](../api/CONTRAT.md) | Contrat HTTP v1 |
| [`docs/api/LOT2_CADRAGE_DEGATS.md`](../api/LOT2_CADRAGE_DEGATS.md) | Modèle de cadrage |
| [`docs/web/BRIEF_FABLE_AFFICHAGE.md`](../web/BRIEF_FABLE_AFFICHAGE.md) | Placeholders carte lot 4 — **non modifiés** ici |

---

## 11. Validation

| Rôle | Action |
|---|---|
| Mainteneur | ✅ Périmètre §4–§5 et arbitrages §7 actés (2026-08-13) |
| Agent implémentation | **Peut démarrer** — statut **Accepté** |
| Revue | Remonter si le périmètre final réintroduit LoS, pathfinding ou filtrage positions |
