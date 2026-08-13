# Cadrage lot 6 — map tactique (client Web)

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** — mainteneur 2026-08-13 |
| **Date** | 2026-08-13 (acceptation arbitrages §12) |
| **Prérequis** | Lot 8 moteur + API ✅ ([`BRIEF_LOT8_GEOMETRIE.md`](../combat/BRIEF_LOT8_GEOMETRIE.md)) ; lot 7 MVP combat ✅ ; lot 4 HUD visuel ✅ ; **1018** tests verts |
| **Découpage** | **6a** — map REST jouable ✅ · **6b** — WebSocket temps réel ([`BRIEF_LOT6B_WEBSOCKET.md`](BRIEF_LOT6B_WEBSOCKET.md)) · **6c** (optionnel) — polish visuel Figma |
| **Hors périmètre de ce document** | Implémentation commits, détail endpoint WebSocket, auth multi-poste |

**Décisions proposées (à acter §12)** :

- Livrer **6a d'abord** (grille + jetons + `POST …/move` + budget pieds) — **sans WebSocket**.
- **6b** ensuite — contrat transport distinct, push `PositionChanged` / état combat.
- **Fable 5** réservé au **6c polish visuel** — **pas** au câblage fonctionnel 6a ni au WebSocket 6b.
- Aucune règle D&D côté client : pas de prévisualisation de portée/atteignable calculée localement.
- Conserver l'ADN visuel lot 4 (`MapPlaceholder.svelte`) en **décoration non interactive** sous la grille fonctionnelle (6c ou fin 6a minimal).

---

## 1. Mission

Remplacer la **carte décorative** du HUD combat par une **grille interactive** branchée sur l'API lot 8 : afficher `grid` et `position` réels, permettre un déplacement par clic (`POST /v1/combats/{id}/move`), aligner le HUD sur `movement_remaining_ft`.

**Principe directeur** (VISION D7, `AGENTS.md` §6, ADR-007) :

| Priorité | Règle |
|---|---|
| 1 | Consommer l'API existante — **aucune** règle métier D&D dans `web/` |
| 2 | Comportement combat lot 7 **préservé** (attaque, sorts, tour, journal, viewer) |
| 3 | Données réelles uniquement — pas de jetons fictifs, pas de fausses positions |
| 4 | Placeholders explicites pour LoS, brouillard, pathfinding, mesure (lots futurs) |
| 5 | Maquette Figma = cible **visuelle** — ne justifie jamais une donnée inventée |

---

## 2. Réserve mainteneur (non négociables)

### 2.1 Pas de règles métier client

Le moteur valide distance, budget, case libre, tour courant. Le client **ne calcule pas** :

| Interdit client | Raison |
|---|---|
| Cases « atteignables » surlignées via Chebyshev × 5 ft | Dupliquerait `grid_geometry.py` |
| Filtrage positions par `viewer` | Politique lot 8 — brouillard = lot terrain + LoS |
| Pathfinding / trajectoire multi-cases | Hors lot 8 — enregistrement d'état direct |
| Rejet local `OUT_OF_RANGE` avant `POST …/attack` | Le serveur tranche ; le client **peut** afficher l'erreur API |

**Autorisé client** : afficher `movement_remaining_ft` tel que renvoyé ; surligner `current_combatant_id` ; désactiver l'UI move hors tour.

### 2.2 Mouvement — clic destination, pas drag obligatoire

`POST …/move` enregistre un **saut** direct vers `(x, y)`. Le client envoie la case cliquée ; le serveur accepte ou rejette.

| Inclus 6a | Exclu 6a |
|---|---|
| Clic case vide → `move` si UX autorisée (§5) | Drag & drop jeton (6c ou lot ultérieur) |
| Clic sur jeton → sélection / focus (cosmétique) | Animation de déplacement le long d'un chemin |
| Feedback erreurs API (`409`) | Retry automatique silencieux |

### 2.3 WebSocket — lot 6b, pas bloquant pour 6a

Le banc local fonctionne avec **refresh après action** (pattern actuel de `CombatScreen.svelte`). Le multi-joueur sans rechargement manuel = **6b**.

---

## 3. État réel du code (référence factuelle, 2026-08-13)

### 3.1 API lot 8 — livrée

| Élément | État |
|---|---|
| `GET /v1/combats/{id}` | `grid: { width, height }` ; combattants avec `position: { x, y }` si `active` |
| `POST …/activate` | Body optionnel `grid`, `placements` ; positions dès activation |
| `POST …/move` | Body `{ combatant_id, x, y }` |
| Budget | `movement_remaining_ft: int` — **`has_movement` retiré** côté moteur |
| Erreurs | `OUT_OF_RANGE`, `CELL_OCCUPIED`, `INVALID_POSITION`, `NOT_COMBATANT_TURN`, `ACTION_BUDGET_EXHAUSTED` |
| Événement | `PositionChanged` publié côté moteur (journal / futur WS) |

Référence : [`docs/api/CONTRAT.md`](../api/CONTRAT.md) §5.5.

### 3.2 Client Web — lot 6a livré (2026-08-13)

| Fichier | État |
|---|---|
| `web/src/lib/types/combat.ts` | `grid`, `position`, `movement_remaining_ft` |
| `web/src/lib/api/combat.ts` | `postCombatMove()` |
| `web/src/lib/components/combat/TacticalMap.svelte` | Grille + jetons API |
| `web/src/lib/screens/CombatScreen.svelte` | Intégration map, budget ft |
| `MapPlaceholder.svelte` | Archivé — non importé |
| WebSocket | **Absent** — lot **6b** |

### 3.3 Ressources réutilisables

| Élément | Usage lot 6 |
|---|---|
| `MapPlaceholder.svelte` | Référence visuelle / extraction décor (6c) ; **remplacé** fonctionnellement par `TacticalMap.svelte` |
| `tokens.css`, composants combat lot 4 | Charte sombre/ambre, cartes, panneaux |
| `CombatScreen.svelte` | Parent — passe `combat`, `viewer`, callbacks refresh |
| `fetchCombatState` + `refreshCombat` | Mise à jour post-move identique aux autres actions |

---

## 4. Périmètre fonctionnel

### 4.1 Lot 6a — map REST (priorité)

#### Affichage grille

- Lire `combat.grid` et `combat.combatants[*].position`.
- Grille **cases carrées** scroll/zoom **non requis** en 6a — viewport CSS avec `width × height` cases visibles (grille 20×20 par défaut API).
- Coordonnées **0-indexées** alignées API : `x` colonne, `y` ligne (documenter dans le composant).
- Axes : labels optionnels (A–T / 1–20) — cosmétique.
- État `preparing` ou `ended` : message explicite (« Carte disponible après activation » / « Combat terminé ») — **pas** de fausse grille.

#### Jetons

- Un jeton par combattant avec `position` définie.
- Distinction visuelle allié / ennemi : **`kind`** ou convention existante (`pc` vs `npc` / `character_id` du viewer) — **sans** inventer de faction.
- Surbrillance : `combatant_id === current_combatant_id`.
- Initiales ou pastille couleur — **pas** d'`image_url` (dette lot 4).

#### Interaction déplacement

| Condition | UI move |
|---|---|
| `status === "active"` | Grille interactive |
| `current_combatant_id` défini | Seul ce combattant est déplaçable via API |
| Viewer renseigné **et** `viewer.combatant_id === current_combatant_id` | Clic case → `postCombatMove` |
| Viewer absent ou autre combattant au tour | Carte **lecture seule** (positions visibles, pas de clic move) |
| `movement_remaining_ft === 0` | Move désactivé + indication pieds restants |

**Note banc local** : pas d'auth MJ — un client pourrait appeler `move` pour le combattant du tour sans être le « propriétaire » du viewer. En 6a, l'UI reste conservative (viewer = combattant actif) ; durcissement auth = lot futur (ADR-007 §Conséquences).

#### Alignement HUD

- Remplacer chip booléen « Mouvement » par **`{n} ft`** depuis `movement_remaining_ft` (masquer si clé absente — CONTRAT §2.8).
- Après move réussi : `applyCombatState` comme attaque/sort.
- Erreurs move : `ErrorAlert` avec code API (`CELL_OCCUPIED`, etc.).

#### API client

```typescript
// Signature indicative
postCombatMove(
  combatId: string,
  body: { combatant_id: string; x: number; y: number },
  viewer?: string,
): Promise<CombatState>
```

#### Amélioration UX optionnelle (stretch 6a, non bloquante)

- Clic jeton ennemi/allié → pré-remplit `targetId` du panneau attaque/sort **si** le combattant existe dans `combatants` — **sans** validation de portée client.

### 4.2 Lot 6b — WebSocket temps réel (après 6a)

**Objectif** : synchroniser la map entre clients sans bouton « Recharger ».

| Élément | Intention |
|---|---|
| Transport | WebSocket FastAPI (ADR-003, ADR-007) — **contrat distinct** à rédiger avant implémentation |
| Subscription | Par `combat_id` |
| Messages minimum | `PositionChanged` ; extension possible `TurnStarted`, état combat partiel |
| Client | Remplacer / compléter polling manuel sur la route combat |
| Auth | Hors scope — banc local ; lien viewer → personnage = dette ADR-007 |

**Ne pas démarrer 6b** dans le même commit que 6a — arbitrage transport requis (§12.3).

### 4.3 Lot 6c — polish visuel Figma (optionnel, agent Fable 5)

Voir **§8 — Quand utiliser Fable 5**.

---

## 5. Classification rendu — map centrale

| Niveau | Élément | Traitement 6a |
|---|---|---|
| **① Fonctionnel** | Grille + jetons positions API | `TacticalMap.svelte` — données `GET combat` |
| **① Fonctionnel** | Clic move + refresh état | `postCombatMove` |
| **② Donnée si présente** | `movement_remaining_ft` | Afficher en ft ; masquer si absent |
| **③ Placeholder** | Vision / mesure / brouillard | Boutons **disabled** + « À VENIR » (reprendre libellés lot 4) |
| **③ Placeholder** | Toggle grille | Optionnel — grille toujours visible en 6a |
| **④ Hors lot** | Surlignage portée attaque/sort | Pas de calcul client |
| **④ Hors lot** | LoS, obstacles, terrain | Lots 9+ |

---

## 6. Pièges — interdits

| Piège | Alternative |
|---|---|
| Recalculer distance Chebyshev pour griser des cases | Afficher `movement_remaining_ft` ; laisser le serveur rejeter |
| Garder `DEMO_TOKENS` avec positions % | Supprimer du chemin actif ; conserver en commentaire 6c si utile |
| Afficher `has_movement` | Migrer types + UI vers `movement_remaining_ft` |
| Modifier Python pour le 6a | Lot front strict — sauf bug API avéré (signaler, ne pas corriger hors périmètre) |
| WebSocket « minimal » dans 6a | Reporter 6b |
| Cacher la map si viewer absent | Positions non filtrées serveur — carte visible, move conditionné au viewer |

---

## 7. Fonctionnalités à conserver (checklist non négociable)

Reprendre [`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md) §7 + :

1. Parcours lobby → activer → combat avec **positions visibles** post-activation.
2. Move au tour du viewer → jeton change de case + `movement_remaining_ft` diminue.
3. Move hors tour → `409 NOT_COMBATANT_TURN` affiché.
4. Case occupée → `409 CELL_OCCUPIED`.
5. Attaque / sort / advance-turn / close **inchangés** fonctionnellement.
6. `npm run build` + `npm run check` OK.

**Parcours manuel 6a** :

Lobby → créer → activer → combat `#/combat/{id}?viewer=` → vérifier grille + jetons → clic case adjacente → move → attaque (vérif `OUT_OF_RANGE` possible si cible trop loin) → tour suivant → clôturer.

---

## 8. Quand utiliser Fable 5

Fable 5 est l'agent cible des briefs **visuels sans changement de contrat** ([`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md)). Pour le lot 6 :

| Phase | Agent recommandé | Fable 5 ? |
|---|---|---|
| **6a — map REST** | Agent implémentation standard | **Non** — nouveaux types, appel `POST …/move`, logique UX (tour / viewer), remplacement composant |
| **6b — WebSocket** | Agent implémentation standard | **Non** — plumbing API + client, contrat transport |
| **6c — polish map** | **Fable 5** | **Oui** — une fois 6a **validé fonctionnellement** |
| Refonte HUD global (colonnes, journal…) | Fable 5 | **Déjà livré** lot 4 — ne pas refaire |

### Fable 5 intervient si (6c)

- La grille **fonctionne** (jetons réels, move OK) mais l'écart visuel vs maquette Figma / `MapPlaceholder` est trop grand.
- Mission type : **conserver** le comportement 6a, **transformer** le rendu (textures pierre, cercle rituel en arrière-plan non interactif, jetons, hover, transitions, densité).
- **Interdit Fable** : ajouter calcul de portée, WebSocket, nouvelles routes, données fictives.

### Fable 5 ne pas utiliser quand

- Il faut **brancher l'API** ou **corriger les types** → agent implémentation 6a.
- Il faut **WebSocket** ou modifier `interfaces/api/` → agent 6b.
- La map n'affiche pas encore les vraies positions → terminer 6a d'abord.

**Ordre recommandé** : brief acté → **6a agent standard** → validation mainteneur → **6c Fable optionnel** → **6b WebSocket**.

---

## 9. Fichiers autorisés / interdits

### 6a — autorisés

```
web/src/lib/types/combat.ts
web/src/lib/api/combat.ts
web/src/lib/components/combat/TacticalMap.svelte    (nouveau)
web/src/lib/components/combat/MapPlaceholder.svelte  (suppression ou conservation archive — ne plus importer depuis CombatScreen)
web/src/lib/screens/CombatScreen.svelte
web/src/lib/components/combat/*.svelte              (ajustements mineurs si besoin)
```

### 6a — interdits

| Zone | Raison |
|---|---|
| `jdr_engine/`, `interfaces/api/` | Sauf 6b ou bug bloquant signalé |
| `bot/` | D2 |
| `web/package.json` | Sans accord |
| `ROADMAP.md`, `VISION.md`, ADR | Pilotés mainteneur |

### 6b — extension

```
interfaces/api/*.py          (endpoint WS)
web/src/lib/api/combat_ws.ts (indicatif)
docs/api/CONTRAT_WS.md       (nouveau contrat transport — proposition)
```

---

## 10. Critères de done — lot 6a

1. **`npm run build`** et **`npm run check`** — exit 0.
2. **`MapPlaceholder` non utilisé** sur la route combat active (composant archivé ou supprimé).
3. Types TS alignés sur `output_serializers.py` (`grid`, `position`, `movement_remaining_ft`).
4. **`postCombatMove`** implémenté et branché.
5. Grille + jetons visibles après `activate` sans move préalable.
6. Move consomme budget — affichage ft à jour.
7. Checklist §7 passée manuellement.
8. **Aucun** fichier Python modifié.
9. Rapport agent : capture ou description de l'écart visuel restant → décision 6c Fable.

**Tests moteur** : delta **0** attendu pour 6a pur front.

---

## 11. Ordre d'implémentation proposé — 6a

1. **Types** — `GridPosition`, `CombatGrid`, `ActionBudget.movement_remaining_ft`, `CombatState.grid`.
2. **API client** — `postCombatMove`.
3. **`TacticalMap.svelte`** — grille + jetons (MVP visuel sobre acceptable).
4. **`CombatScreen.svelte`** — remplacer placeholder, wiring move, chip ft.
5. **Validation** — build/check + parcours §7.
6. **(Optionnel 6c)** — brief Fable ou consigne polish reprenant décor lot 4.

---

## 12. Arbitrages proposés (validation mainteneur)

### 12.1 Découpage 6a / 6b — **recommandé : accepter**

**Décision proposée** : 6a livrable seul (REST + refresh). 6b après contrat WS.

**Rejeté** : bloquer 6a en attendant WebSocket.

### 12.2 UX move — **recommandé : clic case, viewer = combattant actif**

**Décision proposée** : clic sur case vide ; move autorisé UI seulement si `viewer.combatant_id === current_combatant_id`.

**Alternative** : tout client peut move le combattant du tour (mode « table MJ partagée ») — plus permissif, moins safe multi-poste.

### 12.3 WebSocket 6b — **recommandé : contrat avant code**

**Décision proposée** : rédiger `docs/api/CONTRAT_WS.md` (ou section CONTRAT) avant implémentation 6b.

### 12.4 Décor lot 4 — **recommandé : sobre en 6a, Fable en 6c**

**Décision proposée** : 6a = grille lisible fonctionnelle (cases + jetons). Réintégration pierre / rituel = **6c Fable**, pas critère de done 6a.

**Alternative** : porter le CSS décoratif de `MapPlaceholder` dès 6a — acceptable si **zero régression** fonctionnelle et temps maîtrisé.

### 12.5 Clic jeton → cible attaque — **recommandé : stretch non bloquant**

**Décision proposée** : nice-to-have 6a ; omit si retard.

---

## 13. Références

| Document | Rôle |
|---|---|
| [`BRIEF_LOT8_GEOMETRIE.md`](../combat/BRIEF_LOT8_GEOMETRIE.md) | API consommée |
| [`docs/api/CONTRAT.md`](../api/CONTRAT.md) §5.5 | Formes JSON, codes erreur |
| [`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md) | Placeholders lot 4 ; cadre Fable |
| [`ADR-007`](../adr/ADR-007-stack-client-web.md) | REST vs WebSocket |
| [`ROADMAP.md`](../../ROADMAP.md) | Piste client Web — lot 6 |
| `web/src/lib/components/combat/MapPlaceholder.svelte` | État décoratif actuel |
| `jdr_engine/application/dto/output_serializers.py` | Source vérité champs sérialisés |

---

## 14. Validation

| Rôle | Action |
|---|---|
| Mainteneur | ✅ Périmètre §12 acté (2026-08-13) |
| Agent 6a | ✅ **Clôturé** août 2026 |
| Agent 6b | Voir [`BRIEF_LOT6B_WEBSOCKET.md`](BRIEF_LOT6B_WEBSOCKET.md) — après validation mainteneur |

**Phrase de mission 6a (copier-coller)** :

> Implémente le lot 6a map tactique REST : types et client `postCombatMove`, composant `TacticalMap.svelte` (grille + jetons réels), intégration `CombatScreen`, budget `movement_remaining_ft`. Aucun Python, aucune règle D&D client, pas de WebSocket. Suis `docs/web/BRIEF_LOT6_MAP_TACTIQUE.md`.

---

## 15. Instructions d'exécution pour Fable 5 (lot 6c uniquement)

**Ne lire cette section que si le 6a est validé et qu'un polish visuel est demandé.**

1. Lire ce brief §8 et `TacticalMap.svelte` + `MapPlaceholder.svelte` (référence décor).
2. **Ne pas modifier** les appels API ni la logique move / tour / viewer.
3. Améliorer le rendu (textures, jetons, header map, footer échelle) pour rapprocher la maquette Figma.
4. Conserver placeholders §5 pour vision / mesure / brouillard.
5. `npm run build` + `npm run check` + parcours §7 sans régression.

**Phrase de mission Fable (6c)** :

> Le lot 6a map tactique fonctionne. Conserve intégralement son comportement et ses appels API ; transforme uniquement le rendu visuel de la carte pour rapprocher la maquette Figma et l'ADN de `MapPlaceholder` (sombre/ambre, décor non interactif). Aucun Python, aucune donnée inventée, aucun calcul de portée. Suis `docs/web/BRIEF_LOT6_MAP_TACTIQUE.md` §8 et §15.
