"""Banc d'essai : page d'ecoute a l'aveugle (notebooks/evaluation_audio.ipynb).

Pour chaque morceau-requete, les candidats proposes par les variantes sont
melanges, sans indiquer la variante. On note chaque candidat : proche, moyen
ou sans rapport. Les reponses restent dans le navigateur (reprise possible)
et s'exportent en CSV (q, c, note) ; la cle (quelle variante a propose quel
candidat) reste dans le notebook.
"""
import html

PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ecoute a l'aveugle</title>
<style>
:root {{ --bg: #fafaf9; --card: #ffffff; --text: #1c1917; --muted: #78716c; --line: #e7e5e4; --accent: #2563eb; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #1c1917; --card: #292524; --text: #f5f5f4; --muted: #a8a29e; --line: #44403c; --accent: #60a5fa; }}
}}
body {{ background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, sans-serif; margin: 0; }}
main {{ max-width: 860px; margin: 0 auto; padding: 16px; }}
header {{ position: sticky; top: 0; background: var(--bg); padding: 8px 0; border-bottom: 1px solid var(--line); z-index: 1; }}
.bloc {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 16px; margin: 16px 0; }}
.requete {{ font-weight: 600; margin-bottom: 8px; }}
.cand {{ display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; align-items: center; padding: 8px 0; border-top: 1px solid var(--line); }}
.titre {{ color: var(--muted); font-size: 13px; }}
audio {{ width: 100%; height: 32px; }}
.notes label {{ margin-left: 8px; white-space: nowrap; }}
button {{ background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 6px 12px; font: inherit; cursor: pointer; }}
@media (max-width: 600px) {{ .cand {{ grid-template-columns: 1fr; }} .notes label {{ margin: 0 8px 0 0; }} }}
</style>
</head>
<body>
<main>
<header>
  <strong>Ecoute a l'aveugle</strong> — <span id="avancement"></span>
  <button id="exporter">Exporter mes reponses</button>
</header>
<p>Pour chaque morceau, ecoutez-le, puis notez chaque proposition : <b>proche</b>, <b>moyen</b> ou
<b>sans rapport</b>. L'ordre des propositions est tire au sort et ne dit rien de leur origine.
Les reponses sont gardees dans ce navigateur : vous pouvez fermer la page et reprendre.
A la fin, « Exporter mes reponses » telecharge <code>ecoute_reponses.csv</code>.</p>
{blocs}
</main>
<script>
const CLE = "museme-ecoute-{version}";
let reponses = {{}};
try {{ reponses = JSON.parse(localStorage.getItem(CLE) || "{{}}"); }} catch (e) {{}}
const radios = document.querySelectorAll("input[type=radio]");
const total = new Set([...radios].map(r => r.name)).size;
function sauver() {{ try {{ localStorage.setItem(CLE, JSON.stringify(reponses)); }} catch (e) {{}} }}
function avancement() {{
  document.getElementById("avancement").textContent = Object.keys(reponses).length + " / " + total + " notes";
}}
radios.forEach(r => {{
  if (reponses[r.name] === r.value) r.checked = true;
  r.addEventListener("change", () => {{ reponses[r.name] = r.value; sauver(); avancement(); }});
}});
document.querySelectorAll("audio").forEach(a => a.addEventListener("play", () => {{
  document.querySelectorAll("audio").forEach(b => {{ if (b !== a) b.pause(); }});
}}));
document.getElementById("exporter").addEventListener("click", () => {{
  const lignes = ["q,c,note"];
  for (const [nom, note] of Object.entries(reponses)) {{
    const [, q, c] = nom.split("_");
    lignes.push(q + "," + c + "," + note);
  }}
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([lignes.join("\\n") + "\\n"], {{ type: "text/csv" }}));
  lien.download = "ecoute_reponses.csv";
  lien.click();
}});
avancement();
</script>
</body>
</html>
"""


def write_page(requetes, candidats, path, version="1"):
    """requetes : DataFrame (q, Song, Artist, audio) ; candidats : DataFrame
    (q, c, Song, Artist, audio), dans l'ordre d'affichage. audio : chemin ou
    URL de l'extrait, relatif a la page. Change version pour repartir de zero."""
    blocs = []
    for req in requetes.itertuples():
        lignes = [
            f'<div class="bloc"><div class="requete">{req.q}. {html.escape(req.Song)} — '
            f'{html.escape(req.Artist)}</div>'
            f'<audio controls preload="none" src="{html.escape(req.audio)}"></audio>'
        ]
        for cand in candidats[candidats["q"] == req.q].itertuples():
            nom = f"n_{req.q}_{cand.c}"
            notes = "".join(
                f'<label><input type="radio" name="{nom}" value="{v}"> {lib}</label>'
                for v, lib in ((2, "proche"), (1, "moyen"), (0, "sans rapport")))
            lignes.append(
                f'<div class="cand"><div><div class="titre">{html.escape(cand.Song)} — '
                f'{html.escape(cand.Artist)}</div>'
                f'<audio controls preload="none" src="{html.escape(cand.audio)}"></audio></div>'
                f'<div class="notes">{notes}</div></div>')
        lignes.append("</div>")
        blocs.append("\n".join(lignes))
    path.write_text(PAGE.format(blocs="\n".join(blocs), version=version), encoding="utf-8")
