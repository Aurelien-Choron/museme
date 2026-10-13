// node --test tests/*.test.mjs
// Recherche du site (web/search.js) sur le vrai catalogue (web/data/catalog.json,
// ecrit par python -m pipeline site).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { createIndex, highlight, normalize, search } from "../web/search.js";

const catalog = JSON.parse(readFileSync(new URL("../web/data/catalog.json", import.meta.url), "utf-8"));
const tracks = catalog.tracks;
const index = createIndex(tracks);
const label = (row) => `${tracks[row][0]} — ${tracks[row][1]}`;
const find = (query, limit) => search(index, query, limit).map(label);

test("normalisation : accents, casse, ponctuation, & et $", () => {
  assert.equal(normalize("Beyoncé"), "beyonce");
  assert.equal(normalize("  MØ  "), "mo");
  assert.equal(normalize("Simon & Garfunkel"), "simon and garfunkel");
  assert.equal(normalize("Don't Stop"), "dont stop");
  assert.equal(normalize("Ke$ha"), "kesha");
  assert.equal(normalize("AC/DC"), "ac dc");
});

test("titre et artiste, dans les deux ordres", () => {
  assert.match(find("daft punk get lucky")[0], /^Get Lucky .* — Daft Punk$/);
  assert.match(find("get lucky daft")[0], /^Get Lucky .* — Daft Punk$/);
  assert.match(find("lucky get")[0], /^Get Lucky .* — Daft Punk$/);
});

test("debut de mot en cours de frappe", () => {
  assert.match(find("get luc")[0], /^Get Lucky/);
});

test("sans accents : beyonce trouve Beyoncé", () => {
  const results = find("beyonce");
  assert.ok(results.length > 0);
  assert.ok(results.every((r) => r.endsWith("— Beyoncé")), results.join(", "));
});

test("un titre partage par deux artistes est propose deux fois", () => {
  const results = find("baby").slice(0, 4);
  assert.ok(results.includes("Baby — Brandy"), results.join(", "));
  assert.ok(results.includes("Baby — Justin Bieber"), results.join(", "));
});

test("un artiste : ses morceaux d'abord, puis les titres qui le citent", () => {
  const results = find("madonna");
  const own = tracks.filter((t) => t[1] === "Madonna").length;
  assert.ok(own > 0 && own < 8);
  assert.ok(results.slice(0, own).every((r) => r.endsWith("— Madonna")), results.join(", "));
  assert.ok(results.includes("I Could Be Madonna — Barry Can't Swim"), results.join(", "));
});

test("titre japonais par sous-chaine", () => {
  const row = tracks.findIndex((t) => t[0] === "銀河鉄道の夜");
  assert.ok(row >= 0);
  assert.ok(search(index, "鉄道").includes(row));
});

test("requete vide ou sans resultat", () => {
  assert.deepEqual(search(index, ""), []);
  assert.deepEqual(search(index, "   "), []);
  assert.deepEqual(search(index, "zzzqqqxxx"), []);
});

test("un meme titre du meme artiste n'apparait qu'une fois", () => {
  // We'll Be Coming Back (Calvin Harris) et Spell of Destruction (Burzum) :
  // deux albums, meme morceau, a la casse pres pour le second.
  const keys = new Set(index.map((e) => e.title + "|" + e.artist));
  assert.equal(keys.size, index.length);
  assert.equal(index.length, tracks.length - 2);
  assert.equal(find("spell of destruction").length, 1);
});

test("mise en gras du debut des mots trouves", () => {
  assert.deepEqual(highlight("Get Lucky", "luc"), [["Get", false], [" ", false], ["Luc", true], ["ky", false]]);
  assert.deepEqual(highlight("Beyoncé", "beyonce"), [["Beyoncé", true]]);
  assert.deepEqual(highlight("(feat. Pharrell", "feat"), [["(feat", true], [".", false], [" ", false], ["Pharrell", false]]);
  assert.deepEqual(highlight("Abc", ""), [["Abc", false]]);
});

test("filtrer tout le catalogue prend quelques millisecondes", () => {
  const queries = ["a", "the", "love", "daft punk get lucky", "beyonce", "baby", "z"];
  const start = performance.now();
  for (let i = 0; i < 20; i++) for (const q of queries) search(index, q);
  const perQuery = (performance.now() - start) / (20 * queries.length);
  console.log(`  ${perQuery.toFixed(2)} ms par frappe`);
  assert.ok(perQuery < 16, `${perQuery} ms`);
});
