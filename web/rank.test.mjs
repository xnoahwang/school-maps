/* Ranking rules that must stay stable when the page is rearranged.
 * Run: node --test web/rank.test.mjs
 * Does not load the map or the JSON files.
 */
import assert from "node:assert/strict";
import test from "node:test";
import {
  blockScore, citySpan, examForSpan, inConfig, isHighSchool, listedResult,
  passesDirectory, sortListed,
} from "./rank.js";

const cbe = "The Calgary School Division";

test("a senior school and a grade span ending at 10 stay off the list", () => {
  assert.equal(isHighSchool({ senior: true, board: cbe }), true);
  assert.equal(isHighSchool({ grade_min: 10, grade_max: 12, board: cbe }), true);
  assert.equal(inConfig({ senior: true, board: cbe }, { board: "all", grade: "all" }), false);
});

test("K-6 is grade 6 and 7-9 is grade 9; a high-school span has no exam", () => {
  assert.equal(examForSpan([0, 6]), "pat6");
  assert.equal(examForSpan([7, 9]), "pat9");
  assert.equal(examForSpan([10, 12]), null);
  assert.equal(examForSpan(null), null);
});

test("a missing rate stays null and is not scored as zero", () => {
  assert.equal(blockScore(null), null);
  assert.equal(blockScore({ acc: null, exc: 10 }), null);
  assert.equal(blockScore({ acc: 0, exc: 0 }), 0);
  const school = {
    board: cbe, grade_min: 0, grade_max: 6, cbe_grades: "K-6",
    rank_exam: "pat6", rank_score: null, rank_year: null, g6_latest: null,
  };
  assert.equal(listedResult(school).score, null);
});

test("the listed score follows the pipeline when the exam matches", () => {
  const school = {
    board: cbe, grade_min: 0, grade_max: 6, cbe_grades: "K-6",
    rank_exam: "pat6", rank_score: 70.3, rank_year: 2025,
    g6_latest: { acc: 80, exc: 40, year: 2025 },
  };
  assert.deepEqual(listedResult(school).score, 70.3);
  assert.equal(listedResult(school).year, 2025);
});

test("grade 6 as a group sorts ahead of grade 9, and a missing score sorts last inside its exam", () => {
  const row = (name, exam, score) => ({ school: { name }, result: { exam, score } });
  const sorted = sortListed([
    row("No score", "pat6", null),
    row("Junior", "pat9", 90),
    row("Elem low", "pat6", 10),
    row("Elem high", "pat6", 80),
  ], true);
  assert.deepEqual(sorted.map((entry) => entry.school.name), ["Elem high", "Elem low", "No score", "Junior"]);
});

test("an empty search matches, and a program filter drops other programs", () => {
  const school = { name: "Briar Hill School", board: cbe, program_names: ["Regular"] };
  assert.equal(passesDirectory(school, { program: "all", query: "" }), true);
  assert.equal(passesDirectory(school, { program: "all", query: "briar" }), true);
  assert.equal(passesDirectory(school, { program: "French", query: "" }), false);
});

test("an unknown city grade label has no span", () => {
  assert.equal(citySpan(null), null);
  assert.equal(citySpan("Unknown"), null);
  assert.equal(citySpan("not a grade"), null);
});
