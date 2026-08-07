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

## Endpoints v1

| Méthode | Route | Corps | Effet |
|---|---|---|---|
| GET | `/v1/characters/{id}/sheet` | — | Fiche calculée (fusionnée si combat ouvert) |
| POST | `/v1/characters/{id}/cast` | `{"spell_id": "hex"}` | Lance un sort |
| POST | `/v1/characters/{id}/short-rest` | `{"dice_to_spend": 2}` | Repos court |
| POST | `/v1/characters/{id}/long-rest` | — | Repos long |
| POST | `/v1/combats` | `{"character_ids": [...]}` | Crée un lobby |
| GET | `/v1/combats/{id}` | — | État rencontre |
| POST | `/v1/combats/{id}/activate` | — | Active le combat |
| POST | `/v1/combats/{id}/attack-roll` | `attacker_id`, `target_id`, portée | Jet d'attaque |
| POST | `/v1/combats/{id}/close` | — | Clôture + sync PV |

Exemple :

```bash
curl http://127.0.0.1:8000/v1/characters/abc123/sheet
curl -X POST http://127.0.0.1:8000/v1/characters/abc123/cast -H "Content-Type: application/json" -d "{\"spell_id\": \"hex\"}"
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
| 404 | `CHARACTER_NOT_FOUND`, `COMBAT_NOT_FOUND`, `COMBATANT_NOT_FOUND` |
| 409 | `SPELL_CAST_REJECTED`, `REST_REJECTED`, `COMBAT_STATUS_INVALID`, … |
| 422 | `VALIDATION_ERROR` |
| 500 | `INTERNAL_ERROR` |

Catalogue complet : `docs/api/CONTRAT.md` §3.3.

## Limites connues

- Pas de contrôle de concurrence (last-writer-wins).
- Pas d'authentification — usage local.
- Dégâts post-attaque, sorts/conditions combat, avancement de tour : hors lot 1.
- Dette : `COMBAT_STATE_UNSUPPORTED` — voir `docs/api/CONTRAT.md` §10.4.
