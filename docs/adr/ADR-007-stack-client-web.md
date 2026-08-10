# ADR-007 — Stack du client web

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-08-08 |
| **Décideurs** | Lead Architect, Product Owner |
| **Contexte** | ÉTAPE 7 — Client Web ; VISION.md §4, D1/D2 ; API REST v1 (`interfaces/api/`, `docs/api/CONTRAT.md`) |

---

## Contexte

Le développement sur Discord a été abandonné. Le moteur n'a plus de client permettant de vérifier visuellement son comportement, ce qui rend les tests manuels difficiles. Un client web devient nécessaire, à la fois comme surface de test et comme interface cible du produit.

Deux besoins fonctionnels contraignent le choix :

1. **Map dynamique multi-utilisateur** mise à jour en temps réel ;
2. **Affichage différencié par joueur** — chaque joueur ne voit que ce que son personnage a découvert, le MJ voit l'intégralité. Cette différenciation doit être activable ou désactivable par le MJ lors de la préparation du scénario, et **n'est pas requise immédiatement**.

Le moteur reste une API pure (ADR-004, VISION.md D3/D4) ; cette décision porte **uniquement** sur la couche client et ses contraintes sur les contrats de sortie.

---

## Options envisagées

### 1. Templates serveur (Jinja) rendus par FastAPI

Pas de build, pas de CORS.

**Écarté** : convient mal aux états qui changent en continu ; la map imposerait du JavaScript manuel en marge des templates.

### 2. HTMX avec templates serveur

Pas de bundler, bonne ergonomie pour les listes et formulaires.

**Écarté** : cède sur la map dynamique (pions, zoom, canvas), ce qui conduirait à mélanger deux paradigmes dans une même page.

### 3. SPA JavaScript avec build

**Retenu** (voir Décision).

---

## Décision

Le client web est développé comme une **SPA en Svelte**, buildée avec **Vite**, servie **séparément** de l'API en développement.

| Canal | Usage |
|---|---|
| **REST** | États ponctuels — fiche, lobby, actions de combat |
| **WebSocket** | Map temps réel — **prévu, non implémenté** à ce stade |

**Svelte** est préféré à React pour un volume de code plus faible et l'absence d'écosystème de gestion d'état imposé, adaptés à un développement solo.

Le découpage de livraison front (lots 0–4) est consigné dans [`ROADMAP.md`](../../ROADMAP.md) — section **Piste client Web**.

---

## Conséquences

### Positives

- Un seul paradigme UI pour fiche, combat et map (composants Svelte + canvas/WebSocket).
- Alignement avec VISION.md §4 (client Web interface de jeu), **D7 révisé** (moteur prioritaire, client en parallèle) et ADR-003 (WebSocket push depuis l'API).
- Surface de test manuelle dès le lot 1 (fiche via `/v1/characters/{id}/sheet`).
- Le développement parallèle du client n'est pas une dérogation : c'est l'application de **D7** (révision 2026-08-08) — le retour visuel fait partie de la boucle de vérification du moteur.

### Négatives / contraintes

- **CORS** devra être activé côté FastAPI dès que le front appellera l'API depuis son serveur de développement (lot 1 front — hors périmètre de cet ADR).
- **Deux processus** en développement (API + serveur Vite) et **deux artefacts** à déployer.
- **Contrainte structurante immédiate** : toute fonction sérialisant un état de jeu à destination d'un client **doit accepter** un paramètre identifiant le destinataire de la vue (par exemple `viewer`), **même si ce paramètre est ignoré** dans un premier temps. Cela permet d'introduire l'affichage différencié par joueur sans modifier les appelants ni le protocole.
- **Jalon identifié, non planifié** : le multi-poste réel exigera une notion d'utilisateur authentifié, ou au minimum un lien joueur → personnage. L'API n'a aujourd'hui aucune authentification et accepte les `character_id` sans vérifier l'émetteur. Ce point devra être traité avant l'ouverture du jeu à plusieurs machines (lot 4 map / ADR futur auth).

### Non impacté par cette décision

- Le **Game Engine** et le **Rule Engine** — aucun import Svelte/Vite côté `jdr_engine/`.
- Le **Combat Engine** reste API moteur pure (ADR-004) ; le HUD de combat vit côté client.
- Discord reste social/notifications (VISION.md §3, D2).

---

## Documents associés

- [`VISION.md`](../../VISION.md) — §3 Discord, §4 client Web, **D7** (moteur prioritaire, client en parallèle — révisé 2026-08-08)
- [`ROADMAP.md`](../../ROADMAP.md) — section **Piste client Web**
- [`docs/api/CONTRAT.md`](../api/CONTRAT.md) — contrat REST v1 consommé par le front
- [ADR-003](ADR-003%20-%20Pourquoi%20utiliser%20un%20EventBus.md) — WebSocket push
- [ADR-004](ADR-004-modele-combat.md) — combat moteur pur
