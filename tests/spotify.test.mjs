// node --test tests/*.test.mjs
// Lecture complete par Spotify (web/spotify.js) : fonctions sans DOM ni reseau.
import assert from "node:assert/strict";
import { test } from "node:test";

import { base64url, challenge, playList, randomString, rowOf } from "../web/spotify.js";

test("defi PKCE : exemple de la RFC 7636 (annexe B)", async () => {
  assert.equal(await challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
               "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
});

test("base64url : sans +, / ni =", () => {
  assert.equal(base64url(new Uint8Array([251, 255, 191])), "-_-_");
  assert.equal(base64url(new Uint8Array([1])), "AQ");
});

test("verificateur PKCE : longueur et caracteres autorises", () => {
  const verifier = randomString(64);
  assert.equal(verifier.length, 64);
  assert.match(verifier, /^[A-Za-z0-9_-]+$/);
  assert.notEqual(randomString(64), verifier);
});

// Catalogue fictif : les lignes 2 et 5 n'ont pas d'identifiant.
const ids = ["a".repeat(22), "b".repeat(22), null, "c".repeat(22), "d".repeat(22), null];
const uri = (row) => `spotify:track:${ids[row]}`;

test("file envoyee a Spotify : morceaux sans identifiant sautes, position du morceau demande", () => {
  const queue = [3, 2, 0, 5, 1];
  assert.deepEqual(playList(queue, ids, 3), { uris: [uri(3), uri(0), uri(1)], position: 0 });
  assert.deepEqual(playList(queue, ids, 1), { uris: [uri(3), uri(0), uri(1)], position: 2 });
});

test("morceau hors de la file : joue seul", () => {
  assert.deepEqual(playList([3, 0], ids, 4), { uris: [uri(4)], position: 0 });
  assert.deepEqual(playList([3, 0], ids, 5), { uris: [], position: 0 });
});

test("morceau joue -> ligne : par identifiant, linked_from, de preference dans la file", () => {
  assert.equal(rowOf({ id: ids[3] }, ids, [0, 3]), 3);
  assert.equal(rowOf({ id: "z".repeat(22), linked_from: { id: ids[1] } }, ids, []), 1);
  assert.equal(rowOf({ id: "z".repeat(22), linked_from: null }, ids, []), null);
  assert.equal(rowOf(null, ids, []), null);
  // Deux lignes pour un meme identifiant : celle de la file l'emporte.
  const shared = [ids[0], ids[0], null];
  assert.equal(rowOf({ id: ids[0] }, shared, [2, 1]), 1);
  assert.equal(rowOf({ id: ids[0] }, shared, []), 0);
});
