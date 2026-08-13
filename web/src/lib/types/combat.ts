/**
 * Miroir TypeScript de ``combat_state_to_dict`` (jdr_engine/application/dto/output_serializers.py).
 * Champs restreints par ``viewer`` : optionnels — présence = droit de voir, pas supposition client.
 */

export type CombatStatus = "preparing" | "active" | "ended";

export type ExpiryMode = "concentration" | "rounds" | string;

/**
 * Identifiants de caractéristiques — alignés sur le compendium / fiche personnage.
 */
export type AbilityId = "str" | "dex" | "con" | "int" | "wis" | "cha";

export const COMBAT_ABILITY_IDS: readonly AbilityId[] = [
  "str",
  "dex",
  "con",
  "int",
  "wis",
  "cha",
] as const;

/** Budget d'action tour — présent seulement si le serveur l'expose pour ce combattant. */
export interface ActionBudget {
  has_action: boolean;
  has_bonus_action: boolean;
  has_reaction: boolean;
  /** Pieds de mouvement restants pour le tour (lot 8). */
  movement_remaining_ft?: number;
}

/** Case de grille — aligné sur ``GridPosition.to_dict`` moteur. */
export interface GridPosition {
  x: number;
  y: number;
}

/** Dimensions de la carte — aligné sur ``CombatGrid.to_dict`` moteur. */
export interface CombatGrid {
  width: number;
  height: number;
}

/**
 * Combattant dans la map ``combatants`` (clé = ``combatant_id``).
 * ``initiative_total`` absent en lobby ``preparing`` avant activation.
 */
export interface Combatant {
  combatant_id: string;
  display_name: string;
  kind: string;
  character_id: string;
  is_active: boolean;
  initiative_total?: number;
  hp_current?: number;
  hp_max?: number;
  ac?: number;
  concentration_spell_id?: string;
  concentration_spell_name?: string;
  action_budget?: ActionBudget;
  /** Présents si le viewer peut voir la fiche détaillée (MJ ou propre PJ). */
  ability_scores?: Partial<Record<AbilityId, number>>;
  ability_modifiers?: Partial<Record<AbilityId, number>>;
  ability_labels?: Partial<Record<AbilityId, string>>;
  class_id?: string;
  class_name?: string;
  level?: number;
  race_name?: string;
  /** Présent si combat actif et géométrie initialisée (lot 8). */
  position?: GridPosition | null;
}

export interface ActiveEffect {
  effect_id: string;
  source_id: string;
  target_id: string;
  applied_at_round: number;
  expiry_mode: ExpiryMode;
  duration_rounds?: number;
}

/** Vue incantation — alignée sur ``spellcasting_view_to_dict`` (fiche / combat viewer). */
export interface SpellcastingView {
  ability?: string;
  pact_magic?: boolean;
  slots_max: Record<string, number>;
  slots_remaining: Record<string, number>;
  concentration?: {
    spell_id?: string;
    spell_name?: string;
  } | null;
  cantrips_known?: string[];
  spells_prepared?: string[];
  spells_known?: string[];
  spellbook?: string[];
  domain_spells?: string[];
  /** True après repos long — re-préparation requise (clerc, druide, paladin, magicien). */
  prepared_rechoice_pending?: boolean;
}

/** Présent lorsque la requête inclut ``?viewer=character_id``. */
export interface CombatViewerContext {
  character_id: string;
  combatant_id: string | null;
  castable_spells: string[];
  /** Sorts action bonus — overlay (ex. ``hunters_mark``) + résolus (ex. ``spiritual_weapon``). */
  castable_bonus_spells: string[];
  /** Réactions overlay (ex. ``shield``) — hors tour propre. */
  castable_reaction_spells: string[];
  /** Emplacements et listes dérivées de la fiche ; absent si non-lanceur. */
  spellcasting?: SpellcastingView | null;
}

export interface CombatState {
  combat_id: number | null;
  status: CombatStatus;
  ruleset_id: string;
  round_number: number;
  turn_index: number;
  /** Slot de tour courant (ordre figé) — null si hors bornes ou ordre vide. */
  current_combatant_id: string | null;
  /** Ordre d'initiative — liste de ``combatant_id`` (pas de ``character_id``). */
  initiative_order: string[];
  combatants: Record<string, Combatant>;
  /** Présent si combat actif — absent en ``preparing``. */
  grid?: CombatGrid | null;
  active_effects: ActiveEffect[];
  started_at: string | null;
  ended_at: string | null;
  viewer?: CombatViewerContext;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export type LoadError =
  | { kind: "api"; status: number; code: string; message: string }
  | { kind: "network"; message: string };

/** Entrée journal — ``GET /v1/combats/{id}/events``. */
export interface CombatJournalEntry {
  log_id: number;
  kind: "attack" | "spell" | "system";
  summary: string;
  detail: string;
  event_type: string;
  created_at: string;
}
