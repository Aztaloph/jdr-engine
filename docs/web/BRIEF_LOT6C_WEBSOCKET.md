# Cadrage lot 6c — WebSocket temps réel (map / rencontre)

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** (mainteneur 2026-08-13) |
| **Date** | 2026-08-13 |
| **Prérequis** | Lot **6a** ✅ · lot **6b** scène statique ✅ · lot 8 ✅ · **1018** tests verts |
| **Contrat** | [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) — **Accepté** |
| **Hors périmètre de ce document** | Auth multi-poste · modèle scène/campagne · Redis |

**Décisions actées** :

- WebSocket **rencontre-scoped** (`combat_id`) — pas de canal « scène ».
- Push **événements métier** sérialisés — pas de duplication de règles côté transport.
- Quatre messages MVP dont **`combat_state_invalidated`** (resync GET sur attaque, dégâts, effets, etc.).
- Le client **6a REST** reste fallback (reconnexion sauf `4404`, bouton Recharger, GET post-action initiateur).
- **Aucune** migration scène/rencontre — voir [`VISION.md`](../../VISION.md) §5 et §10.

---

## 1. Mission

Synchroniser la **map tactique** et le **HUD rencontre** entre plusieurs clients **sans rechargement manuel**, en poussant les événements combat déjà publiés par l'EventBus (ADR-003).

Le lot **6a** fonctionne en pull (`GET /v1/combats/{id}` après chaque action). Le lot **6c** ajoute un **canal push** pour que les autres postes voient moves, tours, **PV cohérents après attaque**, et clôture en temps quasi réel.

**Périmètre immédiat** : écran `#/combat/{id}` — pas la future page scène unifiée ([`VISION.md`](../../VISION.md) §4.0).

---

## 2. Contrats à respecter

| Document | Obligation lot 6c |
|---|---|
| [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) | **Source normative** transport WS |
| [`CONTRAT.md`](../api/CONTRAT.md) | REST = source de vérité ; WS = complément |
| [`VISION.md`](../../VISION.md) **§4.0, §5, §10 D9** | Canal rencontre only |
| [`ADR-003`](../adr/ADR-003-Pourquoi-utiliser-un-EventBus.md) | Abonnement EventBus côté API |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | Comportement 6a **préservé** |

---

## 3. État réel du code

| Élément | État |
|---|---|
| `TacticalMap.svelte` | Move REST (6a) ; scène (6b) |
| `CombatScreen.svelte` | Pas de subscription WS |
| EventBus combat | Publié moteur — non relayés WS |
| FastAPI WebSocket | **Absent** |

---

## 4. Périmètre fonctionnel

### 4.1 Transport

Voir [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) §2 — URL `WS /v1/combats/{combat_id}/ws?viewer=`, rejet **`4404`**, dette keep-alive §2.4.

### 4.2 Messages serveur → client (MVP)

| `type` | Effet client |
|---|---|
| `position_changed` | Patch jeton / mouvement (ou GET) |
| `turn_started` | Patch tour courant (ou GET) |
| `combat_ended` | Fin rencontre + fermeture canal |
| `combat_state_invalidated` | **GET complet** — attaque, dégâts, soins, effets, etc. |

### 4.3 Messages client → serveur

**Aucune action de jeu** — REST uniquement.

### 4.4 Client

`combat_ws.ts` + hook `CombatScreen` ; fallback 6a ; pas de reconnexion sur **`4404`**.

### 4.5 API

`CombatWsHub` + handlers EventBus ; tests §6.4 du contrat (T1–T7, **+6** tests).

---

## 5. Hors périmètre

Modèle scène · auth · Redis · move via WS · journal texte riche temps réel · messages WS typés `damage_dealt` (phase 2).

---

## 6. Pièges — interdits

Move via WS · canal scène globale · supprimer refresh 6a · divergence PV silencieuse · reconnexion sur `4404`.

---

## 7. Critères de done

1. [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) **Accepté** ✅
2. Tests Python T1–T7 ; delta **≥ +6** vs **1018**
3. `npm run build` + `npm run check` OK
4. Deux onglets : move **et** attaque/dégâts visibles sans Recharger manuel (B)
5. Fallback 6a OK ; `4404` sans reconnexion
6. Aucun modèle scène introduit

---

## 8. Fichiers autorisés

`interfaces/api/**` (WS) · `tests/unit/test_api_v1_combat_ws.py` · `web/src/lib/api/combat_ws.ts` · `CombatScreen.svelte`

**Interdit** : `jdr_engine/` · `ROADMAP.md` / `VISION.md` (cases manuelles).

---

## 9. Ordre d'implémentation

1. API WS + hub EventBus → 2. Tests T1–T7 → 3. Client → 4. Validation §9 `CONTRAT_WS.md`.

---

## 10. Arbitrages actés

| # | Décision |
|---|---|
| 10.1 | Canal **rencontre** only |
| 10.2 | Ping/pong natif |
| 10.3 | État initial via GET REST |
| 10.4 | Journal temps réel **hors MVP** ; invalidation ≠ journal |
| 10.5 | GET post-REST chez l'initiateur |
| 10.6 | `combat_id` entier JSON |
| 10.7 | `combat_state_invalidated` MVP |
| 10.8 | Fermeture **`4404`** si combat absent |

---

## 11. Gate documentaire

**Levée** 2026-08-13 — implémentation autorisée après validation mainteneur post-cadrage.

---

## 12. Validation

| Rôle | Action |
|---|---|
| Mainteneur | **Accepté** 2026-08-13 |
| Agent | Implémentation **après** validation du commit cadrage |

**Phrase de mission** :

> Implémente le lot 6c WebSocket selon [`CONTRAT_WS.md`](../api/CONTRAT_WS.md) Accepté : route FastAPI, hub EventBus (quatre types MVP dont `combat_state_invalidated`), tests T1–T7, client `combat_ws.ts`, fallback 6a. Ne pas modifier `jdr_engine/`.
