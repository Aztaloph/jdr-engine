# Cadrage jalon S — Éditeur de scènes & pont rencontre

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** (mainteneur 2026-08-19 — arbitrages §11 tranchés) |
| **Date** | 2026-08-19 |
| **Prérequis** | Lot **6** map tactique ✅ · lot **B1 auth** ✅ · **1038** tests verts |
| **Contrats existants** | [`CONTRAT.md`](../api/CONTRAT.md) · [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) |
| **Hors périmètre de ce document** | Workshop / marketplace · pipeline PNG · LoS · brouillard de guerre · navigation inter-scènes · refactor « scène = page principale » (VISION D9) · collision murs côté moteur |

> **Nomenclature** : **jalon S** (scènes). Commits : `feat(scenes): lot Sa — …`, `feat(scenes): lot Sd — …`, etc. Ne pas confondre avec **Axe B — B1** (inventaire sorts, ✅ terminé).

---

## 1. Mission

Permettre à un **MJ** de construire une **scène** à la souris (page dédiée, hors HUD combat), de la **sauvegarder**, de la **recharger à l'identique**, et de **lancer un combat dedans** — sans curl ni fixtures écrites à la main.

**Seuil « V1 jouable »** : c'est le premier jalon où tester le moteur en conditions réalistes côté table.

**Principe directeur** (VISION §4.2, dette assumée §407–411) :

| Règle | Application jalon S |
|---|---|
| La **scène** est un **artefact de contenu** | Fichier JSON autonome, versionné, exportable |
| La **rencontre** reste l'objet combat actuel | Pas de refactor « combat = mode de scène » |
| Le HUD **consomme** la scène | Calque statique + état combat par-dessus |
| Aucune règle D&D dans le client | Pas de LoS, fog, collision murs calculée localement |

---

## 2. Contexte — état réel du code

| Élément | Comportement actuel |
|---|---|
| Grille combat | Appliquée à **`activate`** — défaut **20×20** (`combat_routes.py`) |
| Coordonnées | Cases entières, origine coin haut-gauche (`GridPosition`) |
| Carte HUD | `TacticalMap.svelte` — grille API + fond SVG décoratif (`SCENE_TEST_MAP_URL`) |
| Create combat | `POST /v1/combats` — `character_ids[]` ; pas de scène |
| Persistance | SQLite `combats` + blob `CombatState` v3 — **pas** de table scènes |
| Auth | B1 ✅ — GM pour create/activate ; player owner sur mutations |

---

## 3. Objectifs fonctionnels

### 3.1 Ce que le jalon S garantit

1. **Format `scene.json` v1** stable, validable, partageable (un seul fichier copiable).
2. **CRUD scènes** API + SQLite.
3. **Pont rencontre** : `scene_id` optionnel au create → snapshot → activate applique `grid` depuis le snapshot (plus de 20×20 en dur si scène fournie).
4. **Éditeur** page dédiée (`#/scenes/…`) — palette, canvas, save/reload.
5. **Renderer partagé** `SceneRenderer` — **même code** éditeur et HUD combat.
6. **Lobby** — sélection de scène à la création de rencontre.
7. **Parcours manuels écrits** (§13) — **obligatoires** pour clôturer Sd, Se, Sf.

### 3.2 Hors périmètre (explicitement reporté)

| Exclusion | Raison |
|---|---|
| Assets PNG / pipeline images | `asset_id` réservé, jamais lu au rendu v1 |
| `lights[]` — comportement | Stocké, **ignoré** au rendu |
| `door.target_scene_id` — navigation | Saisissable éditeur, **aucune** navigation en jeu |
| Collision / `blocks_movement` moteur | Jalon terrain / LoS futur |
| Scène = page principale (D9) | Pont create-only ; convergence ultérieure |
| Tests unitaires de l'**UI éditeur** | Validation manuelle §13 |
| Choix manuel spawn au lobby | Assignation automatique par index (§6.5) |

---

## 4. Découpage livrable

```
Sa format  →  Sb API  →  Sc pont combat  →  Sd éditeur MVP + SceneRenderer  →  Sf HUD + lobby  →  Se polish éditeur  →  Sg clôture
```

| Lot | Livrable | Tests auto | Parcours manuel |
|---|---|---|---|
| **Sa** | Schéma v1 + fixtures + validateur | ✅ round-trip / validation structure | — |
| **Sb** | SQLite `scenes` + CRUD `/v1/scenes` | ✅ API CRUD + égalité JSON | — |
| **Sc** | `scene_id` au create, snapshot, activate lit snapshot | ✅ intégration create→activate→grid | — |
| **Sd** | Éditeur MVP + **`SceneRenderer` partagé** | ❌ UI | ✅ §13.1 |
| **Sf** | Lobby scène + HUD consomme snapshot | ❌ rendu visuel | ✅ §13.3 |
| **Se** | Rotation, resize, inspecteur complet, champs futurs | ❌ UI | ✅ §13.2 |
| **Sg** | Doc, CONTRAT, ROADMAP | — | ✅ checklist §13.4 |

> **Ordre impératif** : **Sf juste après Sd** — un éditeur dont le HUD n'affiche pas le résultat n'est pas validable. **Se** arrive une fois la boucle fermée (polish sur pipeline existant).

---

## 5. Format `scene.json` v1

### 5.1 En-tête obligatoire

```json
{
  "schema_version": 1,
  "name": "Taverne du port",
  "grid": {
    "width": 16,
    "height": 10,
    "enabled": true
  },
  "objects": [],
  "lights": []
}
```

| Champ | Type | Règle |
|---|---|---|
| `schema_version` | `int` | **Obligatoire.** Valeur **1** pour ce jalon. |
| `name` | `string` | Nom affiché (doublon avec colonne SQL autorisé). |
| `grid.width`, `grid.height` | `int ≥ 1` | Dimensions en **cases**. Plafond v1 : **50×50** (à valider en implémentation, documenter dans validateur). |
| `grid.enabled` | `bool` | `false` = **masquer le quadrillage** uniquement. Coords restent en cases. |
| `objects` | `array` | Objets de scène (§5.3). |
| `lights` | `array` | **Stocké, ignoré au rendu v1.** Schéma minimal figé §5.4. |

**Interdit** : chemins absolus, références binaires externes, dépendance à un fichier annexe non embarqué.

### 5.2 Coordonnées — une seule unité

| Décision | Valeur actée |
|---|---|
| Unité | **Cases entières** exclusivement |
| Origine | Coin **haut-gauche**, **x** → droite, **y** → bas (aligné `GridPosition`) |
| `grid.enabled: false` | Quadrillage masqué ; **pas** de canvas libre, **pas** de second système |
| Fond plein écran | Objet `kind: "background"` occupant toute la grille (ex. 16×10 en `(0,0)`) |

### 5.3 Objet de scène

```json
{
  "id": "wall-north-1",
  "kind": "wall",
  "x": 0,
  "y": 0,
  "width": 16,
  "height": 1,
  "quarter_turns": 0,
  "asset_id": null,
  "door": null,
  "spawn": null
}
```

#### Enum `kind` v1 — **fermée** (9 valeurs)

| `kind` | Rôle v1 |
|---|---|
| `background` | Fond / illustration procédurale plein cadre |
| `floor` | Sol |
| `wall` | Mur (décoratif v1) |
| `door` | Porte — métadonnée `door.target_scene_id` |
| `table` | Meuble |
| `chest` | Conteneur |
| `torch` | Source lumineuse décorative (sans mécanique) |
| `npc` | PNJ décoratif (ne devient **pas** combattant auto) |
| `spawn` | Point d'apparition combattant (§5.5) |

Ajout d'une valeur = **`schema_version` 2** — trivial grâce au versioning.

#### Champs communs

| Champ | Type | Défaut | Règle |
|---|---|---|---|
| `id` | `string` | — | Unique **dans la scène** ; slug éditeur autorisé |
| `kind` | enum §5.3 | — | Obligatoire |
| `x`, `y` | `int ≥ 0` | — | Coin supérieur gauche de l'emprise |
| `width`, `height` | `int ≥ 1` | `1` | Emprise en cases **avant** rotation |
| `quarter_turns` | `0..3` | `0` | **Pas de degrés.** |
| `asset_id` | `string \| null` | `null` | **Jamais lu au rendu v1** |

#### Rotation et emprise (risque élevé — **fermé**)

> **Règle normative** : un objet de taille `width × height` avec `quarter_turns` **impair** (1 ou 3) occupe **`height × width`** cases à la position `(x, y)`.

- `quarter_turns` pair (0, 2) : emprise `width × height`
- `quarter_turns` impair (1, 3) : emprise `height × width`

Le validateur Sa **rejette** les objets dont l'emprise déborde de la grille.

#### Porte (stockage only)

```json
"door": { "target_scene_id": "scene-crypte-v1" }
```

Absente ou `null` si `kind !== "door"`. **Aucune navigation** en jeu v1.

#### Spawn (assignation combattants)

```json
"spawn": { "role": "player", "index": 0 }
```

| Champ | Valeurs |
|---|---|
| `role` | `"player"` \| `"enemy"` |
| `index` | `int ≥ 0` — **explicite**, indépendant de l'ordre JSON |

Seuls les spawns `role: "player"` participent à l'assignation au create (§6.5). Spawns `enemy` : stockés pour futur ; **ignorés** au create v1.

### 5.4 Lumières (stockage only)

Entrée minimale v1 — **ignorée au rendu** :

```json
{ "x": 5, "y": 3, "radius_cells": 4, "color": "#f59e0b" }
```

---

## 6. Persistance & pont rencontre

### 6.1 Table SQLite `scenes` (décision C1)

```sql
scenes (
  id          TEXT PRIMARY KEY,   -- UUID ou slug stable
  name        TEXT NOT NULL,
  json        TEXT NOT NULL,        -- scene.json complet
  owner_id    TEXT NOT NULL,        -- session.user_id du créateur
  updated_at  TEXT NOT NULL
)
```

| Opération | Auth |
|---|---|
| `GET /v1/scenes`, `GET /v1/scenes/{id}` | Session valide (GM + player) |
| `POST`, `PUT`, `DELETE` | **GM only** |
| `GET /v1/scenes/{id}/export` | Blob JSON brut téléchargeable (autonomie Workshop) |

L'autonomie du format est une propriété du **JSON**, pas du support de stockage.

### 6.2 Snapshot au create (décision C2)

| Moment | Comportement |
|---|---|
| `POST /v1/combats` avec `scene_id` | Charger scène → **`scene_snapshot`** = copie intégrale du JSON → persister avec la rencontre |
| Métadonnée `scene_id` | Conservée pour **traçabilité** — **jamais relue** pendant un combat ouvert |
| Édition ultérieure de la scène source | **N'affecte pas** les combats déjà créés |

**Frontière moteur** : `scene_snapshot` vit côté **persistance API** (colonne JSON ou sous-objet blob API), **pas** dans `CombatState` moteur — le moteur continue de recevoir `grid_width` / `grid_height` / `placements` à l'activate.

### 6.3 Application physique à activate (décision C3)

| Étape | Comportement |
|---|---|
| **Create** (`preparing`) | Accepte `scene_id?` ; stocke snapshot ; lobby peut **afficher** dimensions + aperçu objets |
| **Activate** | Lit **`scene_snapshot.grid`** → `grid_width`, `grid_height` (remplace 20×20 en dur) ; dérive **`placements`** depuis spawns + assignation §6.5 |
| **Reste du flux** | Inchangé — attaque, sort, move, advance-turn, close, WS |

Body `activate` existant (`grid`, `placements`) : en v1, **ignoré ou rejeté** si snapshot présent (à trancher en implémentation Sc — recommandation : **snapshot prime**, body grid ignoré avec log dev).

### 6.4 Assignation spawns (décision B5)

À `POST /v1/combats` avec snapshot :

1. Lister les objets `kind: "spawn"` avec `spawn.role === "player"`.
2. Trier par **`spawn.index`** croissant.
3. Assigner `character_ids[0]` → spawn index le plus bas, etc.
4. **Surplus** de personnages sans spawn disponible → **placement par défaut** existant (comportement actuel moteur).
5. **Pas** de choix manuel au lobby v1.

### 6.5 Rendu v1 — table `kind → forme + couleur + label`

| `kind` | Rendu procédural (éditeur **et** HUD) |
|---|---|
| `background` | Rectangle plein, teinte neutre / placeholder |
| `floor` | Carreau discret |
| `wall` | Bloc opaque |
| `door` | Arc + label « porte » |
| `table` | Rectangle bois |
| `chest` | Carré accent |
| `torch` | Cercle + label |
| `npc` | Cercle + label « PNJ » |
| `spawn` | Marqueur dashed + label `P{index}` / `E{index}` |

Implémentation unique : **`web/src/lib/scene/SceneRenderer.svelte`** (ou module équivalent) — livré en **Sd**, consommé en **Sf**.

---

## 7. Impact API (amendements CONTRAT)

### 7.1 Nouvelles routes

| Route | Description |
|---|---|
| `GET /v1/scenes` | Liste (filtrage `owner_id` optionnel v1) |
| `POST /v1/scenes` | Créer |
| `GET /v1/scenes/{id}` | Lire |
| `PUT /v1/scenes/{id}` | Mettre à jour |
| `DELETE /v1/scenes/{id}` | Supprimer (v1 si trivial) |
| `GET /v1/scenes/{id}/export` | JSON brut |

### 7.2 Route modifiée

```http
POST /v1/combats
{ "character_ids": ["…"], "scene_id": "optional-uuid" }
```

Réponse `preparing` : inclure métadonnées scène pour le lobby (`scene_snapshot` ou vue réduite — **pas** tout le JSON si lourd ; arbitrage implémentation : `grid` + `object_count` minimum).

### 7.3 GET combat

Exposer `scene_snapshot` (ou calque dérivé) dans la réponse GET pour le HUD — **lecture seule**, objets statiques immuables pendant la rencontre.

---

## 8. Impact client web

| Fichier / zone | Lot | Changement |
|---|---|---|
| `lib/scene/SceneRenderer.svelte` | **Sd** | Renderer partagé kind → forme |
| `lib/scene/scene_types.ts` | Sa/Sd | Types alignés schéma v1 |
| `screens/SceneEditorScreen.svelte` | Sd/Se | Page dédiée `#/scenes/new`, `#/scenes/{id}` |
| `screens/LobbyScreen.svelte` | Sf | Sélecteur `scene_id` au create |
| `components/combat/TacticalMap.svelte` | Sf | Remplace fond SVG par `SceneRenderer` + snapshot |
| `App.svelte` | Sd | Routes éditeur — guard GM |

**Hors périmètre front S** : drag de jetons sur calque statique, édition in-combat, preview LoS.

---

## 9. Tests attendus (preuve de done)

> L'**éditeur UI** ne se valide **pas** par tests unitaires. Les parcours §13 sont **obligatoires**.

### 9.1 Fichier `tests/unit/test_scenes_format.py` (Sa)

| # | Scénario | Attendu |
|---|---|---|
| T1 | Fixture valide | validate → OK |
| T2 | `kind` inconnu | rejet |
| T3 | Objet hors grille | rejet |
| T4 | `quarter_turns: 1` sur 2×3 | emprise effective 3×2 |
| T5 | Round-trip dict → json → dict | égalité |

### 9.2 Fichier `tests/unit/test_api_v1_scenes.py` (Sb)

| # | Scénario | Attendu |
|---|---|---|
| T1 | POST scène GM | 201 + id |
| T2 | POST scène player | 403 |
| T3 | GET round-trip | JSON identique |
| T4 | export | blob autonome |

### 9.3 Fichier `tests/unit/test_api_v1_combat_scene.py` (Sc)

| # | Scénario | Attendu |
|---|---|---|
| T1 | create + scene_id | snapshot persisté |
| T2 | activate | grid depuis snapshot, pas 20×20 |
| T3 | 2 characters + 2 spawns player index 0,1 | placements corrects |
| T4 | surplus character sans spawn | placement défaut |
| T5 | edit scène source après create | combat inchangé |

---

## 10. Risques documentés & mitigations

| Risque | Mitigation actée |
|---|---|
| Double système de coords | Tout en cases ; fond = objet `background` |
| Rotation ambiguë | `quarter_turns` 0..3 + règle emprise §5.3 |
| HUD / éditeur divergent | **`SceneRenderer` livré Sd**, réutilisé Sf |
| create vs activate grid | C3 §6.3 — snapshot create, apply activate |
| Dépendance ordre JSON spawns | **`spawn.index` explicite** |
| `door` / `lights` confusion QA | Labels inspecteur « stocké — hors périmètre jeu » |
| Tension VISION D9 | Pont explicite ; pas de migration scène/page principale |

---

## 11. Arbitrages mainteneur — **actés** (2026-08-19)

| # | Sujet | Décision |
|---|---|---|
| **A2** | Scène sans quadrillage | Tout en cases ; `grid.enabled: false` masque le quadrillage ; fond = `kind: "background"` sur toute la grille |
| **B3** | Rotation | `quarter_turns: 0..3` ; emprise impaire = `h×w` ; **pas de degrés** |
| **B4** | Enum `kind` | **Fermée** — 9 valeurs §5.3 |
| **B5** | Spawns | `spawn.role` + `spawn.index` ; assignation `character_ids` par index croissant ; surplus → défaut |
| **C1** | Stockage | SQLite table `scenes` |
| **C2** | Snapshot | **Au create** ; `scene_id` traçabilité only |
| **C3** | Moment application | Snapshot au create ; **grid/placements appliqués à activate** ; lobby voit dimensions en `preparing` |

---

## 12. Ordre d'implémentation & dépendances

```
Sa ──► Sb ──► Sc ──► Sd (+ SceneRenderer) ──► Sf ──► Se ──► Sg
                         │                      │
                         └──── boucle validable ──┘
```

| Lot | Bloque |
|---|---|
| Sa | Sb, Sd (types) |
| Sb | Sd (save), Sc (scene_id) |
| Sc | Sf (combat avec scène) |
| Sd | Sf (**renderer obligatoire**) |
| Sf | Se (polish sur boucle fermée) |

**Parallélisable** avec Sa–Sc : push journal WS (ÉTAPE 6), Axe B3/B4 moteur — sans dépendance bloquante.

---

## 13. Parcours de validation manuelle (obligatoires)

> **Règle** : aucun lot **Sd**, **Se** ou **Sf** n'est clos sans exécution de son parcours. Chronomètre cible : **< 5 minutes** pour la partie éditeur seule.

### 13.1 Parcours Sd — Éditeur MVP

1. `launcher_web_auth.bat` — connexion **GM**.
2. Ouvrir `#/scenes/new`.
3. Grille **16×10**, quadrillage visible.
4. Palette : poser **4 murs** (périmètre), **1 table**, **2 torches**.
5. Déplacer la table d'une case ; supprimer une torche.
6. **Sauvegarder** `test-sd-taverne`.
7. Recharger la page / rouvrir la scène.
8. **Vérifier identique** : 6 objets, coords exactes, grille 16×10, rendu `SceneRenderer` cohérent.

### 13.2 Parcours Se — Éditeur complet

Chronomètre — repartir de zéro :

1. Grille **12×8**, `grid.enabled: true`.
2. Mur **2×1** → `quarter_turns: 1` → vérifier emprise **1×2** visuellement.
3. Redimensionner en **1×3** (`quarter_turns: 1` → emprise **3×1**).
4. Porte + inspecteur : `target_scene_id = "scene-crypte-v1"`.
5. Ajouter une entrée `lights[]` (inspecteur).
6. **2 spawns** `player` index **0** et **1** aux coords fixées.
7. Save `test-se-dungeon` → reload → **identique** (objets, rotation, taille, métadonnées).

### 13.3 Parcours Sf — Bout-en-bout V1 jouable

1. Scène `test-se-dungeon` existante (ou créée en Se).
2. Lobby : create combat — **2 personnages** + `scene_id`.
3. Vérifier lobby : dimensions **12×8** visibles en `preparing`.
4. Activate → HUD combat.
5. **Même rendu** objets statiques qu'à l'éditeur (`SceneRenderer`).
6. **2 jetons** aux spawns index 0 et 1.
7. Move un jeton — objets statiques **immobiles**.
8. Onglet **player** : voit carte + jetons ; **pas** d'outils MJ / create.

### 13.4 Parcours S — Scène sans quadrillage

1. Nouvelle scène : `grid.enabled: false`, objet `background` **16×10** en `(0,0)`.
2. Poser **3 objets** décoratifs (`npc`, `table`, `torch`).
3. Save / reload → identique ; **pas de lignes de grille** à l'écran.
4. Create combat → activate → HUD sans quadrillage, coords stables, jetons placables.

### 13.5 Checklist clôture jalon S (Sg)

- [ ] Parcours §13.1–13.4 exécutés et OK
- [ ] `docs/scenes/SCENE_SCHEMA.md` ou JSON Schema à jour
- [ ] Amendement `CONTRAT.md` § scènes
- [ ] Section `API_LOCAL.md` — flow éditeur + create avec `scene_id`
- [ ] ROADMAP — jalon S coché (mainteneur)

---

## 14. Références

| Document | Lien |
|---|---|
| Vision scène / rencontre | [`VISION.md`](../../VISION.md) §1, §4.2, §4.5, D9 |
| Map tactique actuelle | [`BRIEF_LOT6_MAP_TACTIQUE.md`](../web/BRIEF_LOT6_MAP_TACTIQUE.md) |
| Auth | [`BRIEF_LOT_B1_AUTH.md`](../api/BRIEF_LOT_B1_AUTH.md) |
| Grille moteur | [`BRIEF_LOT8_GEOMETRIE.md`](../combat/BRIEF_LOT8_GEOMETRIE.md) |
| Coordonnées | `jdr_engine/domain/combat/grid_position.py` |

---

*Document de cadrage **accepté** — arbitrages §11 tranchés 2026-08-19. Implémentation : ordre Sa → Sg.*
