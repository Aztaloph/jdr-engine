# Cadrage lot 6b — WebSocket temps réel (map / rencontre)

| Attribut | Valeur |
|---|---|
| **Statut** | **Proposé** — en attente validation mainteneur |
| **Date** | 2026-08-13 |
| **Prérequis** | Lot **6a** map REST ✅ ([`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md)) ; lot 8 géométrie ✅ ; lot 7 MVP combat ✅ ; **1018** tests verts |
| **Successeur optionnel** | Lot **6c** polish visuel Figma (agent Fable 5) |
| **Hors périmètre de ce document** | Implémentation commits, auth multi-poste, modèle scène/campagne |

**Décisions proposées (à acter §10)** :

- WebSocket **rencontre-scoped** (`combat_id`) — pas de canal « scène » tant que le modèle scène n'existe pas.
- Push **événements métier** sérialisés — pas de duplication de règles côté transport.
- Le client **6a REST** reste fallback (reconnexion, bouton recharger, tests sans WS).
- **Aucune** migration scène/rencontre dans ce lot — voir [`VISION.md`](../../VISION.md) §5 et §10.

---

## 1. Mission

Synchroniser la **map tactique** et le **HUD rencontre** entre plusieurs clients **sans rechargement manuel**, en poussant les événements combat déjà publiés par l'EventBus (ADR-003).

Le lot **6a** fonctionne en pull (`GET /v1/combats/{id}` après chaque action). Le lot **6b** ajoute un **canal push** pour que les autres postes voient moves, tours et dégâts en temps quasi réel.

**Périmètre immédiat** : écran `#/combat/{id}` et composant `TacticalMap.svelte` — pas la future page scène unifiée ([`VISION.md`](../../VISION.md) §4.0).

---

## 2. Contrats à respecter

| Document | Obligation lot 6b |
|---|---|
| [`VISION.md`](../../VISION.md) **§4.0** | La page principale cible est la **scène** ; le HUD combat n'est qu'un **mode rencontre** temporaire. Le WebSocket 6b ne construit **pas** la scène unifiée — il synchronise l'état **rencontre** sur l'écran combat actuel (étape intermédiaire explicitement compatible §4.0). |
| [`VISION.md`](../../VISION.md) **§5** | L'objet `CombatState` actuel = **rencontre** ; pas de rattachement scène dans ce lot. |
| [`VISION.md`](../../VISION.md) **§10 D9** | Combat = mode temporaire ; le canal WS est lié à la **rencontre** (`combat_id`), pas à une campagne. |
| [`docs/api/CONTRAT.md`](../api/CONTRAT.md) | REST v1 inchangé comme source de vérité ; WS = transport complémentaire. |
| [`ADR-003`](../adr/ADR-003-Pourquoi-utiliser-un-EventBus.md) | Abonnement EventBus côté API ; le moteur ne connaît pas le WebSocket. |
| [`ADR-007`](../adr/ADR-007-stack-client-web.md) | REST = états ponctuels ; WS = map temps réel **rencontre**. |
| [`AGENTS.md`](../../AGENTS.md) §6 | Pas de règles D&D dans `web/` ; le client applique les payloads reçus. |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | Comportement 6a **préservé** ; WS complète, ne remplace pas `postCombatMove` / refresh. |

**Garde-fou vision** : si une implémentation 6b introduit un modèle « scène », « campagne live » ou un déplacement de jetons hors rencontre → **critère d'arrêt AGENTS.md #6** — arbitrage mainteneur requis.

---

## 3. État réel du code (référence factuelle, 2026-08-13)

### 3.1 Lot 6a — livré

| Élément | État |
|---|---|
| `TacticalMap.svelte` | Grille + jetons + clic move |
| `postCombatMove()` | Branché ; refresh via `applyCombatState` |
| `CombatScreen.svelte` | Parent ; pas de subscription WS |
| Fallback | Bouton « Recharger » + refresh post-action |

### 3.2 Moteur & API — réutilisable

| Élément | Fichier | Usage 6b |
|---|---|---|
| `PositionChanged` | `jdr_engine/core/events/combat_events.py` | Push move map |
| `TurnStarted`, `TurnEnded` | idem | Push tour courant |
| `DamageDealt`, `AttackRollResolved` | idem | Push HUD / journal |
| `CombatStarted`, `CombatEnded` | idem | Lifecycle canal |
| `RecordingEventBus` | `interfaces/api/diagnostic/recording_bus.py` | Pattern enregistrement — **ne pas** confondre avec push prod |
| `EventRingBuffer` | `interfaces/api/diagnostic/event_buffer.py` | Diagnostic `/debug/events` — hors contrat v1 |
| `create_app()` | `interfaces/api/app.py` | Point d'accroche WS FastAPI |
| FastAPI WebSocket | **Absent** | À implémenter |

### 3.3 Dettes explicites (hors 6b)

| Dette | Lot futur |
|---|---|
| Modèle **scène** / page principale | Lot dédié (nom explicite) |
| WS scène hors-combat (carte statique, sandbox/live) | Après modèle scène |
| Auth viewer → personnage | ADR-007 §Conséquences |
| Filtrage positions par joueur (brouillard) | Lot terrain + LoS |

---

## 4. Périmètre fonctionnel

### 4.1 Transport

| Élément | Décision proposée |
|---|---|
| Protocole | WebSocket (FastAPI natif) |
| URL indicative | `WS /v1/combats/{combat_id}/ws` |
| Subscription | Client ouvre WS avec `combat_id` ; serveur enregistre la connexion |
| Identité | Query `viewer` optionnel (miroir REST) — **sans auth** en 6b |
| Heartbeat | Ping/pong ou message `ping` applicatif — à trancher §10.2 |
| Reconnexion | Client : backoff + `GET` état complet au reconnect |

**Document normatif** : [`docs/api/CONTRAT_WS.md`](../api/CONTRAT_WS.md) — **rédigé dans ce lot avant code** (§11).

### 4.2 Messages serveur → client (minimum viable)

Envelope commune :

```json
{
  "type": "<event_type>",
  "combat_id": 42,
  "payload": { }
}
```

| `type` | Source EventBus | Effet client minimum |
|---|---|---|
| `position_changed` | `PositionChanged` | Mettre à jour jeton + `movement_remaining_ft` sur map / fiche tour |
| `turn_started` | `TurnStarted` | `current_combatant_id`, surbrillance initiative |
| `combat_state_snapshot` | Sérialisation `combat_state_to_dict` | Reconnexion / join tardif — **optionnel MVP** si `GET` suffit au reconnect |
| `combat_ended` | `CombatEnded` | Notification + désactiver move |

**Extension post-MVP** (non bloquante) : `damage_dealt`, `attack_roll_resolved`, `spell_cast` — pour journal temps réel sans refresh.

### 4.3 Messages client → serveur (6b)

| Direction | Contenu |
|---|---|
| Client → serveur | **Aucune action de jeu** en 6b — les actions restent **REST** (`POST …/move`, `…/attack`, etc.) |
| Optionnel | `subscribe` / `ping` uniquement |

**Interdit** : envoyer un move via WS — dupliquerait le contrat REST et contournerait la validation moteur.

### 4.4 Intégration client (`web/`)

| Composant | Changement |
|---|---|
| `CombatScreen.svelte` | Ouvrir WS au mount ; fermer au unmount / clôture |
| `TacticalMap.svelte` | Recevoir positions via props — **pas** de logique WS interne |
| Nouveau `combat_ws.ts` (indicatif) | Connexion, parse envelope, callback typed |
| Fallback | Si WS déconnecté : comportement 6a (refresh manuel + post-action) |

### 4.5 Intégration API (`interfaces/api/`)

| Composant | Changement |
|---|---|
| Handler WS | Connection manager par `combat_id` |
| Subscriber EventBus | Au boot : handlers qui broadcast aux WS abonnés |
| Sérialisation | Réutiliser DTO existants — pas de nouveau schéma métier |
| Tests | Unitaires API (connexion mock, broadcast sur `PositionChanged`) |

**Invariant** : `jdr_engine/` **n'importe pas** FastAPI ni WebSocket.

---

## 5. Hors périmètre (volontaire)

| Item | Raison |
|---|---|
| Modèle scène / campagne | [`VISION.md`](../../VISION.md) §4.0 — lot dédié |
| Déplacement jetons hors rencontre | Dette §10 VISION |
| Auth / sessions joueur | Banc local |
| Redis / broker externe | ADR-003 — in-process suffit |
| Remplacement complet du REST | WS = push ; REST = actions + source de vérité |
| OpenAPI WS normatif | `CONTRAT_WS.md` prime |
| Discord notifications via WS | Étape 8 |

---

## 6. Pièges — interdits

| Piège | Alternative |
|---|---|
| Calculer portée / move côté client sur message WS | Appliquer payload ; conserver validation REST |
| Canal WS « scène globale » sans modèle scène | Canal **rencontre** (`combat_id`) |
| Move via message WS entrant | `POST …/move` uniquement |
| Dupliquer `combat_state_to_dict` avec champs inventés | DTO moteur existants |
| Supprimer le refresh 6a | Fallback obligatoire |
| Bloquer 6b sur auth multi-poste | Documenter limite ; livrer banc local |

---

## 7. Critères de done — lot 6b

1. **`docs/api/CONTRAT_WS.md`** publié et cohérent avec ce brief.
2. **Tests Python** : au moins broadcast `PositionChanged` + `TurnStarted` vers client mock ; delta documenté vs **1018**.
3. **`npm run build`** + **`npm run check`** OK.
4. **Parcours manuel deux onglets** : même `combat_id`, viewer A move → viewer B voit le jeton **sans** cliquer Recharger.
5. **Fallback** : WS coupé → 6a fonctionne (move + refresh).
6. **Aucune** règle D&D ajoutée dans `web/`.
7. **Aucun** modèle scène/campagne introduit.
8. **`VISION.md` §4.0** respecté — écran combat reste étape intermédiaire.

**Parcours manuel** :

Deux navigateurs → même combat actif → viewer A au tour → move → B voit position ; A fin de tour → B voit tour courant ; clôture → WS se ferme proprement.

---

## 8. Fichiers autorisés / interdits

### Autorisés

```
docs/api/CONTRAT_WS.md                    (nouveau)
interfaces/api/combat_ws.py               (indicatif — nouveau)
interfaces/api/app.py                     (enregistrement route WS)
interfaces/api/combat_routes.py           (si helper partagé)
tests/unit/test_api_v1_combat_ws.py       (nouveau)
web/src/lib/api/combat_ws.ts              (nouveau)
web/src/lib/screens/CombatScreen.svelte
web/src/lib/types/combat.ts               (types envelope WS si besoin)
```

### Interdits

| Zone | Raison |
|---|---|
| `jdr_engine/game/`, `jdr_engine/rules/` | Pas de couplage transport |
| `bot/` | D2 |
| `ROADMAP.md`, `VISION.md`, ADR | Pilotés mainteneur — sauf `CONTRAT_WS.md` |
| Nouvelle dépendance npm / pip | Sans accord (`AGENTS.md`) |
| Modèle scène / campagne | Hors lot |

---

## 9. Ordre d'implémentation proposé

1. **Contrat** — `docs/api/CONTRAT_WS.md` (envelope, types, lifecycle, erreurs).
2. **API** — connection manager + route WS + subscribers EventBus.
3. **Tests API** — mock client, broadcast minimal.
4. **Client** — `combat_ws.ts` + hook dans `CombatScreen`.
5. **Validation** — parcours §7 deux onglets + fallback.

---

## 10. Arbitrages proposés (validation mainteneur)

### 10.1 Scope canal — **recommandé : rencontre only**

**Décision proposée** : `WS /v1/combats/{combat_id}/ws` — aligné vocabulaire rencontre (`VISION.md` §5).

**Rejeté** : canal générique « session » ou « scène » avant modèle scène.

### 10.2 Heartbeat — **recommandé : ping FastAPI natif**

**Décision proposée** : ping/pong framework ; pas de message applicatif sauf besoin proxy.

### 10.3 Snapshot au connect — **recommandé : GET REST, pas snapshot WS obligatoire**

**Décision proposée** : à l'ouverture WS, le client fait déjà `GET /v1/combats/{id}` (mount existant) ; le WS ne pousse que les **deltas**.

**Alternative** : premier message `combat_state_snapshot` — utile si on supprime le GET au mount (non recommandé).

### 10.4 Journal temps réel — **recommandé : hors MVP**

**Décision proposée** : MVP = map + tour ; journal reste refresh / `GET …/events` en 6b.

---

## 11. Livrable documentaire préalable (gate)

**Aucun code 6b** avant publication de `docs/api/CONTRAT_WS.md` validé par le mainteneur (reprise des §4.1–4.3 de ce brief).

---

## 12. Références

| Document | Rôle |
|---|---|
| [`VISION.md`](../../VISION.md) §4.0, §5, §10 | Scène / rencontre — contrainte produit |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | 6a consommé |
| [`BRIEF_LOT8_GEOMETRIE.md`](../combat/BRIEF_LOT8_GEOMETRIE.md) | Positions / move |
| [`docs/api/CONTRAT.md`](../api/CONTRAT.md) | REST v1 |
| [`ADR-003`](../adr/ADR-003-Pourquoi-utiliser-un-EventBus.md) | Pub/sub |
| [`ADR-007`](../adr/ADR-007-stack-client-web.md) | Stack client |
| `jdr_engine/core/events/combat_events.py` | Types événements |
| `web/src/lib/components/combat/TacticalMap.svelte` | Cible sync visuelle |

---

## 13. Validation

| Rôle | Action |
|---|---|
| Mainteneur | Valider §10 → statut **Accepté** |
| Agent implémentation | Démarrer après **Accepté** + `CONTRAT_WS.md` acté |

**Phrase de mission 6b (copier-coller)** :

> Implémente le lot 6b WebSocket rencontre : `CONTRAT_WS.md`, route FastAPI, broadcast EventBus (`PositionChanged`, `TurnStarted` minimum), client `combat_ws.ts` intégré à `CombatScreen` avec fallback 6a. Pas de modèle scène, pas de move via WS, pas de règles client. Suis `docs/web/BRIEF_LOT6B_WEBSOCKET.md` et `VISION.md` §4.0.
