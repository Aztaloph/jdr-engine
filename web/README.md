# Client web — banc de test combat

SPA **Svelte + Vite + TypeScript** pour valider empiriquement les contrats API
combat (`combat_state_to_dict`, `weapon_attack_result_to_dict`).

## Prérequis

1. **API FastAPI** en marche sur `http://127.0.0.1:8000` :

   ```bash
   venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
   ```

2. **Node.js** 18+ et npm.

3. Deux **character_id** existants en base (ex. créés via tests E2E ou Discord).

## Installation

```bash
cd web
npm install
```

## Lancement

```bash
npm run dev
```

Ouvrir l'URL affichée (souvent `http://localhost:5173`).

Le proxy Vite redirige `/v1/*` vers `http://127.0.0.1:8000` — pas de configuration CORS Python requise.

## Navigation (hash routing)

| Route | Écran |
|---|---|
| `#/` ou `#/lobby` | Création / activation d'une rencontre |
| `#/combat/{id}` | Combat existant (vue MJ par défaut) |
| `#/combat/{id}?viewer={character_id}` | Combat filtré joueur |

Le **viewer** est porté dans le hash pour des URLs partageables. Modifier le champ viewer sur l'écran combat met à jour l'URL.

## Parcours complet (sans curl)

1. **Lobby** — saisir deux `character_id`, **Créer le combat** → `POST /v1/combats`.
2. **Activer et jouer** → `POST /v1/combats/{id}/activate`, navigation vers `#/combat/{id}`.
3. **Combat** — recharger si besoin, **Tour suivant**, **Attaquer** (`POST /v1/combats/{id}/attack`).

« Tour suivant » et « Attaquer » sont désactivés si `status !== "active"`.

## Types

| Fichier | Contrat Python |
|---|---|
| `src/lib/types/combat.ts` | `combat_state_to_dict` |
| `src/lib/types/attack.ts` | `weapon_attack_result_to_dict` |

## Vérification

```bash
npm run build
npm run check
```
