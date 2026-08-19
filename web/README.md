# Client web — interface de jeu (banc de test)

SPA **Svelte + Vite + TypeScript** — consomme l'API FastAPI (`docs/api/CONTRAT.md`).

## Prérequis

- Node.js 18+ et npm
- Python venv avec extra `api` (uvicorn)
- Personnages en base SQLite (Discord ou seed) — `venv\Scripts\python.exe tools\list_characters.py`

## Démarrage rapide (Windows)

| Lanceur | Usage |
|---|---|
| **`launcher_web.bat`** | API `:8000` + client `:5173` — **sans auth** (banc ouvert) |
| **`launcher_web_auth.bat`** | API avec `JDR_API_AUTH=1` + client → **`#/login`** |

Le client appelle l'API via le **proxy Vite** (`/v1` → `127.0.0.1:8000`). Sans uvicorn : **HTTP 502** au lobby.

**URL à utiliser** : `http://localhost:5173` — **pas** `http://127.0.0.1:8000/` (banc statique Python legacy, hors parcours jeu).

### Manuel (deux terminaux)

**Terminal 1 — racine** :

```powershell
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

**Terminal 2 — `web/`** :

```powershell
cd web
npm install
npm run dev
```

Auth activée :

```powershell
$env:JDR_API_AUTH="1"
$env:JDR_AUTH_DEV="1"
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

## Navigation (svelte-spa-router, hash)

| Route | Écran |
|---|---|
| `#/` | Landing page |
| `#/login` | Connexion dev (auth ON) |
| `#/lobby` | Création / activation rencontre |
| `#/combat/{id}` | HUD combat + map tactique |
| `#/combat/{id}?viewer={character_id}` | Vue joueur filtrée |
| `#/character/{id}` | Fiche personnage |

Avec **`JDR_API_AUTH=1`**, les routes protégées redirigent vers `#/login` si pas de session.

## Parcours combat (sans curl)

1. **Lobby** — personnages + **Créer** → `POST /v1/combats`
2. **Activer et jouer** → grille + positions, `#/combat/{id}`
3. **Combat** — map (clic move), attaque, sorts, fin de tour, journal, WebSocket sync multi-onglets
4. **Clôturer** — libère les personnages pour retester

Auth ON : MJ = create/activate/close/advance ; joueur = mutations sur **ses** combattants uniquement.

## Vérification

```bash
npm run check
npm run build
```

Suite Python (racine) : `python -m unittest discover -s tests -p "test_*.py" -q`

## Types / contrats

| Fichier | Contrat Python |
|---|---|
| `src/lib/types/combat.ts` | `combat_state_to_dict` |
| `src/lib/types/attack.ts` | `weapon_attack_result_to_dict` |
| `src/lib/types/sheet.ts` | `character_sheet_to_dict` |

## Prochain jalon front

**Jalon S — éditeur de scènes** : [`docs/scenes/BRIEF_JALON_S.md`](../docs/scenes/BRIEF_JALON_S.md)
