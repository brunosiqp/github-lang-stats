# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

`github-lang-stats` generates two "Languages" cards, `language-stats.svg` (by number of repositories)
and `language-stats-size.svg` (by code size), with the percentage of each
language across **all** repositories owned by the GitHub user (public and private). The SVG is
embedded in `README.md` via `./language-stats.svg` and refreshed daily by a GitHub Actions workflow.

- Owner / GitHub account: `brunosiqp`
- Visibility: public repository (the SVG only exposes aggregate percentages, never repo names)
- Everything in the repository is in **English**: README, code comments, log messages and the
  workflow's commit message (`chore: update language stats`).
- License: MIT (`LICENSE`).

## Layout

| Path | Purpose |
|---|---|
| `language_stats.py` | The whole tool: fetch repos, count repositories per language, render SVG |
| `requirements.txt` | `requests` and `PyYAML` (to parse Linguist's `languages.yml`) |
| `.github/workflows/update-language-stats.yml` | Cron once a day at 07:37 Brasília (10:37 UTC); GitHub often starts it hours later, but it runs daily + `workflow_dispatch`; runs the script and commits the SVG |
| `language-stats.svg`, `language-stats-size.svg` | Generated output. **Never edit by hand**; the workflow overwrites them |

## Commands

```bash
pip install -r requirements.txt
export GH_TOKEN=...            # classic PAT with `repo` + `read:user`; never commit or paste it
python language_stats.py       # writes both SVGs and prints the percentages
```

Trigger the workflow manually:

```bash
gh workflow run update-language-stats.yml -R brunosiqp/github-lang-stats
gh run watch -R brunosiqp/github-lang-stats
```

## How the calculation works (important)

`language_stats.py` does **not** use the GitHub `/languages` endpoint. That endpoint counted
accidentally committed build output (PyInstaller `build/*.toc` showed up as 88% "TeX"). Instead:

1. `load_linguist()` downloads GitHub Linguist's `languages.yml` (through the API, so it works with
   the token) and fills `EXT_CANDIDATES` / `NAME_CANDIDATES` / `LANGUAGE_COLORS` with **every**
   language GitHub knows, with official colors. Only `programming` and `markup` types are counted;
   `data`/`prose` extensions go to `UNCOUNTED_KEYS`. If the download fails, the built-in
   `EXTENSIONS` / `FILENAMES` / `LANGUAGE_COLORS` tables are used as fallback.
2. `get_repos()` lists owned repos (`/user/repos?type=owner`, including forks and archived), so new
   public and private repos are picked up automatically. `get_contributed_repos()` adds other people's
   and organizations' repos (collaborator / organization member, plus GraphQL
   `repositoriesContributedTo` for commits and PRs). `aggregate_languages()` counts:
   - owned non-fork repos: every file;
   - forks: only files changed vs. upstream (`fork_files()`, compare API), never the upstream code;
   - third-party repos: only files touched by the user's last 100 commits (`authored_files()`).
   `aggregate_languages()` returns two totals from the same pass (`language_sizes()` per repository):
   - `by_repos` → `language-stats.svg`: each repository adds **1** to every language it has at least one
     counted file in, regardless of size (one huge Python project kept Python above 90% by size);
   - `by_size` → `language-stats-size.svg`: bytes of code per language.
   The user wants **both** cards shown on the profile.
3. `get_tree()` reads the recursive git tree of the default branch; `language_for()` maps each file
   by exact filename or longest extension (`.d.ts` before `.ts`).
4. Ambiguous extensions are resolved with the repo's `/languages` result (only a hint, never summed):
   `.gd` → GDScript (not GAP) in a Godot repo. Without a hint, the `EXTENSIONS` entry wins; an
   extension also claimed by data/prose (`.md` = Markdown and "GCC Machine Description") is not counted.
5. Files under `IGNORED_DIRS` (`build`, `dist`, `node_modules`, `venv`, ...) are ignored.
6. `IGNORED_EXTENSIONS` (`.sql`) are never counted, even though Linguist also maps `.sql` to TSQL/PLSQL.
   Generated multi-MB `.sql` files otherwise made SQL 94% of the chart.
7. `to_percentages()` returns every language, sorted, with no "Other" bucket; `fmt_pct()` adds decimals
   to small values (`0.04%`, `0.003%`) so no language shows as zero.

A new language usually needs no code change. Add to `EXTENSIONS` only to set a preference for an
ambiguous extension (and to the fallback `LANGUAGE_COLORS`).

## Conventions and gotchas

- The workflow pushes to `main` every day, so **run `git pull --rebase origin main` before pushing**;
  otherwise the push is rejected.
- The workflow needs `permissions: contents: write` and the repository secret `GH_PAT`.
  `GITHUB_TOKEN` cannot see other repos, so a personal token is required.
- SVG text must be XML-escaped (`html.escape`); a raw `<0.1%` once broke the file.
- Keep the script dependency-free apart from `requests` and `PyYAML`; target Python 3.12 (used by the workflow).
- The Actions log is public: never print repo names (private repos would leak), only aggregates.
- Test changes offline (`language_for()`, `build_svg()` + `xml.dom.minidom.parseString`) before running
  against the API. Do not commit `__pycache__/` (it is git-ignored).

## Git rules for this repo

- Author every commit and PR as `brunosiqp <168676931+brunosiqp@users.noreply.github.com>`
  (`git config user.name` / `user.email` locally). The workflow uses the same identity.
- No `Co-Authored-By: Claude` trailer and no "Generated with Claude Code" line in commits or PRs.
- Commit messages, PR titles and PR descriptions are written in **English**
  (Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`).
- Open changes as a pull request from a branch; do not push directly to `main` and do not merge unless asked.
