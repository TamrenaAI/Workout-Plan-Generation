/**
 * Ports frontend/src/pages/plan.js's parsePlanToHtml/renderPlanTable to a
 * typed block structure instead of HTML strings, since React Native has no
 * raw-HTML rendering. The agents write a fairly consistent markdown subset
 * (### headings, **bold** labels, pipe tables, "- " bullet lists — see
 * prompts/plan_assembler.md's session format) that this walks line-by-line.
 *
 * Sections are grouped by heading. dayNumber is set when a heading matches
 * "Day {N}" (e.g. "Day 1 — Push: Chest Focus") — the mobile screens use
 * this to pick which day's exercises to show, since the backend has no
 * concept of which real calendar date "Day N" falls on.
 */

export type PlanBlock =
  | { type: 'note'; label: string; text: string }
  | { type: 'table'; header: string[]; rows: string[][] }
  | { type: 'list'; items: string[] }
  | { type: 'paragraph'; text: string };

export interface PlanSection {
  title: string;
  dayNumber: number | null;
  blocks: PlanBlock[];
}

export function parsePlanMarkdown(markdown: string): PlanSection[] {
  const lines = markdown.split('\n');
  const sections: PlanSection[] = [];
  let current: PlanSection | null = null;
  let i = 0;

  function pushBlock(block: PlanBlock) {
    if (!current) {
      current = { title: '', dayNumber: null, blocks: [] };
      sections.push(current);
    }
    current.blocks.push(block);
  }

  while (i < lines.length) {
    const line = lines[i];

    // "### Day 1 — Push: Chest Focus" or "### Weekly Volume Summary". The
    // memory file's own "## Weekly Schedule"/"## Full Workout Plan" section
    // marker is skipped — it's a wrapper heading, not a day or sub-section.
    const heading = line.match(/^#{2,3}\s+(.*)/);
    if (heading) {
      const title = heading[1].trim();
      i++;
      if (/^(weekly schedule|full workout plan)$/i.test(title)) continue;
      const dayMatch = title.match(/^Day\s+(\d+)/i);
      current = { title, dayNumber: dayMatch ? parseInt(dayMatch[1], 10) : null, blocks: [] };
      sections.push(current);
      continue;
    }

    // Pipe table — consume every consecutive "|"-prefixed line as one table.
    if (line.trim().startsWith('|')) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      const table = parseTable(tableLines);
      if (table) pushBlock(table);
      continue;
    }

    // "**Label:** text" — e.g. "**Warm-up:** ..." / "**Coaching notes:** ..."
    const boldLine = line.match(/^\*\*(.+?):\*\*\s*(.*)/);
    if (boldLine) {
      pushBlock({ type: 'note', label: boldLine[1], text: boldLine[2] });
      i++;
      continue;
    }

    // Bullet list
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
        i++;
      }
      pushBlock({ type: 'list', items });
      continue;
    }

    // Horizontal rule / blank line — section separators, no visible output.
    if (/^-{3,}\s*$/.test(line.trim()) || !line.trim()) {
      i++;
      continue;
    }

    pushBlock({ type: 'paragraph', text: line.trim() });
    i++;
  }

  return sections;
}

function parseTable(tableLines: string[]): { type: 'table'; header: string[]; rows: string[][] } | null {
  const rows = tableLines
    .filter((l) => !/^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$/.test(l)) // drop the "|---|---|" separator row
    .map((l) => {
      const cells = l.split('|').map((c) => c.trim());
      if (cells[0] === '') cells.shift();
      if (cells[cells.length - 1] === '') cells.pop();
      return cells;
    });

  if (rows.length === 0) return null;
  const [header, ...body] = rows;
  return { type: 'table', header, rows: body };
}

/** Finds the column index whose header matches, case-insensitively. -1 if
 * not found — callers should treat that as "field unavailable", not crash. */
export function findColumn(header: string[], match: RegExp): number {
  return header.findIndex((h) => match.test(h));
}
