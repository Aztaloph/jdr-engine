# Brief Fable 5 — refonte visuelle HUD combat

| Attribut | Valeur |
|---|---|
| **Statut** | Brief d'implémentation visuelle — prêt pour agent Fable 5 |
| **Date** | 2026-08-11 (révision architecte) |
| **Épic** | Transformer l'affichage du HUD combat pour qu'il ressemble à la maquette Figma, **sans changer le comportement ni les contrats** |
| **Agent cible** | Fable 5 (implémentation autonome) |
| **Références** | [`docs/api/CONTRAT.md`](../api/CONTRAT.md) §2.8–2.9 · [`ADR-007`](../adr/ADR-007-stack-client-web.md) · `web/src/lib/screens/CombatScreen.svelte` |

---

## 1. Mission exacte

**Prendre le HUD combat Svelte existant, conserver intégralement son comportement et ses contrats API, et transformer son affichage pour qu'il ressemble réellement à la maquette Figma du HUD combat (layout trois colonnes, charte sombre / ambre, hiérarchie visuelle).**

Ce n'est **pas** une mission d'implémentation backend, ni de nouvelles fonctionnalités de jeu, ni de landing page.

**Principe directeur** :

| Priorité | Règle |
|---|---|
| 1 | Contrats API et données réellement disponibles |
| 2 | Contraintes d'architecture du projet (`AGENTS.md`, ADR) |
| 3 | Fonctionnalités actuellement fonctionnelles (à ne pas casser) |
| 4 | Maquette Figma pour la **présentation visuelle** |
| 5 | Hypothèses / embellissements — **interdits** |

**Corollaire** : la maquette **ne justifie jamais** d'inventer une donnée ou une fonctionnalité. **Inversement**, l'absence d'une fonctionnalité backend **n'empêche pas** de construire sa **place visuelle** avec un placeholder explicite.

---

## 2. Références visuelles

| Référence | Rôle dans ce lot |
|---|---|
| **Maquette Figma — HUD combat** | **Cible visuelle principale** — layout 3 colonnes, en-tête, cartes combattants, initiative horizontale, zone carte, panneau actions, journal, pied de page dés |
| **Maquette Figma — landing page** | **Horizon produit uniquement** — extraire tokens communs (palette, ambre, typo, surfaces) ; **ne pas implémenter** la landing |
| **Capture / état actuel de l'app** | Point de départ fonctionnel — mono-colonne, fieldsets, HUD v1 opérationnel |
| **Commit `fc66507` (sous-lot A)** | Tokens déjà livrés — `web/src/lib/styles/tokens.css`, charte sombre/ambre sur les 3 écrans ; **ne pas repartir de zéro** |

---

## 3. État réel du code (vérifié 2026-08-11)

### Stack

| Élément | État réel |
|---|---|
| Client | Svelte 5 + Vite + TS, port **5173**, proxy `/v1` → `:8000` |
| Routage | Hash — `#/lobby`, `#/combat/{id}?viewer=`, `#/character/{id}` |
| Tokens | **`web/src/lib/styles/tokens.css`** — ambre `#f59e0b`, fond `#0a0a0a`, Inter + Playfair (Google Fonts dans `web/index.html`) |
| Layout app | `#app` → `max-width: var(--layout-max-width)` avec `--layout-max-width: min(80rem, 100%)` — **pas** le 52rem d'origine, mais le HUD 3 colonnes peut nécessiter **pleine largeur viewport** sur la route combat |
| Tests moteur | **945 tests OK** — lot front sans toucher Python |

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `web/src/lib/screens/CombatScreen.svelte` | **Cible** — ~695 lignes, logique + template mono-colonne + styles scoped |
| `web/src/lib/api/combat.ts` | `fetchCombatState`, `advanceCombatTurn`, `postWeaponAttack`, `postCombatCast`, `closeCombat` |
| `web/src/lib/types/combat.ts` | Miroir `combat_state_to_dict` |
| `web/src/lib/types/attack.ts` | `WEAPON_IDS`, `WeaponAttackResult` |
| `web/src/app.css` | Styles globaux + charte A |
| `web/src/App.svelte` | Nav minimale (Lobby · Combat id · Fiche id) |
| `web/src/lib/components/ErrorAlert.svelte` | Erreurs API / réseau |

### Comportement fonctionnel à préserver (inventaire code)

Tout ceci **doit continuer à marcher** après la refonte visuelle :

| Zone | Comportement |
|---|---|
| **Viewer** | Select ou input ; sync URL `?viewer=` ; filtre sorts et visibilité |
| **Chargement** | `GET /v1/combats/{id}?viewer=` au mount et reload |
| **En-tête données** | `status`, `round_number`, tour via `current_combatant_id` |
| **Tour courant** | PV, CA, budget action/bonus, concentration (si clés présentes) |
| **Initiative** | Liste `initiative_order[]`, surbrillance tour, `is_active`, lien `#/character/{id}` |
| **Effets actifs** | Liste `active_effects[]` (ids bruts) |
| **Attaque** | Selects attaquant / cible / arme (`WEAPON_IDS`) + `POST …/attack` + journal client |
| **Sorts** | Boutons depuis **`viewer.castable_spells[]` uniquement** + `POST …/cast` |
| **Aide sorts** | Messages hors tour / pas de viewer / pas de sorts — conserver la logique |
| **Journal** | Tableau **client-side** post-attaque / post-cast — pas de log serveur |
| **Actions globales** | Recharger, tour suivant (`advance-turn`), clôturer → lobby |
| **Erreurs** | `ErrorAlert`, dont 502 « API injoignable » |

### Écart visuel actuel vs maquette

| Aspect | Actuel | Maquette |
|---|---|---|
| Structure | Mono-colonne, fieldsets, liste verticale | 3 colonnes + en-tête + pied de page |
| Combattants | Items dans liste initiative | Cartes groupe à gauche + bandeau initiative |
| Carte | Absente | Panneau central dominant |
| Actions | Formulaire + boutons | Boutons « Actions rapides » + panneaux |
| Caractéristiques | Absentes du combat | Grille 6 stats à droite |
| Dés | Absents | Barre d4–d20 + historique |
| En-tête | Titre « Combat » + hint | Barre JDR ENGINE + pills ROUND / tour / timer / MJ |

---

## 4. Classification obligatoire — quatre niveaux de rendu

Chaque élément de la maquette doit être classé **avant** implémentation. Fable 5 applique la règle correspondante sans exception.

| Niveau | Signification | Action Fable |
|---|---|---|
| **① Fonctionnel maintenant** | Donnée + interaction déjà branchées | Rendre visuellement proche de Figma **et** garder le comportement |
| **② Affichage données disponibles** | Donnée partielle ou filtrée par viewer | Afficher **si clé présente** ; masquer si absente — **jamais** de valeur par défaut fictive |
| **③ Placeholder visuel** | Présent dans Figma, absent côté backend | Construire le **panneau / bouton / zone** ; marquer **« EN DÉVELOPPEMENT »**, **« À VENIR »** ou libellé équivalent ; **disabled** si bouton |
| **④ Hors périmètre** | Ne doit pas exister dans ce lot | Ne pas coder — pas même un placeholder si cela implique une fausse dynamique (ex. timer qui tick) |

### Convention placeholders (niveau ③)

- Texte court, visible, cohérent charte : `EN DÉVELOPPEMENT`, `À VENIR`, `CARTE TACTIQUE — EN DÉVELOPPEMENT`.
- Style : bordure pointillée ou fond atténué, typo `--color-text-muted`, badge discret.
- **Interdit** : fausses valeurs (PV inventés, jetons sur fausse grille, timer `02:45:12` qui avance, « MJ en ligne » vert simulé).

---

## 5. Mapping maquette → rendu (tableau de décision)

### En-tête HUD

| Élément Figma | Niveau | Source / traitement |
|---|---|---|
| Logo « JDR ENGINE » | ③ ou statique | Texte UI fixe autorisé (marque) |
| Titre campagne | ③ | Pas de `campaign_name` — zone placeholder **« Campagne — à venir »** ou titre neutre `Rencontre {combat_id}` |
| Pilule **ROUND** *n* | ① | `round_number` |
| Pilule **Tour de :** *nom* | ① | `current_combatant_id` + `display_name` |
| Timer session | ④ | Hors périmètre — **ne pas afficher** de fausse horloge |
| « MJ en ligne » | ④ | Hors périmètre |

### Colonne gauche — groupe & initiative

| Élément Figma | Niveau | Source / traitement |
|---|---|---|
| Cartes **Membres du groupe** | ①② | `combatants` + `initiative_order` ; nom `display_name` ; PV/CA **②** ; barre PV **②** si `hp_current` **et** `hp_max` ; bordure ambre si `current_combatant_id` |
| Avatar circulaire | ③ | Placeholder initiales ou silhouette neutre — **pas** d'`image_url` fetch |
| Sous-titre « Mage — Niveau 5 » | ③ | **Pas** de fetch fiche — ligne placeholder **« Classe — à venir »** ou omise |
| Badges « BÉNI », « EMPOISONNÉ » | ② | Uniquement `effect_id` sur `active_effects[]` ciblant ce combattant — afficher l'**id** (`bless`, `hex`…), **pas** de traduction FR inventée |
| Bandeau **initiative** horizontal | ①② | Jetons ordonnés ; score si `initiative_total` **présent** ; surbrillance tour |
| Lien fiche | ① | `#/character/{character_id}` |

### Colonne centrale — carte

| Élément Figma | Niveau | Source / traitement |
|---|---|---|
| Plan / grille / jetons | ③ | Panneau central **« CARTE TACTIQUE — EN DÉVELOPPEMENT »** — pas de fausse carte |
| Nom du plan | ③ | Sous-titre placeholder ou omis |
| Toggles vision / mesure / grille | ③ | Boutons **disabled** + badge « à venir » **ou** omis — pas de faux état actif |

### Colonne droite — fiche active, actions, journal

| Élément Figma | Niveau | Source / traitement |
|---|---|---|
| Grille 6 caractéristiques | ③ | **Ne pas** appeler `GET …/sheet` — panneau **« Fiche active — caractéristiques à venir »** ou 6 cellules vides avec label `--` |
| Nom personnage actif | ① | Combattant du tour ou du viewer selon contexte maquette |
| **Attaque d'arme** | ① | Conserver selects attaquant/cible/arme + `POST …/attack` — présentation maquette (bouton + panneau dépliable) **autorisée** |
| **Lancer un sort** | ① | Boutons depuis `viewer.castable_spells[]` + `POST …/cast` |
| **Compétences** | ③ | Bouton visible **disabled** + « à venir » |
| **Fin de tour** | ① | `advanceCombatTurn` — libellé maquette autorisé |
| Budget / concentration | ② | Afficher si `action_budget` / `concentration_*` présents |
| **Journal** | ① | Contenu journal client existant — mise en forme maquette |
| Texte narratif RP | ④ | Pas de fausse narration serveur |
| Horodatage journal | ③ optionnel | Horodatage **local** au push = cosmétique acceptable ; **pas** d'heure serveur simulée |

### Pied de page — bassin de dés

| Élément Figma | Niveau | Source / traitement |
|---|---|---|
| Boutons d4–d20 | ③ | Barre visuelle + boutons **disabled** + label **« Bassin de dés — en développement »** |
| Historique de jets | ③ | Zone placeholder ou message « à venir » |
| Toggles torche / grille | ③ | Disabled ou omis |

### Landing page

| Élément | Niveau |
|---|---|
| Toute la landing | ④ — hors lot |

---

## 6. Pièges — ce qui pousserait Fable à déraper (interdit)

| Piège | Pourquoi c'est interdit | Alternative |
|---|---|---|
| `GET /v1/characters/{id}/sheet` pour remplir FOR/DEX | Appel API **nouveau** dans ce lot ; données hors agrégat combat | Placeholder panneau fiche |
| `GET /v1/characters` pour classe/niveau sur cartes | Join client non autorisé ; N+1 | Placeholder « classe — à venir » |
| Dictionnaire FR `bless` → « BÉNI » | Règle métier / i18n côté client | Afficher `effect_id` brut |
| Liste sorts en dur `[hunters_mark, bless, hex]` | Contourne `viewer.castable_spells[]` | Toujours la liste serveur |
| Fausses positions / jetons carte | Simule moteur C4 | Placeholder panneau carte |
| Timer / présence MJ dynamiques | Fausses données temps réel | Niveau ④ — ne pas afficher |
| WebSocket / polling | Hors contrat v1 | — |
| Modifier Python / types / API | Hors périmètre front | — |
| Cacher le formulaire attaque sans remplacement | Régression fonctionnelle | Bouton maquette + formulaire accessible |
| Afficher `0` pour PV/CA absents | Violation CONTRAT §2.8 | Masquer le champ |

---

## 7. Fonctionnalités à conserver impérativement

Checklist **non négociable** — toute refonte visuelle doit passer ces tests :

1. `GET /v1/combats/{id}?viewer=` — chargement et affichage état
2. Sélecteur viewer + mise à jour URL hash
3. `POST …/advance-turn` — bouton fin de tour
4. `POST …/attack` — attaque avec les 3 selects
5. `POST …/cast` — sorts depuis `castable_spells[]` (ex. `hunters_mark` rôdeur au bon tour)
6. Journal client alimenté après attaque et sort
7. `POST …/close` — clôturer
8. Lien fiche depuis initiative
9. Messages d'erreur (`ErrorAlert`, codes API)
10. États `preparing` / `active` / `ended` gérés comme aujourd'hui

**Parcours de validation manuel** (personnages test : rôdeur `a505d6d5`, clerc `385022fd`) :

Lobby → créer → activer → combat → viewer → attaquer → `hunters_mark` → tour suivant → clôturer.

---

## 8. Contraintes d'architecture

Issues de `AGENTS.md` et du contrat — **garde-fous immuables** :

| Contrainte | Détail |
|---|---|
| Aucun Python | `jdr_engine/`, `interfaces/api/*.py`, tests moteur — **0 modification** |
| Aucune règle métier client | Pas de calcul toucher, visibilité PV, liste sorts, budget |
| `viewer.castable_spells[]` | Seule source des sorts affichables |
| Visibilité viewer | Champ absent ≠ `null` ≠ `0` — ne pas afficher |
| Tour courant | `current_combatant_id` — **pas** `initiative_order[turn_index]` |
| `WEAPON_IDS` | Liste fermée documentée — ne pas élargir |
| Pas de nouvelle dépendance npm | Sans accord mainteneur |
| `interfaces/api/static/` | Intouchable |
| Fiche / lobby | Cohérence tokens seulement — **pas** refonte structure lobby/fiche dans ce lot (sauf ajustements CSS mineurs si collision) |

---

## 9. Fichiers autorisés / interdits

### Autorisés

```
web/src/**
web/index.html          (si besoin meta / fonts — déjà configuré)
```

Création attendue :

```
web/src/lib/components/combat/*.svelte   (CombatantCard, Panel, StatusBadge, JournalEntry, MapPlaceholder, …)
web/src/lib/styles/*.css                 (extension tokens si besoin)
```

### Interdits

| Zone | Raison |
|---|---|
| Tout hors `web/` | Lot front strict |
| `web/package.json` | Sans accord |
| Python, types moteur, API | Hors périmètre |

---

## 10. Cible visuelle — structure attendue (vertical slice)

Objectif : **une seule session de travail** doit produire un HUD **recognizable** vs la maquette Figma.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ EN-TÊTE : marque · pills ROUND / Tour · actions (recharger, clôturer)   │
├──────────────┬──────────────────────────────┬───────────────────────────┤
│ COLONNE G.   │ COLONNE CENTRE               │ COLONNE D.                │
│ Membres      │ CARTE — EN DÉVELOPPEMENT     │ Fiche active (placeholder │
│ (cartes)     │ (grand panneau)              │  ou nom + budget)         │
│ Initiative   │                              │ Actions rapides (①+③)     │
│ (bandeau)    │                              │ Journal (①)               │
├──────────────┴──────────────────────────────┴───────────────────────────┤
│ PIED : Bassin de dés — EN DÉVELOPPEMENT (boutons disabled)              │
└─────────────────────────────────────────────────────────────────────────┘
```

**Notes layout** :

- Route combat : utiliser **pleine largeur** (wrapper `.combat-layout` ou override `#app` sur cet écran) — `--layout-max-width: 80rem` peut être trop étroit pour la maquette.
- Viewer : peut rester en en-tête ou panneau latéral — **ne pas supprimer**.
- Responsive : empilement vertical &lt; ~1024px = acceptable en phase 2 ; phase 1 desktop-first acceptable si 3 colonnes visibles à 1280px.

---

## 11. Découpage recommandé — vertical slice d'abord

### Contexte : sous-lot A déjà livré (`fc66507`)

Les tokens et la charte de base existent. **Ne pas refaire A.** Enchaîner directement sur le HUD maquette.

### Phase 1 — Vertical slice visuel (**priorité absolue**, commit 1)

**Objectif** : en **un commit**, livrer un HUD combat qui **ressemble à la maquette** avec placeholders explicites et **toutes** les interactions ① fonctionnelles.

Contenu minimal Phase 1 :

- Restructuration `CombatScreen` en 3 colonnes + en-tête + pied
- Composants extraits (au moins : carte combattant, panneau, placeholder carte, entrée journal)
- Placeholders niveau ③ pour : carte, avatars, classe/niveau, caractéristiques, compétences, dés, campagne
- Données ①② branchées comme aujourd'hui
- `npm run build` + `npm run check` OK
- Parcours attaque + `hunters_mark` OK

**Critère de succès Phase 1** : le mainteneur ouvre `#/combat/{id}` et **identifie immédiatement** la cible Figma, sans ambiguïté sur ce qui est réel vs en développement.

**Point d'arrêt recommandé** : commit + capture d'écran + message « vertical slice prêt pour validation visuelle ». Pas obligatoire d'attendre validation avant Phase 2, **mais** Phase 1 doit être **auto-suffisante** pour feedback visuel.

### Phase 2 — Finitions (**commit 2**, après Phase 1)

- Barres PV soignées, badges `effect_id`, journal typographié façon maquette
- Responsive dégradé
- Nettoyage CSS scoped legacy / duplication
- Ajustements tokens si écart maquette
- Polish placeholders (cohérence libellés)

**Ne pas bloquer Phase 1** pour la perfection pixel-perfect.

### Ancienne découpe A → B → C

**Remplacée.** A est fait. B et C fusionnés en **Phase 1 (slice)** + **Phase 2 (finitions)**. La sécurité ne repose plus sur « tokens seuls avant layout », mais sur :

- garde-fous § 8 (pas de backend, pas de données inventées) ;
- checklist § 7 (fonctionnel préservé) ;
- placeholders explicites § 4 ;
- parcours manuel obligatoire.

---

## 12. Critères de validation

### Automatisés (chaque commit)

```bash
cd web
npm run build    # exit 0
npm run check    # 0 erreur
```

### Manuels — Phase 1 (obligatoires)

- [ ] Layout 3 colonnes visible à 1280px
- [ ] Placeholder carte clairement libellé
- [ ] Cartes combattants avec données réelles (nom, PV/CA si visibles)
- [ ] Initiative + tour courant identifiables
- [ ] Attaque complète fonctionne
- [ ] Sort overlay (`hunters_mark`) fonctionne avec viewer
- [ ] Journal reçoit entrées attaque/sort
- [ ] Aucune donnée fictive (timer, MJ, fausses stats, fausse carte)
- [ ] Zones ③ clairement marquées en développement

### Manuels — Phase 2

- [ ] Responsive acceptable tablette / mobile
- [ ] Cohérence visuelle journal / badges / barres PV
- [ ] Pas de régression vs checklist Phase 1

### Non-régression moteur

Aucun fichier hors `web/src/**` (+ `web/index.html` si touché).

---

## 13. Dettes / fonctionnalités futures (nommées, non traitées)

| Dette | Débloqueur |
|---|---|
| Carte tactique réelle | Moteur C4, WebSocket (ROADMAP lot 4) |
| Avatars | `image_url` sur combattant ou asset statique |
| Classe / niveau en combat | Enrichissement DTO ou join serveur |
| Caractéristiques HUD | Embed sheet partiel dans GET combat **ou** fetch autorisé (décision produit) |
| Libellés effets FR | Compendium / i18n API |
| Bassin de dés | Endpoint jets |
| Timer / présence MJ | Auth, sessions |
| Journal serveur | EventBus / endpoint log |
| Landing marketing | Écran public séparé |

---

## 14. Ambiguïtés — décisions refusées sans mainteneur

| Sujet | Options | Recommandation brief (défaut Fable) |
|---|---|---|
| Titre campagne en en-tête | Placeholder vs `Rencontre {combat_id}` | **`Rencontre #{combat_id}`** + petit badge « campagne à venir » |
| Panneau caractéristiques droite | 6 cellules vides vs message unique | **Message unique** « Caractéristiques — à venir » (moins trompeur que six `--`) |
| Pied de page dés | Barre complète disabled vs bandeau texte | **Barre visuelle** avec boutons disabled + label développement |
| Horodatage journal local | Oui / non | **Optionnel** Phase 2 — pas requis Phase 1 |
| Nav `App.svelte` | Style maquette en-tête vs nav actuelle | **Conserver** nav actuelle Phase 1 ; harmonisation Phase 2 si temps |
| Pleine largeur combat | Override `#app` vs wrapper interne | **Wrapper `.combat-shell`** pleine largeur — ne pas casser lobby/fiche |

Si Fable rencontre un cas non couvert : **placeholder ③ + note dans le rapport**, jamais invention de donnée.

---

## 15. Instructions d'exécution pour Fable 5

1. Lire ce brief et `CombatScreen.svelte` en entier.
2. **Phase 1 d'abord** — vertical slice complet en un commit.
3. Ne pas modifier le `<script>` sauf extraction helpers présentation ou déplacement markup — **logique API inchangée**.
4. Extraire composants dans `web/src/lib/components/combat/`.
5. Réutiliser / étendre `tokens.css` — ne pas dupliquer palette.
6. Placeholders **visibles et honnêtes** pour tout niveau ③.
7. Valider build/check + parcours § 12.
8. Phase 2 seulement après Phase 1 commitée et validée visuellement (par mainteneur ou auto si consigne explicite).

**Phrase de mission pour copier-coller** :

> Prends le HUD combat existant (`CombatScreen.svelte`), conserve intégralement son comportement et ses contrats API, et transforme son affichage pour qu'il ressemble à la maquette Figma (3 colonnes, sombre/ambre). Données réelles où elles existent ; placeholders « EN DÉVELOPPEMENT » partout ailleurs. Aucun Python, aucun nouvel appel API, aucune donnée inventée. Livrer d'abord un vertical slice visuel (Phase 1), puis finitions (Phase 2). Suis `docs/web/BRIEF_FABLE_AFFICHAGE.md`.

---

## Références code

| Sujet | Fichier |
|---|---|
| HUD actuel | `web/src/lib/screens/CombatScreen.svelte` |
| Tokens | `web/src/lib/styles/tokens.css` |
| Types combat | `web/src/lib/types/combat.ts` |
| API client | `web/src/lib/api/combat.ts` |
| Contrat | `docs/api/CONTRAT.md` §2.8–2.9 |
| Lancement | `web/README.md` |
