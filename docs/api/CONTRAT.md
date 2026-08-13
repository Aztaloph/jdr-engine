# Contrat API HTTP — v1 (décisions structurantes)

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté (arbitrages mainteneur 2026-08-07 ; amendement lot 2 attaque 2026-08-07) |
| **Date** | 2026-08-07 |
| **Périmètre** | Décisions coûteuses à revenir en arrière une fois qu'un client consomme l'API |
| **Hors périmètre** | Spécification endpoint par endpoint, schémas champ par champ, catalogue d'erreurs exhaustif |

**Critère de tri** : une décision entre ici si la changer plus tard **casse un client existant** ou **impose une migration**. Tout le reste sera découvert à l'implémentation et est listé comme hors contrat.

**État de référence moteur** : 923 tests ; lot 1 API livré (`7878e9a`) ; attaque fusionnée et client web lot 2 exercés ; combat persistant (initiative, tours, attaques, sorts, conditions, concentration) ; registre d'effets unifié (ADR-006).

**Préfixe URL** : toutes les routes contractuelles vivent sous **`/v1/`**.

### Cadrage produit — API seule interface de jeu (2026-08-07)

**Décision mainteneur** : Discord n'est **plus** une interface de jeu. Il sert au **vocal** et, éventuellement, au **chat** (relay de messages vers l'API — transport, pas mécanique). Aucune mécanique de jeu (combat, jets, gestion de fiche) ne passera par Discord.

**Conséquences contractuelles** :

- L'**API HTTP** est le **seul client de jeu** ; pas de cohabitation avec un second point d'entrée sur les mêmes invariants.
- Tout développement visant une double utilisation API + Discord est **arrêté**.
- Le code Discord existant n'est **pas supprimé** dans le lot 1, mais **n'est plus une cible d'évolution** — ne rien y ajouter.
- Les invariants métier se posent **côté API** sans compatibilité Discord.

---

## 1. Frontière du modèle

### 1.1 Principe

L'API expose des **ressources** et des **résultats d'actions**. Elle n'expose pas les mécanismes internes de collecte, de résolution ni les structures de convenance du moteur Python.

Le vocabulaire exposé devient **contrat de stabilité** : tout identifiant string publié (`spell_id`, `condition_id`, `effect_id`, `ability_id`) engage sur la persistance sémantique de cette chaîne côté moteur et compendium.

### 1.2 Inventaire des concepts

| Concept interne | Traverse l'API ? | Forme côté client | Justification |
|---|---|---|---|
| **`Character`** (fiche SQLite) | **Oui** | Ressource `/v1/characters/{character_id}` ; agrégat calculé « fiche » (DTO existant `character_sheet_to_dict`, éventuellement enrichi — §2.6) | Source de vérité persistante hors rencontre (ADR-004 §1, ADR-005 sync-on-close) |
| **`Combatant`** (overlay rencontre) | **Oui** | Objet embarqué dans la ressource combat ; référencé par `combatant_id` dans les actions | PV/CA/tour/concentration overlay pendant le combat (ADR-004 §9) ; distinct de la fiche |
| **`CombatState`** | **Oui** (partiel) | Agrégat combat : statut, round, tour, ordre d'initiative, combattants, effets actifs | Snapshot sérialisable déjà persisté en blob SQLite |
| **`ActiveEffect`** | **Oui** (snapshot) | Liste `active_effects[]` avec les champs de `ActiveEffect.to_dict()` | État observable des buffs/conditions mécaniques ; mutations via actions API, pas via écriture directe |
| **`ActiveEffectRegistry`** | **Non** | — | Structure runtime (`CombatManager._effect_registries`) ; reconstruite à partir du blob + hydratation (`load_combat`) ; aucune opération client légitime sur le registre lui-même |
| **Collecteurs `collect_*`** (`rules/effects/collect.py`) | **Non** | — | Traduction registre → `effects[]` pour `d20.py` ; détail d'implémentation ADR-006 décision 3 |
| **Distinction attaquant / défenseur du collecteur** | **Non** (mécanisme) ; **Oui** (sémantique) | Les actions d'attaque prennent `attacker_id` + `target_id` (identifiants **combattant**) et `weapon_id` (id compendium arme — §2.7) ; le moteur dérive portée et modificateurs | Le paramètre interne `defender_id` de `roll_d20_for_combatant` est un détail de pipeline ; le contrat API reproduit la paire attaquant/cible + référence d'arme |
| **Résolution attaque d'arme (lot 2)** | **Oui** | `POST /v1/combats/{id}/attack` — réponse fusionnée jet + dégâts + PV cible (§2.7) | Orchestration API de `resolve_attack_roll` + `apply_damage` ; pas d'état pending dans le blob |
| **`D20RollRequest`** | **Non** en entrée brute ; **Oui** en sortie partielle | Entrée : sous-ensemble explicite « contexte de jet » par type d'action ; Sortie : objet `d20` dans les résultats (DTO `_d20_result_to_dict`, sans `modifier_breakdown`) | Dataclass interne riche et évolutive |
| **`D20RollResult`** | **Oui** | Objet structuré dans la réponse d'action | Résultat métier ; déjà sérialisé pour l'API personnage |
| **`effect_id` / `source_id`** | **Oui** | Champs string dans `active_effects[]` et traces dans `applied_effects` | Vocabulaire moteur stable |
| **`EventBus` / événements domaine** | **Non** (contrat principal) | Option dev : tampon diagnostic (ex. `/debug/events`) non garanti en prod | Les clients métier lisent l'état post-action |
| **`RuleEngine` / compendium** | **Non** | Les réponses portent des **ids** et libellés déjà résolus | Pas d'introspection compendium générique en v1 |
| **`ActionBudget`** | **Oui** (lecture) ; **Non** (écriture directe) | Sous-objet du combattant en combat actif | Consommé par les actions ; pas de PATCH manuel |

### 1.3 Identifiants stables exposés

| Identifiant | Portée | Stabilité contractuelle |
|---|---|---|
| `character_id` | Persistant, cross-session | Stable — clé SQLite courte |
| `combat_id` | Rencontre | Stable — entier SQL auto-incrémenté |
| `combatant_id` | Rencontre | Stable **dans** la rencontre — opaque (UUID tronqué 8 car.) |
| `spell_id`, `condition_id`, `effect_id` | Ruleset / catalogue moteur | Stable |
| `ability_id`, `skill` | Ruleset | Stable — vocabulaire SRD 2014 |

### 1.4 Double source Character / Combatant — règle temporelle API

Alignement ADR-005 pour la **persistance** (non négociable) :

- **Pendant** `status ∈ {preparing, active}` : overlay `Combatant` fait foi pour le **moteur** combat.
- **Après** `close_combat` : sync PV fiche ; conditions/effets rencontre non propagés sur `Character`.
- **Vue API fiche** (§2.6) : pendant un combat actif, `GET /v1/characters/{id}/sheet` expose une **vue fusionnée** pour le parcours joueur — sans écrire l'overlay sur la fiche SQLite.

---

## 2. Modèle d'état et de session

### 2.1 Qui possède la session de combat

Le **serveur** possède l'état ; le client le **référence** par `combat_id` (entier) dans `/v1/combats/{combat_id}`.

Pas de session HTTP dédiée. Pas de sticky session en mémoire requise (blob SQLite + réhydratation registre à la demande).

### 2.2 Cycle de vie — alignement moteur strict

```
preparing → active → ended
```

| Transition moteur | Sémantique API |
|---|---|
| `create_combat` | `POST /v1/combats` — statut `preparing` |
| `add_combatant` | Ajout participant (**preparing** uniquement en v1 — voir §10) |
| `activate_combat` | `POST /v1/combats/{id}/activate` |
| Mutations combat | Actions POST sous `/v1/combats/{id}/…` |
| `close_combat` | `POST /v1/combats/{id}/close` |

Séquence `close_combat` (ADR-005, implémentée) — l'endpoint de clôture ne la réordonne pas :

1. Sync PV overlay → fiche
2. Réconciliation concentration overlay → fiche
3. Conditions : discard fiche (archive `active_effects` blob OK)
4. `status=ended`, persist, `CombatEnded`

### 2.3 Persistance

- **Durable** : blob `CombatState` + colonne SQL `status`.
- **Cache process** : `ActiveEffectRegistry` par `combat_id`, reconstruit depuis le blob.
- **Redémarrage serveur** : reprise depuis SQLite ; pas de perte si base intacte.

Modèle **stateless HTTP + état serveur durable**. Idempotence des POST **non** garantie en v1.

### 2.4 Concurrence

**Décision** : **last-writer-wins** — pas de `revision`, pas de `If-Match`, pas de file d'actions en v1.

Deux requêtes concurrentes sur le même `combat_id` ou `character_id` peuvent se recouvrir. Documenter l'interdiction d'accès parallèle non coordonné sur la même ressource.

**Alternative écartée** : verrou optimiste — reporté ; migration coûteuse une fois des clients en production.

### 2.5 Scope de création — body `POST /v1/combats`

Les champs `guild_id` et `channel_id` sont une **projection interne** du scope de persistance SQLite — **pas** du vocabulaire client.

| Champ | Statut |
|---|---|
| `character_ids` | **Obligatoire** |
| `channel_id` | **Optionnel** — généré côté serveur (UUID) si absent |
| `guild_id` | **Optionnel** — défaut serveur `"api"` ; jamais requis du client |

**Client minimal** :

```json
{ "character_ids": ["abc123", "def456"] }
```

Le serveur mappe en interne vers `create_combat(guild_id, channel_id, character_ids)` avec les valeurs par défaut ou générées.

**Parallélisme** : plusieurs combats ouverts simultanés via des `channel_id` distincts (générés ou fournis). L'index partiel SQLite `idx_combats_open_channel` limite à **un** combat ouvert par couple `(guild_id, channel_id)` — suffisant sans imposer des ids Discord réels.

**Invariant lobby (lot 1)** : voir §10.3 — un personnage ne peut être que dans **un** combat ouvert à la fois (`CHARACTER_ALREADY_IN_COMBAT`).

**Alternative écartée** : exiger `guild_id` + `channel_id` au client HTTP — rejetée (fuite du modèle Discord).

### 2.6 Fiche fusionnée pendant combat actif

**Décision (option B)** : `GET /v1/characters/{character_id}/sheet` retourne une **vue fusionnée** lorsque le personnage participe à un combat **ouvert** (`preparing` ou `active`) :

- **`hp_current`** (et champs overlay pertinents) ← combattant overlay ;
- **`active_effects`** (ou sous-ensemble contractuel) ← registre / snapshot combat pour ce `combatant_id` ;
- le reste ← fiche calculée habituelle.

La recherche du combat ouvert se fait **uniquement** par `character_id` — **sans** paramètre `combat_id` sur la route fiche. Cette unicité est garantie par l'invariant lobby (§10.3) : au plus un combat ouvert par personnage.

**Important** : fusion **lecture API uniquement** — la fiche SQLite reste au snapshot pré-sync (ADR-005) jusqu'à `close_combat`. Le client combat continue de lire `/v1/combats/{id}` pour l'état complet de rencontre.

**Alternative écartée** : fiche = SQLite seule pendant le combat — rejetée pour l'objectif parcours joueur unifié.

### 2.6.1 Libellés fiche — caractéristiques et compétences (lot maîtrises)

**Règle** (alignée §1.3) : les **ids** restent le contrat stable ; les **libellés** accompagnent lorsque le serveur seul peut les résoudre (pas d'introspection compendium en v1 — §1.2).

| Champ | Forme | Notes |
|---|---|---|
| `ability_labels` | `dict[str, str]` | 6 clés (`str`…`cha`), libellés lisibles. Identique pour tous les personnages d'une locale — table de correspondance transportée par la fiche ; candidat futur `/v1/compendium`. |
| `proficient_skills` | `[{ "id", "label" }]` | Remplace **`proficient_skill_ids`** (breaking change). Ordre stable = ordre moteur. Modificateurs de compétence **non** exposés (table `skill_id → ability_id` absente du moteur). |
| `saving_throws` | inchangé | `{ ability_id, modifier, proficient }[]` — clés `ability_id` = mêmes ids que `ability_scores`. |
| `proficiency_bonus` | inchangé | Entier. |

**Exclus** (inchangé) : chaînes pré-formatées doublant un bloc structuré (`*_text`, `*_lines`, `spellcasting_summary`), `@property` recomposables (`class_display`, `hit_dice_display`), `trait_ids` (champ mal nommé), `proficient_skill_labels` (domaine — remplacé par `proficient_skills` côté DTO).

### 2.7 Attaque d'arme fusionnée (lot 2 — 2026-08-07)

**Décision mainteneur** : **option A (fusionné)** — une requête API orchestre jet d'attaque et application des dégâts. Pas de modèle « attaque pending » dans le blob ; pas de second endpoint `apply-damage` pour les armes en lot 2.

#### Route et breaking change lot 1

| Lot 1 (livré) | Lot 2 (cible) |
|---|---|
| `POST /v1/combats/{id}/attack-roll` — jet seul | **`POST /v1/combats/{id}/attack`** — résolution complète |

**Breaking change assumé** : `attack-roll` est **retiré** sans redirect permanent. Fenêtre courte (lot 1 récemment poussé) ; le nom « attack-roll » devient trompeur dès que les dégâts sont inclus.

#### Corps de requête (intention)

| Champ | Statut |
|---|---|
| `attacker_id` | Obligatoire — identifiant **combattant** |
| `target_id` | Obligatoire — identifiant **combattant** |
| `weapon_id` | Obligatoire — **id compendium arme** (stable, vocabulaire ruleset) |

**Sémantique `weapon_id`** : clé **compendium**, pas entrée d'inventaire. Le moteur en dérive notation de dégâts, propriétés (finesse, deux mains…) et contexte mêlée/distance pour le jet. Une future vérification « le personnage possède l'arme » s'ajoutera sur le **même** identifiant — sans changer la sémantique du champ.

**Champs retirés (lot 2)** : `melee_weapon`, `ranged_weapon` (lot 1 / `attack-roll`). Le body **`AttackRequest`** n'accepte **aucune** clé supplémentaire (`extra="forbid"`) — un client lot 1 qui les envoie encore reçoit **`422 VALIDATION_ERROR`**, pas un comportement silencieux.

Le client **ne fournit pas** : `attack_bonus`, `damage_amount`, `hit`, `critical` — mêmes principes que le lot 1 (modificateurs dérivés fiche moteur ; dégâts calculés serveur).

#### Sémantique serveur

1. Consommer le budget `action` (`resolve_attack_roll` moteur).
2. Si toucher : `apply_damage` avec notation dérivée de `weapon_id` + `critical` du jet.
3. Si manqué : pas de dégâts ; budget déjà consommé.
4. Overlay PV mis à jour ; fiche SQLite **inchangée** (ADR-005).

**Anti-rejeu** : le budget d'action consommé en étape 1 — pas d'`Idempotency-Key` requis pour ce cas (contrat §2.3).

**Pause narrative (UI)** : la réponse est **complète** dès la réponse HTTP ; l'UI peut révéler jet puis PV en deux temps **sans** figer la base ni état pending serveur.

#### Corps de réponse (intention — blocs séparés)

Trois blocs **distincts et lisibles** — le client ne doit pas rappeler `GET /v1/combats/{id}` pour animer l'action :

| Bloc | Contenu |
|---|---|
| `attack` | `d20` (DTO existant) + `outcome` (`hit`, `critical`, `automatic_miss`, `target_ac`) |
| `damage` | **`null`** si manqué ; sinon jet + application (`notation`, `rolls`, `total`, `critical`, `hp_before`, `hp_after`, `damage_dealt`) |
| `target` | `combatant_id`, `hp_current`, `hp_max` **après** résolution (overlay post-action) |

Données seulement — pas de champ calculé UI (« peut agir », libellés formatés).

#### Alternatives écartées

| Option | Motif |
|---|---|
| **Séparé** (`attack-roll` + `apply-damage`) | État pending blob, idempotence, zombies tour — voir `docs/api/LOT2_CADRAGE_DEGATS.md` |
| **PV serveur figés** pendant pause narrative | Besoin présentation ; coût modèle sans gain mécanique |
| **`damage_amount` client** | Contournement des règles — rejeté |

---

### 2.8 État combat — lecture et visibilité (2026-08-09)

Lot **cohérence lecture combat** : aligner GET et advance-turn, exposer le tour courant, documenter le contrat de sérialisation `combat_state_to_dict`.

#### Paramètre `viewer`

| Aspect | Règle |
|---|---|
| **Sémantique** | `character_id` du joueur dont on simule la vue |
| **Vue MJ** | Paramètre **absent**, `null`, ou **chaîne vide** (y compris espaces seuls après trim) → intégralité des champs |
| **Routes** | `GET`, `POST advance-turn`, `POST attack` et `POST cast` — query `viewer` optionnel (`character_id`) |
| **Erreur** | `404 VIEWER_NOT_IN_COMBAT` si `viewer` non vide et `character_id` absent de la rencontre |
| **Hors périmètre viewer** | `create`, `activate`, `close` — réponses vue MJ intégrale (actions MJ) |

#### Trois politiques de visibilité coexistantes

| Source | Clé d'entrée | Champs sensibles |
|---|---|---|
| **Agrégat combat** | `viewer` query (`character_id`) ou MJ | PV, CA, budget, concentration : soi ou MJ ; autres combattants : champs publics seulement |
| **Fiche personnage** | `character_id` dans l'URL (`GET …/sheet`) | Overlay du **personnage de la route** uniquement ; effets ciblant son `combatant_id` |
| **Résultat d'attaque** | `viewer` query (`character_id`) ou MJ | Bloc `attack` (jet) toujours visible ; `target` / `damage` : PV (`hp_*`) **absents** si la cible n'est pas « soi » ni vue MJ — même règle d'omission que l'agrégat combat |

#### Pont `character_id` ↔ `combatant_id`

Deux espaces d'identifiants stables (§1.3) coexistent dans l'agrégat combat :

| Identifiant | Où l'utiliser |
|---|---|
| `character_id` | Paramètre `viewer` ; clé fiche perso ; recherche combat ouvert par personnage |
| `combatant_id` | Clés de `combatants` ; `initiative_order[]` ; `active_effects[].target_id` ; `active_effects[].source_id` ; corps `attack` (`attacker_id`, `target_id`) ; `current_combatant_id` |

**Traduction** : la map `combatants` est le dictionnaire de correspondance — chaque entrée porte les deux identifiants. Pour un `cid` dans `initiative_order`, `combatants[cid].character_id` donne le personnage ; inversement, parcourir les valeurs pour résoudre un `character_id` vers un `combatant_id`.

#### Champ `current_combatant_id`

| Situation | Valeur JSON |
|---|---|
| `initiative_order` vide | `null` |
| `turn_index` hors `[0, len(initiative_order)-1]` | `null` |
| Sinon | `initiative_order[turn_index]` |

**Sémantique** : slot de tour dans l'ordre d'initiative **figé** — **pas** « qui peut agir maintenant ». Le moteur peut légitimement y pointer un combattant `is_active: false` (ex. après retrait sans avancement) ; `TurnEnded` est publié sur cet identifiant.

Le client **ne doit pas** déduire le tour courant via `initiative_order[turn_index]` — utiliser `current_combatant_id`.

#### Champs de l'agrégat combat (sérialisation API)

| Champ | Notes |
|---|---|
| `combat_id` | **Toujours `number`** via HTTP (identifiant route). Le `null` possible dans le sérialiseur interne (`state.combat_id` absent) n'atteint jamais le client — artefact blob, pas contrat HTTP. |
| `status` | `preparing` \| `active` \| `ended` |
| `round_number` | **`0` en `preparing`** (avant activation) ; ≥ 1 en `active` |
| `turn_index` | Index dans `initiative_order` ; non validé au chargement blob |
| `initiative_order` | Liste ordonnée de `combatant_id` |
| `combatants` | Map `combatant_id` → objet combattant |
| `active_effects` | Snapshot ; voir ci-dessous |
| `started_at` / `ended_at` | ISO 8601 UTC (ex. `2026-08-07T12:00:00+00:00`) ou `null` |

**Exclus volontairement de l'API combat** : `schema_version`, `guild_id`, `channel_id` (internes persistence / blob).

#### Combattant embarqué

| Champ | Toujours | Conditionnel |
|---|---|---|
| `combatant_id`, `display_name`, `kind`, `character_id`, `is_active` | Oui | — |
| `initiative_total` | — | Présent si jet établi (absent en lobby avant activation) |
| `hp_current`, `hp_max`, `ac`, `concentration_*`, `action_budget` | — | Vue MJ ou combattant « soi » uniquement |

**`kind`** — énumération fermée v1 : `"player_character"` (seule valeur domaine aujourd'hui).

**Omission vs `null`** : un champ **masqué** ou **non applicable** est **absent** de l'objet JSON. Le client **ne doit jamais** interpréter `null` comme « non visible ». S'applique à `hp_current`, `ac`, `action_budget`, `initiative_total`, `duration_rounds` (effets), etc.

#### `active_effects[]`

| Champ | Règle |
|---|---|
| `effect_id` | Opaque — vocabulaire moteur ; **pas de libellé lisible** en v1 (lot affichage / compendium ultérieur) |
| `source_id`, `target_id` | `combatant_id` |
| `applied_at_round`, `expiry_mode` | Toujours |
| `duration_rounds` | Présent si défini ; absent si `null` |
| `expires_at_round` | **Exclu** — recomposable : `applied_at_round + duration_rounds` quand applicable |

Filtrage `viewer` joueur : effets dont `target_id` = combattant du viewer ; MJ : liste intégrale.

#### Bloc `viewer` (query `viewer` renseigné)

Présent sur `GET`, `POST advance-turn`, `POST attack` et `POST cast` lorsque le query `viewer` (`character_id`) est non vide après trim.

| Champ | Règle |
|---|---|
| `character_id` | Echo du paramètre query |
| `combatant_id` | `combatant_id` résolu via `combatants` ; **`null`** si le personnage ne participe pas au combat |
| `castable_spells` | Liste ordonnée de `spell_id` overlay lançables **maintenant** par ce combattant |

**Critères `castable_spells[]`** (moteur `list_combat_castable_spell_ids`) :

1. Combat `active` et combattant `is_active`.
2. `action_budget` exposé et suffisant pour le `action_kind` du sort (registre overlay).
3. Sort présent dans le registre overlay avec **`expose_in_castable: true`** — exclut **`shield`** (réaction, `expose_in_castable: false`).
4. Tour : `require_own_turn: true` → uniquement au tour propre ; `false` → uniquement **hors** tour propre (réactions — non listées tant qu'`expose_in_castable` est faux).
5. Sort disponible sur la fiche (`spell_is_available`).

Registre overlay v1 : `hunters_mark`, `hex`, `bless`, `shield` — seuls les trois premiers peuvent apparaître dans `castable_spells` (`shield` exclu).

Absent du query `viewer` ou vue MJ : pas de bloc `viewer`.

#### Matrice statut × actions (routes v1)

| Statut | Actions autorisées | Lecture |
|---|---|---|
| **`preparing`** | `GET`, `POST activate`, `POST close` ; ajout combattant moteur (`add_combatant`) | `initiative_order` vide ; `current_combatant_id` null ; `round_number` 0 |
| **`active`** | `GET`, `POST attack`, `POST cast`, `POST advance-turn`, `POST close` ; mutations moteur combat | Ordre établi ; budgets rafraîchis au début de tour |
| **`ended`** | `GET` (état final) ; `POST close` idempotent côté moteur | `advance-turn` / `attack` → `409 COMBAT_STATUS_INVALID` |

Les transitions invalides lèvent `CombatStatusError` → `409 COMBAT_STATUS_INVALID` (message français variable).

#### Asymétrie POST mutate (documentée)

`POST create`, `activate`, `close` renvoient `combat_state_to_dict` **sans** `viewer` — vue MJ intégrale. Actions MJ sans conséquence visibilité joueur. **`POST attack`**, **`POST cast`**, **`GET`** et **`advance-turn`** partagent la politique `viewer` (2026-08-09). Un client qui enchaîne mutation MJ puis relecture filtrée doit préférer `GET ?viewer=` après mutation.

---

### 2.9 Sort en combat — `POST /v1/combats/{combat_id}/cast` (2026-08-10)

Route unifiée pour les sorts overlay et le dispatch combat (registre ADR-006 + attaque/sauvegarde hors overlay).

#### Requête

| Élément | Règle |
|---|---|
| **Query** | `viewer` optionnel (`character_id`) — filtre la réponse comme §2.8 |
| **Corps** | `caster_id` (`combatant_id`), `spell_id`, `target_ids[]`, `slot_level` optionnel |
| **`extra`** | **Interdit** (`422 VALIDATION_ERROR`) |

**`target_ids`** : liste de `combatant_id` — bornes par sort (registre overlay) :

| `spell_id` | Cibles min–max | `action_kind` |
|---|---|---|
| `hunters_mark` | 1–1 | `bonus_action` |
| `hex` | 1–1 | `action` |
| `bless` | 1–3 | `action` |
| `shield` | 0–0 (corps vide) | `reaction` |

#### `slot_level`

| Cas | Comportement |
|---|---|
| Champ **absent** ou **`null`** | Accepté |
| Valeur **présente** | **Rejeté** — `422 SPELL_CAST_REJECTED` (message : `slot_level non pris en charge pour '<spell_id>' en combat.`) |
| Registre `UPCAST_COMBAT_SPELLS` | **Vide** en v1 — aucun sort n'accepte l'upcast combat |

Validation Pydantic : si présent, entier `1`–`9` ; le rejet métier intervient ensuite dans le moteur.

#### Réponse

`combat_state_to_dict` complet (même forme que `GET`) — **pas** de DTO sort dédié. Le client anime depuis l'état renvoyé ou relit via `GET`.

#### Erreurs stables

| Situation | HTTP | `code` |
|---|---|---|
| Combat absent | 404 | `COMBAT_NOT_FOUND` |
| `caster_id` / cible absente de la rencontre | 404 | `COMBATANT_NOT_FOUND` |
| Personnage SQLite introuvable | 404 | `CHARACTER_NOT_FOUND` |
| Hors tour / budget / statut | 409 | `NOT_COMBATANT_TURN`, `ACTION_BUDGET_EXHAUSTED`, `COMBAT_STATUS_INVALID`, `OUT_OF_RANGE`, `CELL_OCCUPIED`, `INVALID_POSITION` |
| Règle sort (cibles, emplacement, etc.) | 422 | `SPELL_CAST_REJECTED` |
| `viewer` inconnu | 404 | `VIEWER_NOT_IN_COMBAT` |

#### Écarts connus client (non bloquants en local)

| Écart | Détail |
|---|---|
| **`bless` multi-cible** | Le serveur accepte jusqu'à **3** cibles ; le panneau web v1 n'envoie qu'**une** cible via le sélecteur partagé avec l'attaque. |
| **`caster_id` vs `viewer`** | Le corps fixe le lanceur (`combatant_id`) ; le query `viewer` ne filtre que la **réponse**. Aucun contrôle d'autorisation — un client peut lancer au nom de n'importe quel combattant (trou identifié, acceptable banc local). |

---

## 3. Format d'erreur

### 3.1 Structure unique

```json
{
  "error": {
    "code": "COMBAT_STATUS_INVALID",
    "message": "Les attaques ne sont possibles qu'en combat actif.",
    "details": {}
  }
}
```

| Champ | Obligatoire | Stabilité |
|---|---|---|
| `code` | Oui | Contrat — `SCREAMING_SNAKE_CASE` |
| `message` | Oui | Français ; non garanti stable |
| `details` | Non | Objet extensible |

Migration : l'API personnage actuelle (`detail` string) adopte ce format — breaking change assumé.

### 3.2 HTTP

| HTTP | Famille |
|---|---|
| **404** | Ressource absente |
| **409** | Règle métier / conflit d'état |
| **422** | Validation corps ou valeur métier inconnue dans le body (`VALIDATION_ERROR`, `WEAPON_UNKNOWN`) |
| **500** | Erreur inattendue (`INTERNAL_ERROR`) |

### 3.3 Codes stables (minimum contractuel)

| Exception moteur | `code` |
|---|---|
| Personnage introuvable | `CHARACTER_NOT_FOUND` |
| Combat introuvable | `COMBAT_NOT_FOUND` |
| Combattant introuvable | `COMBATANT_NOT_FOUND` |
| `SpellCastError` | `SPELL_CAST_REJECTED` |
| `RestError` | `REST_REJECTED` |
| `CombatStatusError` | `COMBAT_STATUS_INVALID` |
| `UnknownCombatConditionError` | `UNKNOWN_CONDITION` |
| `ActionBudgetExhaustedError` | `ACTION_BUDGET_EXHAUSTED` |
| `OpenCombatExistsError` | `OPEN_COMBAT_EXISTS` |
| `InsufficientCombatantsError` | `INSUFFICIENT_COMBATANTS` |
| `NotCombatantTurnError` | `NOT_COMBATANT_TURN` |
| `UnknownWeaponError` | `WEAPON_UNKNOWN` (HTTP **422**) |
| `CombatStateVersionError` | `COMBAT_STATE_UNSUPPORTED` |
| `require_spell_attack_type` | `SPELL_ATTACK_TYPE_MISSING` |
| Personnage déjà dans un combat ouvert | `CHARACTER_ALREADY_IN_COMBAT` |
| `viewer` (`character_id`) absent de la rencontre | `VIEWER_NOT_IN_COMBAT` |

---

## 4. Conventions de nommage et de versionnement

### 4.1 Chemins

- Préfixe **`/v1/`** sur toutes les routes contractuelles.
- Ressources plurielles snake_case : `/v1/characters`, `/v1/combats`.
- Actions : kebab-case — `/v1/combats/{id}/attack`, `/v1/combats/{id}/close`.
- **Lot 1 → lot 2** : `attack-roll` remplacé par `attack` (§2.7) — breaking change documenté.
- Diagnostic dev (`/debug/…`) hors contrat prod ; non préfixé ou explicitement exclu du contrat v1.

### 4.2 Champs JSON

snake_case ; vocabulaire SRD ; modes de jet `normal` / `avantage` / `desavantage` ; clés d'emplacements en string.

### 4.3 Versionnement

**Décision** : préfixe **`/v1/`** dès le premier lot implémentable. Ruptures futures → `/v2/` ; pas de version implicite.

---

## 5. Périmètre des lots implémentables

### 5.1 Parcours cible (bout-en-bout)

1. `GET /v1/characters/{id}/sheet` — fiche initiale
2. `POST /v1/combats` — body minimal `{ "character_ids": [...] }` ; vérification unicité lobby
3. `POST /v1/combats/{id}/activate`
4. `POST /v1/combats/{id}/attack` — attaque d'arme complète (jet + dégâts si toucher — §2.7)
5. `POST /v1/combats/{id}/cast` — sort en combat (overlay ou dispatch — §2.9)
6. `GET /v1/combats/{id}` — état rencontre
7. `GET /v1/characters/{id}/sheet` — **fiche fusionnée** si combat ouvert (`preparing` ou `active` — §2.6) : PV overlay, effets actifs
8. `POST /v1/combats/{id}/close` — clôture + sync PV fiche

### 5.2 Ressources (intention, sans schémas)

| Intention | Route | Body |
|---|---|---|
| Fiche (fusionnée si combat ouvert) | `GET /v1/characters/{character_id}/sheet` | — |
| Créer rencontre (lobby) | `POST /v1/combats` | `character_ids` obligatoire ; `channel_id`, `guild_id` optionnels |
| Lire rencontre | `GET /v1/combats/{combat_id}` | Query `viewer` optionnel (`character_id`) — §2.8 |
| Avancer le tour | `POST /v1/combats/{combat_id}/advance-turn` | Query `viewer` optionnel — §2.8 |
| Activer | `POST /v1/combats/{combat_id}/activate` | Body optionnel §5.5 (`grid`, `placements`) |
| Déplacer | `POST /v1/combats/{combat_id}/move` | §5.5 ; query `viewer` optionnel |
| Attaque d'arme (fusionnée) | `POST /v1/combats/{combat_id}/attack` | §2.7 ; query `viewer` optionnel — §2.8 |
| Sort en combat | `POST /v1/combats/{combat_id}/cast` | §2.9 ; query `viewer` optionnel — §2.8 |
| Clore | `POST /v1/combats/{combat_id}/close` | — |

### 5.3 Lot 1 — livré

- Format erreur, préfixe `/v1/`, cycle de vie combat, invariant lobby, fiche fusionnée lecture, `attack-roll` jet seul (**remplacé lot 2**).
- **Tests** : libération personnages après `close` ; parcours E2E sans dégâts appliqués.

### 5.4 Lot 2 — attaque d'arme fusionnée (livré)

- Route **`POST /v1/combats/{id}/attack`** — remplace `attack-roll` (breaking change §2.7).
- DTO `weapon_attack_result_to_dict` — blocs `attack`, `damage`, `target`.
- Résolution `weapon_id` → notation dégâts moteur (liste fermée transitoire §10.5).
- Parcours §5.1 : étape 4 + PV overlay post-attaque étape 6.
- **Client web lot 2** (2026-08-09) : panneau attaque ; filtrage `viewer` sur `target`/`damage` aligné GET combat.

**Hors lot 2 API** : sorts combat, conditions API, `apply-damage` générique exposé, Extra Attack, état pending, `Idempotency-Key`. *(Avancement de tour : lot 0 API + web.)*

### 5.5 Lot 8 — géométrie de combat (livré)

Brief : [`docs/combat/BRIEF_LOT8_GEOMETRIE.md`](../combat/BRIEF_LOT8_GEOMETRIE.md).

- **`COMBAT_STATE_VERSION` = 3** — blobs antérieurs refusés (`CombatStateVersionError` → recréer la rencontre).
- **`GET /v1/combats/{id}`** (combat `active`) : `grid: { width, height }` ; chaque combattant inclut `position: { x, y }` (**sans filtrage `viewer`**).
- **`POST /v1/combats/{id}/activate`** — body optionnel :

```json
{
  "grid": { "width": 20, "height": 20 },
  "placements": { "<combatant_id>": { "x": 1, "y": 10 } }
}
```

Défaut : grille **20×20**, placement automatique (ligne horizontale selon `initiative_order`).

- **`POST /v1/combats/{id}/move`** — body `{ "combatant_id", "x", "y" }` ; enregistrement d'état direct (pas de pathfinding). Consomme `movement_remaining_ft` (Chebyshev × 5 ft, conforme SRD).
- **`ActionBudget`** : `movement_remaining_ft: int` remplace `has_movement`.
- **Portée** : `POST …/attack` et `POST …/cast` rejettent `409 OUT_OF_RANGE` si cible hors portée spatiale.
- **Codes erreur lot 8** : `OUT_OF_RANGE`, `CELL_OCCUPIED`, `INVALID_POSITION`.
- **Hors lot 8** : ligne de vue, brouillard de guerre, pathfinding, terrain difficile, attaques d'opportunité.

---

## 6. Hors périmètre explicite (v1 contrat)

| Exclusion | Raison |
|---|---|
| Authentification / autorisation | Banc local |
| Rate limiting, pagination | Infra / volume |
| WebSocket / temps réel | Contrat transport distinct — voir [`CONTRAT_WS.md`](CONTRAT_WS.md) |
| OpenAPI comme contrat normatif | Ce document prime |
| CORS, déploiement multi-instance | Hors lot |
| Idempotency-Key, webhooks | Reportés |
| Introspection compendium | ids via moteur |
| Création / édition personnage | Autre lot |
| Action economy complète | Extension post-validation noyau |

---

## 7. Discord — hors périmètre jeu

Le code Discord (`bot/`, `interfaces/discord/`) reste en dépôt pour le vocal et le chat futur, mais **n'est plus une interface de jeu** (voir préambule). Aucune évolution Discord dans les lots API. Les handlers historiques (fiche, sorts, `/roll`) ne définissent pas le contrat v1.

---

## 8. État documentaire (post-résorption 2026-08-07)

| Point | Statut |
|---|---|
| ADR-004/006 conditions → registre | ADR realignés |
| Collecteur `rules/effects/collect.py` | ADR realignés |
| `close_combat` vs ADR-005 | ADR-005 complété (§ état implémenté) |
| Format erreur API | Lot 1 ✅ |
| Endpoints combat cycle de vie | Lot 1 ✅ |
| `attack-roll` jet seul | Lot 1 ✅ — **remplacé lot 2** |
| Attaque d'arme fusionnée | Lot 2 — arbitrage 2026-08-07 |
| Tests référence | **886** mesurés (2026-08-07) |

---

## 9. Synthèse des décisions

| # | Décision | Statut |
|---|---|---|
| 1 | Ressources Character + Combat (+ ActiveEffect snapshot) | Tranché |
| 2 | Registre, collecteurs, D20RollRequest complet : internes | Tranché |
| 3 | Session = `combat_id` + SQLite | Tranché |
| 4 | Cycle de vie moteur strict | Tranché |
| 5 | Concurrence last-writer-wins | Tranché |
| 6 | Format erreur structuré | Tranché |
| 7 | Métier → 409, not found → 404 | Tranché |
| 8 | snake_case, ids SRD stables | Tranché |
| 9 | Préfixe `/v1/` | Tranché |
| 10 | Body création : `character_ids` seul requis ; scope interne | Tranché |
| 11 | Fiche fusionnée ; unicité combat ouvert par personnage | Tranché |
| 12 | Invariant lobby — `CHARACTER_ALREADY_IN_COMBAT` (lot 1) | Tranché |
| 13 | API seule interface de jeu ; Discord hors évolution | Tranché |
| 14 | Attaque d'arme **fusionnée** — une requête, pas de pending blob | Tranché (2026-08-07) |
| 15 | Route `POST …/attack` remplace `attack-roll` (breaking change) | Tranché (2026-08-07) |
| 16 | Réponse en blocs `attack` / `damage` / `target` | Tranché (2026-08-07) |
| 17 | `weapon_id` client ; dégâts calculés moteur — pas d'injection | Tranché (2026-08-07) |
| 18 | `weapon_id` = id **compendium** arme (pas inventaire) | Tranché (2026-08-07) |
| 19 | Body `attack` : `extra="forbid"` — rejette `melee_weapon`/`ranged_weapon` legacy | Tranché (2026-08-07) |

---

## 10. Réserves architecturales

### 10.1 Modèle cible — lobby

**Modèle produit** : un combat est un **lobby** que les joueurs rejoignent et quittent.

| Règle | Lot 1 | Plus tard |
|---|---|---|
| Un personnage ≤ un combat **ouvert** à la fois | **Oui** — `CHARACTER_ALREADY_IN_COMBAT` à l'entrée (couche API, sans modifier le moteur) | — |
| Tant qu'il est dans un lobby, pas d'interaction avec un autre combat | Implicite via unicité | — |
| Rejoindre un combat **déjà `active`** | Moteur **oui** (`add_combatant`) ; route HTTP **non** | `POST /v1/combats/{id}/combatants` (à exposer) |
| Sortir par **fuite** (action de jeu, jet possible) | Non | Chantier gameplay |

**Lot 1** : vérification API — requête sur les combats ouverts contenant le `character_id` avant `create_combat` / `add_combatant`. **Ne pas modifier** `CombatManager` pour cet invariant.

**Clôture** : `close_combat` passe le statut SQL à `ended` — le personnage est **libéré**. Test obligatoire (commit 3) : personnages réutilisables dans un nouveau combat après `close`.

### 10.2 Rejoindre un combat déjà `active`

Le moteur **`add_combatant`** accepte les statuts **`preparing` et `active`** : en combat actif, le nouveau PJ reçoit un jet d'initiative et est inséré dans l'ordre figé sans recalculer les tours passés (`combat_manager.add_combatant`).

**API v1** : pas encore de route HTTP exposant ce join — prérequis documentaire pour une future `POST /v1/combats/{id}/combatants`. Le contrat ne fige pas la liste des combattants comme immuable après `activate`.

### 10.3 Scope repository

L'unicité `(guild_id, channel_id)` pour combats ouverts reste en base ; l'API masque ce détail via defaults et génération de `channel_id`. Assouplir l'unicité globale = chantier repository distinct, **non requis** lot 1.

### 10.4 Dette post-lot 1 (2026-08-07)

| Dette | État | Résolution cible |
|---|---|---|
| **`COMBAT_STATE_UNSUPPORTED` non câblé** | Identifiée | Mapper `CombatStateVersionError` → `409` + code §3.3 sur le **chemin de chargement** d'état combat — pas route par route. Routes concernées : `GET /v1/combats/{id}`, `activate`, `attack`, `close`, fiche fusionnée. Aujourd'hui : blob incompatible → `500 INTERNAL_ERROR`. Aucun blob legacy en circulation — non bloquant. |

### 10.5 Dette lot 2 — catalogue armes compendium (2026-08-07)

| Dette | État | Résolution cible |
|---|---|---|
| **Pas de catalogue `compendium/…/weapons/` exploitable** | Identifiée | Schéma compendium armes (notation dégâts, mêlée/distance, finesse…) puis lookup `weapon_id` → YAML. |
| **Liste fermée transitoire (commit 2)** | Acceptée si compendium absent | Tant que le catalogue n'existe pas : ids documentés **`longsword`**, **`shortsword`**, **`shortbow`**, **`longbow`** — suffisants au parcours §5.1. Implémentation = table explicite côté API/moteur, **référencée ici** ; retrait dès le compendium armes livré. Pas de liste en dur non documentée. |

---

## Références

- `docs/adr/ADR-004-modele-combat.md` — conditions, registre
- `docs/adr/ADR-005-transition-fin-rencontre.md` — sync-on-close
- `docs/adr/ADR-006-modele-effets-actifs.md` — ActiveEffect
- `docs/api/LOT2_CADRAGE_DEGATS.md` — cadrage lot 2 (option A retenue)
- `docs/API_LOCAL.md` — lancement local
- `jdr_engine/game/combat_manager.py`
- `jdr_engine/rules/effects/collect.py`
- `jdr_engine/application/dto/output_serializers.py`
- `interfaces/api/app.py`
