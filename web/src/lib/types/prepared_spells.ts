/** Miroir de ``prepared_spells_view_to_dict`` (API v1). */

export interface PreparedSpellsView {
  character_id: string;
  eligible: boolean;
  prepared_rechoice_pending: boolean;
  character_name?: string;
  class_id?: string;
  level?: number;
  quota?: number;
  srd_quota?: number;
  pool?: string[];
  domain_spells?: string[];
  spells_prepared?: string[];
  paladin_no_slots_notice?: string | null;
  pool_capped_notice?: string | null;
}

export interface PreparedSpellsRequest {
  spell_ids: string[];
}
