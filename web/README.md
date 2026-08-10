# Client web — banc de test combat

SPA **Svelte + Vite + TypeScript** pour valider empiriquement les contrats API
combat (`combat_state_to_dict`, `weapon_attack_result_to_dict`).

## Prérequis

Node.js 18+ et npm. Deux **character_id** existants en base (ex. tests E2E ou Discord).

## Démarrage — deux terminaux obligatoires

Le client Svelte (`5173`) appelle l'API via le proxy Vite (`/v1` → `127.0.0.1:8000`). **Sans uvicorn, le lobby renvoie HTTP 502** (connexion refusée — ce n'est pas une erreur métier).

**Raccourci Windows** — double-clic sur `launcher_web.bat` à la racine du dépôt (ouvre deux fenêtres cmd : API `:8000` + client `:5173`).

**Terminal 1 — racine du dépôt** (API sur le port **8000**) :

```powershell
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

Attendre `Uvicorn running on http://127.0.0.1:8000` — laisser ce terminal ouvert.

**Terminal 2 — dossier `web/`** (client sur le port **5173**) :

```powershell
cd web
npm install
npm run dev
```

Ouvrir **http://localhost:5173** (pas `:8000` — celui-ci sert le banc statique Python, distinct).

**Lister les personnages en terminal** (si la liste du lobby est vide) :

```powershell
venv\Scripts\python.exe tools\list_characters.py
```

Après ajout de la route `GET /v1/characters`, **redémarrer uvicorn** pour que le lobby charge la liste déroulante.

## Installation

Une seule fois : `cd web && npm install`.

## Navigation (svelte-spa-router, hash)

Routage via [svelte-spa-router](https://github.com/ItalyPaleAle/svelte-spa-router) (hash natif). Helpers : `src/lib/navigation.ts`.

| Route | Écran |
|---|---|
| `#/` ou `#/lobby` | Création / activation d'une rencontre |
| `#/combat/{id}` | Combat existant (vue MJ par défaut) |
| `#/combat/{id}?viewer={character_id}` | Combat filtré joueur |
| `#/character/{id}` | Fiche personnage (minimal) |

Le **viewer** est porté dans le hash pour des URLs partageables. Modifier le champ viewer sur l'écran combat met à jour l'URL.

## Fiche personnage

Depuis le lobby (**Consulter une fiche**) ou l'URL `#/character/{character_id}`. Pendant un combat, lien **fiche** depuis l'initiative si `character_id` est exposé.

## Parcours complet (sans curl)

1. **Lobby** — saisir deux `character_id`, **Créer le combat** → `POST /v1/combats`.
2. **Activer et jouer** → `POST /v1/combats/{id}/activate`, navigation vers `#/combat/{id}`.
3. **Combat** — recharger si besoin, **Tour suivant**, **Attaquer**, sorts (viewer requis).
4. **Clôturer** — lobby ou écran combat (`POST …/close`) libère les personnages pour retester.

« Tour suivant » et « Attaquer » sont désactivés si `status !== "active"`.

## Types

| Fichier | Contrat Python |
|---|---|
| `src/lib/types/combat.ts` | `combat_state_to_dict` |
| `src/lib/types/attack.ts` | `weapon_attack_result_to_dict` |
| `src/lib/types/sheet.ts` | `character_sheet_to_dict` (+ overlay combat) |

## Vérification

```bash
npm run build
npm run check
```
