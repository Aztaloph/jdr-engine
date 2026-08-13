# Cadrage lot 6b — scène statique (carte + colonne droite)

| Attribut | Valeur |
|---|---|
| **Statut** | **Proposition** — pas d'implémentation avant passage en **Accepté** |
| **Date** | 2026-08-13 |
| **Prérequis** | Lot **6a** map REST ✅ ([`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md)) ; lot 4 HUD visuel ✅ ; [`VISION.md`](../../VISION.md) livré (livrable 1) |
| **Successeur** | Lot **6c** WebSocket ([`BRIEF_LOT6C_WEBSOCKET.md`](BRIEF_LOT6C_WEBSOCKET.md)) |
| **Hors périmètre de ce document** | Implémentation, gestion d'assets, moteur, API |

---

## 1. Mission

Rendre l'écran de combat **visuellement conforme à la maquette Figma** sur **trois points structurels**, et **préparer techniquement** l'affichage d'une carte (couche fond + grille transparente), **sans introduire aucun mécanisme de gestion d'assets**.

| Priorité | Règle |
|---|---|
| 1 | Comportement **6a préservé** (move, attaque, sorts, tour) |
| 2 | **`web/src/**` uniquement** — zéro Python |
| 3 | Préparation visuelle compatible [`VISION.md`](../../VISION.md) **§4.0** (future scène) — **sans** implémenter le modèle scène |
| 4 | Maquette Figma = cible layout — **pas** de refonte design system |

---

## 2. Contrats à respecter

| Document | Obligation lot 6b |
|---|---|
| [`VISION.md`](../../VISION.md) **§4.0** | La cible long terme est une **scène** (carte hors-combat majoritaire). Ce lot améliore la **carte en mode rencontre** sur l'écran combat actuel — couche `background-image` + grille calque = **première brique visuelle** réutilisable quand la scène unifiée existera. **Ne pas** construire le modèle scène/campagne. |
| [`VISION.md`](../../VISION.md) **§1** | Assets (upload, calage, échelle) = **arbitrage ouvert** — **interdits** dans ce lot. |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | Logique move / API **inchangée** ; pas de règles D&D client. |
| [`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md) | Classification ①–④ : données réelles conservées ; pas de fonctionnalité retirée. |
| [`AGENTS.md`](../../AGENTS.md) §6 | Aucune modification moteur / API. |

**Garde-fou** : introduction d'un sélecteur d'image, d'une API asset ou d'un mode hors-combat → **critère d'arrêt AGENTS.md #6**.

---

## 3. Constat de départ (état après 6a — vérifié 2026-08-13)

| Zone | Écart mesuré vs maquette |
|---|---|
| **Carte** | Grille 20×20 **collée en haut à gauche** du conteneur scroll ; **vide important** à droite et en dessous |
| **Cellules** | `--cell-size: 2rem` **fixe** ; bordures opaques sur fond `#0b0a08` **plat** — empêche toute image de fond visible |
| **Colonne droite** | Trois `<select>` attaque, **chips de sorts** et bloc **« Outils MJ (banc de test) »** toujours visibles — la maquette montre **quatre boutons empilés** compacts |
| **Référence visuelle** | `MapPlaceholder.svelte` — textures pierre / dégradé ambre (**non branché** depuis 6a) |

Fichiers concernés : `TacticalMap.svelte`, `CombatScreen.svelte` (panneau « Actions rapides »).

---

## 4. Périmètre — trois axes

### 4.1 Axe A — Dimensionnement

| Attendu | Détail |
|---|---|
| Remplissage cadre | La carte **remplit son cadre** (colonne centrale HUD) à **±10 px** sur les deux axes |
| Ratio | **Carré préservé** — la zone jouable reste un carré inscrit dans le cadre |
| Taille de case | **Dérivée de l'espace disponible** (`min(width, height) / grid.width`) — **pas** de `2rem` en dur comme seule source |
| Cadre | Bordure selon maquette Figma ; contenu **centré** dans le panneau map |
| Scroll | Éviter le scroll interne si la grille tient dans le cadre à 1280px ; scroll acceptable en repli si grille > viewport |

### 4.2 Axe B — Grille comme calque

| Couche | Rôle |
|---|---|
| **Fond** | `background-image` sur le conteneur scène — **constante en dur** (`web/src/…` — un seul asset de test) |
| **Fallback** | Si asset absent : **dégradé sombre** inspiré `MapPlaceholder` (pierre / ambre) — **jamais** noir plat `#0b0a08` seul |
| **Grille** | Cellules **transparentes** ; liseré **8–12 %** opacité (aligné maquette) |
| **Jetons** | Positionnés en **`absolute` + pourcentage** par rapport au carré de jeu — alignés sur `position` API (x/y grille) |
| **Interaction** | Clic move **conservé** — hit-test sur calque grille transparente ou overlay clic (implémentation libre tant que 6a OK) |

**Constante indicative** :

```typescript
// Exemple — chemin unique, non paramétrable
export const SCENE_TEST_MAP_URL = "/assets/maps/test-scene.jpg";
```

Aucune UI pour changer cette constante.

### 4.3 Axe C — Colonne droite

| Élément actuel | Traitement |
|---|---|
| Formulaire **Attaque d'arme** (3 selects + bouton) | **Replié** derrière un bouton « Attaque d'arme » — déplié au clic |
| Bloc **Lancer un sort** (chips + selects) | **Replié** derrière un bouton « Lancer un sort » |
| **Compétences** (placeholder lot 4) | Inchangé ou intégré à la pile de boutons maquette |
| **Fin de tour** | Bouton visible (équivalent maquette) |
| **Outils MJ (banc de test)** | Panneau **dépliable**, **replié par défaut** |
| Réactions / préparation sorts | **Aucune fonctionnalité retirée** — repli ou sous-panneau acceptable |

**Cible visuelle** : colonne droite **sans scroll vertical** à la **résolution de référence 1280×800** (viewport combat, 3 colonnes visibles — cf. [`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md) §12).

---

## 5. Non-objectifs (explicitement hors lot)

| Exclusion | Raison |
|---|---|
| Upload, sélection, calage, échelle ou offset d'image | Aucun mécanisme ; aucun placeholder d'API |
| Mode **hors-combat**, scènes persistantes, jetons hors rencontre | [`VISION.md`](../../VISION.md) §4.0 — lots dédiés |
| Portraits jetons, brouillard, LoS, mesure, vision | Placeholders lot 4 / lots terrain |
| Modification **moteur** ou **API** | Lot front strict |
| Refonte **design system** (`tokens.css`, typo globale) | Hors périmètre — ajustements locaux map/panneaux OK |
| **WebSocket** | Lot **6c** |
| Agent **Fable 5** obligatoire | Lot structurel + layout — agent standard ; Fable optionnel **après** 6b si polish pixel-perfect demandé |

---

## 6. Pièges — interdits

| Piège | Alternative |
|---|---|
| Hardcoder une fausse grille sans données API | Positions réelles 6a |
| Retirer attaque / sorts / outils MJ | Replier, ne pas supprimer |
| Introduire `input type=file"` ou route asset | Constante unique |
| Casser `postCombatMove` / hit-test | Tester parcours §8 |
| Refonte tokens globaux | Styles scoped map + colonne droite |
| WebSocket « en passant » | Lot 6c |

---

## 7. Fichiers autorisés

```
web/src/lib/components/combat/TacticalMap.svelte
web/src/lib/screens/CombatScreen.svelte
web/src/lib/components/combat/*.svelte     (extract panneaux repli si pertinent)
web/src/assets/**                          (un asset test — nouveau)
web/public/**                              (alternative asset statique Vite)
```

**Interdit** : tout hors `web/src/**` (+ asset sous `web/`).

---

## 8. Critères de done (mesurables)

1. La grille **remplit son cadre** à **±10 px** (largeur et hauteur utiles du panneau map).
2. Une image **arbitraire** substituée à la constante s'affiche **sous** les jetons et **sous** le liseré grille.
3. Colonne droite **sans scroll vertical** à **1280×800** (Chrome, combat actif, viewer renseigné).
4. **Aucun** mécanisme de sélection ou upload d'image.
5. **`npm run build`** et **`npm run check`** — exit 0.
6. **Parcours manuel sans régression** (§9).
7. **Aucun** fichier Python modifié.

---

## 9. Parcours manuel obligatoire

Lobby → créer → activer → combat `#/combat/{id}?viewer=` →

1. Vérifier carte centrée, cadre rempli, fond visible (image ou dégradé).
2. **Déplacer** un jeton (move 6a).
3. **Attaquer** (formulaire replié puis déplié).
4. **Fin de tour**.
5. Ouvrir **Outils MJ** (replié par défaut) — heal / repos si utilisé.

---

## 10. Dettes assumées (à documenter en fin de lot)

| Dette | Lot futur |
|---|---|
| Image **non paramétrable** (constante unique) | Gestion assets / scène |
| Jetons en **initiales** (pas de portraits) | Assets compendium |
| **Pas de calage** grille ↔ image (offset/scale) | Éditeur scène / MJ |
| Écran combat ≠ page scène unifiée | Lot scène [`VISION.md`](../../VISION.md) §4.0 |

---

## 11. Découpe proposée (si > une session)

Périmètre **non réductible** — decoupage en **deux commits** recommandé :

| Phase | Contenu | Critère intermédiaire |
|---|---|---|
| **6b-1 — Carte** | Axes A + B (`TacticalMap.svelte`, asset test, dimensionnement, calque) | Critères done §8.1–8.2 + move OK |
| **6b-2 — Colonne droite** | Axe C (`CombatScreen.svelte`, panneaux repli) | Critères §8.3–8.6 |

**6b-1** livrable seul pour validation visuelle carte ; **6b-2** ensuite.

---

## 12. Agent recommandé

| Agent | Quand |
|---|---|
| **Agent standard** | Implémentation 6b (structure, layout, asset constant) |
| **Fable 5** | Optionnel **après** 6b si écart pixel-perfect maquette > seuil mainteneur |

---

## 13. Références

| Document | Rôle |
|---|---|
| [`VISION.md`](../../VISION.md) §4.0 | Scène vs rencontre — préparation carte |
| [`BRIEF_LOT6_MAP_TACTIQUE.md`](BRIEF_LOT6_MAP_TACTIQUE.md) | 6a fonctionnel |
| [`BRIEF_FABLE_AFFICHAGE.md`](BRIEF_FABLE_AFFICHAGE.md) | Maquette 3 colonnes, 1280px |
| `MapPlaceholder.svelte` | Référence dégradé / décor |
| `TacticalMap.svelte` | Point de départ 6a |

---

## 14. Validation

| Rôle | Action |
|---|---|
| Mainteneur | Passer statut **Proposition** → **Accepté** |
| Agent | Démarrer après **Accepté** |

**Phrase de mission (copier-coller)** :

> Implémente le lot 6b scène statique : dimensionnement carte (ratio carré, case dérivée), calque fond + grille transparente + jetons en %, colonne droite repliée (attaque, sorts, outils MJ). Constante image unique, fallback dégradé. Aucun Python, aucun upload, aucune API. Comportement 6a intact. Suis `docs/web/BRIEF_LOT6B_SCENE_STATIQUE.md` et `VISION.md` §4.0.
