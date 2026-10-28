#!/usr/bin/env python3
"""
Builds a summary of the % of languages used across ALL repositories
(public and private) of a GitHub account and renders an SVG similar to
the "Most Used Languages" card from github-readme-stats.

How it works: for each repository (public or private) it reads the file
tree, finds which languages have at least one code file (by extension) and
counts 1 per repository for each of them, so one huge project does not dominate
the chart. It ignores generated folders (build/, dist/, node_modules/, venv/ ...). That way,
accidentally committed artifacts (e.g. a PyInstaller build) do not skew the
result, as they do with GitHub's /languages API.

The extension -> language table (and the colors) comes from GitHub Linguist
(languages.yml), downloaded on every run: any language GitHub recognizes
(GDScript, GDShader, ...) is counted without editing this file. Ambiguous
extensions (e.g. .gd = GDScript or GAP) are resolved with the languages
GitHub itself detected in the repository.

Requirements:
    pip install -r requirements.txt

Environment variables:
    GH_TOKEN   -> Personal Access Token with the "repo" scope (to read
                  private repositories) and "read:user".
    GH_USER    -> (optional) user/organization to analyze.
                  Defaults to the token owner.

Local usage:
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
USERNAME = os.environ.get("GH_USER")  # optional

if not TOKEN:
    sys.exit("Set the GH_TOKEN environment variable to a Personal Access Token.")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# GitHub's official language table (extensions, filenames and colors).
LINGUIST_URL = f"{API}/repos/github-linguist/linguist/contents/lib/linguist/languages.yml"
# Types GitHub counts in its language bar (data and prose are left out).
COUNTED_TYPES = {"programming", "markup"}

# Fallback colors, used if Linguist's languages.yml cannot be downloaded.
# Any language without a color gets a default gray.
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

# Preferred mapping, and fallback if Linguist cannot be downloaded: when an
# extension belongs to several languages, the one here comes first.
# Programming/markup languages only (data and prose such as JSON, YAML, SQL and
# Markdown are left out, like GitHub Linguist does).
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

# Never counted, even though Linguist maps them to a programming language
# (.sql is also TSQL/PLSQL): generated .sql dumps once made up 94% of the chart.
IGNORED_EXTENSIONS = {".sql"}

# extension / filename -> candidate languages (preferred first).
# load_linguist() fills in every language GitHub knows.
EXT_CANDIDATES = {ext: [lang] for ext, lang in EXTENSIONS.items()}
NAME_CANDIDATES = {name: [lang] for name, lang in FILENAMES.items()}
# Extensions/names also claimed by data or prose (.md = Markdown and
# "GCC Machine Description"): counted only if GitHub detected the language in the repo.
UNCOUNTED_KEYS = set()

# Generated/dependency folders: not code you wrote.
IGNORED_DIRS = {
    "build", "dist", "node_modules", "venv", ".venv", "__pycache__",
    "site-packages", "vendor", "target", "obj", ".git", ".idea", ".vscode",
    "third_party",
}

# In other people's repos, how many of the user's commits are read (the per-page maximum).
MAX_COMMITS_PER_REPO = 100

CONTRIBUTED_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositoriesContributedTo(first: 100, includeUserRepositories: false,
                              contributionTypes: [COMMIT, PULL_REQUEST]) {
      nodes { nameWithOwner }
    }
  }
}"""


def get_json(url, params=None):
    """GET from the API; None if the response is not 200 (empty repo, no access...)."""
    resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
    return resp.json() if resp.status_code == 200 else None


def get_all_pages(url, params):
    items = []
    page = 1
    while True:
        resp = requests.get(url, headers=HEADERS, params={**params, "per_page": 100, "page": page}, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        items.extend(batch)
        page += 1
    return items


def get_login():
    """User being analyzed: GH_USER or the token owner."""
    if USERNAME:
        return USERNAME
    resp = requests.get(f"{API}/user", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["login"]


def get_repos():
    """All repositories of the user/organization (owner, public+private, forks and archived)."""
    base_url = f"{API}/user/repos" if not USERNAME else f"{API}/users/{USERNAME}/repos"
    return get_all_pages(base_url, {"type": "owner"})


def get_contributed_repos(login, owned):
    """Other people's/organizations' repos the user has access to or contributed to."""
    names = set()
    if not USERNAME:
        repos = get_all_pages(f"{API}/user/repos", {"affiliation": "collaborator,organization_member"})
        names.update(repo["full_name"] for repo in repos)
    resp = requests.post(
        f"{API}/graphql",
        headers=HEADERS,
        json={"query": CONTRIBUTED_QUERY, "variables": {"login": login}},
        timeout=60,
    )
    user = ((resp.json().get("data") or {}).get("user") or {}) if resp.status_code == 200 else {}
    if not user:
        print(f"  warning: could not list contributions (HTTP {resp.status_code})")
    nodes = (user.get("repositoriesContributedTo") or {}).get("nodes", [])
    names.update(node["nameWithOwner"] for node in nodes)
    repos = (get_json(f"{API}/repos/{name}") for name in sorted(names - owned))
    return [repo for repo in repos if repo]


def fork_files(repo):
    """Files the fork changed compared with the upstream repo (the user's contributions)."""
    parent = repo.get("parent") or (get_json(repo["url"]) or {}).get("parent")
    if not parent:
        return set()
    data = get_json(
        f"{API}/repos/{parent['full_name']}/compare/"
        f"{parent['default_branch']}...{repo['owner']['login']}:{repo['default_branch']}"
    )
    return {f["filename"] for f in (data or {}).get("files", []) if f["status"] != "removed"}


def authored_files(repo, login):
    """Files touched by the user's commits in someone else's repo."""
    commits = get_json(
        f"{API}/repos/{repo['full_name']}/commits",
        {"author": login, "per_page": MAX_COMMITS_PER_REPO},
    ) or []
    files = set()
    for commit in commits:
        detail = get_json(commit["url"]) or {}
        files.update(f["filename"] for f in detail.get("files", []) if f["status"] != "removed")
    return files


def load_linguist():
    """Fills EXT_CANDIDATES, NAME_CANDIDATES and LANGUAGE_COLORS from Linguist."""
    try:
        resp = requests.get(
            LINGUIST_URL,
            headers={**HEADERS, "Accept": "application/vnd.github.raw"},
            timeout=60,
        )
        resp.raise_for_status()
        languages = yaml.safe_load(resp.text)
    except (requests.RequestException, yaml.YAMLError) as exc:
        print(f"  warning: Linguist languages.yml unavailable ({exc}); using built-in table")
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
    print(f"  {len(languages)} languages loaded from GitHub Linguist.")


def lookup_key(name):
    """Lookup key for a file: the exact name or the longest extension (.d.ts > .ts)."""
    if name in NAME_CANDIDATES or name in UNCOUNTED_KEYS:
        return name
    lower = name.lower()
    for i, ch in enumerate(lower):
        if ch == "." and (lower[i:] in EXT_CANDIDATES or lower[i:] in UNCOUNTED_KEYS
                          or lower[i:] in IGNORED_EXTENSIONS):
            return lower[i:]
    return None


def language_for(path, repo_languages=()):
    """Language of a file by its path, or None if it should be ignored.

    repo_languages are the languages GitHub detected in the repository; they
    break ties for ambiguous extensions (.gd -> GDScript instead of GAP).
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
    """Files (blobs) on the repository's default branch."""
    resp = requests.get(
        f"{API}/repos/{repo['full_name']}/git/trees/{repo['default_branch']}",
        headers=HEADERS,
        params={"recursive": "1"},
        timeout=60,
    )
    if resp.status_code == 409:  # empty repository
        return []
    if resp.status_code != 200:
        # No repo name: the Actions log is public and the repo may be private.
        print(f"  warning: could not read a repository (HTTP {resp.status_code})")
        return []
    data = resp.json()
    if data.get("truncated"):
        print("  warning: truncated tree in a repository (repo too large)")
    return [e for e in data.get("tree", []) if e["type"] == "blob"]


def get_repo_languages(repo):
    """Languages GitHub detected in the repo (used only to break ties)."""
    resp = requests.get(repo["languages_url"], headers=HEADERS, timeout=30)
    return set(resp.json()) if resp.status_code == 200 else set()


def languages_in(entries, only=None, repo_languages=()):
    """Set of languages with at least one file among the tree entries."""
    found = set()
    for entry in entries:
        if only is not None and entry["path"] not in only:
            continue
        lang = language_for(entry["path"], repo_languages)
        if lang:
            found.add(lang)
    return found


def aggregate_languages(repos, login):
    """Counts, per language, how many repositories use it.

    Each repository adds 1 to every language it has at least one file in, no matter
    how big the files are, so one huge project does not dominate the chart.
    Owned repos count in full. In forks and in other people's repos only the
    files the user changed count, so other people's code is never added.
    """
    totals = {}
    counts = {"own": 0, "forks": 0, "third_party": 0}
    for repo in repos:
        if repo["owner"]["login"].lower() != login.lower():
            kind, only = "third_party", authored_files(repo, login)
        elif repo.get("fork"):
            kind, only = "forks", fork_files(repo)
        else:
            kind, only = "own", None
        if only is not None and not only:
            continue  # fork/third-party repo with no changes from the user
        counts[kind] += 1
        for lang in languages_in(get_tree(repo), only, get_repo_languages(repo)):
            totals[lang] = totals.get(lang, 0) + 1
    print(
        f"  {counts['own']} owned repositories, {counts['forks']} forks and "
        f"{counts['third_party']} third-party repositories with your contributions."
    )
    return totals


def to_percentages(totals):
    """Every language, largest first (no "Other" bucket)."""
    total = sum(totals.values()) or 1
    items = [(lang, count / total * 100) for lang, count in totals.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    return items


def fmt_pct(pct):
    """1 decimal place; small values get more decimals until they show (0.04%, 0.003%)."""
    if round(pct, 1) >= 0.1:
        return f"{pct:.1f}%"
    for decimals in range(2, 7):
        if round(pct, decimals) > 0:
            return f"{pct:.{decimals}f}%"
    return "<0.000001%"


def build_svg(percentages, width=830, title="Most Used Languages"):
    pad = 28
    bar_y = 88
    bar_height = 12
    bar_width = width - 2 * pad
    columns = 4
    col_width = bar_width / columns
    legend_y = bar_y + bar_height + 40
    row_height = 28

    segments = []
    legend_items = []
    cursor = pad
    for i, (lang, pct) in enumerate(percentages):
        color = LANGUAGE_COLORS.get(lang, DEFAULT_COLOR)
        seg_width = bar_width * (pct / 100)
        segments.append(
            f'<rect x="{cursor:.2f}" y="{bar_y}" width="{seg_width:.2f}" '
            f'height="{bar_height}" fill="{color}" />'
        )
        cursor += seg_width

        row, col = divmod(i, columns)
        lx = pad + col * col_width
        ly = legend_y + row * row_height
        legend_items.append(
            f'<circle cx="{lx + 5:.1f}" cy="{ly - 4}" r="5" fill="{color}" />'
            f'<text x="{lx + 18:.1f}" y="{ly}"><tspan class="name">{escape(lang)}</tspan>'
            f'<tspan dx="6" class="pct">{escape(fmt_pct(pct))}</tspan></text>'
        )

    rows_used = (len(percentages) - 1) // columns + 1
    total_height = legend_y + (rows_used - 1) * row_height + 30

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">
  <style>
    .title {{ font: 600 20px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .subtitle {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #8b949e; }}
    .name {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #c9d1d9; }}
    .pct {{ font: 600 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #8b949e; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{total_height - 1}" rx="12" fill="#0d1117" stroke="#30363d" />
  <text x="{pad}" y="44" class="title">{escape(title)}</text>
  <text x="{pad}" y="66" class="subtitle">All repositories · public and private · by number of repositories</text>
  <clipPath id="barClip">
    <rect x="{pad}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_height / 2:.1f}" />
  </clipPath>
  <rect x="{pad}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_height / 2:.1f}" fill="#161b22" />
  <g clip-path="url(#barClip)">
    {''.join(segments)}
  </g>
  {''.join(legend_items)}
</svg>'''
    return svg


def main():
    print("Loading language table...")
    load_linguist()

    print("Fetching repositories...")
    login = get_login()
    repos = get_repos()
    print(f"{len(repos)} owned repositories found (public + private).")
    contributed = get_contributed_repos(login, {repo["full_name"] for repo in repos})
    print(f"{len(contributed)} third-party repositories with access or contributions.")

    print("Counting repositories per language...")
    totals = aggregate_languages(repos + contributed, login)

    percentages = to_percentages(totals)
    print("\nResult:")
    for lang, pct in percentages:
        print(f"  {lang:<20} {fmt_pct(pct)}")

    svg = build_svg(percentages)
    with open("language-stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("\nlanguage-stats.svg generated.")


if __name__ == "__main__":
    main()
