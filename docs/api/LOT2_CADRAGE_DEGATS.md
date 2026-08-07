# Cadrage lot 2 API — dégâts post-attaque d'arme

| Attribut | Valeur |
|---|---|
| **Statut** | **Accepté** — option A retenue (mainteneur 2026-08-07) |
| **Date** | 2026-08-07 |
| **Prérequis** | Lot 1 API livré (`7878e9a`, 886 tests) |
| **Hors périmètre de ce document** | Implémentation, découpage commits, OpenAPI |

**Question à trancher avant toute ligne de code** : l'API **fusionne-t-elle** jet + dégâts en une action, ou **expose-t-elle** deux endpoints distincts ?

**Décision (2026-08-07)** : **Option A — fusionné.** Route cible `POST /v1/combats/{id}/attack` ; breaking change `attack-roll` retiré. Voir `docs/api/CONTRAT.md` §2.7, §5.4, décisions #14–17.

---

## 1. État moteur (référence factuelle)

Le moteur **sépare déjà** les deux étapes (ADR-004 §9) :

| Étape | Méthode | Budget `action` | PV overlay | Événement | Persisté dans blob |
|---|---|:---:|:---:|---|---|
| Jet vs CA | `resolve_attack_roll` | **Oui** | Non | `AttackRollResolved` | Budget combattant |
| Dégâts | `apply_damage` | **Non** | Oui | `DamageDealt` | PV combattant |

Points mesurés dans le code (`combat_manager.py`) :

- `resolve_attack_roll` consomme le budget **avant** le jet, publie le résultat, **ne modifie pas les PV**.
- `apply_damage` accepte `damage_notation` (jet moteur + critique) ou `damage_amount` (montant fixe) ; applique bonus registre (`hunters_mark`, `hex`) côté serveur ; déclenche save CON concentration si dégâts > 0 (C5).
- **Aucun état « attaque en suspens »** dans `CombatState` : pas de `pending_attack`, pas de référence jet → dégâts dans le blob.

Lot 1 API (`POST …/attack-roll`) :

- Body client : `attacker_id`, `target_id`, `melee_weapon` / `ranged_weapon` (portée).
- Modificateurs d20 **dérivés moteur** (`build_weapon_attack_request`) — pas de `attack_bonus` injectable.
- Réponse : `attack_roll_resolution_to_dict` (`d20` + `outcome`) — **sans** état combat mis à jour côté PV.

---

## 2. Contraintes d'arbitrage (mainteneur)

### 2.1 Le jet n'est pas une lecture pure

`attack-roll` lot 1 **mutate déjà** : vérifie le tour (`NOT_COMBATANT_TURN`), consomme `action` (`ACTION_BUDGET_EXHAUSTED`), persiste le budget.

La question n'est donc pas « endpoint sans effet de bord », mais :

> **Un jet peut-il rester non résolu en base, et pendant combien de temps ?**

| Réponse | Conséquence |
|---|---|
| **Non** (pas d'état intermédiaire) | Séparer jet et dégâts **sans fusion** exige soit de **refaire** le jet (double budget), soit de **faire confiance au client** pour le toucher — les deux sont problématiques (§2.3, §3). |
| **Oui** (état intermédiaire) | Nouveau modèle : attaque lancée, dégâts non appliqués — **absent du moteur aujourd'hui** (blob, registre, expiration tour). Chantier ADR + persistance, pas seulement API. |

### 2.2 Qui choisit les dégâts — principe lot 1

Le d20 est déterminé par le moteur. Les dégâts dépendent de l'**arme** (notation dés + modificateur), du **critique**, et des **effets actifs** (maléfice, marque du chasseur…).

**Principe réaffirmé** : le client ne injecte **pas** de valeurs de règles (`damage_amount`, `hit`, `critical` arbitraires).

| Ce que le client peut fournir | Ce que le serveur calcule |
|---|---|
| Identifiant d'arme ou notation validée compendium | Jet de dés, modificateur STR/DEX, bonus effets |
| Contexte déjà lot 1 : portée, paire attaquant/cible | Toucher, critique, application overlay |

**Dette connexe** : la fiche expose `inventory[]` mais **aucun modèle « arme équipée »** combat-ready. Le lot 2 devra trancher le vocabulaire client (`weapon_id`, entrée inventaire, notation figée…) — hors scope de ce cadrage, mais bloquant pour les deux options.

### 2.3 Idempotence

Contrat §2.4 / §6 : **idempotence POST non garantie v1** ; `Idempotency-Key` reporté.

| Modèle | Rejeu du même POST | Garde-fou naturel |
|---|---|---|
| **Fusionné** | 2e appel = budget épuisé → `409 ACTION_BUDGET_EXHAUSTED` | Budget `action` consommé une fois |
| **Séparé** | 2e `apply-damage` identique = **double dégâts** | **Aucun** — `apply_damage` ne consomme pas de budget |

Un modèle séparé **réouvre** la question idempotence (clé, attaque pending liée, ou acceptation explicite du double-appel).

---

## 3. Option A — Fusionné (jet + dégâts, une requête)

### Description

Étendre `POST /v1/combats/{id}/attack-roll` (ou le renommer `weapon-attack`) pour enchaîner, **côté serveur** :

1. `resolve_attack_roll` (inchangé) ;
2. si `outcome.hit` : `apply_damage` avec notation dérivée de l'arme + `critical=outcome.critical` ;
3. si manqué : pas de dégâts ;
4. réponse agrégée : jet + dégâts (ou `damage: null`).

Le client fournit : combattants, portée, **référence arme** (à définir). Il ne fournit **pas** le montant de dégâts ni le toucher.

### Alignement ADR

| ADR | Impact |
|---|---|
| **ADR-004 §9** | Respecte la **séparation interne** moteur ; l'API **orchestre** les deux appels — pas de fusion dans `CombatManager`. |
| **ADR-005** | Overlay PV muté ; fiche SQLite inchangée jusqu'à `close` — identique lot 1 + test garde-fou existant. |
| **ADR-004 §11 (C4)** | Budget consommé une fois au début du pipeline — cohérent. |
| **ADR-004 §12 (C5)** | Save CON déclenchée par `apply_damage` — incluse automatiquement si toucher. |

### Implications contrat

- §5.1 étape 4 devient « attaque d'arme complète » (jet + dégâts si toucher).
- Nouveau DTO sortie (ex. `weapon_attack_result_to_dict`) — **données seulement** : reprendre `attack_roll_resolution_to_dict` + bloc dégâts optionnel + snapshot combat optionnel (ou renvoi vers `GET /v1/combats/{id}`).
- Pas de nouvel état blob « pending ».
- Idempotence : **statu quo v1** suffit grâce au budget (§2.3).
- §6 « Idempotency-Key reportés » : **non réouvert** pour le cas attaque d'arme standard.

### Avantages

- Pas de modèle intermédiaire à inventer.
- Cohérent avec le principe « le moteur décide, le client observe ».
- Anti-rejeu gratuit via budget d'action.
- Parcours client simple : une action = une requête.

### Inconvénients / limites

- **Annonce du jet avant application** (voir §5) : le client reçoit jet + dégâts **dans la même réponse** — pas de pause serveur entre les deux.
- Sorts, attaques multiples (Extra Attack), dégâts sans toucher préalable : **autres endpoints** ultérieurs (`apply-damage` moteur reste libre pour sorts à save).

---

## 4. Option B — Séparé (jet puis dégâts)

### Description

Conserver `POST …/attack-roll` tel quel, ajouter `POST …/apply-damage` (ou `…/weapon-damage`).

### Variante B1 — Sans état serveur (client retient la réponse)

Flux : `attack-roll` → UI affiche → `apply-damage`.

Problème : pour recalculer les dégâts **sans faire confiance au client**, le serveur doit connaître **hit/critical**. Options :

| Mécanisme | Verdict |
|---|---|
| Client envoie `hit` / `critical` | **Rejeté** — contourne les règles (§2.2). |
| Client renvoie le `d20` complet | **Rejeté** — rejeu / falsification du jet. |
| Serveur **rejoue** `attack-roll` | Double consommation budget — **inacceptable** sans idempotence. |

→ **B1 non viable** sans état serveur ou fusion.

### Variante B2 — État « attaque pending » dans le blob

Après `attack-roll`, persister une structure `pending_weapon_attack` (attaquant, cible, outcome, arme, round/tour, TTL).

`apply-damage` consomme le pending et appelle `apply_damage` moteur.

| Aspect | Charge |
|---|---|
| Modèle | Nouveau champ blob + règles expiration (fin de tour ? timeout ? annulation ?) |
| ADR-004 §9 | Écart explicite : séparation API ≠ séparation moteur ; couche état API/moteur à documenter |
| Idempotence | `apply-damage` idempotent **si** pending consommé atomiquement ; `attack-roll` ne doit pas créer deux pending sans règle |
| Concurrence | Last-writer-wins sur pending + budget — combinaison fragile (contrat §2.4) |

### Variante B3 — Deux endpoints, fusion de fait côté client

Le client enchaîne deux POST sans pause UI. **Strictement équivalent produit à l'option A**, avec latence double et fenêtre d'idempotence entre les deux — **sans bénéfice**.

### Implications contrat (B2 — seule variante séparée défendable)

- Nouvelle ressource ou sous-état `pending_attack` — **non prévu** contrat v1.
- Nouveaux codes : `PENDING_ATTACK_NOT_FOUND`, `PENDING_ATTACK_EXPIRED`, …
- §2.4 idempotence : **à retrancher ou préciser** pour `apply-damage`.
- Dette §10 : mapping `COMBAT_STATE_UNSUPPORTED` + **version blob** si pending ajouté.

### Avantages (B2 uniquement)

- Pause produit **réelle** entre annonce du jet et application des dégâts (§5).
- `apply_damage` moteur reste réutilisable tel quel pour sorts.

### Inconvénients

- **Chantier modèle** le plus lourd (blob, tests, migration, expiration).
- Réouvre idempotence et concurrence.
- Risque de « second moteur de règles » si la sémantique pending dérive du moteur.

---

## 5. Cas d'usage produit — faut-il séparer jet et dégâts ?

| Cas | Besoin de séparation serveur ? | Commentaire |
|---|---|---|
| **Attaque standard** (clic → résultat) | Non | Option A suffit. |
| **Annoncer le jet au groupe avant d'appliquer les dégâts** | Oui, **UX** | Pause entre affichage d20 et baisse de PV. |
| **MJ valide manuellement** | Oui, **UX** | Même pattern. |
| **Attaque de sort** (toucher + dégâts) | Hors lot 2 arme | Moteur a déjà `cast_spell_attack` — endpoint distinct futur. |
| **Dégâts sans toucher** (save, zone) | Hors lot 2 arme | `apply_damage` direct — pas via `attack-roll`. |
| **Extra Attack** (2 actions) | Non | Deux appels fusionnés = deux budgets — naturel en A. |

### Analyse « jet annoncé au groupe »

Deux implémentations possibles **sans** état pending serveur :

1. **Pause client pure** : l'API fusionnée renvoie jet + dégâts ; l'UI **retarde l'affichage PV** — le serveur a déjà appliqué. Le groupe voit le jet puis les PV **côté UI**, pas côté règles. ADR-005 respecté (overlay déjà muté). **Pas de mensonge mécanique** si l'UI ne ment pas sur l'état serveur avant refresh.

2. **Pause serveur réelle** : nécessite variante B2 (pending) — état « touché mais PV pas encore baissés » **existe en base**.

Question produit pour l'arbitrage :

> La pause « annonce au groupe » exige-t-elle que **les PV serveur** restent inchangés pendant la pause, ou suffit-il que **l'interface** staged l'information ?

- Si **UI seulement** → **Option A** + client staging.
- Si **PV serveur figés** → **Option B2** (coût modèle).

---

## 6. Matrice de décision

| Critère | Option A — Fusionné | Option B2 — Séparé + pending |
|---|---|---|
| Cohérence principe lot 1 (pas d'injection règles) | ✅ | ✅ si pending serveur |
| Alignement ADR-004 séparation moteur | ✅ orchestration | ⚠️ nouvel état |
| Idempotence v1 | ✅ budget | ⚠️ à concevoir |
| Complexité blob / persistance | ✅ aucune | ❌ élevée |
| Jet annoncé (UI staging) | ✅ | ✅ |
| Jet annoncé (PV serveur figés) | ❌ | ✅ |
| Sorts / dégâts hors attaque (lots futurs) | ✅ `apply_damage` libre | ✅ |
| Dette COMBAT_STATE_UNSUPPORTED | Inchangée | Aggravée (blob) |

---

## 7. Recommandation de rédaction (agent — non décision)

**Penchement technique aligné avec l'intuition mainteneur** : **Option A (fusionné)** pour le lot 2 arme, sauf si le produit exige explicitement des **PV serveur figés** pendant la pause post-jet.

Motifs :

1. Budget d'action = anti-rejeu sans rouvrir l'idempotence (§2.3).
2. Pas d'état intermédiaire absent du moteur (§2.1).
3. Dégâts toujours recalculés moteur ; le client ne fournit qu'une **référence arme** (§2.2).
4. Le cas « annonce au groupe » le plus courant en JDR numérique se satisfait d'un **staging UI** sur réponse fusionnée (§5).

**Si Option A retenue**, trancher avant implémentation :

- [ ] Vocabulaire arme client (`weapon_id` ? item inventaire ? notation compendium ?).
- [ ] Forme de la réponse (jet + dégâts + éventuel `combat` embed vs renvoi `GET`).
- [ ] Comportement manqué / critique / nat 1 (pas de `apply_damage` si miss — déjà moteur).
- [ ] Renommage route (`attack-roll` → `weapon-attack`) ou sémantique étendue du même path.

**Si Option B retenue** : exiger B2 (pending) ; refuser B1 ; produire ADR ou amendement contrat §10 **avant** code.

---

## 8. Hors lot 2 (rappel)

- Sorts combat, conditions API, `advance_turn`, Extra Attack.
- `COMBAT_STATE_UNSUPPORTED` (dette §10.4) — chemin load, pas lié au choix A/B mais à livrer en parallèle ou juste après.
- Réalignement §5.1 étape 6 ↔ §2.6 (fusion en `preparing`) — cosmétique contrat, non bloquant.

---

## Références

- `docs/api/CONTRAT.md` — §2.4, §2.6, §5.1, §10.4
- `docs/adr/ADR-004-modele-combat.md` — §9, §11 (budget), §12 (concentration)
- `docs/adr/ADR-005-transition-fin-rencontre.md` — sync-on-close, overlay
- `jdr_engine/game/combat_manager.py` — `resolve_attack_roll`, `apply_damage`
- Lot 1 : `interfaces/api/combat_attack.py`, `combat_routes.py`
