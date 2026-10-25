/* Who appears on the Calgary ranking list, and in what order.
 * Pure functions: no page, no network. The list renders these results as-is.
 * A missing score stays null. It is never turned into 0.
 */

const CHARTER_BOARDS = new Set([
  "Calgary Girls' School Society",
  "Calgary Arts Academy Society",
  "Almadina School Society",
  "STEM Innovation Academy Society",
  "Alberta Classical Academy Ltd.",
]);

/** City grade labels are bands. Returns [low, high], or null when the label is missing. */
export function citySpan(grades) {
  if (!grades || grades === "Unknown") return null;
  let low = null, high = null;
  const add = (a, b) => { low = low == null ? a : Math.min(low, a); high = high == null ? b : Math.max(high, b); };
  for (const part of grades.split("/")) {
    const name = part.trim();
    if (name === "Elementary") add(0, 6);
    else if (name === "Junior High") add(7, 9);
    else if (name === "Senior High") add(10, 12);
  }
  return low == null ? null : [low, high];
}

/** CBE numeric span when the directory has one, otherwise the city band. */
export function schoolSpan(school) {
  if (school.grade_min != null && school.grade_max != null) return [school.grade_min, school.grade_max];
  return citySpan(school.grades);
}

export function displayName(school) {
  return school.cbe_name || school.name;
}

/** Grade 10 and above stays off the list. This ranking is elementary and junior high. */
export function isHighSchool(school) {
  if (school.senior) return true;
  const span = schoolSpan(school);
  return !!(span && span[1] >= 10);
}

/** "K-6" or "7-9" as [low, high]. A single grade uses that grade for both ends. */
export function rangeEnds(label) {
  const [low, high] = String(label).split("-");
  const num = (part) => part === "K" ? 0 : Number(part);
  return [num(low), high == null ? num(low) : num(high)];
}

/** Which published exam this grade range writes. Null when the range has no PAT. */
export function examForSpan(span) {
  if (!span || span[1] >= 10) return null;
  if (span[1] >= 9 && span[0] <= 9) return "pat9";
  if (span[1] >= 6 && span[0] <= 6) return "pat6";
  return null;
}

/** (% acceptable + % excellence) / 2. Null when either rate is missing. */
export function blockScore(block) {
  if (!block || block.acc == null || block.exc == null) return null;
  return Math.round((block.acc + block.exc) / 2 * 10) / 10;
}

/** CBE ranges use the published span. Other schools fall back to the city grade band. */
export function listedExam(school) {
  const fromSpan = examForSpan(schoolSpan(school));
  if (school.cbe_grades) return fromSpan;
  if (fromSpan) return fromSpan;
  if (school.rank_exam === "pat6" || school.rank_exam === "pat9") return school.rank_exam;
  return null;
}

/**
 * The score, year, and exam shown on one row.
 * Uses the pipeline score when the exam matches. Recomputes only when a CBE
 * grade range calls for the other exam's latest-year block.
 */
export function listedResult(school) {
  const exam = listedExam(school);
  const block = exam === "pat9" ? school.g9_latest : exam === "pat6" ? school.g6_latest : null;
  if (exam && school.rank_exam === exam) return { score: school.rank_score, year: school.rank_year, exam, detail: block };
  const fromBlock = blockScore(block);
  if (fromBlock != null) return { score: fromBlock, year: block.year || null, exam, detail: block };
  return { score: null, year: null, exam, detail: null };
}

/** Public board bucket: cbe, cssd, franco, charter, other_public, private, or null. */
export function boardGroup(school) {
  const board = school.board || "";
  if (!board) return null;
  if (board === "The Calgary School Division") return "cbe";
  if (board === "The Calgary Roman Catholic Separate School Division") return "cssd";
  if (board === "The Southern Francophone Education Region") return "franco";
  if (board.includes("Charter") || CHARTER_BOARDS.has(board)) return "charter";
  if (board.includes("School Division") || board.includes("Education Region")) return "other_public";
  return "private";
}

export function gradeBand(school) {
  const exam = listedExam(school);
  if (exam === "pat6") return "elem";
  if (exam === "pat9") return "junior";
  return "unknown";
}

/**
 * Whether this school belongs on the list for the current board and grade filters.
 * filter.board and filter.grade use the select values ("all", "cbe", "K-6", ...).
 */
export function inConfig(school, filter) {
  if (isHighSchool(school) || !school.board) return false;
  if (filter.board !== "all" && boardGroup(school) !== filter.board) return false;
  if (filter.grade === "all") return true;
  if (filter.grade === "elem") return gradeBand(school) === "elem";
  if (filter.grade === "junior") return gradeBand(school) === "junior";
  if (filter.grade === "unlisted") return !school.cbe_grades && gradeBand(school) === "elem";
  if (filter.grade === "unknown") {
    if (filter.board === "cbe") return !school.cbe_grades && gradeBand(school) === "unknown";
    return gradeBand(school) === "unknown";
  }
  return school.cbe_grades === filter.grade;
}

/** i18n key for the note under the filters. Does not include a program or search filter. */
export function noteForConfig(filter) {
  if (filter.grade === "all") return "rank_note_all";
  if (filter.grade === "junior") return "rank_note_pat9";
  if (filter.grade === "elem" || filter.grade === "unlisted") return "rank_note_pat6";
  if (filter.grade === "unknown") return "rank_note_unknown";
  const exam = examForSpan(rangeEnds(filter.grade));
  if (exam === "pat9") return "rank_note_pat9";
  if (exam === "pat6") return "rank_note_pat6";
  return "rank_note_noscore";
}

/** Program select and the search box. An empty query matches every school. */
export function passesDirectory(school, filter) {
  if (filter.program !== "all" && !(school.program_names || []).includes(filter.program)) return false;
  const q = (filter.query || "").toLowerCase();
  if (!q) return true;
  const programs = (school.program_names || []).join(" ");
  return (displayName(school) + " " + school.name + " " + (school.board || "") + " " + programs).toLowerCase().includes(q);
}

/**
 * Grade 6 before Grade 9 when both are on screen. A missing score sorts last
 * inside that exam. `entries` are { school, result } from listedResult.
 */
export function sortListed(entries, mixed) {
  const examOrder = { pat6: 0, pat9: 1 };
  return [...entries].sort((a, b) => {
    if (mixed && (a.result.exam || "") !== (b.result.exam || "")) {
      return (examOrder[a.result.exam] ?? 2) - (examOrder[b.result.exam] ?? 2);
    }
    if (a.result.score == null && b.result.score == null) return displayName(a.school).localeCompare(displayName(b.school));
    if (a.result.score == null) return 1;
    if (b.result.score == null) return -1;
    return b.result.score - a.result.score || displayName(a.school).localeCompare(displayName(b.school));
  });
}

/** Same folding as build_data.normalize_name, so a contact row can match a school. */
export function contactKey(name) {
  let text = String(name || "").toLowerCase().replace(/&/g, " and ");
  text = text.replace(/\bst\.?\s/g, "saint ");
  text = text.replace(/[^a-z0-9 ]+/g, " ");
  const stop = new Set(["the", "school", "of", "and", "campus"]);
  return text.split(/\s+/).filter((word) => word && !stop.has(word)).join(" ");
}

/** Alberta school code with leading zeros removed. Empty stays empty. */
export function contactCode(value) {
  const text = String(value == null ? "" : value).replace(/\.0$/, "").trim();
  if (!text) return "";
  return text.replace(/^0+/, "") || "0";
}
