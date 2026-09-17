#!/usr/bin/env python3
"""
Gera um resumo de % de linguagens usadas em TODOS os repositórios
(públicos e privados) de uma conta do GitHub, e produz um SVG
parecido com o card "Most Used Languages" do github-readme-stats.

Requisitos:
    pip install -r requirements.txt

Variáveis de ambiente esperadas:
    GH_TOKEN   -> Personal Access Token com escopo "repo" (para ler
                  repositórios privados) e "read:user".
    GH_USER    -> (opcional) usuário/organização a analisar.
                  Se não definido, usa o dono do token (o "eu mesmo").

Uso local:
    export GH_TOKEN=ghp_xxx
    python language_stats.py
"""

import os
import sys
import requests

API = "https://api.github.com"

TOKEN = os.environ.get("GH_TOKEN")
USERNAME = os.environ.get("GH_USER")  # opcional

if not TOKEN:
    sys.exit("Defina a variável de ambiente GH_TOKEN com um Personal Access Token.")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Cores aproximadas do GitHub Linguist para as linguagens mais comuns.
# Qualquer linguagem fora dessa lista recebe uma cor cinza padrão.
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Java": "#b07219",
    "CMake": "#DA3434",
    "Shell": "#89e051",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Dockerfile": "#384d54",
    "Vue": "#41b883",
    "Jupyter Notebook": "#DA5B0B",
}
DEFAULT_COLOR = "#8b8b8b"


def get_repos():
    """Lista todos os repositórios do usuário/organização (owner, público+privado)."""
    repos = []
    page = 1
    base_url = f"{API}/user/repos" if not USERNAME else f"{API}/users/{USERNAME}/repos"
    while True:
        params = {"per_page": 100, "page": page, "type": "owner"}
        resp = requests.get(base_url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def get_languages(full_name):
    """Retorna dict {linguagem: bytes} para um repositório."""
    resp = requests.get(f"{API}/repos/{full_name}/languages", headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return {}
    return resp.json()


def aggregate_languages(repos):
    totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue  # ignora forks, ajuste se quiser incluir
        langs = get_languages(repo["full_name"])
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return totals


def to_percentages(totals, min_percent=0.4):
    total_bytes = sum(totals.values()) or 1
    items = [(lang, bytes_ / total_bytes * 100) for lang, bytes_ in totals.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    # agrupa linguagens muito pequenas em "Other"
    main = [i for i in items if i[1] >= min_percent]
    other = sum(i[1] for i in items if i[1] < min_percent)
    if other > 0:
        main.append(("Other", other))
    return main


def build_svg(percentages, width=700, height=220, title="Languages"):
    bar_height = 24
    bar_y = 60
    x = 20
    bar_width = width - 40

    segments = []
    legend_items = []
    cursor = x
    for i, (lang, pct) in enumerate(percentages):
        color = LANGUAGE_COLORS.get(lang, DEFAULT_COLOR)
        seg_width = bar_width * (pct / 100)
        rx = 6 if i == 0 else 0
        segments.append(
            f'<rect x="{cursor:.2f}" y="{bar_y}" width="{seg_width:.2f}" '
            f'height="{bar_height}" fill="{color}" />'
        )
        cursor += seg_width

        col = i % 3
        row = i // 3
        lx = x + col * 220
        ly = bar_y + bar_height + 40 + row * 26
        legend_items.append(
            f'<circle cx="{lx}" cy="{ly - 5}" r="5" fill="{color}" />'
            f'<text x="{lx + 14}" y="{ly}" class="legend-text">{lang} {pct:.1f}%</text>'
        )

    rows_used = (len(percentages) - 1) // 3 + 1
    total_height = bar_y + bar_height + 50 + rows_used * 26

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">
  <style>
    .title {{ font: 600 20px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .legend-text {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #d0d0d0; }}
  </style>
  <rect width="100%" height="100%" rx="8" fill="#0d1117" />
  <text x="20" y="35" class="title">{title}</text>
  <clipPath id="barClip">
    <rect x="{x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_height/2:.1f}" />
  </clipPath>
  <g clip-path="url(#barClip)">
    {''.join(segments)}
  </g>
  {''.join(legend_items)}
</svg>'''
    return svg


def main():
    print("Buscando repositórios...")
    repos = get_repos()
    print(f"{len(repos)} repositórios encontrados (públicos + privados).")

    print("Somando bytes de código por linguagem...")
    totals = aggregate_languages(repos)

    percentages = to_percentages(totals)
    print("\nResultado:")
    for lang, pct in percentages:
        print(f"  {lang:<20} {pct:.1f}%")

    svg = build_svg(percentages)
    with open("language-stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("\nArquivo language-stats.svg gerado com sucesso.")


if __name__ == "__main__":
    main()
