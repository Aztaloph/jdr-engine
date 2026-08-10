/** Entrée minimale de GET /v1/characters (banc de test). */
export interface CharacterListEntry {
  character_id: string;
  name: string;
  class_id: string;
  level: number;
  race_id: string;
}

export interface CharacterListResponse {
  characters: CharacterListEntry[];
}
