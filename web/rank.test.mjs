/* Ranking rules that must stay stable when the page is rearranged.
 * Run: node --test web/rank.test.mjs
 * Does not load the map or the JSON files.
 */
import assert from "node:assert/strict";
import test from "node:test";
import {
  blockScore, citySpan, examForSpan, inConfig, isHighSchool, listedResult,
  passesDirectory, shortGrades, sortListed,
} from "./rank.js";

const cbe = "The Calgary School Division";
const all = { board: "all", grade: "all" };

test("a K-12 school is listed on each level with that level's score", () => {
  const school = {
    name: "Renert School", board: "The Renert School Foundation",
    grades: "Elementary/Junior High/Senior High", elem: true, junior: true, senior: true,
    g6_latest: { acc: 99.0, exc: 77.8, year: 2025 },
    g9_latest: { acc: 99.6, exc: 75.0, year: 2025 },
    diploma_latest: { acc: 100.0, exc: 96.8, year: 2025 },
  };
  assert.equal(inConfig(school, all), true);
  assert.equal(inConfig(school, { ...all, level: "junior" }), true);
  assert.equal(inConfig(school, { ...all, level: "high" }), true);
  assert.equal(listedResult(school, "elem").score, 88.4);
  assert.equal(listedResult(school, "junior").score, 87.3);
  assert.equal(listedResult(school, "high").score, 98.4);
  assert.equal(listedResult(school, "high").year, 2025);
});

test("a high-school-only span stays off the earlier lists", () => {
  const school = { board: cbe, grade_min: 10, grade_max: 12, senior: true };
  assert.equal(isHighSchool(school), true);
  assert.equal(inConfig(school, all), false);
  assert.equal(inConfig(school, { ...all, level: "junior" }), false);
  assert.equal(inConfig(school, { ...all, level: "high" }), true);
  assert.equal(inConfig({ board: cbe, grade_min: 0, grade_max: 6 }, { ...all, level: "high" }), false);
  assert.equal(listedResult({ senior: true, board: cbe, diploma_latest: null }, "high").score, null);
});

test("a K-4 school stays on elementary with no score, and a K-6 school is not junior high", () => {
  const early = { board: cbe, grade_min: 0, grade_max: 4, g6_latest: { acc: 90, exc: 40, year: 2025 } };
  assert.equal(inConfig(early, all), true);
  assert.equal(inConfig(early, { ...all, level: "junior" }), false);
  assert.equal(listedResult(early, "elem").score, null);
  const elem = { board: cbe, grade_min: 0, grade_max: 6 };
  assert.equal(inConfig(elem, { ...all, level: "junior" }), false);
  assert.equal(inConfig({ board: cbe, grade_min: 7, grade_max: 9 }, all), false);
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

test("each level uses its own latest block, not the stored rank", () => {
  const school = {
    board: cbe, grade_min: 0, grade_max: 9, elem: true, junior: true,
    rank_exam: "pat9", rank_score: 90, rank_year: 2025,
    g6_latest: { acc: 80, exc: 40, year: 2024 },
    g9_latest: { acc: 90, exc: 50, year: 2025 },
  };
  assert.equal(listedResult(school, "elem").score, 60);
  assert.equal(listedResult(school, "elem").year, 2024);
  assert.equal(listedResult(school, "junior").score, 70);
  assert.equal(listedResult(school, "junior").year, 2025);
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

test("acceptable and excellence sorts use that rate, and a missing rate stays last", () => {
  const row = (name, acc, exc) => ({
    school: { name },
    result: { exam: "pat6", score: acc == null || exc == null ? null : (acc + exc) / 2, detail: acc == null ? null : { acc, exc } },
  });
  const rows = [row("Low", 10, 80), row("None", null, null), row("High", 90, 20)];
  assert.deepEqual(sortListed(rows, false, { by: "acc", dir: "desc" }).map((entry) => entry.school.name), ["High", "Low", "None"]);
  assert.deepEqual(sortListed(rows, false, { by: "acc", dir: "asc" }).map((entry) => entry.school.name), ["Low", "High", "None"]);
  assert.deepEqual(sortListed(rows, false, { by: "exc", dir: "desc" }).map((entry) => entry.school.name), ["Low", "High", "None"]);
  assert.deepEqual(sortListed(rows, false, { by: "nope" }).map((entry) => entry.school.name), ["High", "Low", "None"]);
});

test("a tied acceptable rate breaks on excellence, and a tied excellence rate breaks on acceptable", () => {
  const row = (name, acc, exc) => ({
    school: { name },
    result: { exam: "pat6", score: (acc + exc) / 2, detail: { acc, exc } },
  });
  const tied = [row("Delta", 100, 55.6), row("Harold", 100, 62.5), row("Webber", 100, 88.4), row("Lower", 99.3, 87.5)];
  assert.deepEqual(sortListed(tied, false, { by: "acc", dir: "desc" }).map((entry) => entry.school.name), ["Webber", "Harold", "Delta", "Lower"]);
  assert.deepEqual(sortListed(tied, false, { by: "acc", dir: "asc" }).map((entry) => entry.school.name), ["Lower", "Delta", "Harold", "Webber"]);
  const excTie = [row("Zed", 70, 50), row("Ann", 90, 50), row("Mid", 80, 40)];
  assert.deepEqual(sortListed(excTie, false, { by: "exc", dir: "desc" }).map((entry) => entry.school.name), ["Ann", "Zed", "Mid"]);
  assert.deepEqual(sortListed([row("Zed", 100, 50), row("Ann", 100, 50)], false, { by: "acc", dir: "desc" }).map((entry) => entry.school.name), ["Ann", "Zed"]);
});

test("an empty search matches, and a program filter drops other programs", () => {
  const school = { name: "Briar Hill School", board: cbe, program_names: ["Regular"] };
  assert.equal(passesDirectory(school, { program: "all", query: "" }), true);
  assert.equal(passesDirectory(school, { program: "all", query: "briar" }), true);
  assert.equal(passesDirectory(school, { program: "French", query: "" }), false);
});

test("long grade labels use short display names, and CBE spans stay as stored", () => {
  assert.equal(shortGrades("Elementary"), "Elem");
  assert.equal(shortGrades("Junior High"), "Jr");
  assert.equal(shortGrades("Senior High"), "Sr");
  assert.equal(shortGrades("Elementary/Junior High"), "Elem/Jr");
  assert.equal(shortGrades("Junior High/Senior High"), "Jr/Sr");
  assert.equal(shortGrades("Elementary/Junior High/Senior High"), "Elem/Jr/Sr");
  assert.equal(shortGrades("K-6"), "K-6");
  assert.equal(shortGrades("10-12"), "10-12");
  assert.equal(shortGrades("Unknown"), "Unknown");
  assert.equal(shortGrades(null), null);
  assert.equal(shortGrades(""), "");
});

test("an unknown city grade label has no span", () => {
  assert.equal(citySpan(null), null);
  assert.equal(citySpan("Unknown"), null);
  assert.equal(citySpan("not a grade"), null);
});
