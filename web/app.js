// Museme : recherche, morceau de depart, recommandations et lecteur.
// Aucune requete apres le chargement, hors pochettes, extraits et suite de la
// file de lecture (queue.json) : les recommandations sont precalculees par
// python -m pipeline site.

import { createIndex, highlight, search } from "./search.js";

const COVER_URL = "https://i.scdn.co/image/";
const PREVIEW_URL = "https://p.scdn.co/mp3-preview/";
// Tailles d'une pochette sur le CDN Spotify : meme identifiant, prefixe different.
const COVER_SIZES = { 64: "ab67616d00004851", 300: "ab67616d00001e02", 640: "ab67616d0000b273" };
// Accueil : 4 morceaux tires au sort a chaque visite, de genres differents.
// Numeros de ligne du catalogue (pipeline merge ajoute en fin de fichier : ils
// ne bougent pas). Choisis le 2026-10-11 : connus, et dont les recos ont ete
// bien notees a l'ecoute (note) ou semblent coherentes (non ecoutees).
const EXAMPLES = [
  4277, // 4 Minutes - Madonna (2,0)
  4723, // Bad Moon Rising - Creedence Clearwater Revival (1,8)
  3630, // Boom Clap - Charli XCX (1,8)
  1693, // Next To You - Ciara (1,8)
  3926, // See You Again - Tyler, The Creator (1,8)
  1324, // Island Rain - Kenny Chesney (1,8)
  4238, // One Last Time - Ariana Grande (1,7)
  4630, // Another One Bites The Dust - Queen
  4673, // Smells Like Teen Spirit - Nirvana
  3936, // Blinding Lights - The Weeknd
  4055, // Don't Start Now - Dua Lipa
  4227, // Wake Me Up - Avicii
  4201, // Do I Wanna Know? - Arctic Monkeys
  4708, // Master of Puppets - Metallica
  1181, // La femme d'argent - Air
  500,  // Blue in Green - Miles Davis
  3975, // Dynamite - BTS
  2601, // Leggo Beast - Steel Pulse
  1657, // Couleurs - Fally Ipupa
  3974, // Too Sweet - Hozier
];
const EXAMPLES_SHOWN = 4;
const SUGGESTIONS = 8;
const RECOS_SHOWN = 10; // la lecture enchaine ensuite jusqu'au 50e voisin
const SPOTIFY_CLIENT_KEY = "museme-spotify-client";

const $ = (id) => document.getElementById(id);
const els = {
  search: $("search"), results: $("results"), surprise: $("surprise"),
  layout: $("layout"), hero: $("hero"), try: $("try"),
  seed: $("seed"), count: $("count"), examples: $("examples"),
  recos: $("recos"), recosSeed: $("recos-seed"), recoList: $("reco-list"),
  player: $("player"), pCover: $("p-cover"), pTitle: $("p-title"), pArtist: $("p-artist"),
  pPrev: $("p-prev"), pPlay: $("p-play"), pNext: $("p-next"), pSimilar: $("p-similar"),
  pSeek: $("p-seek"), pTime: $("p-time"), pDuration: $("p-duration"), pLine: $("p-line"),
  pMute: $("p-mute"), pVolume: $("p-volume"), pSpotify: $("p-spotify"), toast: $("toast"),
  spotify: $("spotify"),
};
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

let tracks = [];
let genres = [];
let neighbors = [];  // les 10 voisins affiches
let more = null;     // voisins 11 a 50 (queue.json), charges au premier morceau joue
let moreRequest = null;
let index = [];
let seed = null;     // ligne du morceau de depart
let queue = [];      // ordre de lecture : le depart puis ses 50 voisins
let playing = null;  // ligne chargee dans le lecteur (en lecture ou en pause)
let results = [];    // suggestions affichees
let active = -1;     // suggestion choisie au clavier
let seeking = false;

const audio = new Audio();
audio.preload = "none";

// ---------- Donnees ----------

function track(row) {
  const [title, artist, album, genre, cover, preview] = tracks[row];
  return { row, title, artist, album, genre: genre == null ? null : genres[genre], cover, preview };
}

// Point d'entree des reglages du lot 2 : seule fonction a remplacer pour
// recommander autrement. Les RECOS_SHOWN premiers sont affiches ; tous sont
// enchaines a la lecture.
function recommend(row) {
  return more ? neighbors[row].concat(more[row]) : neighbors[row];
}

// Suite de la file (365 Ko compresses) : au premier morceau joue, pas a la
// visite. Une session Spotify l'attend avant d'envoyer la file.
function loadMore() {
  moreRequest ??= fetchJson("data/queue.json").then((data) => {
    more = data;
    if (seed != null) queue = [seed, ...recommend(seed)];
  }).catch((err) => {
    console.warn(err);
    moreRequest = null;
  });
  return moreRequest;
}

function coverUrl(id, size) {
  if (!id) return null;
  const large = COVER_SIZES[640];
  return id.startsWith(large) ? COVER_URL + COVER_SIZES[size] + id.slice(large.length) : COVER_URL + id;
}

// ---------- Construction du DOM (textes en noeuds texte : jamais d'innerHTML) ----------

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    el.setAttribute(name, value === true ? "" : value);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

function icon(name, extra = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `icon ${extra}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

function setIcon(button, name) {
  button.querySelector("use").setAttribute("href", `#i-${name}`);
}

function cover(t, className, size, attrs = {}) {
  if (!t.cover) return h("div", { class: `${className} cover-missing`, "aria-hidden": "true" }, "♪");
  return h("img", { class: className, src: coverUrl(t.cover, size), alt: "", decoding: "async", ...attrs });
}

function marked(text, query) {
  return highlight(text, query).map(([part, found]) => (found ? h("mark", {}, part) : part));
}

// ---------- Morceau de depart et recommandations ----------

function setSeed(row) {
  seed = row;
  if (els.layout.classList.contains("is-empty")) {
    // L'accueil (recherche au centre) laisse place aux deux colonnes.
    els.layout.classList.remove("is-empty");
    els.hero.hidden = true;
    els.try.hidden = true;
    els.search.placeholder = "Track or artist";
  }
  renderSeed();
  renderRecos();
  if (window.scrollY > 0) window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
}

function renderSeed() {
  const t = track(seed);
  els.seed.replaceChildren(
    cover(t, "seed-cover", 640, {
      srcset: t.cover ? `${coverUrl(t.cover, 300)} 300w, ${coverUrl(t.cover, 640)} 640w` : null,
      sizes: "(max-width: 599px) 88px, 340px",
      width: 640, height: 640,
      style: t.cover ? `--thumb: url("${coverUrl(t.cover, 64)}")` : null,
    }),
    h("div", { class: "seed-text" },
      h("p", { class: "label" }, "Your pick"),
      h("h2", { class: "seed-title", title: t.title }, t.title),
      h("p", { class: "seed-artist" }, t.artist),
      t.album && h("p", { class: "seed-album", title: t.album }, t.album),
      h("button", { class: "play-pill", type: "button", id: "seed-play" }, icon("play"), h("span", {}, playLabel(seed))),
    ),
  );
  els.seed.hidden = false;
}

function renderRecos() {
  const rows = recommend(seed);
  queue = [seed, ...rows];
  els.recosSeed.textContent = track(seed).title;
  els.recoList.replaceChildren(...rows.slice(0, RECOS_SHOWN).map((row, i) => recoRow(track(row), i + 1)));
  els.recos.hidden = false;
  growList();
  syncPlaying();
}

// Quand la lecture depasse les recommandations affichees, la liste s'allonge
// jusqu'au morceau joue (numerotation continue).
function growList() {
  const rank = queue.indexOf(playing);
  for (let i = els.recoList.children.length + 1; i <= rank; i++) {
    els.recoList.append(recoRow(track(queue[i]), i));
  }
}

function recoRow(t, rank) {
  return h("li", { class: "row", "data-row": t.row },
    h("button", { class: "row-main", type: "button", "data-action": "play", title: `${t.title} — ${t.artist}` },
      h("span", { class: "row-rank", "aria-hidden": "true" },
        h("span", { class: "row-num" }, String(rank).padStart(2, "0")),
        icon("play", "row-icon-play"), icon("pause", "row-icon-pause"),
        h("span", { class: "eq" }, h("i"), h("i"), h("i"))),
      cover(t, "row-cover", 64, { loading: "lazy", width: 48, height: 48 }),
      h("span", { class: "row-text" },
        h("span", { class: "row-title" }, t.title),
        h("span", { class: "row-artist" }, t.artist))),
    h("button", { class: "icon-btn row-similar", type: "button", "data-action": "similar",
                  title: "Find similar", "aria-label": `Find tracks similar to ${t.title}` }, icon("similar")),
  );
}

// Titre court pour les etiquettes : sans « (feat. ...) » ni mention de remaster.
function shortTitle(title) {
  return title
    .replace(/ \((feat\.|with) [^)]*\)/i, "")
    .replace(/ - (\d{4} )?Remaster(ed)?( \d{4})?$/i, "")
    .replace(/ \((\d{4} )?Remaster(ed)?\)$/i, "");
}

// Tirage sans remise, un seul morceau par genre.
function pickExamples() {
  const pool = EXAMPLES.filter((row) => row < tracks.length);
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  const picked = [];
  const seen = new Set();
  for (const row of pool) {
    const genre = tracks[row][3];
    if (seen.has(genre)) continue;
    seen.add(genre);
    picked.push(row);
    if (picked.length === EXAMPLES_SHOWN) break;
  }
  return picked;
}

function renderExamples() {
  els.examples.replaceChildren(...pickExamples().map((row) => {
    const t = track(row);
    return h("button", { class: "chip", type: "button", "data-row": row },
      cover(t, "", 64, { loading: "lazy", width: 34, height: 34 }),
      h("span", {}, h("b", {}, shortTitle(t.title)), ` · ${t.artist}`));
  }));
}

// ---------- Lecteur ----------

// Deux sources de lecture, meme interface : l'extrait de 30 s, pour tous, et
// le morceau entier par Spotify (spotify.js), pour une session invitee.
const preview = {
  start(row) {
    audio.src = PREVIEW_URL + tracks[row][5];
    this.resume();
  },
  resume() {
    audio.play().catch((err) => {
      if (err.name !== "AbortError") console.warn(err);
    });
  },
  pause: () => audio.pause(),
  get paused() { return audio.paused; },
  get position() { return audio.currentTime; },
  get duration() { return Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 30; },
  seek(seconds) { audio.currentTime = seconds; },
};
let source = preview;
let spotify = null; // session Spotify prete (spotify.js), sinon null

function play(row) {
  const wanted = spotify?.has(row) ? spotify : preview;
  if (wanted !== source) {
    source.pause();
    source = wanted;
  } else if (playing === row) {
    source.resume();
    return;
  }
  playing = row;
  renderPlayer();
  growList();
  source.start(row);
  loadMore();
}

function togglePlay(row) {
  if (playing === row && !source.paused) source.pause();
  else play(row);
}

function step(delta) {
  const next = queue.indexOf(playing) + delta;
  if (next < 0 || next >= queue.length) return false;
  play(queue[next]);
  return true;
}

// Fin d'un extrait : le suivant, en attendant la suite de la file si elle
// n'est pas encore chargee ; apres le 50e, arret.
async function advance() {
  if (step(1)) return;
  if (!more) {
    await loadMore();
    if (step(1)) return;
  }
  audio.currentTime = 0;
  syncPlaying();
}

function previous() {
  if (source.position > 3 || queue.indexOf(playing) <= 0) {
    source.seek(0);
    play(playing);
  } else {
    step(-1);
  }
}

function playLabel(row) {
  return spotify?.has(row) ? "Play" : "Play preview";
}

function renderPlayer() {
  const t = track(playing);
  els.pCover.replaceChildren(cover(t, "", 64, { width: 52, height: 52 }));
  els.pTitle.textContent = t.title;
  els.pTitle.title = t.title;
  els.pArtist.textContent = t.artist;
  // Attribution Spotify : lien vers le morceau joue en entier.
  const url = source === spotify ? spotify.trackUrl(playing) : null;
  els.pSpotify.hidden = !url;
  if (url) els.pSpotify.href = url;
  els.player.hidden = false;
  document.body.classList.add("has-player");
  updateProgress();
  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: t.title,
      artist: t.artist,
      album: t.album || "",
      artwork: t.cover ? [64, 300, 640].map((s) => ({ src: coverUrl(t.cover, s), sizes: `${s}x${s}`, type: "image/jpeg" })) : [],
    });
  }
}

// Etat de lecture partout ou il se voit : lignes, carte de depart, barre.
function syncPlaying() {
  const isPlaying = playing != null && !source.paused;
  for (const li of els.recoList.children) {
    const current = Number(li.dataset.row) === playing;
    li.classList.toggle("is-current", current);
    li.classList.toggle("is-playing", current && isPlaying);
  }
  const seedPlay = $("seed-play");
  if (seedPlay) {
    const on = playing === seed && isPlaying;
    setIcon(seedPlay, on ? "pause" : "play");
    seedPlay.lastChild.textContent = on ? "Pause" : playLabel(seed);
  }
  setIcon(els.pPlay, isPlaying ? "pause" : "play");
  els.pPlay.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
  if ("mediaSession" in navigator) navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
}

function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function updateProgress() {
  const duration = source.duration;
  const position = Math.min(source.position, duration);
  const percent = `${duration > 0 ? (position / duration) * 100 : 0}%`;
  els.pSeek.max = duration;
  if (!seeking) els.pSeek.value = position;
  els.pSeek.style.setProperty("--p", percent);
  els.pLine.style.width = percent;
  els.pTime.textContent = formatTime(position);
  els.pDuration.textContent = formatTime(duration);
}

let toastTimer;
function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove("is-visible"), 3000);
}

audio.addEventListener("play", syncPlaying);
audio.addEventListener("pause", syncPlaying);
audio.addEventListener("timeupdate", () => { if (source === preview) updateProgress(); });
audio.addEventListener("loadedmetadata", () => { if (source === preview) updateProgress(); });
// Les extraits s'enchainent : le depart, puis ses 50 voisins.
audio.addEventListener("ended", () => { if (source === preview) advance(); });
audio.addEventListener("error", () => {
  if (!audio.src || source !== preview) return;
  toast("Preview unavailable");
  advance();
});

els.pPlay.addEventListener("click", () => togglePlay(playing));
els.pPrev.addEventListener("click", previous);
els.pNext.addEventListener("click", () => step(1));
els.pSimilar.addEventListener("click", () => setSeed(playing));

els.pSeek.addEventListener("input", () => {
  seeking = true;
  els.pSeek.style.setProperty("--p", `${(els.pSeek.value / els.pSeek.max) * 100}%`);
  els.pTime.textContent = formatTime(els.pSeek.value);
});
els.pSeek.addEventListener("change", () => {
  source.seek(Number(els.pSeek.value));
  seeking = false;
});

// Le volume et la sourdine sont ceux de l'element audio, repris par Spotify.
const volume = () => (audio.muted ? 0 : audio.volume);

function setVolume(value) {
  audio.volume = value;
  audio.muted = value === 0;
  els.pVolume.value = value;
  els.pVolume.style.setProperty("--p", `${value * 100}%`);
  setIcon(els.pMute, audio.muted ? "mute" : "volume");
  els.pMute.setAttribute("aria-label", audio.muted ? "Unmute" : "Mute");
  spotify?.setVolume(volume());
}
els.pVolume.addEventListener("input", () => {
  const value = Number(els.pVolume.value);
  setVolume(value);
  try { localStorage.setItem("museme-volume", String(value)); } catch { /* stockage indisponible */ }
});
els.pMute.addEventListener("click", () => {
  audio.muted = !audio.muted;
  setIcon(els.pMute, audio.muted ? "mute" : "volume");
  els.pMute.setAttribute("aria-label", audio.muted ? "Unmute" : "Mute");
  spotify?.setVolume(volume());
});
try {
  const saved = Number(localStorage.getItem("museme-volume"));
  if (localStorage.getItem("museme-volume") !== null && saved >= 0 && saved <= 1) setVolume(saved);
  else setVolume(1);
} catch {
  setVolume(1);
}

if ("mediaSession" in navigator) {
  const actions = {
    play: () => { if (playing != null) play(playing); },
    pause: () => source.pause(),
    previoustrack: previous,
    nexttrack: () => step(1),
    seekto: (details) => source.seek(details.seekTime),
  };
  for (const [action, handler] of Object.entries(actions)) {
    try { navigator.mediaSession.setActionHandler(action, handler); } catch { /* action non geree */ }
  }
}

// ---------- Recherche ----------

function openResults(query) {
  els.results.replaceChildren(...(results.length
    ? results.map((row, i) => {
        const t = track(row);
        return h("li", { id: `opt-${i}`, role: "option", "aria-selected": String(i === active), "data-row": row },
          cover(t, "opt-cover", 64, { width: 40, height: 40 }),
          h("span", { class: "opt-text" },
            h("span", { class: "opt-title" }, marked(t.title, query)),
            h("span", { class: "opt-artist" }, marked(t.artist, query))));
      })
    : [h("li", { class: "empty", role: "presentation" }, "No track found")]));
  els.results.hidden = false;
  els.search.setAttribute("aria-expanded", "true");
  setActive(active);
}

function closeResults() {
  els.results.hidden = true;
  els.search.setAttribute("aria-expanded", "false");
  els.search.removeAttribute("aria-activedescendant");
}

function setActive(i) {
  active = i;
  els.results.querySelectorAll("[role=option]").forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
  if (i >= 0) {
    els.search.setAttribute("aria-activedescendant", `opt-${i}`);
    $(`opt-${i}`).scrollIntoView({ block: "nearest" });
  } else {
    els.search.removeAttribute("aria-activedescendant");
  }
}

function updateResults() {
  const query = els.search.value;
  if (!query.trim()) {
    results = [];
    closeResults();
    return;
  }
  results = search(index, query, SUGGESTIONS);
  active = results.length ? 0 : -1;
  openResults(query);
}

function choose(row) {
  els.search.value = "";
  closeResults();
  els.search.blur();
  setSeed(row);
}

els.search.addEventListener("input", updateResults);
els.search.addEventListener("focus", () => { if (els.search.value.trim()) updateResults(); });
els.search.addEventListener("blur", closeResults);
els.search.addEventListener("keydown", (e) => {
  const open = !els.results.hidden && results.length > 0;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (!open) return updateResults();
    const delta = e.key === "ArrowDown" ? 1 : -1;
    setActive((active + delta + results.length) % results.length);
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (open && active >= 0) choose(results[active]);
  } else if (e.key === "Escape") {
    // Chrome vide un champ de recherche a Echap : d'abord fermer les suggestions.
    if (!els.results.hidden) {
      e.preventDefault();
      closeResults();
    }
  }
});
// mousedown + preventDefault : le champ garde le focus jusqu'au clic (souris et tactile).
els.results.addEventListener("mousedown", (e) => e.preventDefault());
els.results.addEventListener("click", (e) => {
  const li = e.target.closest("[role=option]");
  if (li) choose(Number(li.dataset.row));
});

els.surprise.addEventListener("click", () => setSeed(Math.floor(Math.random() * tracks.length)));
els.examples.addEventListener("click", (e) => {
  const chip = e.target.closest("[data-row]");
  if (chip) setSeed(Number(chip.dataset.row));
});
els.seed.addEventListener("click", (e) => {
  if (e.target.closest("#seed-play")) togglePlay(seed);
});
els.recoList.addEventListener("click", (e) => {
  const button = e.target.closest("button[data-action]");
  if (!button) return;
  const row = Number(button.closest("[data-row]").dataset.row);
  if (button.dataset.action === "similar") setSeed(row);
  else togglePlay(row);
});

// « / » : aller a la recherche. Espace : lecture / pause, hors des champs et
// des boutons (qui gerent deja l'espace).
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const typing = e.target.closest("input:not([type=range]), textarea, select, [contenteditable]");
  if (e.key === "/" && !typing && !els.search.disabled) {
    e.preventDefault();
    els.search.focus();
  } else if (e.key === " " && !typing && !e.target.closest("button, a, input") && playing != null) {
    e.preventDefault();
    togglePlay(playing);
  }
});

// ---------- Session Spotify (morceaux entiers, comptes invites) ----------

// Seulement dans un navigateur ouvert une fois avec le lien prive
// #spotify=<Client ID> : les visiteurs ne chargent pas spotify.js.
function invited() {
  if (/[#&]spotify=/.test(location.hash)) return true;
  try { return localStorage.getItem(SPOTIFY_CLIENT_KEY) !== null; } catch { return false; }
}

async function startSpotify() {
  const { connect } = await import("./spotify.js");
  connect({
    button: els.spotify,
    queue: () => queue,
    queueReady: loadMore,
    volume,
    toast,
    // Session prete : les morceaux qui ont un identifiant se jouent en entier.
    ready(session) {
      spotify = session;
      syncPlaying();
    },
    // Fin de session (deconnexion, jeton expire, compte refuse) : extraits.
    ended() {
      const wasPlaying = source === spotify;
      spotify = null;
      if (wasPlaying) {
        source = preview;
        renderPlayer();
      }
      syncPlaying();
    },
    // Lecture, pause, position.
    state() {
      if (source !== spotify) return;
      syncPlaying();
      updateProgress();
    },
    time() { if (source === spotify) updateProgress(); },
    // Spotify enchaine la file envoyee et signale chaque nouveau morceau.
    track(row) {
      if (source !== spotify || row === playing) return;
      if (!queue.includes(row)) {
        // Morceau de la file d'un ancien depart : on passe a la file
        // actuelle, comme les extraits.
        if (!step(1)) source.pause();
        return;
      }
      playing = row;
      renderPlayer();
      growList();
      syncPlaying();
    },
    // Spotify n'a pas pu jouer ce morceau : son extrait a la place.
    fail(row) {
      if (source !== spotify || playing !== row) return;
      source = preview;
      preview.start(row);
      renderPlayer();
    },
  });
}

// ---------- Chargement ----------

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} : ${response.status}`);
  return response.json();
}

async function load() {
  try {
    const [catalog, nearest] = await Promise.all([fetchJson("data/catalog.json"), fetchJson("data/neighbors.json")]);
    tracks = catalog.tracks;
    genres = catalog.genres;
    neighbors = nearest;
    index = createIndex(tracks);
  } catch (err) {
    console.error(err);
    els.search.placeholder = "Couldn't load the catalogue — reload the page";
    return;
  }
  els.count.textContent = tracks.length.toLocaleString("en-US");
  renderExamples();
  els.search.disabled = false;
  els.surprise.disabled = false;
  els.search.placeholder = seed == null ? "Search a track or an artist" : "Track or artist";
  // A la souris, la recherche est prete a la frappe ; pas sur ecran tactile,
  // ou le clavier virtuel cacherait la page.
  if (seed == null && matchMedia("(hover: hover)").matches) els.search.focus();
}

load();
if (invited()) startSpotify().catch((err) => console.warn(err));
