# AGENTS.md — instructions pour les agents IA

Projet : **JDR Engine** — moteur de jeu de rôle D&D 5e (SRD 5.1 **2014 uniquement**).
Langue de travail : **français** (code, commentaires, docstrings, commits, documentation).

Tu démarres sans mémoire des sessions précédentes. Ce fichier et les documents canoniques sont ta seule source de contexte. **Ne déduis rien d'un historique de chat.**

---

## 1. Documents canoniques

| Document | Rôle | À lire |
|---|---|---|
| `AGENTS.md` | Ce fichier — règles de travail | Toujours |
| `VISION.md` | Stratégie : le « pourquoi », décisions arrêtées D1–D8 | Toujours |
| `ROADMAP.md` | Opérationnel : quoi livrer, dans quel ordre, statuts | Toujours |
| `docs/adr/` | Décisions techniques actées (ADR-001/002/003) | Si tu touches l'architecture |
| `docs/ARCHITECTURE.md` | Architecture **actuelle** — état réel du dépôt | Si tu touches l'architecture |
| `docs/ARCHITECTURE_TARGET.md` | Architecture **cible** — non implémentée ou partielle | Si tu touches l'architecture |
| `compendium/dnd5e/entries/spells/` (YAML), `docs/SPELL_SCHEMA.md`, `docs/SPELLS_B2_MIGRATION_NOTES.md` | Sorts : source de vérité compendium, schéma v2.0, dette migration | Si tu touches les sorts |
| `docs/COMBAT_ROLL_PREREQUISITES.md` | Prérequis flags `/roll` — **documenté, non implémenté** | Si tu touches les jets |
| `docs/MIGRATION.md` | Journal historique — **s'arrête à la Phase 4.8, périmé** | Contexte seulement |

## 2. Ordre de priorité en cas de contradiction

1. **Le code réel** — l'architecture existante prime sur toute supposition et sur toute documentation.
2. **`VISION.md`** — pour toute question stratégique (cible, périmètre, décisions D1–D8).
3. **`ROADMAP.md`** — pour toute question opérationnelle (quel lot, quel ordre, quel statut).
4. **ADR** — pour les décisions techniques.
5. **`docs/ARCHITECTURE_TARGET.md`** — cible souhaitée. **`docs/ARCHITECTURE.md`** — état réel. Là où la cible contredit le code, **le code gagne**.

Une contradiction se **signale dans ton rapport**, elle ne se corrige pas en silence.

## 3. Frontières architecturales (vérifiées dans le code)

- `jdr_engine/` **n'importe jamais** `discord`, `interfaces` ni `bot` (zéro occurrence aujourd'hui — cet invariant doit être préservé).
- Sens des dépendances : `bot/` → `interfaces/` → `jdr_engine/application` → `rules`/`domain`.
- **`bot/` est vivant, pas du code mort.** `main.py` charge les cogs depuis `bot.cogs.*` ; le bot ne démarre pas sans eux. `ARCHITECTURE.md` §8 documente l'état actuel ; `ARCHITECTURE_TARGET.md` prévoit une migration vers `interfaces/discord` en Phase 10. **Ne pas supprimer.**
- `bot/cogs/*` sont des points d'entrée fins qui délèguent à `interfaces/discord/handlers/*`.
- **Aucune règle D&D dans `bot/` ou `interfaces/`.** Les règles vivent dans `jdr_engine/rules/`, les données dans `compendium/`.
- Placeholders réels (1–2 lignes, aucun code) : `jdr_engine/core/events/`, `jdr_engine/core/i18n/`, `jdr_engine/core/config/`, `jdr_engine/core/plugins/`, `jdr_engine/game/`, `plugins/`, `compendium/_schemas/`.
- `jdr_engine/core/assets/` **n'est pas** un placeholder (`resolver.py` est réel et testé).
- `interfaces/api/` **existe** (lot DTO/API, accord mainteneur 2026-07-30) : API FastAPI de banc de test — fiche, sort, repos. Même règle que le reste d'`interfaces/` : aucune règle D&D, couche fine au-dessus du moteur et des DTO (`jdr_engine/application/dto/output_serializers.py`). Lancement local : `docs/API_LOCAL.md`.
- `interfaces/web/` **n'existe pas** — ne pas le créer avant l'ÉTAPE 6 (voir `ROADMAP.md`).
- Les JSON Schema réels sont dans `compendium/schemas/` (et non `_schemas/`, qui est vide).
- Les pools de sorts sont **dérivés du YAML** (`spell_pool_builder.py`) — ne jamais coder une liste de sorts en dur.

## 4. Commandes

**Validées** (référence historique commit `bf24622` : 645 tests ; **référence courante** : section auto-sync de `ROADMAP.md`) :

```bash
# Tests — voir ROADMAP.md (section auto-sync) pour le nombre courant
python -m unittest discover -s tests -p "test_*.py" -q

# Validation du Compendium — référence : [OK] Compendium valide
python tools/validate_compendium.py dnd5e
```

> `python` désigne **l'interpréteur du venv** : `venv\Scripts\python.exe` sous Windows, `venv/bin/python` sous Unix. Active le venv au préalable, ou préfixe la commande par ce chemin.

La CI (`.github/workflows/ci.yml`) exécute `python -m unittest discover -s tests -v` puis `python tools/validate_compendium.py dnd5e`.

**Indisponibles — ne pas invoquer, ne pas installer :**

| Besoin | État vérifié |
|---|---|
| Lint | **Aucun outil, aucune configuration.** `ruff`, `flake8`, `black` absents du venv ; rien dans `pyproject.toml` ; aucune étape lint en CI. |
| Type-check | **Aucun.** `mypy` absent. |
| Build | **Impossible.** `setuptools` et `build` absents. |
| `pytest` | Déclaré dans `pyproject.toml` (extra `dev` + `[tool.pytest.ini_options]`) mais **non installé**. Utiliser `unittest`. |

Python de référence : **3.12** (testé en CI). `pyproject.toml` exige `>=3.11` (minimum supporté). Venv local mesuré : **3.14.6** — toléré en dev, non couvert par la CI.

Framework de tests : **`unittest`**, jamais `pytest`. Un fichier de test par lot, nommé d'après le lot.

## 5. Modification de la documentation

- **Interdit sans accord explicite du mainteneur** : `VISION.md`, `ROADMAP.md` (cases à cocher et jalons), `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_TARGET.md`, `docs/adr/**`.
- **Exception** : la section `<!-- ROADMAP-AUTO:START -->` … `<!-- ROADMAP-AUTO:END -->` de `ROADMAP.md` est mise à jour automatiquement par `tools/update_roadmap_metrics.py` (hook Git pre-commit).
- Ces fichiers sont pilotés par le mainteneur et l'agent d'architecture, pas par les agents d'implémentation — sauf métriques auto-sync ci-dessus.
- Toute décision structurelle **doit produire un ADR avant implémentation** (`docs/adr/README.md`).
- Ne jamais dupliquer VISION dans ROADMAP ou inversement : on **référence** (`VISION.md` §5), on ne recopie pas.
- Un chiffre écrit dans un document (nombre de tests, de sorts) doit être **mesuré**, jamais estimé.

## 6. Interdictions structurantes

Issues des décisions arrêtées de `VISION.md` §10 :

1. **Aucune nouvelle fonctionnalité joueur pour Discord** (D2). Les commandes existantes sont maintenues, pas étendues.
2. **Le Combat Engine est une API moteur pure** (D3) : fonctions déterministes + événements. **Aucun rendu Discord ni Web**, aucun embed, bouton ou composant.
3. **Le moteur ne connaît aucune interface** (D4) : publication d'événements, jamais d'appel direct à une UI.
4. **Ne pas démarrer le Combat Engine (ÉTAPE 4) sans RFC approuvée.**
5. **Ne pas créer `interfaces/web/`** avant l'ÉTAPE 6. (`interfaces/api/` existe depuis le lot DTO/API, sur accord explicite du mainteneur — 2026-07-30.)
6. **Ne pas ajouter de dépendance ni d'outil** sans accord explicite. (Accordées à ce jour : `fastapi`, `uvicorn` — extra `api` de `pyproject.toml` — et `httpx` — extra `dev` ; toutes trois aussi dans `requirements.txt` pour la CI.)
7. **Ne pas supprimer `bot/`** ni le mode `USE_ENGINE_V2`.
8. Règles issues du **SRD 5.1 2014 uniquement** — le portage 2024 est l'ÉTAPE 5, en toute fin.
9. **Principe d'intégrité des stats** (`ROADMAP.md`) : PV, emplacements et caractéristiques sont **dérivés**, jamais saisis librement.

## 7. Preuve exigée avant d'annoncer une tâche terminée

Ne déclare **jamais** un lot terminé sans coller dans ton rapport :

1. La sortie brute de la commande de tests — les lignes `Ran N tests` **et** `OK`.
2. La sortie de `tools/validate_compendium.py dnd5e` si tu as touché au `compendium/`.
3. Le **delta du nombre de tests** par rapport à la référence courante dans `ROADMAP.md` (section auto-sync). Baseline historique : 645 au commit `bf24622`. Un lot fonctionnel moteur qui n'augmente pas ce nombre n'a pas livré de tests.

Règles de véracité :

- N'affirme jamais qu'un élément existe, fonctionne ou est terminé sans l'avoir vérifié avec un outil.
- Si tu n'as pas pu vérifier quelque chose, écris explicitement **« non vérifié »**.
- Ne présente pas un fichier créé comme une fonctionnalité fonctionnelle.
- Distingue dans tes rapports : **fait observé**, **incohérence**, **recommandation**, **décision nécessitant l'accord du mainteneur**.

## 8. Git et périmètre

- Branche d'intégration : **`main`**. Une branche par lot : `feat/c1-combat-state`, `feat/b3-sorts-niv5`.
- Commits **Conventional Commits en français**, scope entre parenthèses — convention observée dans l'historique :
  `feat(spells): …`, `fix(level-up): …`, `docs(roadmap): …`, `chore(tooling): …`
- **Ne jamais commiter** `.env`, `config.json`, `data/bot.db`, `venv/`.
- **Ne pas commiter ni pousser sans demande explicite** du mainteneur.
- **Périmètre strict** : ne modifie que les fichiers nécessaires au lot demandé. Si tu découvres un problème hors périmètre, **signale-le, ne le corrige pas**.
- Si le lot demandé s'avère plus large que prévu, **arrête-toi et remonte** au lieu d'élargir seul.

## 9. Protocole de travail autonome

Objectif : avancer lot par lot avec un minimum d'interruptions ; l'utilisateur tranche uniquement les décisions qu'il est seul à pouvoir prendre.

### Source de vérité et lecture

| Priorité | Document | Usage |
|---|---|---|
| 1 | **Code réel** | État effectif |
| 2 | `VISION.md` | Stratégie, décisions D1–D8 |
| 3 | **`ROADMAP.md`** | Lots, ordre, statuts — **source opérationnelle** |
| 4 | Brief de lot (ex. `docs/web/BRIEF_*.md`) | Périmètre du lot courant uniquement |
| 5 | ADR / architecture | Décisions techniques |

**Au démarrage d'un lot** (pas à chaque micro-action) : relire `AGENTS.md`, la section pertinente de `ROADMAP.md`, le brief du lot s'il existe, puis le code concerné.

**En cas de conflit** : le code prime sur la doc ; `ROADMAP.md` prime sur un brief, sauf instruction explicite du mainteneur pour ce lot. Si `ROADMAP.md` semble en retard : vérifier dans le code, continuer le lot demandé, **signaler l'écart** (ne pas corriger les cases à cocher sans accord).

### Règle de tri (autonomie vs arrêt)

Avant une action : une erreur se voit-elle **immédiatement à l'écran** (front, CSS, layout, textes, placeholders, libellés) ?

- **Oui** → décider seul, implémenter, continuer.
- **Non** (SRD, calculs, contrats API, persistance, migrations, schémas) → appliquer les critères d'arrêt ci-dessous.

### Critères d'arrêt (un point à la fois)

Tu t'arrêtes **uniquement** si :

1. Deux implémentations possibles ont des conséquences **durables divergentes** et la roadmap ne tranche pas.
2. Une modification casse un **contrat d'API** exposé ou impose une **migration de données**.
3. Une règle **SRD** est ambiguë ou absente du compendium, et l'interpréter engage le moteur.
4. Le lot **contredit** un choix architectural antérieur.
5. Un test existant échoue pour une **divergence de conception**, pas un simple bug.

Sinon : trancher seul, documenter le choix dans le commit. Ne pas s'arrêter pour validation esthétique ni pour un point perfectible.

### Format d'un point d'arbitrage

```
Contexte : (3 lignes max)
Question : (une seule, fermée)
Options : (2 ou 3, conséquence durable chacune)
Recommandation : (2 lignes)
Ce qui est bloqué :
```

Bloc autonome — transmissible à un modèle externe sans accès au dépôt. **Un arbitrage par message**, jamais regroupé.

### Placeholders

Toute fonctionnalité non implémentée reste **visible** avec un marqueur explicite (« À VENIR », lot concerné). Ne jamais masquer un manque ni simuler une donnée.

### Hooks Git (métriques roadmap)

Après clone ou une fois par machine : `powershell tools/setup_git_hooks.ps1` (active `.githooks/pre-commit`). Chaque commit inclut la sync auto des métriques mesurables de `ROADMAP.md`.
