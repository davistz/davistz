"""Gera o card de stats do perfil (SVG claro e escuro) sem serviço de terceiros.

Contribuições: calendário público em github.com/users/<user>/contributions. Linguagens: API REST dos repositórios.
Uso: python stats/stats.py <pasta_saida>   (env OWNER, GITHUB_TOKEN opcional)
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, timedelta
from html import escape

USER = os.environ.get("OWNER", "davistz")
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
CORES_LING = {"TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "C#": "#178600", "HTML": "#e34c26",
              "CSS": "#663399", "SCSS": "#c6538c", "Java": "#b07219", "Shell": "#89e051", "PowerShell": "#012456",
              "TSQL": "#e38c00", "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883", "Dockerfile": "#384d54"}
TEMAS = {
    "dark": dict(bg="#0d1117", borda="#30363d", fg="#e6edf3", sub="#8b949e", acento="#ffc56b", vazio="#161b22", trilho="#21262d"),
    "light": dict(bg="#ffffff", borda="#d0d7de", fg="#1f2328", sub="#59636e", acento="#bf8700", vazio="#eff2f5", trilho="#eaeef2"),
}


def get(url, json_=True):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats", "Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN") and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        corpo = r.read().decode("utf-8")
    return json.loads(corpo) if json_ else corpo


def contribuicoes():
    html = get(f"https://github.com/users/{USER}/contributions", json_=False)
    datas = {i: d for d, i in re.findall(r'data-date="(\d{4}-\d{2}-\d{2})" id="([^"]+)"', html)}
    dias = {}
    for alvo, txt in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)', html):
        if alvo in datas:
            m = re.match(r"\s*(\d+)\s+contribution", txt)
            dias[datas[alvo]] = int(m.group(1)) if m else 0
    return dict(sorted(dias.items()))


def sequencias(dias, hoje):
    datas = sorted(dias)
    maior, atual, ini, melhor = 0, 0, None, (None, None)
    for d in datas:
        if dias[d] > 0:
            atual += 1
            ini = ini or d
            if atual > maior:
                maior, melhor = atual, (ini, d)
        else:
            atual, ini = 0, None
    # sequência atual: termina hoje ou ontem (hoje ainda pode não ter commit)
    cur, d = 0, hoje
    if dias.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    while dias.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= timedelta(days=1)
    return cur, maior, melhor


def linguagens():
    tot = {}
    for r in get(f"https://api.github.com/users/{USER}/repos?per_page=100"):
        if r["fork"] or r["name"] == USER:
            continue
        for ling, b in get(r["languages_url"]).items():
            tot[ling] = tot.get(ling, 0) + b
    soma = sum(tot.values()) or 1
    top = sorted(tot.items(), key=lambda x: -x[1])[:5]
    return [(l, 100 * b / soma) for l, b in top]


def fmt_data(iso):
    m = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    d = date.fromisoformat(iso)
    return f"{d.day} {m[d.month - 1]}"


def card(t, dias, cur, maior, melhor, langs):
    W, H = 880, 250
    fonte = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
    total = sum(dias.values())
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="{total} contribuições no último ano, sequência atual de {cur} dias, maior sequência de {maior} dias">',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="{t["bg"]}" stroke="{t["borda"]}"/>',
         f'<g font-family="{fonte}">']
    faixa = f"{fmt_data(melhor[0])} – {fmt_data(melhor[1])}" if melhor[0] else "—"
    for i, (num, rot, nota) in enumerate(((f"{total:,}".replace(",", "."), "contribuições", "nos últimos 12 meses"),
                                          (str(cur), "sequência atual", "dias seguidos"),
                                          (str(maior), "maior sequência", faixa))):
        x = 40 + i * 280
        s.append(f'<text x="{x}" y="66" font-size="38" font-weight="700" fill="{t["acento"] if i == 1 else t["fg"]}">{num}</text>'
                 f'<text x="{x}" y="90" font-size="14" font-weight="600" fill="{t["fg"]}">{rot}</text>'
                 f'<text x="{x}" y="108" font-size="12" fill="{t["sub"]}">{escape(nota)}</text>')
    # barras semanais
    semanas, acc = [], []
    for i, d in enumerate(dias):
        acc.append(dias[d])
        if len(acc) == 7 or i == len(dias) - 1:
            semanas.append(sum(acc))
            acc = []
    semanas = semanas[-53:]
    mx = max(semanas) or 1
    bw, gap, x0, base = 12, 3, 40, 178
    for i, v in enumerate(semanas):
        h = 3 + 42 * v / mx if v else 3
        s.append(f'<rect x="{x0 + i * (bw + gap)}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="2" '
                 f'fill="{t["acento"] if v else t["vazio"]}" opacity="{.35 + .65 * v / mx if v else 1:.2f}"/>')
    s.append(f'<text x="{W - 40}" y="128" font-size="11" fill="{t["sub"]}" text-anchor="end">contribuições por semana</text>')
    # linguagens
    x, y = 40, 200
    larg = W - 80
    s.append(f'<rect x="{x}" y="{y}" width="{larg}" height="8" rx="4" fill="{t["trilho"]}"/>')
    acc = x
    for l, p in langs:
        w = larg * p / 100
        s.append(f'<rect x="{acc:.1f}" y="{y}" width="{max(w, 1):.1f}" height="8" fill="{CORES_LING.get(l, "#8b949e")}"/>')
        acc += w
    lx = x
    for l, p in langs:
        rot = f"{l} {p:.0f}%"
        s.append(f'<circle cx="{lx + 5}" cy="{y + 30}" r="5" fill="{CORES_LING.get(l, "#8b949e")}"/>'
                 f'<text x="{lx + 15}" y="{y + 34}" font-size="12.5" fill="{t["fg"]}">{escape(rot)}</text>')
        lx += 160
    s.append('</g></svg>')
    return "\n".join(s)


def main():
    dias = contribuicoes()
    assert len(dias) > 300, f"calendário não lido ({len(dias)} dias)"
    cur, maior, melhor = sequencias(dias, date.today())
    langs = linguagens()
    os.makedirs(OUT, exist_ok=True)
    for nome, t in TEMAS.items():
        open(os.path.join(OUT, f"stats-{nome}.svg"), "w", encoding="utf-8").write(card(t, dias, cur, maior, melhor, langs))
    print(f"{sum(dias.values())} contribuições, sequência {cur}, maior {maior}, linguagens {langs}")


if __name__ == "__main__":
    # verificação rápida da lógica de sequência
    h = date(2026, 1, 10)
    d = {(h - timedelta(days=i)).isoformat(): v for i, v in enumerate([0, 2, 1, 0, 3, 3, 3, 0])}
    assert sequencias(d, h)[:2] == (2, 3), sequencias(d, h)
    main()
