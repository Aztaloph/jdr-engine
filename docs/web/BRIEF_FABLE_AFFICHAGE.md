# Brief — refonte visuelle HUD combat (charte Figma)

| Attribut | Valeur |
|---|---|
| **Statut** | Prompt de référence pour agent d'implémentation |
| **Date** | 2026-08-11 |
| **Épic** | Refonte visuelle du HUD combat vers la charte cible, **à données constantes** |
| **Maquette** | Figma — HUD combat trois colonnes + landing (landing = horizon, hors lot) |
| **Découpe** | **Obligatoire** — sous-lots A → B → C, **trois commits** ; B interdit avant validation visuelle de A (§ Découpe obligatoire) |
| **Références** | [`docs/api/CONTRAT.md`](../api/CONTRAT.md) §2.8–2.9 · [`ADR-007`](../adr/ADR-007-stack-client-web.md) · `web/src/lib/screens/CombatScreen.svelte` |

---

## Mission en une phrase

Habiller et restructurer l'écran combat Svelte existant selon la direction artistique sombre / ambre et un layout trois colonnes proche de la maquette Figma, **sans ajouter de donnée, d'appel API ni de logique métier**.

### Ce que ce lot n'est pas

- Ce n'est **pas** la carte tactique, la landing publique, le temps réel, ni une refonte fonctionnelle du combat.
- Ce n'est **pas** un lot moteur : **aucun fichier Python**, **aucune modification** de `interfaces/api/static/`.
- Ce n'est **pas** l'ajout de champs inventés (classe/niveau sur carte combattant, libellés d'effets traduits, timer de session, bassin de dés, etc.) faute de les trouver dans le DTO combat.

---

## État de départ

### Stack et lancement

| Élément | État |
|---|---|
| Client | SPA **Svelte 5 + Vite + TypeScript**, port **5173**, proxy `/v1` → `:8000` |
| Routage | `svelte-spa-router` (hash) — `App.svelte`, `web/src/lib/navigation.ts` |
| Styles globaux | `web/src/app.css` — thème **système clair/sombre**, accent **bleu** (`#3b82f6`), `#app` **max-width 52rem** (layout mono-colonne) |
| Tests moteur | **945 tests OK** mesurés le 2026-08-11 (`python -m unittest discover -s tests -p "test_*.py" -q`) — lot **sans impact** attendu sur ce chiffre |

### Écrans concernés

| Fichier | Rôle actuel |
|---|---|
| `web/src/lib/screens/CombatScreen.svelte` | **Cible principale** — HUD v1 fonctionnel (~690 lignes, styles scoped) |
| `web/src/lib/screens/LobbyScreen.svelte` | Création / activation / combats ouverts — cohérence visuelle minimale seulement |
| `web/src/lib/screens/CharacterScreen.svelte` | Fiche minimal — cohérence visuelle minimale seulement |
| `web/src/App.svelte` | Nav globale — hériter tokens (fond, liens, boutons) |
| `web/src/lib/components/ErrorAlert.svelte` | Erreurs API / réseau — conserver le comportement, appliquer la charte |

### Ce qui marche déjà sur `CombatScreen` (ne pas régresser)

Lecture `GET /v1/combats/{id}?viewer=` et mutations existantes :

| Fonctionnalité | Implémentation actuelle |
|---|---|
| Sélecteur **viewer** | Dropdown participants ou saisie `character_id` ; met à jour l'URL hash |
| En-tête combat | `status`, `round_number` |
| **Tour courant** | `current_combatant_id` → PV, CA, budget action / action bonus, concentration |
| **Initiative** | Liste ordonnée `initiative_order[]` — surlignage tour, `is_active`, lien fiche |
| **Effets actifs** | `active_effects[]` (ids bruts + métadonnées) |
| **Actions** | Attaque (attaquant, cible, arme `WEAPON_IDS`), sorts depuis `viewer.castable_spells[]`, messages d'aide si hors tour / pas de sorts |
| **Journal session** | Tableau **client-side** alimenté après attaque (`WeaponAttackResult`) et cast — **pas** de log serveur |
| Barre d'actions | Recharger, tour suivant, clôturer → lobby |
| Erreurs | `ErrorAlert` — 502 proxy → « API injoignable » |

### Types TypeScript (miroir DTO)

| Fichier | Source Python |
|---|---|
| `web/src/lib/types/combat.ts` | `combat_state_to_dict` |
| `web/src/lib/types/attack.ts` | `weapon_attack_result_to_dict` |
| `web/src/lib/types/sheet.ts` | `character_sheet_to_dict` (+ overlay §2.6) |
| `web/src/lib/types/character.ts` | `GET /v1/characters` (liste lobby uniquement) |

### Écarts constatés entre la demande initiale et le code réel

| Point | Constat |
|---|---|
| Référence « 943 tests » | Dépôt mesuré à **945** tests OK au 2026-08-11 — utiliser la mesure à jour pour les rapports de lot. |
| Layout maquette vs `#app` | `app.css` limite la largeur à **52rem** et centre une colonne — **incompatible** avec un HUD trois colonnes pleine largeur ; levée ou override combat requis. |
| Accent couleur | Code actuel = **bleu** ; maquette = **ambre** — changement voulu, pas une régression. |
| Grille caractéristiques (colonne droite maquette) | Présente sur **`CharacterScreen`** via `GET …/sheet`, **absente** de `CombatScreen` (pas d'appel fiche). Ne pas l'ajouter sans nouvel appel API (hors périmètre). |
| `initiative_total` | Exposé conditionnellement sur le combattant (CONTRAT §2.8) mais **non affiché** aujourd'hui — affichage autorisé si présent, interdit de l'inventer. |
| Journal avec horodatage | Maquette Figma montre des timestamps ; le journal actuel **n'en a pas** (construction locale sans horloge) — ne pas simuler d'heure serveur. |

---

## Inventaire données maquette ↔ DTO

Légende : **Existe** = affichable depuis le DTO combat ou la réponse d'action déjà consommée ; **Partiel** = donnée incomplète, filtrée par viewer, ou hors agrégat combat ; **Absent** = pas dans l'API v1 / exclus du lot.

### En-tête global (barre supérieure maquette)

| Bloc visuel maquette | Donnée | Statut | Source / remarque |
|---|---|---|---|
| Logo / titre produit « JDR ENGINE » | — | **Absent** (UI statique) | Texte de marque — pas de champ API ; libellé fixe autorisé |
| Titre campagne (« La Crypte des Ombres ») | — | **Absent** | Aucun `campaign_name` / `encounter_name` dans `CombatState` |
| Pilule **ROUND** *n* | `round_number` | **Existe** | Entier ; `0` en `preparing` |
| Pilule **Tour de :** *nom* | `current_combatant_id` + `combatants[id].display_name` | **Existe** | Ne pas déduire le tour via `turn_index` (CONTRAT §2.8) |
| Timer session (ex. `02:45:12`) | — | **Absent** | Non-objectif explicite |
| Statut « MJ en ligne » | — | **Absent** | Non-objectif ; pas d'auth / présence |

### Colonne gauche — groupe & initiative

| Bloc visuel maquette | Donnée | Statut | Source / remarque |
|---|---|---|---|
| Portrait / avatar circulaire | — | **Absent** | Non-objectif ; `image_url` existe sur fiche personnage mais **pas** sur `Combatant` |
| Nom du personnage | `display_name` | **Existe** | Toujours |
| Sous-titre classe + niveau (ex. « Mage — Niveau 5 ») | — | **Absent** du DTO combat | `class_id` / `level` existent sur **`CharacterListEntry`** (lobby) et **`CharacterSheet`** (autre route) — **ne pas fetcher** la fiche depuis le HUD sans accord API |
| Badge **CA** | `ac` | **Partiel** | Présent seulement vue MJ ou combattant « soi » ; **omis** (clé absente) pour les autres — ne jamais afficher « 0 » par défaut |
| Barre **PV** *courant/max* | `hp_current`, `hp_max` | **Partiel** | Même règle de visibilité que CA |
| Badges d'état lisibles (« BÉNI », « EMPOISONNÉ »…) | `active_effects[]` | **Partiel** | Seul `effect_id` (opaque, pas de libellé FR — CONTRAT §2.8) ; afficher l'**id** ou une dérivation **cosmétique non traduite** (ex. `bless` → badge `bless`), **pas** de mapping inventé vers des états non portés par le moteur |
| Carte combattant actif (bordure ambre) | `current_combatant_id` | **Existe** | Comparaison d'id |
| Combattant inactif / retiré (atténué) | `is_active` | **Existe** | Déjà utilisé (classe `is-inactive`) |
| Lien vers fiche | `character_id` | **Existe** | Route `#/character/{id}` déjà en place |
| Bandeau **ordre d'initiative** (jetons + score) | `initiative_order`, `display_name`, `initiative_total` | **Partiel** | Ordre et noms : oui ; **`initiative_total`** absent avant activation ou masqué — afficher seulement si clé présente |
| Surbrillance initiative = tour courant | `current_combatant_id` | **Existe** | — |

### Colonne centrale — carte / plan

| Bloc visuel maquette | Donnée | Statut | Source / remarque |
|---|---|---|---|
| Plan de salle, grille, jetons, positions | — | **Absent** | Moteur C4 inerte ; **placeholder** obligatoire, libellé explicite (ex. « Carte — non implémentée ») |
| Nom du plan (« Les Oubliettes… ») | — | **Absent** | — |
| Toggles vision / mesure / grille | — | **Absent** | Non-objectifs |

### Colonne droite — fiche active, actions, journal

| Bloc visuel maquette | Donnée | Statut | Source / remarque |
|---|---|---|---|
| Grille **6 caractéristiques** (FOR, DEX…) | — | **Absent** de l'agrégat combat | Disponible sur **`CharacterSheet`** via autre écran — **ne pas** ajouter `GET …/sheet` dans ce lot |
| Nom du personnage actif | `display_name` du tour ou du viewer | **Existe** | Tour courant : `current_combatant_id` ; viewer : `viewer.combatant_id` |
| Bouton **Attaque d'arme** | UI + `POST …/attack` | **Existe** | Formulaire attaquant / cible / `weapon_id` — conserver les champs |
| Bouton **Lancer un sort** | `viewer.castable_spells[]` + `POST …/cast` | **Existe** | Liste **serveur** ; ids bruts (`hunters_mark`, `bless`, `hex`) — pas de catalogue en dur côté client |
| Bouton **Compétences** | — | **Absent** | Pas d'endpoint compétences en combat v1 |
| Bouton **Fin de tour** | `POST …/advance-turn` | **Existe** | Bouton actuel « Tour suivant » |
| Budget d'action (action / bonus / réaction / mouvement) | `action_budget` | **Partiel** | Objet optionnel ; champs `has_action`, `has_bonus_action`, `has_reaction`, `has_movement` — aujourd'hui seuls action et bonus action sont affichés ; **étendre l'affichage** autorisé si le serveur expose le budget, sans recalcul client |
| Concentration | `concentration_spell_name`, `concentration_spell_id` | **Partiel** | Présents si applicable et visibles selon viewer |
| **Journal de combat** — texte narratif | — | **Absent** (serveur) | Pas de flux narration API |
| **Journal** — action + résultat | Journal client + blocs attaque | **Partiel** | Résumés construits localement depuis `WeaponAttackResult` et état post-cast ; pas de relecture GET pour animer |
| **Journal** — horodatage | — | **Absent** | Option : horodatage **local** `Date` au moment du push — cosmétique, pas une donnée DTO |
| Encarts « Dégâts : 28 (8d6) » stylisés | `damage` dans réponse attaque | **Partiel** | Disponible au moment de l'attaque ; journal actuel résume en texte — enrichissement visuel OK, contenu inchangé |

### Pied de page — bassin de dés

| Bloc visuel maquette | Donnée | Statut | Source / remarque |
|---|---|---|---|
| Boutons d4–d20 | — | **Absent** | Non-objectif ; pas de source API |
| Historique de jets | — | **Absent** | Non-objectif |
| Toggles torche / grille | — | **Absent** | Non-objectif |

### Données combat présentes au DTO mais absentes de la maquette / UI actuelle

| Champ | Statut | Remarque |
|---|---|---|
| `combat_id` | **Existe** | Affiché en hint — conserver accessibilité debug |
| `status` | **Existe** | `preparing` / `active` / `ended` |
| `ruleset_id` | **Existe** | Peut rester en hint discret |
| `turn_index` | **Existe** | **Ne pas** l'utiliser pour l'affichage tour (CONTRAT) |
| `started_at`, `ended_at` | **Existe** | ISO 8601 — affichage optionnel discret ; pas de timer dérivé imposé |
| `viewer.character_id`, `viewer.combatant_id` | **Existe** | Contexte viewer / sorts |
| `kind` sur combattant | **Existe** | `"player_character"` seule v1 — pas utile visuellement |
| Liste armes | `WEAPON_IDS` client | **Partiel** | Liste **fermée documentée** CONTRAT §10.5 — **ne pas** élargir ; pas un catalogue API |

### Landing page (maquette séparée)

| Bloc | Statut |
|---|---|
| Hero, features, pricing, footer | **Absent / hors périmètre** — horizon produit, non traité |

---

## Périmètre inclus

1. **Design tokens CSS** dans un fichier dédié réutilisable (proposition : `web/src/lib/styles/tokens.css` importé depuis `app.css`) :
   - Palette sombre (fonds `#0a0a0a`–`#1a1a1a`, surfaces cartes, bordures subtiles)
   - Accent **ambre** (`#f59e0b` ou dérivés cohérents avec la maquette)
   - Typographie : serif display pour titres (ex. **Playfair Display** ou fallback `Georgia`), sans-serif corps (ex. **Inter** / `system-ui`)
   - Espacements, rayons (`6px`–`8px`), ombres légères, états hover/focus/disabled
   - Variables sémantiques (`--color-accent`, `--surface-panel`, `--text-muted`, `--state-success`, `--state-danger`, etc.)

2. **Layout multi-colonnes** sur `CombatScreen`, proche de la maquette :
   - **Gauche** : liste combattants + initiative (contenu actuel regroupé)
   - **Centre** : placeholder carte **visiblement identifié**
   - **Droite** : tour / actions / journal
   - **En-tête** : statut, round, tour courant, actions globales (recharger, clôturer)
   - **Responsive dégradé** : empilement vertical acceptable &lt; ~1024px ; pas de pixel-perfect mobile exigé

3. **Composants Svelte extraits** (dossier proposé : `web/src/lib/components/combat/`) :
   - `CombatantCard.svelte` — nom, PV/CA si présents, effets ciblant ce combattant (filtrage `active_effects[].target_id`), état tour/inactif
   - `Panel.svelte` — carte à bordure (titre, slot contenu)
   - `StatusBadge.svelte` — badge compact (`effect_id`, « tour », etc.)
   - `JournalEntry.svelte` — entrée attaque / sort (summary + detail existants)

4. **Application charte** :
   - `CombatScreen.svelte` — refonte structure + styles ; logique `<script>` inchangée sauf extraction présentation
   - **Cohérence minimale** `LobbyScreen`, `CharacterScreen`, `App.svelte`, `ErrorAlert` : fond sombre, typo, boutons primaires/secondaires — **sans refonte de structure** des formulaires lobby/fiche
   - Retirer ou migrer les styles combat dupliqués (scoped `CombatScreen` → tokens + composants)

5. **Placeholder carte** : zone centrale non cliquable, message explicite + style « panneau vide » (pas d'image de carte empruntée à la maquette si asset non livré — dégradé / motif neutre suffit).

---

## Non-objectifs stricts

Ne **pas** implémenter, même partiellement :

| Exclusion | Motif |
|---|---|
| Carte tactique, grille, jetons, positions, mouvement | Moteur C4 inert ; lot map = ROADMAP lot 4 + WebSocket |
| Avatars, portraits, `image_url` | Pas sur `Combatant` ; pas de fetch fiche supplémentaire |
| Landing page publique | Horizon produit distinct |
| WebSocket, push temps réel, resync automatique | Hors contrat v1 |
| Timer de session, « MJ en ligne », multi-utilisateurs | Pas de donnée / pas d'auth |
| Bassin de dés interactif, historique de dés | Pas de source API |
| Classe + niveau sur carte combattant combat | Absent du DTO combat — pas de join client avec `GET /v1/characters` |
| Libellés d'état traduits (« BÉNI », « EMPOISONNÉ ») non fournis par le DTO | `effect_id` opaque — CONTRAT §2.8 |
| Grille de caractéristiques dans le HUD combat | Nécessiterait `GET …/sheet` — appel API nouveau |
| Typage / refonte **`spellcasting`** sur fiche | Hors périmètre |
| Toute modification **Python** (`jdr_engine/`, `interfaces/api/*.py`, tests moteur) | Lot front strict |
| Modification **`interfaces/api/static/`** | Banc statique inchangé |
| Nouvelle dépendance npm **sans accord mainteneur** | AGENTS.md §6 |
| Règles D&D côté client (calcul toucher, sorts lançables, visibilité PV) | Interdit — serveur seul arbitre |

---

## Direction artistique (tokens dérivés maquette)

### Palette

| Token sémantique | Cible maquette | Usage |
|---|---|---|
| `--color-bg-base` | ~`#0a0a0a` | Fond application |
| `--color-bg-elevated` | ~`#141414`–`#1a1a1a` | Panneaux / cartes |
| `--color-border-subtle` | gris froid ~`#2a2a2a` | Bordures cartes |
| `--color-accent` | ambre ~`#f59e0b` | CTA, surbrillance tour, chiffres clés |
| `--color-accent-muted` | ambre ~20 % opacité | Fond combattant actif |
| `--color-text-primary` | ~`#f5f5f5` | Texte principal |
| `--color-text-muted` | ~`#9ca3af` | Hints, labels |
| `--color-success` | vert ~`#22c55e` | Toucher, PV OK |
| `--color-danger` | rouge ~`#ef4444` | Dégâts, miss critique (si utilisé) |

Remplacer les variables actuelles `--current-border` / `--current-bg` (bleu) par des tokens ambre **sans casser** les écrans non migrés — migrer les références dans le même lot.

### Typographie

| Rôle | Police | Fallback |
|---|---|---|
| Titres écran / titres panneau | Serif display | `Georgia`, serif |
| Corps, labels, données | Sans-serif | `Inter`, `system-ui`, sans-serif |
| Ids techniques, jets | Monospace | `ui-monospace`, monospace |

Chargement webfont (Google Fonts ou `@fontsource`) : **acceptable** si self-contained dans `web/` ; signaler toute dépendance externe CDN dans le rapport de lot.

### Composants visuels

- **Cartes** : fond `elevated`, bordure 1px, `border-radius: 8px`, padding `--space-md`
- **Badge d'état** : pill, uppercase petit, fond accent ou sémantique
- **Barre PV** : remplissage proportionnel `hp_current/hp_max` **uniquement si les deux valeurs sont présentes**
- **Bouton primaire** : fond ambre, texte sombre ; **secondaire** : contour ambre, fond transparent
- **Placeholder carte** : bordure en pointillés ou hachures, icône/texte « Carte — à venir (lot map) »

---

## Fichiers autorisés à la modification

**Uniquement** sous `web/src/**`, plus import du fichier tokens dans la chaîne CSS existante.

Exemples attendus :

```
web/src/app.css
web/src/App.svelte
web/src/lib/styles/tokens.css          (nouveau)
web/src/lib/screens/CombatScreen.svelte
web/src/lib/screens/LobbyScreen.svelte
web/src/lib/screens/CharacterScreen.svelte
web/src/lib/components/ErrorAlert.svelte
web/src/lib/components/combat/*.svelte   (nouveaux)
```

**Interdit** : `web/package.json` sauf accord explicite ; tout le reste du dépôt.

---

## Contrats à respecter

1. **Aucune règle métier côté client** — pas de calcul de toucher, de visibilité PV, de liste de sorts, de consommation de budget : le serveur tranche ; le client affiche et envoie les POST existants.

2. **`viewer.castable_spells[]`** reste la **seule** source des boutons de sort — ids tels que renvoyés (`hunters_mark`, `bless`, `hex`). Pas de liste en dur parallèle.

3. **Visibilité conditionnelle** (CONTRAT §2.8) : champs absents ≠ zéro ; ne pas afficher CA/PV/budget si la clé manque.

4. **Tour courant** : utiliser **`current_combatant_id`**, jamais `initiative_order[turn_index]`.

5. **Armes** : conserver `WEAPON_IDS` de `web/src/lib/types/attack.ts` — pas d'élargissement non documenté.

6. **Journal** : conserver le contenu informationnel des entrées (résumés attaque/sort) ; amélioration visuelle seulement.

7. **Navigation et URLs hash** : ne pas casser `?viewer=` ni les liens `#/character/{id}`.

8. **Accessibilité minimale** : conserver `aria-label` / `aria-live` sur zones dynamiques (initiative, journal, erreurs).

---

## Critères de done

Chaque sous-lot (A, B, C) produit **un commit distinct**. Build et check s'appliquent à **chaque** commit.

```bash
cd web
npm run build    # exit 0
npm run check    # 0 erreur svelte-check + tsc
```

### Done sous-lot A — tokens (commit 1)

- `tokens.css` importé ; fond sombre, accent ambre, boutons primaire/secondaire sur **Lobby**, **Fiche**, **Combat** (structure inchangée), nav, `ErrorAlert`
- Contrainte `#app { max-width: 52rem }` levée ou contournée de façon documentée (ex. classe layout pleine largeur sur combat — peut rester en A même si le layout trois colonnes n'existe pas encore)
- **Validation visuelle obligatoire** par le mainteneur (capture ou session locale) **avant** tout travail B — voir § Découpe obligatoire
- Parcours lobby → fiche → combat existant : **aucune régression fonctionnelle**

### Done sous-lot B — layout combat (commit 2)

- `CombatScreen` restructuré trois colonnes + placeholder carte + composants extraits (structure)
- Parcours complet attaque + sort (`hunters_mark`) fonctionnel
- Contenu v1 toujours accessible (budget, concentration, effets, viewer, journal) — relocalisé acceptable

### Done sous-lot C — finitions (commit 3)

- Barres PV, badges `effect_id`, journal stylisé, responsive dégradé, nettoyage CSS legacy scoped
- Parcours manuel complet :

Avec uvicorn `:8000` + `npm run dev` `:5173`, personnages de test connus (ex. rôdeur `a505d6d5`, clerc `385022fd`) :

1. **Lobby** — créer combat 2+ persos, **Activer et jouer**
2. **Combat** — round, tour, initiative, PV/CA (vue MJ), effets si présents
3. Viewer rôdeur → tour rôdeur → **`hunters_mark`** → resync + journal
4. **Attaquer** → journal + resync PV
5. **Tour suivant**, **Clôturer** → lobby OK
6. Aucune **régression de contenu** vs v1

### Non-régression moteur

Aucun fichier hors `web/src/**` modifié — **945 tests** moteur inchangés (non relancés obligatoirement par l'agent front, mais aucun commit Python).

### Livrable documentaire agent (par sous-lot)

Rapport court : fichiers touchés, capture ou description visuelle, écarts vs maquette. **Lot A** : signaler explicitement « prêt pour validation mainteneur » et **s'arrêter**.

---

## Dettes assumées et suites (nommées, non traitées)

| Suite | Dépendance | Notes |
|---|---|---|
| **Carte tactique** | Moteur C4, WebSocket lot 4 | Remplace le placeholder |
| **Avatars** | `image_url` ou champ combattant | Fetch fiche ou enrichissement DTO |
| **Libellés d'effets** | Compendium / couche i18n API | Aujourd'hui `effect_id` brut |
| **Classe / niveau en combat** | Enrichissement `Combatant` ou join serveur | Éviter N+1 client |
| **Grille caractéristiques HUD** | Décision produit : embed `sheet` partiel dans GET combat vs panneau latéral linked | Appel API supplémentaire |
| **Journal serveur + timestamps** | EventBus / endpoint log | Aujourd'hui journal session navigateur |
| **Landing marketing** | Écran public séparé | Maquette Figma distincte |
| **Bassin de dés** | Endpoint jets génériques | Hors contrat v1 |
| **Timer / présence MJ** | Auth, sessions | Hors banc local |
| **Thème clair** | Second jeu de tokens | Maquette = sombre only ; `color-scheme` à trancher |

---

## Découpe obligatoire A → B → C

L'épic se livre en **trois sous-lots séquentiels**, chacun = **un commit**. Ce n'est pas un plan de repli : **ne pas fusionner A+B+C** en une seule livraison.

| Sous-lot | Commit | Contenu | Point d'arrêt |
|---|---|---|---|
| **A — Fondations** | 1 | `tokens.css`, import `app.css`, levée `max-width` `#app`, skin nav + `ErrorAlert` + boutons globaux sur Lobby / Fiche / Combat (**structure inchangée**) | **Stop ici** — validation mainteneur requise |
| **B — Layout combat** | 2 | Composants combat + restructuration trois colonnes + placeholder carte | Parcours attaque + sorts OK |
| **C — Finitions** | 3 | Barres PV, badges effets, journal stylisé, responsive, nettoyage CSS scoped | Critères de done complets (§ Critères de done) |

### Règle de enchaînement (non négociable)

**Le sous-lot B ne commence qu'après** :

1. **Commit** du sous-lot A poussé ou livré sur la branche d'intégration ;
2. **Validation visuelle** du mainteneur sur les trois écrans (lobby, fiche, combat en layout v1) — fond sombre, ambre, typo, boutons cohérents ;
3. **Accord explicite** du mainteneur pour enchaîner B.

L'agent qui implémente A **s'arrête** après le commit A et signale « prêt pour validation visuelle ». **Interdit** d'entamer la restructuration `CombatScreen` dans le même commit ou la même session sans ce feu vert.

**Pourquoi** : les tokens seuls changent déjà l'apparence des trois écrans — le mainteneur voit quelque chose de concret avant d'engager le layout. Si B dérape, on n'a pas un demi-HUD trois colonnes cassé : on a une charte validée sur une structure connue.

### Checklist validation visuelle A (mainteneur)

- [ ] Lobby : fond sombre, boutons primaire/secondaire lisibles, formulaires inchangés fonctionnels
- [ ] Fiche personnage : même charte, grille caractéristiques lisible
- [ ] Combat (layout v1 mono-colonne) : même charte, HUD existant intact fonctionnellement
- [ ] Nav + messages d'erreur (`ErrorAlert`, 502 API injoignable) cohérents
- [ ] `npm run build` et `npm run check` OK

---

## Références code (points d'ancrage)

| Sujet | Fichier |
|---|---|
| HUD actuel | `web/src/lib/screens/CombatScreen.svelte` |
| Types combat | `web/src/lib/types/combat.ts` |
| Types attaque | `web/src/lib/types/attack.ts` |
| API client | `web/src/lib/api/combat.ts` |
| Contrat viewer / effets / sorts | `docs/api/CONTRAT.md` §2.8, §2.9 |
| Stack front | `docs/adr/ADR-007-stack-client-web.md` |
| Lancement local | `web/README.md` |
