#!/usr/bin/env python3
"""
Gera um resumo de % de linguagens usadas em TODOS os repositórios
(públicos e privados) de uma conta do GitHub, e produz um SVG
parecido com o card "Most Used Languages" do github-readme-stats.

Como calcula: para cada repositorio (publico ou privado) lê a árvore de
arquivos, soma o tamanho em bytes de cada arquivo de código por extensão e
ignora pastas geradas (build/, dist/, node_modules/, venv/ ...). Assim
artefatos commitados sem querer (ex.: build do PyInstaller) não distorcem
o resultado, como acontece com a API /languages do GitHub.

A tabela extensão -> linguagem (e as cores) vem do GitHub Linguist
(languages.yml), baixada a cada execução: qualquer linguagem que o GitHub
reconhece (GDScript, GDShader, ...) entra no cálculo sem editar este arquivo.
Extensões ambíguas (ex.: .gd = GDScript ou GAP) são resolvidas pelas
linguagens que o próprio GitHub detectou no repositório.

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
from html import escape

import requests
import yaml

API = "https://api.github.com"

TOKEN = os.environ.get("GH_TOKEN")
USERNAME = os.environ.get("GH_USER")  # opcional

if not TOKEN:
    sys.exit("Defina a variável de ambiente GH_TOKEN com um Personal Access Token.")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Tabela oficial de linguagens do GitHub (extensoes, nomes de arquivo e cores).
LINGUIST_URL = f"{API}/repos/github-linguist/linguist/contents/lib/linguist/languages.yml"
# Tipos que o GitHub conta na barra de linguagens (data e prose ficam de fora).
COUNTED_TYPES = {"programming", "markup"}

# Cores de reserva, usadas se o languages.yml do Linguist nao puder ser baixado.
# Qualquer linguagem sem cor recebe um cinza padrão.
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
    "Batchfile": "#C1F12E",
    "PowerShell": "#012456",
    "SQL": "#e38c00",
    "SCSS": "#c6538c",
    "Lua": "#000080",
    "R": "#198CE7",
    "Dart": "#00B4AB",
    "TeX": "#3D6117",
    "VBScript": "#15dcdc",
    "GDScript": "#355570",
    "GDShader": "#478CBF",
}
DEFAULT_COLOR = "#8b8b8b"

# Mapeamento preferido, e de reserva se o Linguist nao puder ser baixado: quando
# uma extensao pertence a varias linguagens, a daqui vem primeiro.
# Somente linguagens de programacao/markup (dados e prosa como JSON, YAML, SQL e
# Markdown ficam de fora, igual ao GitHub Linguist).
EXTENSIONS = {
    ".py": "Python", ".pyw": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS",
    ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".dart": "Dart",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
    ".sh": "Shell", ".bash": "Shell",
    ".bat": "Batchfile", ".cmd": "Batchfile",
    ".ps1": "PowerShell", ".psm1": "PowerShell",
    ".vue": "Vue", ".lua": "Lua", ".r": "R",
    ".ipynb": "Jupyter Notebook", ".cmake": "CMake", ".tex": "TeX", ".vbs": "VBScript",
    ".gd": "GDScript", ".gdshader": "GDShader", ".gdshaderinc": "GDShader",
}
FILENAMES = {"CMakeLists.txt": "CMake", "Dockerfile": "Dockerfile"}

# Nunca contadas, mesmo que o Linguist as associe a uma linguagem de programacao
# (.sql tambem e TSQL/PLSQL): dumps .sql gerados chegaram a ser 94% do grafico.
IGNORED_EXTENSIONS = {".sql"}

# extensao / nome de arquivo -> linguagens candidatas (a preferida primeiro).
# load_linguist() completa com todas as linguagens do GitHub.
EXT_CANDIDATES = {ext: [lang] for ext, lang in EXTENSIONS.items()}
NAME_CANDIDATES = {name: [lang] for name, lang in FILENAMES.items()}
# Extensoes/nomes que tambem pertencem a dados ou prosa (.md = Markdown e
# "GCC Machine Description"): so contam se o GitHub detectou a linguagem no repo.
UNCOUNTED_KEYS = set()

# Pastas geradas/dependencias: nao sao codigo escrito por voce.
IGNORED_DIRS = {
    "build", "dist", "node_modules", "venv", ".venv", "__pycache__",
    "site-packages", "vendor", "target", "obj", ".git", ".idea", ".vscode",
    "third_party",
}


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


def load_linguist():
    """Completa EXT_CANDIDATES, NAME_CANDIDATES e LANGUAGE_COLORS com o Linguist."""
    try:
        resp = requests.get(
            LINGUIST_URL,
            headers={**HEADERS, "Accept": "application/vnd.github.raw"},
            timeout=60,
        )
        resp.raise_for_status()
        languages = yaml.safe_load(resp.text)
    except (requests.RequestException, yaml.YAMLError) as exc:
        print(f"  aviso: languages.yml do Linguist indisponivel ({exc}); usando tabela interna")
        return
    for lang, info in languages.items():
        if info.get("color"):
            LANGUAGE_COLORS[lang] = info["color"]
        counted = info.get("type") in COUNTED_TYPES
        for table, keys in (
            (EXT_CANDIDATES, [e.lower() for e in info.get("extensions", [])]),
            (NAME_CANDIDATES, info.get("filenames", [])),
        ):
            for key in keys:
                if not counted:
                    UNCOUNTED_KEYS.add(key)
                    continue
                candidates = table.setdefault(key, [])
                if lang not in candidates:
                    candidates.append(lang)
    print(f"  {len(languages)} linguagens carregadas do GitHub Linguist.")


def lookup_key(name):
    """Chave do arquivo nas tabelas: o nome exato ou a extensao mais longa (.d.ts > .ts)."""
    if name in NAME_CANDIDATES or name in UNCOUNTED_KEYS:
        return name
    lower = name.lower()
    for i, ch in enumerate(lower):
        if ch == "." and (lower[i:] in EXT_CANDIDATES or lower[i:] in UNCOUNTED_KEYS
                          or lower[i:] in IGNORED_EXTENSIONS):
            return lower[i:]
    return None


def language_for(path, repo_languages=()):
    """Linguagem de um arquivo pelo caminho, ou None se deve ser ignorado.

    repo_languages sao as linguagens que o GitHub detectou no repositorio e
    desempatam extensoes ambiguas (.gd -> GDScript em vez de GAP).
    """
    parts = path.split("/")
    if any(p.lower() in IGNORED_DIRS for p in parts[:-1]):
        return None
    key = lookup_key(parts[-1])
    if key is None or key in IGNORED_EXTENSIONS:
        return None
    candidates = NAME_CANDIDATES.get(key) or EXT_CANDIDATES.get(key, [])
    in_repo = [lang for lang in candidates if lang in repo_languages]
    if in_repo:
        return in_repo[0]
    if key in EXTENSIONS or key in FILENAMES:
        return candidates[0]
    if not candidates or key in UNCOUNTED_KEYS:
        return None
    return candidates[0]


def get_tree(repo):
    """Arquivos (blobs) da branch padrao do repositorio."""
    resp = requests.get(
        f"{API}/repos/{repo['full_name']}/git/trees/{repo['default_branch']}",
        headers=HEADERS,
        params={"recursive": "1"},
        timeout=60,
    )
    if resp.status_code == 409:  # repositorio vazio
        return []
    if resp.status_code != 200:
        # Sem o nome do repo: o log do Actions e publico e o repo pode ser privado.
        print(f"  aviso: nao foi possivel ler um repositorio (HTTP {resp.status_code})")
        return []
    data = resp.json()
    if data.get("truncated"):
        print("  aviso: arvore truncada em um repositorio (repo muito grande)")
    return [e for e in data.get("tree", []) if e["type"] == "blob"]


def get_repo_languages(repo):
    """Linguagens que o GitHub detectou no repo (usadas so para desempate)."""
    resp = requests.get(repo["languages_url"], headers=HEADERS, timeout=30)
    return set(resp.json()) if resp.status_code == 200 else set()


def aggregate_languages(repos):
    totals = {}
    analyzed = 0
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue  # ignora forks/arquivados, ajuste se quiser incluir
        analyzed += 1
        repo_languages = get_repo_languages(repo)
        for entry in get_tree(repo):
            lang = language_for(entry["path"], repo_languages)
            if lang:
                totals[lang] = totals.get(lang, 0) + entry.get("size", 0)
    print(f"  {analyzed} repositórios analisados (forks e arquivados ficam de fora).")
    return totals


def to_percentages(totals):
    """Todas as linguagens, da maior para a menor (sem agrupar em "Other")."""
    total_bytes = sum(totals.values()) or 1
    items = [(lang, bytes_ / total_bytes * 100) for lang, bytes_ in totals.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    return items


def fmt_pct(pct):
    """1 casa decimal; valores pequenos ganham casas ate aparecer (0.04%, 0.003%)."""
    if round(pct, 1) >= 0.1:
        return f"{pct:.1f}%"
    for decimals in range(2, 7):
        if round(pct, decimals) > 0:
            return f"{pct:.{decimals}f}%"
    return "<0.000001%"


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
            f'<text x="{lx + 14}" y="{ly}" class="legend-text">{escape(f"{lang} {fmt_pct(pct)}")}</text>'
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
    print("Carregando tabela de linguagens...")
    load_linguist()

    print("Buscando repositórios...")
    repos = get_repos()
    print(f"{len(repos)} repositórios encontrados (públicos + privados).")

    print("Somando bytes de código por linguagem...")
    totals = aggregate_languages(repos)

    percentages = to_percentages(totals)
    print("\nResultado:")
    for lang, pct in percentages:
        print(f"  {lang:<20} {fmt_pct(pct)}")

    svg = build_svg(percentages)
    with open("language-stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("\nArquivo language-stats.svg gerado com sucesso.")


if __name__ == "__main__":
    main()
