/**
 * Miroir TypeScript de ``weapon_attack_result_to_dict`` (contrat §2.7).
 */

export const WEAPON_IDS = [
  "longsword",
  "shortsword",
  "shortbow",
  "longbow",
] as const;

export type WeaponId = (typeof WEAPON_IDS)[number];

export interface AttackHitOutcome {
  hit: boolean;
  critical: boolean;
  automatic_miss: boolean;
  target_ac: number;
}

/** Sous-ensemble du DTO d20 exposé par l'API — champs utiles à l'affichage. */
export interface AttackD20Result {
  rolls: number[];
  kept_value: number;
  modifier: number;
  total: number;
  natural_20: boolean;
  natural_1: boolean;
}

export interface AttackRollBlock {
  d20: AttackD20Result;
  outcome: AttackHitOutcome;
}

export interface DamageBlock {
  damage_dealt: number;
  hp_before?: number;
  hp_after?: number;
  notation?: string;
  rolls?: number[];
  modifier?: number;
  total?: number;
  critical?: boolean;
}

export interface AttackTargetBlock {
  combatant_id: string;
  hp_current?: number;
  hp_max?: number;
}

export interface WeaponAttackResult {
  attack: AttackRollBlock;
  damage: DamageBlock | null;
  target: AttackTargetBlock;
}
