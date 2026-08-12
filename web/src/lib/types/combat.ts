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
  has_movement: boolean;
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
}

export interface ActiveEffect {
  effect_id: string;
  source_id: string;
  target_id: string;
  applied_at_round: number;
  expiry_mode: ExpiryMode;
  duration_rounds?: number;
}

/** Présent lorsque la requête inclut ``?viewer=character_id``. */
export interface CombatViewerContext {
  character_id: string;
  combatant_id: string | null;
  castable_spells: string[];
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
