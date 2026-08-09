# Client web — banc de test combat

SPA **Svelte + Vite + TypeScript** pour valider empiriquement les contrats API
combat (`combat_state_to_dict`, `weapon_attack_result_to_dict`).

## Prérequis

1. **API FastAPI** en marche sur `http://127.0.0.1:8000` :

   ```bash
   venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
   ```

2. **Node.js** 18+ et npm.

3. Un **combat_id** existant en statut `active` (créer/activer via API ou tests E2E).

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
3. **Recharger** → `GET /v1/combats/{id}?viewer=`.
4. **Tour suivant** → `POST /v1/combats/{id}/advance-turn`.
5. **Attaquer** (combat `active`) → `POST /v1/combats/{id}/attack` — sélection `combatant_id` attaquant/cible, arme fermée.

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
