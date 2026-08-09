# Client web — banc de test combat (lot 1)

SPA **Svelte + Vite + TypeScript** pour valider empiriquement le contrat
`combat_state_to_dict` exposé par l'API.

## Prérequis

1. **API FastAPI** en marche sur `http://127.0.0.1:8000` :

   ```bash
   venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
   ```

2. **Node.js** 18+ et npm.

3. Un **combat_id** existant (créer/activer via API ou tests E2E — pas de découverte auto dans l'UI).

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

## Usage

1. Saisir le **combat_id** (ex. `1`).
2. Optionnel : **viewer** = `character_id` joueur ; laisser vide pour la vue MJ.
3. **Recharger** → `GET /v1/combats/{id}`.
4. **Tour suivant** → `POST /v1/combats/{id}/advance-turn` (avec `viewer` en query si renseigné).

« Tour suivant » est désactivé si `status !== "active"` (ex. combat terminé).

## Types

Contrat TypeScript : `src/lib/types/combat.ts` — miroir de la sérialisation Python.

## Build production

```bash
npm run build
npm run preview
```

Le preview sert les fichiers statiques ; le proxy de dev ne s'applique plus — configurer un reverse proxy ou CORS pour une API distante.
