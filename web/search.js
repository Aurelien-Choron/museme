// Recherche instantanee dans le catalogue, cote navigateur.
// Module pur (aucun acces au DOM) : teste sous Node par tests/search.test.mjs.
//
// Chaque mot tape doit commencer un mot du titre, de l'artiste ou de l'album,
// dans n'importe quel ordre, sans tenir compte des accents ni de la casse :
// « lucky get », « daft punk get lucky » et « beyonce » trouvent ce qu'on
// attend. Les ecritures sans espaces (japonais, chinois) se cherchent par
// sous-chaine.

const LETTERS = { "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l", "đ": "d", "ı": "i", "$": "s" };
const CJK = /[぀-ヿ㐀-鿿豈-﫿]/;

export function normalize(text) {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .normalize("NFC")
    .toLowerCase()
    .replace(/[øæœßłđı$]/g, (c) => LETTERS[c])
    .replace(/&/g, " and ")
    .replace(/['’`]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function words(text) {
  return text ? normalize(text).split(" ").filter(Boolean) : [];
}

// tracks : lignes de catalog.json ([titre, artiste, album, genre, pochette,
// extrait]). Un meme titre du meme artiste n'est propose qu'une fois.
export function createIndex(tracks) {
  const seen = new Set();
  const entries = [];
  tracks.forEach(([title, artist, album], row) => {
    const entry = {
      row,
      title: normalize(title),
      artist: normalize(artist),
      titleWords: words(title),
      artistWords: words(artist),
      albumWords: words(album),
    };
    const key = entry.title + "\u0000" + entry.artist;
    if (seen.has(key)) return;
    seen.add(key);
    entry.titleCompact = entry.title.replace(/ /g, "");
    entry.artistCompact = entry.artist.replace(/ /g, "");
    entry.compact = entry.titleCompact + entry.artistCompact + entry.albumWords.join("");
    entries.push(entry);
  });
  return entries;
}

function wordScore(list, token, exact, prefix) {
  let best = 0;
  for (const w of list) {
    if (w === token) return exact;
    if (w.startsWith(token)) best = prefix;
  }
  return best;
}

// Points d'un mot tape : 0 s'il ne commence aucun mot du morceau. Le titre
// passe avant l'artiste, l'artiste avant l'album.
function tokenScore(entry, token) {
  if (CJK.test(token)) {
    if (entry.title.includes(token)) return 10;
    if (entry.artist.includes(token)) return 8;
    return entry.compact.includes(token) ? 2 : 0;
  }
  return Math.max(
    wordScore(entry.titleWords, token, 12, 8),
    wordScore(entry.artistWords, token, 10, 6),
    wordScore(entry.albumWords, token, 3, 2),
  );
}

// Les `limit` meilleurs numeros de ligne pour `query`, du plus pertinent au
// moins pertinent. Requete vide : aucun resultat.
export function search(index, query, limit = 8) {
  const q = normalize(query);
  if (!q) return [];
  const tokens = q.split(" ");
  const compactQuery = tokens.join("");
  const scored = [];
  for (const entry of index) {
    let score = 0;
    for (const token of tokens) {
      const s = tokenScore(entry, token);
      if (!s) { score = 0; break; }
      score += s;
    }
    // « acdc » pour AC/DC : la requete sans espaces commence le titre ou l'artiste.
    if (!score && compactQuery.length >= 3
        && (entry.titleCompact.startsWith(compactQuery) || entry.artistCompact.startsWith(compactQuery))) {
      score = 5;
    }
    if (!score) continue;
    if (entry.title === q) score += 60;
    else if (entry.title.startsWith(q)) score += 40;
    if (entry.artist === q) score += 50;
    else if (entry.artist.startsWith(q)) score += 30;
    scored.push({ entry, score });
  }
  scored.sort((a, b) => b.score - a.score
    || a.entry.title.length - b.entry.title.length
    || (a.entry.title < b.entry.title ? -1 : a.entry.title > b.entry.title ? 1 : 0)
    || (a.entry.artist < b.entry.artist ? -1 : 1));
  return scored.slice(0, limit).map((s) => s.entry.row);
}

// Decoupe `text` en segments [texte, trouve] pour mettre en gras le debut
// des mots qui correspondent a la requete (« luc » -> **Luc**ky).
export function highlight(text, query) {
  const tokens = normalize(query).split(" ").filter(Boolean);
  if (!tokens.length) return [[text, false]];
  const segments = [];
  for (const part of text.split(/(\s+)/)) {
    if (!part) continue;
    const chars = [...part];
    let norm = "";
    const ends = chars.map((c) => (norm += normalize(c).replace(/ /g, "")).length);
    let length = 0;
    for (const t of tokens) {
      if (t.length > length && norm.startsWith(t)) length = t.length;
    }
    if (!length) {
      segments.push([part, false]);
      continue;
    }
    const cut = ends.findIndex((e) => e >= length) + 1;
    segments.push([chars.slice(0, cut).join(""), true]);
    if (cut < chars.length) segments.push([chars.slice(cut).join(""), false]);
  }
  return segments;
}
