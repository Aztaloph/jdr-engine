/**
 * Miroir TypeScript de ``character_sheet_to_dict`` (+ overlay combat §2.6).
 */
import type { ActiveEffect } from "./combat";

export type AbilityId = "str" | "dex" | "con" | "int" | "wis" | "cha";

export const ABILITY_IDS: readonly AbilityId[] = [
  "str",
  "dex",
  "con",
  "int",
  "wis",
  "cha",
] as const;

export interface SavingThrowEntry {
  ability_id: AbilityId;
  modifier: number;
  proficient: boolean;
}

export interface ProficientSkill {
  id: string;
  label: string;
}

export interface CharacterSheet {
  character_id: string;
  name: string;
  race_name: string;
  class_name: string;
  level: number;
  hp_current: number;
  hp_max: number;
  ac: number;
  ability_scores: Record<AbilityId, number>;
  ability_modifiers: Record<AbilityId, number>;
  ability_labels: Record<AbilityId, string>;
  proficiency_bonus: number;
  saving_throws: SavingThrowEntry[];
  proficient_skills: ProficientSkill[];
  /** Présent uniquement si le personnage est engagé dans un combat ouvert. */
  active_effects?: ActiveEffect[];
  // Surplus API — non affiché lot maîtrises
  owner_id?: string;
  ruleset_id?: string;
  race_id?: string;
  class_id?: string;
  xp?: number;
  image_url?: string | null;
  ability_scores_base?: Record<AbilityId, number>;
  hit_die?: string;
  speed?: number;
  initiative?: number;
  hit_dice_remaining?: number;
  hit_dice_total?: number;
  specialization_id?: string | null;
  specialization_label?: string | null;
  fighting_style_id?: string | null;
  fighting_style_label?: string | null;
  armor_proficiencies?: string[];
  weapon_proficiencies?: string[];
  damage_resistances?: string[];
  trait_names?: string[];
  innate_spells?: unknown[];
  class_features?: unknown[];
  spellcasting?: unknown;
}
