// Museme : morceaux entiers par Spotify (Web Playback SDK), pour les comptes
// invites. Charge par app.js seulement dans un navigateur ouvert une fois avec
// le lien prive #spotify=<Client ID> : le depot est public, l'identifiant de
// l'app n'y figure pas. Spotify n'accepte que les comptes ajoutes a l'app
// (mode developpement : 5 au maximum, Premium obligatoire).
//
// Connexion PKCE (sans secret) : ouvrir le lien prive suffit, il mene droit a
// Spotify. Jetons dans le localStorage de ce navigateur, partages avec l'app
// installee (Android) : la session reprend a chaque visite, jusqu'a ce que
// Spotify demande de se reconnecter (6 mois).
// Museme envoie a Spotify la file de lecture (depart + 50 voisins) : Spotify
// l'enchaine lui-meme et signale chaque nouveau morceau.

const CLIENT_KEY = "museme-spotify-client";
const TOKEN_KEY = "museme-spotify-token";
const LOGIN_KEY = "museme-spotify-login"; // sessionStorage : verificateur PKCE et state
const SCOPES = "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state";
const ACCOUNTS = "https://accounts.spotify.com";
const API = "https://api.spotify.com/v1";
const SDK_URL = "https://sdk.scdn.co/spotify-player.js";
const TICK_MS = 500;

// ---------- Fonctions pures (tests/spotify.test.mjs) ----------

export function base64url(bytes) {
  let text = "";
  for (const byte of new Uint8Array(bytes)) text += String.fromCharCode(byte);
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// Defi PKCE (RFC 7636, methode S256).
export async function challenge(verifier) {
  return base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
}

// 64 caracteres autorises par PKCE : un octet sur 64 valeurs, sans biais.
export function randomString(length) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  return Array.from(crypto.getRandomValues(new Uint8Array(length)), (b) => chars[b & 63]).join("");
}

// File de lecture -> URI envoyees a Spotify et position du morceau demande.
// Les morceaux sans identifiant sont sautes.
export function playList(queue, ids, row) {
  const rows = queue.filter((r) => ids[r]);
  if (!rows.includes(row)) return { uris: ids[row] ? [`spotify:track:${ids[row]}`] : [], position: 0 };
  return { uris: rows.map((r) => `spotify:track:${ids[r]}`), position: rows.indexOf(row) };
}

// Morceau joue par Spotify -> ligne du catalogue, de preference dans la file
// (deux lignes peuvent partager un identifiant). linked_from : Spotify a
// remplace le morceau demande par une autre edition (relinking).
export function rowOf(track, ids, queue) {
  if (!track) return null;
  const wanted = [track.id, track.linked_from?.id].filter(Boolean);
  const inQueue = queue.find((r) => wanted.includes(ids[r]));
  if (inQueue !== undefined) return inQueue;
  const row = ids.findIndex((id) => id && wanted.includes(id));
  return row >= 0 ? row : null;
}

// ---------- Stockage ----------

function read(storage, key) {
  try { return JSON.parse(storage.getItem(key)); } catch { return null; }
}

function write(storage, key, value) {
  try {
    if (value == null) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify(value));
  } catch { /* stockage indisponible */ }
}

// Invitation : #spotify=<Client ID> est garde dans ce navigateur, puis retire
// de l'adresse (un fragment n'est jamais envoye au serveur). opened : le lien
// vient d'etre ouvert.
function invitation() {
  const found = location.hash.match(/[#&]spotify=([0-9a-f]{32})\b/i);
  if (found) {
    write(localStorage, CLIENT_KEY, found[1]);
    history.replaceState(null, "", location.pathname + location.search);
  }
  return { clientId: read(localStorage, CLIENT_KEY), opened: Boolean(found) };
}

// ---------- Connexion et jetons ----------

const redirectUri = () => `${location.origin}/`;

async function login(clientId) {
  const verifier = randomString(64);
  const state = randomString(16);
  write(sessionStorage, LOGIN_KEY, { verifier, state });
  const params = new URLSearchParams({
    client_id: clientId, response_type: "code", redirect_uri: redirectUri(), scope: SCOPES,
    code_challenge_method: "S256", code_challenge: await challenge(verifier), state,
  });
  location.assign(`${ACCOUNTS}/authorize?${params}`);
}

async function tokenRequest(body) {
  const response = await fetch(`${ACCOUNTS}/api/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(data.error_description || data.error || `token ${response.status}`),
                        { code: data.error, status: response.status });
  }
  return data;
}

function saveTokens(data, previous) {
  const token = {
    access: data.access_token,
    // Le jeton de rafraichissement peut changer a chaque rafraichissement.
    refresh: data.refresh_token || previous?.refresh,
    expires: Date.now() + data.expires_in * 1000,
  };
  write(localStorage, TOKEN_KEY, token);
  return token;
}

// Retour de la page d'autorisation : ?code=...&state=... ou ?error=...
async function finishLogin(clientId) {
  const params = new URLSearchParams(location.search);
  if (!params.has("code") && !params.has("error")) return;
  const pending = read(sessionStorage, LOGIN_KEY);
  write(sessionStorage, LOGIN_KEY, null);
  history.replaceState(null, "", location.pathname);
  if (params.has("error")) throw new Error("Spotify connection cancelled");
  if (!pending || params.get("state") !== pending.state) throw new Error("Spotify connection failed — try again");
  saveTokens(await tokenRequest({
    grant_type: "authorization_code", code: params.get("code"), redirect_uri: redirectUri(),
    client_id: clientId, code_verifier: pending.verifier,
  }));
}

// ---------- Session ----------

export async function connect(hooks) {
  const { clientId, opened } = invitation();
  if (!clientId) return;
  const button = hooks.button;

  let player = null;
  let deviceId = null;
  let ids = [];
  let last = null;        // dernier etat du lecteur, avec son instant
  let expecting = null;   // ligne demandee, en attente de l'etat qui la confirme
  let expectTimer = null;
  let ticker = null;
  let refreshing = null;
  let configured = false; // shuffle et repeat coupes sur cet appareil

  function setButton(status) {
    const labels = { connect: "Connect Spotify", connecting: "Connecting…", ready: "Disconnect" };
    const titles = {
      connect: "Full tracks with Spotify Premium (invited accounts only)",
      connecting: "Connecting to Spotify — click to cancel",
      ready: "Full tracks with Spotify — click to disconnect",
    };
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-spotify");
    svg.append(use);
    const label = document.createElement("span");
    label.textContent = labels[status];
    button.replaceChildren(svg, label);
    button.title = titles[status];
    button.setAttribute("aria-label", `${labels[status]} — ${titles[status]}`);
    button.dataset.status = status;
    button.classList.toggle("is-on", status === "ready");
    button.hidden = false;
  }

  const signedOut = () => Object.assign(new Error("signed out"), { code: "signed_out" });

  // Jeton d'acces valide. rejected : jeton refuse par Spotify avant son heure,
  // a remplacer.
  async function accessToken(rejected) {
    const token = read(localStorage, TOKEN_KEY);
    if (!token) throw signedOut();
    if (!rejected && Date.now() < token.expires - 60_000) return token.access;
    refreshing ??= refresh(rejected ?? token.access).finally(() => { refreshing = null; });
    return refreshing;
  }

  // Un seul rafraichissement a la fois pour tous les onglets et l'app
  // installee, qui partagent les jetons : Spotify peut invalider l'ancien jeton
  // de rafraichissement des qu'il en donne un nouveau. Sous le verrou, on relit
  // les jetons : si un autre onglet vient de rafraichir, on prend les siens.
  function refresh(stale) {
    const run = async () => {
      const token = read(localStorage, TOKEN_KEY);
      if (!token) throw signedOut();
      if (token.access !== stale && Date.now() < token.expires - 60_000) return token.access;
      try {
        const data = await tokenRequest({ grant_type: "refresh_token", refresh_token: token.refresh, client_id: clientId });
        return saveTokens(data, token).access;
      } catch (err) {
        // Sans verrou (navigateur ancien), un autre onglet a pu passer avant.
        const now = read(localStorage, TOKEN_KEY);
        if (err.code === "invalid_grant" && now && now.refresh !== token.refresh) return now.access;
        throw err;
      }
    };
    return navigator.locks ? navigator.locks.request("museme-spotify-refresh", run) : run();
  }

  async function api(method, path, body, retry = true) {
    const access = await accessToken();
    const response = await fetch(API + path, {
      method,
      headers: { Authorization: `Bearer ${access}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (response.ok) return null;
    // Jeton refuse : un rafraichissement, puis un seul nouvel essai.
    if (response.status === 401 && retry) {
      await accessToken(access);
      return api(method, path, body, false);
    }
    const data = await response.json().catch(() => ({}));
    throw Object.assign(new Error(data.error?.message || `Spotify ${response.status}`), { status: response.status });
  }

  // Fin de session. signOut : oublier les jetons (deconnexion, jeton refuse).
  function end(message, signOut = true) {
    if (signOut) write(localStorage, TOKEN_KEY, null);
    clearInterval(ticker);
    clearTimeout(expectTimer);
    player?.disconnect();
    player = null;
    deviceId = null;
    last = null;
    expecting = null;
    setButton("connect");
    if (message) hooks.toast(message);
    hooks.ended();
  }

  // Erreur de jeton ou de compte : la session s'arrete. Sans morceau (row
  // null), le lecteur n'a pas demarre. Sinon, le morceau seul est concerne.
  function failed(err, row) {
    if (err.code === "invalid_grant" || err.code === "signed_out" || err.status === 401) {
      end("Spotify session expired — connect again");
    } else if (err.status === 403 && /regist|premium|user/i.test(err.message)) {
      end(`Spotify: ${err.message}`);
    } else if (row == null) {
      console.warn(err);
      end("Spotify player unavailable", false);
    } else {
      console.warn(err);
      hooks.toast("Spotify couldn't play this track — playing the preview");
      hooks.fail(row);
    }
  }

  const session = {
    has: (row) => deviceId != null && Boolean(ids[row]),
    trackUrl: (row) => (ids[row] ? `https://open.spotify.com/track/${ids[row]}` : null),
    start(row) {
      // Dans le geste de l'utilisateur : debloque la lecture sur mobile.
      player.activateElement?.();
      expecting = row;
      clearTimeout(expectTimer);
      hooks.state();
      (async () => {
        await hooks.queueReady();
        const { uris, position } = playList(hooks.queue(), ids, row);
        const body = { uris, offset: { position } };
        try {
          await api("PUT", `/me/player/play?device_id=${deviceId}`, body);
        } catch (err) {
          // Appareil pas encore connu de Spotify : un second essai.
          if (err.status !== 404) throw err;
          await new Promise((resolve) => setTimeout(resolve, 1000));
          await api("PUT", `/me/player/play?device_id=${deviceId}`, body);
        }
        if (!configured) {
          configured = true;
          api("PUT", `/me/player/shuffle?state=false&device_id=${deviceId}`).catch(() => {});
          api("PUT", `/me/player/repeat?state=off&device_id=${deviceId}`).catch(() => {});
        }
        // Sans etat confirmant le morceau, on cesse d'attendre.
        expectTimer = setTimeout(() => {
          expecting = null;
          hooks.state();
        }, 8000);
      })().catch((err) => {
        if (expecting === row) expecting = null;
        failed(err, row);
        hooks.state();
      });
    },
    resume: () => player?.resume(),
    pause: () => player?.pause(),
    get paused() { return expecting == null && (!last || last.paused); },
    get position() {
      if (!last || expecting != null) return 0;
      const elapsed = last.paused ? 0 : performance.now() - last.at;
      return Math.min(last.duration, last.position + elapsed) / 1000;
    },
    get duration() { return last && expecting == null ? last.duration / 1000 : 0; },
    seek(seconds) {
      player?.seek(Math.round(seconds * 1000));
      if (last) last = { ...last, position: seconds * 1000, at: performance.now() };
    },
    setVolume: (value) => player?.setVolume(value),
  };

  async function start() {
    setButton("connecting");
    try {
      const [Spotify, catalogIds] = await Promise.all([
        new Promise((resolve, reject) => {
          if (window.Spotify) return resolve(window.Spotify);
          window.onSpotifyWebPlaybackSDKReady = () => resolve(window.Spotify);
          const script = document.createElement("script");
          script.src = SDK_URL;
          script.onerror = () => reject(new Error("Spotify player unavailable"));
          document.head.append(script);
        }),
        fetch("data/spotify.json").then((r) => (r.ok ? r.json() : [])),
      ]);
      ids = catalogIds;
      await accessToken();
      player = new Spotify.Player({
        name: "Museme",
        getOAuthToken: (callback) => accessToken().then(callback, (err) => failed(err, null)),
        volume: hooks.volume(),
      });
      player.addListener("ready", ({ device_id: id }) => {
        deviceId = id;
        setButton("ready");
        if (!ids.some(Boolean)) hooks.toast("Full tracks aren't available yet");
        hooks.ready(session);
      });
      player.addListener("not_ready", () => {
        deviceId = null;
        setButton("connecting");
      });
      player.addListener("player_state_changed", (state) => {
        if (!state) {
          // Lecture passee sur un autre appareil du compte.
          last = null;
          hooks.state();
          return;
        }
        last = { paused: state.paused, position: state.position, duration: state.duration, at: performance.now() };
        const row = rowOf(state.track_window?.current_track, ids, hooks.queue());
        if (expecting != null) {
          if (row !== expecting) return;
          expecting = null;
          clearTimeout(expectTimer);
        } else if (row != null) {
          hooks.track(row);
        }
        hooks.state();
      });
      player.addListener("initialization_error", ({ message }) => {
        console.warn(message);
        end("This browser can't play Spotify tracks", false);
      });
      player.addListener("authentication_error", () => end("Spotify session expired — connect again"));
      player.addListener("account_error", () => end("Spotify Premium is required for full tracks"));
      player.addListener("playback_error", ({ message }) => {
        console.warn(message);
        hooks.toast("Spotify playback error");
      });
      player.addListener("autoplay_failed", () => hooks.toast("Press play to start"));
      ticker = setInterval(() => { if (last && !last.paused) hooks.time(); }, TICK_MS);
      if (!(await player.connect())) end("Spotify player unavailable", false);
    } catch (err) {
      failed(err, null);
    }
  }

  button.addEventListener("click", () => {
    if (button.dataset.status === "connect") {
      login(clientId).catch((err) => hooks.toast(err.message));
    } else {
      end(null);
    }
  });

  setButton("connect");
  try {
    await finishLogin(clientId);
  } catch (err) {
    hooks.toast(err.message);
  }
  if (read(localStorage, TOKEN_KEY)) start();
  // Lien prive ouvert sans session : droit a Spotify, sans passer par le
  // bouton. Spotify saute sa page d'accord si elle a deja ete acceptee.
  else if (opened) login(clientId).catch((err) => hooks.toast(err.message));
}
