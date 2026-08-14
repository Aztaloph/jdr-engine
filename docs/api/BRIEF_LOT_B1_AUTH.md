# Cadrage lot B1 — Authentification & autorisation API (ÉTAPE 6)

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** (mainteneur 2026-08-14 — arbitrages §11 tranchés) |
| **Date** | 2026-08-14 |
| **Prérequis** | Lot **6a** map REST ✅ · lot **6b** scène statique ✅ · lot **6c** WebSocket ✅ · polish HUD ✅ · **1026** tests verts |
| **Contrats existants** | [`CONTRAT.md`](CONTRAT.md) · [`CONTRAT_WS.md`](CONTRAT_WS.md) |
| **Hors périmètre de ce document** | OAuth Discord production · Redis · modèle scène/campagne · brouillard de guerre · rate limiting |

> **Attention nomenclature** : dans `ROADMAP.md`, **Axe B — B1** = inventaire sorts (✅ terminé). Le présent lot est le **jalon auth de l'ÉTAPE 6** — on l'appelle **« lot B1 auth »** dans la conversation produit pour le distinguer du lot 6 front (map). Dans les commits, préférer : `feat(api): lot B1 auth — …` ou `feat(api): auth viewer et rôle MJ — …`.

---

## 1. Mission

Passer d'un **banc local ouvert** (n'importe qui peut agir au nom de n'importe quel personnage) à une API où **chaque mutation est attribuée à un utilisateur authentifié**, avec des règles d'autorisation explicites joueur / MJ.

**Motivation** (ADR-007 §Conséquences) :

> Le multi-poste réel exigera une notion d'utilisateur authentifié, ou au minimum un lien joueur → personnage. L'API n'a aujourd'hui aucune authentification et accepte les `character_id` sans vérifier l'émetteur.

Le lot **6c** (WebSocket) a validé la sync multi-onglets **sans** auth : deux navigateurs peuvent toujours usurper l'identité d'un autre PJ via `?viewer=` ou le corps `attacker_id` / `caster_id`. **B1 auth** comble ce trou avant toute ouverture réseau (LAN, hébergement, Discord → Web).

---

## 2. Clôture lot 6 front (contexte amont)

| Sous-lot | Livrable | Commit | Statut |
|---|---|---|---|
| **6a** — map REST | `POST …/move`, grille, jetons, consommation mouvement | `81fc9e6` | ✅ |
| **6b** — scène statique | SVG fond carte, panneau droit | `6f26466` | ✅ |
| **6c** — WebSocket | `WS /v1/combats/{id}/ws`, resync, 8 tests T1–T7 | `d4f6415` | ✅ |
| **Polish HUD** | Layout colonne droite, journal enrichi | `e69a77c` | ✅ |
| **6d** — polish Figma | Alignement maquette pixel-perfect | — | ⏭️ optionnel, non bloquant |

**Validation utilisateur** : sync multi-onglets (move, attaque, fin de tour) sans Recharger ; pill dev `WS open · position_changed`.

**Dette lot 6 connue (hors B1)** :

- Journal WS push (événements texte) — backlog ÉTAPE 6
- Keep-alive WS documenté CONTRAT_WS §2.4 — non implémenté
- `bless` multi-cible UI (serveur accepte 3, client 1)

---

## 3. État réel du code (point de départ)

### 3.1 Paramètre `viewer` — visibilité, pas auth

| Aspect | Comportement actuel |
|---|---|
| **Sémantique** | `character_id` dont on simule la **vue** (filtrage PV/CA, bloc `viewer` avec sorts lançables) |
| **Vue MJ** | Query `viewer` **absent**, `null`, ou chaîne vide (trim) → intégralité des champs |
| **Validation** | `404 VIEWER_NOT_IN_COMBAT` si `viewer` non vide et absent de la rencontre |
| **Auth** | **Aucune** — un client peut envoyer `?viewer=alice` sans être Alice |

Documenté explicitement dans [`CONTRAT.md`](CONTRAT.md) §2.8 et §2.9 :

> **`caster_id` vs `viewer`** : le corps fixe le lanceur ; le query `viewer` ne filtre que la **réponse**. Aucun contrôle d'autorisation — acceptable banc local.

§6 hors périmètre v1 : « Authentification / autorisation — Banc local ».

### 3.2 Modèle utilisateur existant (persistance)

| Entité | Champ | Usage |
|---|---|---|
| `Character` | `owner_id: str` | ID Discord du propriétaire (`discord_user_id` en SQLite) |
| `Character` | `guild_id: str` | Scope serveur Discord |
| Combat blob | `guild_id`, `channel_id` | Scope interne persistance — **non exposés** API |

**Absent aujourd'hui** :

- Table ou store **session / token** API
- Endpoint login
- Rôle MJ côté API (Discord a `interfaces/discord/permissions/mj.py` — rôle « MJ », **non branché** à l'API)
- Filtrage `GET /v1/characters` par propriétaire (liste **tous** les personnages — commentaire « banc de test »)

### 3.3 Routes API v1 — inventaire complet

#### Combat (`interfaces/api/combat_routes.py`)

| Route | Query `viewer` | Corps action | Auth actuelle |
|---|---|---|---|
| `POST /v1/combats` | — | `character_ids[]` | ❌ ouverte |
| `GET /v1/combats/open` | — | — | ❌ ouverte |
| `GET /v1/combats/{id}` | optionnel | — | ❌ (filtrage vue seulement) |
| `GET /v1/combats/{id}/events` | — | — | ❌ ouverte |
| `POST …/activate` | — | grid, placements | ❌ ouverte (actions MJ documentées) |
| `POST …/attack` | optionnel | `attacker_id`, `target_id`, `weapon_id` | ❌ usurpation `attacker_id` |
| `POST …/cast` | optionnel | `caster_id`, `spell_id`, `target_ids` | ❌ usurpation `caster_id` |
| `POST …/heal` | optionnel | `combatant_id`, `hp_current?` | ❌ outil dev / MJ implicite |
| `POST …/sync-combatant` | optionnel | `combatant_id` | ❌ ouverte |
| `POST …/move` | optionnel | `combatant_id`, `x`, `y` | ❌ usurpation combattant |
| `POST …/advance-turn` | optionnel | — | ❌ ouverte (historiquement action MJ) |
| `POST …/close` | — | — | ❌ ouverte (action MJ) |

#### Personnage (`interfaces/api/app.py`)

| Route | Auth actuelle |
|---|---|
| `GET /v1/characters` | ❌ liste globale |
| `GET /v1/characters/{id}/sheet` | ❌ ouverte |
| `POST …/cast`, `short-rest`, `long-rest` | ❌ usurpation personnage |
| `GET/PUT …/prepared-spells` | ❌ usurpation personnage |

#### WebSocket (`interfaces/api/combat_ws.py`)

| Route | Auth actuelle |
|---|---|
| `WS /v1/combats/{id}/ws?viewer=` | ❌ ouverte ; `viewer` echo dans `connected` |

#### Diagnostic (hors contrat v1)

| Route | Note |
|---|---|
| `GET /debug/events`, `/debug/events/view` | Dev only — décider si protégé ou désactivé hors dev |

### 3.4 Client web (`web/`)

| Fichier | Rôle auth-related |
|---|---|
| `navigation.ts` | `viewer` dans hash `#/combat/{id}?viewer={character_id}` |
| `api/combat.ts` | Propage `viewer` en query sur toutes les routes combat |
| `api/combat_ws.ts` | `viewer` en query WS |
| `CombatScreen.svelte` | Sélecteur « Vue joueur » (dropdown ou saisie manuelle `character_id`) |
| `LobbyScreen.svelte` | Commentaire « Vue MJ — create/activate sans filtre viewer » |

**Aucun** stockage token, header `Authorization`, écran login.

### 3.5 Fichiers Python clés à toucher (estimation)

```
interfaces/api/
  app.py                    # routes personnage + middleware auth
  combat_routes.py          # garde-fous mutation combat
  combat_ws.py              # auth handshake WS
  errors.py                 # 401/403 si nouveaux codes
  auth/                     # NOUVEAU — sessions, dépendances FastAPI (proposition)
tests/unit/
  test_api_v1_auth.py       # NOUVEAU — fichier dédié lot B1
  test_api_v1_combat.py     # adapter si auth casse tests existants (mode dev?)
docs/api/
  CONTRAT.md                # §6 + nouvelle section auth — accord mainteneur
  CONTRAT_WS.md             # §2.1 token/session WS
web/src/lib/
  api/client.ts ou auth.ts  # NOUVEAU — header Bearer
  api/combat.ts, combat_ws.ts
  screens/LoginScreen.svelte ou modal dev  # NOUVEAU (minimal)
```

**Invariant AGENTS.md** : pas de règles D&D dans `interfaces/` — l'auth est **couche transport**, pas moteur. `jdr_engine/` ne devrait pas importer FastAPI ; la vérification `owner_id` peut rester dans `interfaces/api/` via `CharacterRepository`.

---

## 4. Objectifs fonctionnels (MVP B1)

### 4.1 Ce que B1 doit garantir

1. **Identité** : chaque requête mutante porte une identité utilisateur vérifiable (`user_id` = `owner_id` Discord ou équivalent dev).
2. **Lien joueur → personnage** : un joueur authentifié ne peut agir **que** via les combattants dont le `character.owner_id` correspond à sa session.
3. **Rôle MJ** : les actions « table » (créer/activer/clore rencontre, avancer le tour, heal dev, vue intégrale) exigent un rôle **GM/MJ** explicite dans la session.
4. **Cohérence `viewer`** : si `?viewer=` est présent, il doit correspondre à un personnage **possédé** par l'utilisateur (ou session MJ).
5. **WebSocket** : connexion refusée ou fermée si token absent/invalide ; `viewer` cohérent avec la session.
6. **Rétrocompatibilité dev** : mode « auth désactivée » documenté pour tests unitaires existants et banc local solo (voir §7).

### 4.2 Hors périmètre MVP (explicitement reporté)

| Exclusion | Raison |
|---|---|
| OAuth Discord / SSO | Lot ultérieur (ÉTAPE 8 Discord → lien Web) |
| Inscription / création compte web | Personnages créés via Discord ou seed dev |
| Multi-instance / Redis sessions | Instance unique SQLite |
| Permissions granulaires (PNJ, spectateur) | MJ vs joueur suffit v1 |
| Rate limiting, CSRF production | Infra post-MVP |
| Auth sur diagnostic `/debug/*` | Option : bind localhost only |
| Migration blob combat | Pas de `owner` sur combat — scope via participants |

---

## 5. Matrice d'autorisation cible (proposition)

### 5.1 Rôles

| Rôle session | Capacités |
|---|---|
| **`player`** | Lire état combat avec `viewer` = un de **ses** personnages dans la rencontre ; muter **uniquement** son combattant (attack/cast/move où `character.owner_id == session.user_id`) ; fiche/repos/sorts **de ses personnages** |
| **`gm`** | Tout ce que `player` peut faire **plus** : create/activate/close, advance-turn, heal, sync-combatant arbitraire, GET sans restriction visibilité (équivalent `viewer` absent), liste personnages globale |

### 5.2 Règles par route (normatif proposé)

| Route | `player` | `gm` | Règle détaillée |
|---|---|---|---|
| `GET /v1/combats/{id}` | ✅ si participant | ✅ | `viewer` obligatoire pour player ; doit être **son** `character_id` |
| `POST …/attack` | ✅ | ✅ | `attacker_id` → combattant dont le personnage est **sien** ; tour/budget inchangés (moteur) |
| `POST …/cast` | ✅ | ✅ | idem `caster_id` |
| `POST …/move` | ✅ | ✅ | idem `combatant_id` |
| `POST …/advance-turn` | ❌ | ✅ | Historiquement MJ |
| `POST …/close` | ❌ | ✅ | ADR-005 sync PV |
| `POST …/activate` | ❌ | ✅ | Lobby |
| `POST /v1/combats` | ❌ | ✅ | Création lobby |
| `POST …/heal` | ❌ | ✅ | Outil table / dev |
| `POST …/sync-combatant` | ✅ son combattant | ✅ | Mutation fiche — player owner autorisé (décision mainteneur) |
| `POST …/long-rest`, `short-rest`, `prepared-spells` | ✅ si owner | ✅ | Idem — parcours solo joueur |
| `GET /v1/characters` | ✅ ses persos | ✅ tous | Filtrage `owner_id` |
| `GET …/sheet`, repos, sorts | ✅ si owner | ✅ | |
| `WS …/ws` | ✅ | ✅ | Token requis ; `viewer` cohérent |

### 5.3 Cas d'erreur nouveaux (proposition contrat)

| Situation | HTTP | `code` proposé |
|---|---|---|
| Token absent | **401** | `AUTH_REQUIRED` |
| Token invalide / expiré | **401** | `AUTH_INVALID` |
| Identité valide, action interdite | **403** | `FORBIDDEN` |
| `viewer` ≠ personnage de la session | **403** | `VIEWER_NOT_ALLOWED` |
| Mutation `attacker_id` / `caster_id` / `combatant_id` ≠ personnage possédé | **403** | `COMBATANT_NOT_OWNED` |
| Player tente action MJ | **403** | `GM_REQUIRED` |

**Conserver** les codes existants (`VIEWER_NOT_IN_COMBAT`, etc.) — ordre de validation proposé :

1. Auth (401)
2. Rôle / ownership mutation (403)
3. Existence ressource (404)
4. Règles métier moteur (409/422)

---

## 6. Décisions d'architecture (actées mainteneur 2026-08-14)

### 6.1 Session opaque — retenue (JWT écarté)

Serveur unique, SQLite, aucun besoin de vérification hors-ligne. JWT apporterait révocation impossible et gestion d'expiration pour zéro bénéfice.

**Contrat implémentation** :

```
POST /v1/auth/dev-login  { "user_id": "123", "role": "player"|"gm" }
→ { "token": "…", "expires_at": "…" }

Header REST : Authorization: Bearer <token>
```

- Table SQLite `api_sessions` (ou équivalent) : `token` (index unique), `user_id`, `role`, `expires_at`
- Token aléatoire (`secrets.token_urlsafe` ou similaire) — **pas de JWT**, pas de nouvelle dépendance
- `interfaces/api/auth/session_store.py` + `deps.py` — `get_current_session()`, `require_gm()`
- `dev-login` gated `JDR_AUTH_DEV=1` ou équivalent documenté

### 6.2 WebSocket — token en query (retenu)

Pas de header custom côté navigateur. Cookie possible mais force same-origin et complique les deux onglets de test.

```
WS /v1/combats/{id}/ws?token=<token>&viewer=<character_id>
```

**Dette documentée** (CONTRAT_WS) : le token apparaît dans les logs serveur et l'historique proxy — acceptable banc local ; durcissement ultérieur (cookie, rotation) hors B1.

Code fermeture **`4401`** si token absent/invalide — symétrie avec `4404` (combat absent).

### 6.3 Options écartées

| Option | Motif |
|---|---|
| JWT stateless | Révocation difficile ; overkill instance unique |
| Query `?owner_id=` seul | Trivial à usurper |
| Cookie WS seul | Same-origin, deux onglets difficiles |

---

## 7. Mode compatibilité banc local (critique tests)

Les **1026** tests existants n'envoient **aucun** token. Stratégies :

| Stratégie | Description |
|---|---|
| **S1 — Auth off par défaut en test** | `create_app(auth_enabled=False)` — comportement actuel ; tests auth dans fichier dédié avec `auth_enabled=True` |
| **S2 — Auth on + fixture token** | Helper test `login_as(owner_id, role)` — plus réaliste, plus de churn |

**Recommandation** : **S1** pour minimiser le diff sur `test_api_v1_combat.py` (1825+ lignes) ; **S2** pour les ~15–25 tests neufs B1.

Variable d'environnement : **`JDR_API_AUTH=0|1`** — **défaut `0`** (préserve les 1026 tests existants et le confort banc local).

**Obligation compensatoire** (décision mainteneur) :

- Les **~10–15 tests neufs** (`test_api_v1_auth.py`) tournent **explicitement** avec `auth_enabled=True` / `JDR_API_AUTH=1` — jamais implicitement sur le défaut off.
- Le **parcours de validation manuel B1d** se fait **uniquement** avec `JDR_API_AUTH=1` — sinon le lot livre du code mort.

Entre **B1b** et **B1c**, ne pas tester le front avec auth on : l'API refuserait des actions que le client ne gère pas encore (voir §15).

---

## 8. Impact client web (lot B1c)

### 8.1 Parcours utilisateur cible

1. **Écran login dev** (ou modal) : saisie `user_id` Discord + rôle player/gm — appelle `POST /v1/auth/dev-login`
2. Token stocké `sessionStorage` (pas `localStorage` — limite XSS persistante)
3. Wrapper fetch central injecte `Authorization: Bearer …`
4. WS : append `token` à l'URL dans `combat_ws.ts`
5. **Lobby** : liste personnages filtrée serveur ; boutons create/activate **visibles uniquement si `role=gm`**
6. **Combat** : sélecteur « Vue joueur » conforme à la session (§8.2)

### 8.2 Contraintes UI obligatoires (B1c)

**Principe** : les actions interdites au rôle courant sont **désactivées ou masquées côté client**, pas seulement refusées côté serveur. Un 403 ne doit pas être le feedback normal d'un clic sur un bouton visible.

#### Sélecteur « Vue joueur »

Le `<select>` actuel (`CombatScreen.svelte`) propose tous les combattants — incompatible avec l'auth.

| Rôle session | Options du sélecteur |
|---|---|
| **`player`** | **Uniquement** le(s) PJ de l'utilisateur **présents dans la rencontre** (intersection `session.user_id` → `Character.owner_id` × combattants du combat). Pas de saisie manuelle libre du `character_id`. |
| **`gm`** | Option **« Vue MJ »** (`viewer` absent / vide) **plus** chaque combattant de la rencontre (vue filtrée par PJ si besoin de tester la vision joueur). |

Si l'URL hash contient un `viewer` non autorisé → corriger au chargement (reset vers le PJ autorisé ou vue MJ) + message explicite si 403.

#### Actions combat — visibilité par rôle

| Élément UI | `player` | `gm` |
|---|---|---|
| **Fin de tour** (`advance-turn`) | **Masqué ou disabled** | Actif |
| **Outils MJ (banc de test)** — heal, clôture, etc. | **Masqué** (panneau entier absent) | Actif |
| Attaque / sorts / move | Actif **si** tour du viewer et combattant possédé | Actif (règles moteur inchangées) |
| Boutons repos long / sync fiche | Actif **si** viewer = PJ possédé | Actif |

#### Mode dégradé — erreurs 401/403

Même avec UI préventive, des 403 restent possibles (race, session expirée, tour changé).

| Cas | Comportement client |
|---|---|
| **401** `AUTH_REQUIRED` / `AUTH_INVALID` | Redirect login ou modal ; message « Session expirée » |
| **403** `GM_REQUIRED`, `COMBATANT_NOT_OWNED`, `VIEWER_NOT_ALLOWED` | `ErrorAlert` avec message français du contrat ; **ne pas** laisser l'action « réussir silencieusement » |
| **403** sur action encore visible (bug UI) | Traiter comme bug B1c — le bouton aurait dû être disabled |

Le HUD actuel expose « Outils MJ » et « Fin de tour » toujours actifs — **B1c doit corriger cela** avant validation B1d.

### 8.3 Fichiers web estimés

| Fichier | Changement |
|---|---|
| `lib/api/auth.ts` | login, logout, getToken, fetchWithAuth |
| `lib/api/combat.ts` | utiliser fetchWithAuth |
| `lib/api/combat_ws.ts` | `?token=` |
| `lib/api/characters.ts` | fetchWithAuth |
| `lib/screens/LoginScreen.svelte` ou guard route | nouveau |
| `App.svelte` / router | redirect si pas de token et auth requise |

**Hors périmètre front B1** : beau écran OAuth Discord, gestion profil, « qui est en ligne ».

---

## 9. Tests attendus (preuve de done)

Fichier proposé : `tests/unit/test_api_v1_auth.py`

| # | Scénario | Attendu |
|---|---|---|
| T1 | `POST /attack` sans token (auth on) | 401 `AUTH_REQUIRED` |
| T2 | Token player, `attacker_id` d'un autre owner | 403 `COMBATANT_NOT_OWNED` |
| T3 | Token player, `viewer` = personnage d'un autre | 403 `VIEWER_NOT_ALLOWED` |
| T4 | Token player, mutation légitime son combattant | 200 |
| T5 | Token player, `POST …/advance-turn` | 403 `GM_REQUIRED` |
| T6 | Token gm, advance-turn / close / create | 200 |
| T7 | Token player, `GET /v1/characters` | liste filtrée owner |
| T8 | WS sans token (auth on) | fermeture 4401 ou refus handshake |
| T9 | WS token player + viewer cohérent | `connected` |
| T10 | Auth off (défaut tests existants) | comportement inchangé — régression 0 |
| T11 | Token player, `POST …/sync-combatant` sur **son** combattant | 200 |
| T12 | Token player, `POST …/long-rest` sur personnage possédé | 200 |

**Delta tests** : viser **+10 à +15** tests minimum vs baseline **1026**.

**Règle d'exécution** : T1–T12 (sauf T10) s'exécutent dans `TestApiV1Auth` avec **`create_app(..., auth_enabled=True)`** explicite — pas le défaut `JDR_API_AUTH=0` du reste de la suite.

Commandes preuve (AGENTS.md §7) :

```bash
venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -q
cd web && npm run check && npm run build
```

Pas de toucher `compendium/` → pas de `validate_compendium`.

---

## 10. Documentation à mettre à jour (accord mainteneur)

| Document | Changement |
|---|---|
| [`CONTRAT.md`](CONTRAT.md) | Nouvelle § auth : header, codes 401/403, matrice routes ; retirer « Banc local » du §6 pour les routes protégées |
| [`CONTRAT_WS.md`](CONTRAT_WS.md) | Param `token`, code 4401 |
| [`API_LOCAL.md`](../API_LOCAL.md) | Flow dev-login, variable `JDR_API_AUTH` |
| [`ROADMAP.md`](../../ROADMAP.md) | Cocher lot 6 ; jalon B1 auth |
| **ADR futur ?** | Si choix JWT vs session impacte déploiement — sinon brief suffit |

---

## 11. Arbitrages — tranchés (mainteneur 2026-08-14)

| # | Décision | Choix retenu |
|---|---|---|
| 1 | Session opaque vs JWT | **Session opaque** — table SQLite, token aléatoire, `user_id` + `role` + `expires_at` |
| 2 | `sync-combatant` / repos long | **Player sur son perso** — mutations fiche, pas actions MJ ; GM pour heal arbitrage combat |
| 3 | Token WS | **Query `?token=`** — dette logs documentée CONTRAT_WS |
| 4 | `JDR_API_AUTH` défaut | **`0` par défaut** — tests neufs + parcours manuel B1d **obligatoirement** en mode `1` |

---

## 12. Critères de done (checklist agent)

- [ ] Endpoint établissement session dev (`POST /v1/auth/dev-login` ou équivalent validé)
- [ ] Dependency FastAPI appliquée aux routes §5.2
- [ ] Vérification ownership `attacker_id` / `caster_id` / `combatant_id` vs `Character.owner_id`
- [ ] Vérification cohérence `viewer` query
- [ ] Rôle gm pour actions MJ
- [ ] WS protégé (token + viewer)
- [ ] `GET /v1/characters` filtré pour player
- [ ] Client web B1c : login + header + token WS + **UI préventive** (§8.2)
- [ ] Sélecteur viewer : options autorisées par session uniquement
- [ ] « Outils MJ » et « Fin de tour » absents/disabled en rôle player
- [ ] Tests T1–T12 verts ; auth-on **explicite** dans `test_api_v1_auth.py` ; **1026 + N** total
- [ ] CONTRAT.md + CONTRAT_WS.md amendés (si accord mainteneur)
- [ ] Parcours manuel **B1d avec `JDR_API_AUTH=1`** :
  - Onglet A (gm) : login → create/activate → combat ; Outils MJ visibles
  - Onglet B (player Alice) : move/attack Alice ; **pas** de bouton Fin de tour ni Outils MJ
  - Curl sans token → 401
  - Deux onglets WS sync OK avec tokens distincts

---

## 13. Parcours de validation manuelle (B1d uniquement)

> **Ne pas exécuter avant B1c livré.** Entre B1b et B1c, l'API avec `JDR_API_AUTH=1` casse le front non migré — garder le défaut off pour les tests intermédiaires.

**Obligatoire** : `JDR_API_AUTH=1` pour toute validation manuelle de clôture du lot.

```bash
# Terminal 1 — API auth activée (OBLIGATOIRE B1d)
set JDR_API_AUTH=1
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app

# Terminal 2 — front
cd web && npm run dev

# 1. Login GM
curl -X POST http://127.0.0.1:8000/v1/auth/dev-login \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"gm1\",\"role\":\"gm\"}"
# → noter token

# 2. Créer combat (gm)
curl -X POST http://127.0.0.1:8000/v1/combats \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"character_ids\":[\"alice_id\",\"bob_id\"]}"

# 3. Login player Alice
curl -X POST … -d "{\"user_id\":\"alice_owner\",\"role\":\"player\"}"

# 4. Attaque usurpée (doit échouer 403)
curl -X POST …/attack?viewer=alice_id \
  -H "Authorization: Bearer <alice_token>" \
  -d "{\"attacker_id\":\"<bob_combatant_id>\",…}"

# 5. Deux onglets navigateur — alice et bob sessions distinctes, WS sync OK

# 6. UI — onglet player : Fin de tour et Outils MJ absents ; sélecteur viewer = Alice seulement
# 7. UI — onglet gm : Fin de tour actif ; sélecteur inclut « Vue MJ »
```

Personnages test : s'assurer que `owner_id` en SQLite correspond aux `user_id` de login (`tests` utilisent `owner_id="1"`, `"111"`, etc.).

Checklist UI B1d :

- [ ] Player ne voit pas « Outils MJ (banc de test) »
- [ ] Player ne voit pas « Fin de tour » actif
- [ ] Sélecteur viewer ne liste que les PJ autorisés
- [ ] GM voit les contrôles table et la vue MJ

---

## 14. Interdictions rappel (AGENTS.md)

1. **Pas de nouvelle dépendance** sans accord (`PyJWT`, `python-jose`, etc.) — session opaque stdlib possible.
2. **Pas de règles D&D** dans `interfaces/api/auth/` — seulement identity/ownership.
3. **`jdr_engine/` n'importe pas** FastAPI — la auth reste interface.
4. **Ne pas étendre Discord** (D2) — pas de commande `/login` bot dans ce lot.
5. **Ne pas créer `interfaces/web/`** — client reste `web/`.
6. **Ne pas commiter** sans demande explicite.

---

## 15. Estimation et découpage (ordre strict)

| Phase | Contenu | Auth effective | Validation manuelle |
|---|---|---|---|
| **B1a** | Session store SQLite + dev-login + deps + tests auth de base | Tests auth **on** explicites ; reste suite **off** | ❌ |
| **B1b** | Garde-fous combat + characters + amendement CONTRAT | Idem — **`JDR_API_AUTH=0` défaut effectif** | ❌ **Ne pas** tester le front avec auth on |
| **B1c** | WS token + client web (login, fetch, **UI §8.2**) | Front compatible auth on | Smoke test possible |
| **B1d** | Validation multi-onglets + doc API_LOCAL | **`JDR_API_AUTH=1` obligatoire** | ✅ Clôture lot |

**Risque documenté** : à la fin de B1b, l'API refuse des requêtes que le client web ne gère pas encore. Ce n'est pas un bug si l'agent **ne lance pas** le parcours manuel complet avant B1c.

**Ordre** : B1a → B1b → B1c → B1d — **pas de validation manuelle B1d avant B1c**.

---

## 16. Références

| Document | Lien |
|---|---|
| Contrat REST | [`CONTRAT.md`](CONTRAT.md) §2.8, §2.9, §6 |
| Contrat WS | [`CONTRAT_WS.md`](CONTRAT_WS.md) |
| ADR stack web | [`ADR-007`](../adr/ADR-007-stack-client-web.md) |
| Brief WS 6c | [`BRIEF_LOT6C_WEBSOCKET.md`](../web/BRIEF_LOT6C_WEBSOCKET.md) |
| Brief map 6a | [`BRIEF_LOT6_MAP_TACTIQUE.md`](../web/BRIEF_LOT6_MAP_TACTIQUE.md) |
| Permissions MJ Discord (référence, non branchée) | `interfaces/discord/permissions/mj.py` |
| ROADMAP | [`ROADMAP.md`](../../ROADMAP.md) — ÉTAPE 6, piste client Web lot 6 |

---

*Document de cadrage **accepté** — arbitrages §11 tranchés 2026-08-14. Amendement CONTRAT/CONTRAT_WS lors de l'implémentation B1b.*
