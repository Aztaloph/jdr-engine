# docs/API_LOCAL.md
# API HTTP locale — banc de test (interface de jeu v1)

Petite API FastAPI (`interfaces/api/`) — **seule interface de jeu** du projet.
Contrat : `docs/api/CONTRAT.md`.

## Installation

```bash
venv\Scripts\python.exe -m pip install -r requirements.txt
# ou : pip install fastapi uvicorn
```

## Lancement

```bash
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

Écoute : `http://127.0.0.1:8000` · Swagger : `http://127.0.0.1:8000/docs`

## Client Web (interface de jeu)

Le **client principal** est le SPA Svelte dans `web/` :

- **Sans auth** : `launcher_web.bat` → `http://localhost:5173`
- **Auth B1** : `launcher_web_auth.bat` → `http://localhost:5173/#/login`

`GET http://127.0.0.1:8000/` sert un **banc statique legacy** (`interfaces/api/static/`) — utile pour debug curl, **pas** le parcours lobby/combat/map.

## Endpoints v1

| Méthode | Route | Corps | Effet |
|---|---|---|---|
| GET | `/v1/characters/{id}/sheet` | — | Fiche calculée (fusionnée si combat ouvert). Champs clés : `ability_labels`, `proficient_skills[]`, `saving_throws[]`, `proficiency_bonus`. **`proficient_skill_ids` retiré** — remplacé par `proficient_skills` `{ id, label }`. |
| POST | `/v1/characters/{id}/cast` | `{"spell_id": "hex"}` | Lance un sort |
| POST | `/v1/characters/{id}/short-rest` | `{"dice_to_spend": 2}` | Repos court |
| POST | `/v1/characters/{id}/long-rest` | — | Repos long |
| POST | `/v1/combats` | `{"character_ids": [...]}` | Crée un lobby |
| GET | `/v1/combats/{id}` | `viewer` (query, optionnel) | État rencontre |
| POST | `/v1/combats/{id}/activate` | — | Active le combat |
| POST | `/v1/combats/{id}/advance-turn` | `viewer` (query, optionnel) | Avancement de tour |
| POST | `/v1/combats/{id}/attack` | `attacker_id`, `target_id`, `weapon_id` ; `viewer` (query, optionnel) | Attaque d'arme (jet + dégâts si toucher) |
| POST | `/v1/combats/{id}/close` | — | Clôture + sync PV |

Exemple :

```bash
curl http://127.0.0.1:8000/v1/characters/abc123/sheet
curl -X POST http://127.0.0.1:8000/v1/characters/abc123/cast -H "Content-Type: application/json" -d "{\"spell_id\": \"hex\"}"
```

Extrait réponse fiche (lot maîtrises) :

```json
{
  "ability_labels": { "str": "Force", "dex": "Dextérité" },
  "proficient_skills": [{ "id": "medicine", "label": "Médecine" }],
  "saving_throws": [{ "ability_id": "wis", "modifier": 5, "proficient": true }],
  "proficiency_bonus": 2
}
```

## Format d'erreur

Toutes les erreurs 4xx/5xx métier renvoient :

```json
{
  "error": {
    "code": "CHARACTER_NOT_FOUND",
    "message": "Personnage introuvable.",
    "details": {}
  }
}
```

| HTTP | Exemples `code` |
|---|---|
| 404 | `CHARACTER_NOT_FOUND`, `COMBAT_NOT_FOUND`, `COMBATANT_NOT_FOUND`, `VIEWER_NOT_IN_COMBAT` |
| 409 | `SPELL_CAST_REJECTED`, `REST_REJECTED`, `COMBAT_STATUS_INVALID`, … |
| 422 | `VALIDATION_ERROR` |
| 500 | `INTERNAL_ERROR` |

Catalogue complet : `docs/api/CONTRAT.md` §3.3.

## Authentification (lot B1 — optionnelle)

Par défaut l'auth est **désactivée** (`JDR_API_AUTH` absent ou `0`) — comportement banc local inchangé.

Pour tester le multi-poste :

```powershell
set JDR_API_AUTH=1
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

Connexion dev (client `#/login` ou API) :

```bash
curl -X POST http://127.0.0.1:8000/v1/auth/dev-login ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"owner_alice\",\"role\":\"player\"}"
```

Réponse : `{ "token", "expires_at", "user_id", "role" }`. En-tête suivant : `Authorization: Bearer <token>`.

WebSocket : `WS /v1/combats/{id}/ws?token=<token>&viewer=<character_id>` — fermeture **`4401`** si token absent/invalide.

Brief complet : `docs/api/BRIEF_LOT_B1_AUTH.md`.

## Limites connues

- Pas de contrôle de concurrence (last-writer-wins).
- Auth désactivée par défaut — activer `JDR_API_AUTH=1` pour le parcours multi-poste.
- Dégâts post-attaque, sorts/conditions combat, avancement de tour : hors lot 1.
- Dette : `COMBAT_STATE_UNSUPPORTED` — voir `docs/api/CONTRAT.md` §10.4.
