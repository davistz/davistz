"""Roda uma query da lista fixa sobre os dados públicos do GitHub do dono e escreve o resultado no README.

Entrada (env): TITLE (título da issue, "query: <nome>"), PLAYER (login de quem abriu), OWNER, GITHUB_TOKEN (opcional).
Saída: README.md atualizado, game/plays.json atualizado, game/comment.md com a resposta da issue.
Só nomes da lista QUERIES rodam: o título nunca vira SQL.
"""
import json, os, re, sqlite3, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYS = ROOT / "game" / "plays.json"
README = ROOT / "README.md"
COMMENT = ROOT / "game" / "comment.md"
START, END = "<!-- QUERY:START -->", "<!-- QUERY:END -->"

QUERIES = {
    "top_languages": """SELECT language, ROUND(100.0 * SUM(bytes) / (SELECT SUM(bytes) FROM langs), 1) AS pct
FROM langs GROUP BY language ORDER BY pct DESC LIMIT 5;""",
    "recent_repos": """SELECT name, language, pushed_at
FROM repos ORDER BY pushed_at DESC LIMIT 5;""",
    "biggest_repos": """SELECT name, language, size_kb
FROM repos ORDER BY size_kb DESC LIMIT 5;""",
    "leaderboard": """SELECT player, COUNT(*) AS queries
FROM plays GROUP BY player ORDER BY queries DESC, MAX(at) DESC LIMIT 5;""",
}


def gh(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load(db, owner, plays):
    db.execute("CREATE TABLE repos(name, language, pushed_at, size_kb)")
    db.execute("CREATE TABLE langs(repo, language, bytes)")
    db.execute("CREATE TABLE plays(player, query, at)")
    for r in gh(f"https://api.github.com/users/{owner}/repos?per_page=100"):
        if r["fork"] or r["name"] == owner:
            continue
        db.execute("INSERT INTO repos VALUES(?,?,?,?)", (r["name"], r["language"] or "-", r["pushed_at"][:10], r["size"]))
        for lang, b in gh(r["languages_url"]).items():
            db.execute("INSERT INTO langs VALUES(?,?,?)", (r["name"], lang, b))
    db.executemany("INSERT INTO plays VALUES(?,?,?)", [(p["player"], p["query"], p["at"]) for p in plays])


def table(cur):
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(out) if rows else "_(sem linhas)_"


def main():
    owner = os.environ["OWNER"]
    player = re.sub(r"[^A-Za-z0-9-]", "", os.environ.get("PLAYER", ""))[:39] or "anon"
    m = re.fullmatch(r"\s*query:\s*([a-z_]+)\s*", os.environ.get("TITLE", ""), re.I)
    key = m.group(1).lower() if m else ""
    if key not in QUERIES:
        COMMENT.write_text("Não conheço essa query. Opções: " + ", ".join(f"`{k}`" for k in QUERIES), encoding="utf-8")
        return

    plays = json.loads(PLAYS.read_text(encoding="utf-8")) if PLAYS.exists() else []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    plays.append({"player": player, "query": key, "at": now})

    db = sqlite3.connect(":memory:")
    load(db, owner, plays)
    result = table(db.execute(QUERIES[key]))

    block = f"""{START}
```sql
-- {key} · rodada por {player} em {now}
{QUERIES[key]}
```

{result}

<sub>{len(plays)} queries rodadas até agora</sub>
{END}"""
    text = README.read_text(encoding="utf-8")
    README.write_text(re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: block, text, flags=re.S), encoding="utf-8")
    PLAYS.write_text(json.dumps(plays, indent=1, ensure_ascii=False), encoding="utf-8")
    COMMENT.write_text(f"Pronto, @{player}! Resultado de `{key}`:\n\n{result}\n\nJá está no [perfil](https://github.com/{owner}).", encoding="utf-8")


if __name__ == "__main__":
    main()
