# Cadrage lot 6c — WebSocket temps réel (map / rencontre)

| Attribut | Valeur |
|---|---|
| **Statut** | **Proposition** — pas d'implémentation avant passage en **Accepté** |
| **Date** | 2026-08-13 |
| **Prérequis** | Lot **6a** ✅ · lot **6b** scène statique (recommandé — [`BRIEF_LOT6B_SCENE_STATIQUE.md`](BRIEF_LOT6B_SCENE_STATIQUE.md)) ; lot 8 ✅ ; **1018** tests verts |
| **Hors périmètre de ce document** | Implémentation commits, auth multi-poste, modèle scène/campagne |

**Décisions proposées (à acter §10)** :

- WebSocket **rencontre-scoped** (`combat_id`) — pas de canal « scène » tant que le modèle scène n'existe pas.
- Push **événements métier** sérialisés — pas de duplication de règles côté transport.
- Le client **6a REST** reste fallback (reconnexion, bouton recharger, tests sans WS).
- **Aucune** migration scène/rencontre — voir [`VISION.md`](../../VISION.md) §5 et §10.

---

## 1. Mission

Synchroniser la **map tactique** et le **HUD rencontre** entre plusieurs clients **sans rechargement manuel**, en poussant les événements combat déjà publiés par l'EventBus (ADR-003).

Le lot **6a** fonctionne en pull (`GET /v1/combats/{id}` après chaque action). Le lot **6c** ajoute un **canal push** pour que les autres postes voient moves, tours et dégâts en temps quasi réel.

**Périmètre immédiat** : écran `#/combat/{id}` — pas la future page scène unifiée ([`VISION.md`](../../VISION.md) §4.0).

---

## 2. Contrats à respecter

| Document | Obligation lot 6c |
|---|---|
| [`VISION.md`](../../VISION.md) **§4.0** | Le WS synchronise l'état **rencontre** sur l'écran combat actuel — **ne construit pas** la scène unifiée. |
| [`VISION.md`](../../VISION.md) **§5** | `CombatState` = **rencontre** ; pas de rattachement scène. |
| [`VISION.md`](../../VISION.md) **§10 D9** | Canal lié à la **rencontre** (`combat_id`). |
| [`docs/api/CONTRAT.md`](../api/CONTRAT.md) | REST = source de vérité ; WS = complément. |
| [`ADR-003`](../adr/ADR-003-Pourquoi-utiliser-un-EventBus.md) | Abonnement EventBus côté API. |
| [`ADR-007`](../adr/ADR-007-stack-client-web.md) | REST + WS rencontre. |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | Comportement 6a **préservé**. |

**Garde-fou** : modèle scène / move hors rencontre → **AGENTS.md #6**.

---

## 3. État réel du code

| Élément | État |
|---|---|
| `TacticalMap.svelte` | Move REST (6a) ; calque visuel (6b) |
| `CombatScreen.svelte` | Pas de subscription WS |
| `PositionChanged`, `TurnStarted` | Publiés moteur — non relayés WS |
| FastAPI WebSocket | **Absent** |

---

## 4. Périmètre fonctionnel

### 4.1 Transport

| Élément | Décision proposée |
|---|---|
| Protocole | WebSocket FastAPI |
| URL | `WS /v1/combats/{combat_id}/ws` |
| Identité | Query `viewer` optionnel — sans auth |
| Reconnexion | Backoff + `GET` état complet |

**Gate** : [`docs/api/CONTRAT_WS.md`](../api/CONTRAT_WS.md) **avant code** (§11).

### 4.2 Messages serveur → client (MVP)

```json
{ "type": "<event_type>", "combat_id": 42, "payload": {} }
```

| `type` | Source | Effet client |
|---|---|---|
| `position_changed` | `PositionChanged` | Jeton + `movement_remaining_ft` |
| `turn_started` | `TurnStarted` | Tour courant |
| `combat_ended` | `CombatEnded` | Fermeture canal |

### 4.3 Messages client → serveur

**Aucune action de jeu** — actions via REST uniquement.

### 4.4 Client

`combat_ws.ts` + hook `CombatScreen` ; fallback 6a si WS down.

### 4.5 API

Connection manager + subscribers EventBus ; tests mock broadcast.

---

## 5. Hors périmètre

Modèle scène/campagne · auth · Redis · move via WS · refonte visuelle (6b).

---

## 6. Pièges — interdits

Move via WS · canal scène globale · supprimer refresh 6a · règles client sur payload.

---

## 7. Critères de done

1. `CONTRAT_WS.md` publié.
2. Tests Python broadcast ; delta vs **1018**.
3. `npm run build` + `npm run check` OK.
4. Deux onglets : move visible sans Recharger.
5. Fallback 6a OK.
6. Aucun modèle scène introduit.

---

## 8. Fichiers autorisés

`docs/api/CONTRAT_WS.md` · `interfaces/api/**` (WS) · `tests/unit/test_api_v1_combat_ws.py` · `web/src/lib/api/combat_ws.ts` · `CombatScreen.svelte`

**Interdit** : `jdr_engine/` (couplage transport) · `ROADMAP.md` / `VISION.md`.

---

## 9. Ordre d'implémentation

1. `CONTRAT_WS.md` → 2. API WS → 3. Tests → 4. Client → 5. Validation deux onglets.

---

## 10. Arbitrages proposés

| # | Recommandation |
|---|---|
| 10.1 | Canal **rencontre** only |
| 10.2 | Ping/pong FastAPI |
| 10.3 | État initial via GET REST |
| 10.4 | Journal temps réel hors MVP |

---

## 11. Gate documentaire

**Aucun code 6c** avant `CONTRAT_WS.md` acté.

---

## 12. Validation

| Rôle | Action |
|---|---|
| Mainteneur | **Accepté** + contrat WS |
| Agent | Implémentation après gate |

**Phrase de mission** :

> Implémente le lot 6c WebSocket : `CONTRAT_WS.md`, route FastAPI, broadcast EventBus (`PositionChanged`, `TurnStarted`), client `combat_ws.ts`, fallback 6a. Suis `docs/web/BRIEF_LOT6C_WEBSOCKET.md` et `VISION.md` §4.0.
