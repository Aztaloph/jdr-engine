/** Présentation visuelle du journal combat — données API uniquement. */

export type JournalNameTone = "self" | "ally" | "foe";

export type JournalChipVariant =
  | "damage"
  | "roll"
  | "success"
  | "fail"
  | "info"
  | "system";

export interface JournalChip {
  label: string;
  variant: JournalChipVariant;
}

export interface JournalSegment {
  text: string;
  tone: JournalNameTone | "plain" | "muted";
}

export interface JournalPresentationInput {
  kind: "attack" | "spell" | "system";
  summary: string;
  detail: string;
  event_type: string;
}

export interface JournalPresentation {
  segments: JournalSegment[];
  chips: JournalChip[];
  icon: "sword" | "sparkle" | "shield" | "next" | "scroll" | "wand";
}

function chip(
  label: string,
  variant: JournalChipVariant,
): JournalChip {
  return { label, variant };
}

function buildSegments(
  summary: string,
  nameTones: Map<string, JournalNameTone>,
): JournalSegment[] {
  if (!summary.trim()) {
    return [];
  }

  const names = [...nameTones.keys()].sort((a, b) => b.length - a.length);
  if (names.length === 0) {
    return [{ text: summary, tone: "plain" }];
  }

  const segments: JournalSegment[] = [];
  let cursor = 0;

  while (cursor < summary.length) {
    let matched: { name: string; index: number } | null = null;

    for (const name of names) {
      const index = summary.indexOf(name, cursor);
      if (index === cursor) {
        matched = { name, index };
        break;
      }
    }

    if (matched) {
      segments.push({
        text: matched.name,
        tone: nameTones.get(matched.name) ?? "ally",
      });
      cursor += matched.name.length;
      continue;
    }

    let nextNameAt = summary.length;
    for (const name of names) {
      const index = summary.indexOf(name, cursor + 1);
      if (index !== -1 && index < nextNameAt) {
        nextNameAt = index;
      }
    }

    segments.push({
      text: summary.slice(cursor, nextNameAt),
      tone: "plain",
    });
    cursor = nextNameAt;
  }

  return segments.length > 0 ? segments : [{ text: summary, tone: "plain" }];
}

function chipsFromEntry(entry: JournalPresentationInput): JournalChip[] {
  const { summary, detail, event_type: eventType } = entry;
  const chips: JournalChip[] = [];

  if (eventType === "AttackRollResolved") {
    if (detail) {
      chips.push(chip(`Jet : ${detail}`, "roll"));
    }
    if (summary.includes("critique")) {
      chips.push(chip("Critique", "damage"));
    }
    if (summary.includes("automatiquement")) {
      chips.push(chip("Échec automatique", "fail"));
    }
    return chips;
  }

  if (eventType === "DamageDealt") {
    const damageMatch = summary.match(/subit\s+(\d+)\s+dégâts/i);
    if (damageMatch) {
      chips.push(chip(`Dégâts : ${damageMatch[1]}`, "damage"));
    }
    const diceMatch = detail.match(/·\s*([^·]+?)\s*·/);
    if (diceMatch?.[1]?.trim()) {
      chips.push(chip(diceMatch[1].trim(), "roll"));
    }
    const hpMatch = detail.match(/PV\s+(\d+)→(\d+)/);
    if (hpMatch) {
      chips.push(chip(`PV ${hpMatch[1]} → ${hpMatch[2]}`, "info"));
    }
    return chips;
  }

  if (eventType === "SavingThrowResolved") {
    const succeeded = summary.includes("réussit");
    chips.push(
      chip(
        succeeded ? "Sauvegarde réussie" : "Sauvegarde échouée",
        succeeded ? "success" : "fail",
      ),
    );
    const dcMatch = detail.match(/DD\s+(\d+)/);
    if (dcMatch) {
      chips.push(chip(`DD ${dcMatch[1]}`, "info"));
    }
    const saveMatch = detail.match(/jet\s+(\d+)/i);
    if (saveMatch) {
      chips.push(chip(`Jet ${saveMatch[1]}`, "roll"));
    }
    const dmgMatch = detail.match(/dégâts\s+(\d+)/i);
    if (dmgMatch) {
      chips.push(chip(`Dégâts ${dmgMatch[1]}`, "damage"));
    }
    return chips;
  }

  if (eventType === "SpellCast") {
    if (detail) {
      chips.push(chip(detail, "info"));
    }
    return chips;
  }

  if (eventType === "TurnStarted" && detail) {
    chips.push(chip(detail, "system"));
    return chips;
  }

  if (eventType === "RoundStarted" && detail) {
    chips.push(chip(detail, "system"));
    return chips;
  }

  if (detail.trim()) {
    chips.push(chip(detail, entry.kind === "system" ? "system" : "info"));
  }

  return chips;
}

function iconFromEntry(entry: JournalPresentationInput): JournalPresentation["icon"] {
  switch (entry.event_type) {
    case "AttackRollResolved":
    case "DamageDealt":
      return "sword";
    case "SpellCast":
    case "SavingThrowResolved":
      return "sparkle";
    case "TurnStarted":
    case "RoundStarted":
      return "next";
    case "CombatStarted":
    case "CombatEnded":
      return "scroll";
    default:
      return entry.kind === "spell" ? "sparkle" : entry.kind === "attack" ? "sword" : "wand";
  }
}

export function presentJournalEntry(
  entry: JournalPresentationInput,
  nameTones: Map<string, JournalNameTone>,
): JournalPresentation {
  return {
    segments: buildSegments(entry.summary, nameTones),
    chips: chipsFromEntry(entry),
    icon: iconFromEntry(entry),
  };
}
