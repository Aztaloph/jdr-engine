# Format scene.json v1 — référence normative

Source de vérité détaillée : [`BRIEF_JALON_S.md`](BRIEF_JALON_S.md) §5.

## Validation

```powershell
venv\Scripts\python.exe tools\validate_scenes.py
```

## API (lot Sb)

| Méthode | Route | Auth |
|---|---|---|
| `GET` | `/v1/scenes` | Session |
| `POST` | `/v1/scenes` | GM |
| `GET` | `/v1/scenes/{id}` | Session |
| `PUT` | `/v1/scenes/{id}` | GM |
| `DELETE` | `/v1/scenes/{id}` | GM |
| `GET` | `/v1/scenes/{id}/export` | Session — blob autonome |

Fixtures de référence : `data/scenes/fixtures/*.json`

## Résumé v1

| Champ | Règle |
|---|---|
| `schema_version` | `1` obligatoire |
| `grid.width/height` | 1…50 cases |
| `grid.enabled` | `false` masque le quadrillage seulement |
| `objects[].kind` | Enum fermée (9 valeurs) |
| `objects[].quarter_turns` | 0…3 ; impair → emprise `h×w` |
| `lights[]` | Stocké, ignoré au rendu v1 |

## Module Python

- `interfaces/scenes/validate.py` — `validate_scene_document`, `parse_scene_document`
- `interfaces/scenes/footprint.py` — `effective_footprint`
