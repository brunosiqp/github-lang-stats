# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

`github-lang-stats` generates `language-stats.svg`, a "Languages" card with the percentage of each
language across **all** repositories owned by the GitHub user (public and private). The SVG is
embedded in `README.md` via `./language-stats.svg` and refreshed daily by a GitHub Actions workflow.

- Owner / GitHub account: `brunosiqp`
- Visibility: public repository (the SVG only exposes aggregate percentages, never repo names)
- `README.md` is written in Portuguese; keep it that way unless asked otherwise.

## Layout

| Path | Purpose |
|---|---|
| `language_stats.py` | The whole tool: fetch repos, sum bytes per language, render SVG |
| `requirements.txt` | Only `requests` |
| `.github/workflows/update-language-stats.yml` | Daily cron (06:00 UTC) + `workflow_dispatch`; runs the script and commits the SVG |
| `language-stats.svg` | Generated output. **Never edit by hand**; the workflow overwrites it |

## Commands

```bash
pip install -r requirements.txt
export GH_TOKEN=...            # classic PAT with `repo` + `read:user`; never commit or paste it
python language_stats.py       # writes language-stats.svg and prints the percentages
```

Trigger the workflow manually:

```bash
gh workflow run update-language-stats.yml -R brunosiqp/github-lang-stats
gh run watch -R brunosiqp/github-lang-stats
```

## How the calculation works (important)

`language_stats.py` does **not** use the GitHub `/languages` endpoint. That endpoint counted
accidentally committed build output (PyInstaller `build/*.toc` showed up as 88% "TeX"). Instead:

1. `get_repos()` lists owned repos (`/user/repos?type=owner`); forks and archived repos are skipped.
2. `get_tree()` reads the recursive git tree of the default branch; `language_for()` maps each file
   to a language by extension (`EXTENSIONS`) or filename (`FILENAMES`).
3. Files under `IGNORED_DIRS` (`build`, `dist`, `node_modules`, `venv`, ...) are ignored.
4. `.sql`, JSON, YAML and Markdown are intentionally **not** counted (data/prose, like GitHub Linguist).
   Generated multi-MB `.sql` files otherwise made SQL 94% of the chart.
5. `to_percentages()` returns every language, sorted, with no "Other" bucket; values below 0.1% render as `<0.1%`.

When adding a language: add its extension to `EXTENSIONS` and a color to `LANGUAGE_COLORS`.

## Conventions and gotchas

- The workflow pushes to `main` every day, so **run `git pull --rebase origin main` before pushing**;
  otherwise the push is rejected.
- The workflow needs `permissions: contents: write` and the repository secret `GH_PAT`.
  `GITHUB_TOKEN` cannot see other repos, so a personal token is required.
- SVG text must be XML-escaped (`html.escape`); a raw `<0.1%` once broke the file.
- Keep the script dependency-free apart from `requests`; target Python 3.12 (used by the workflow).
- Test changes offline (`language_for()`, `build_svg()` + `xml.dom.minidom.parseString`) before running
  against the API. Do not commit `__pycache__/` (it is git-ignored).

## Git rules for this repo

- Author every commit and PR as `brunosiqp <168676931+brunosiqp@users.noreply.github.com>`
  (`git config user.name` / `user.email` locally). The workflow uses the same identity.
- No `Co-Authored-By: Claude` trailer and no "Generated with Claude Code" line in commits or PRs.
- Commit messages, PR titles and PR descriptions are written in **English**
  (Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`).
- Open changes as a pull request from a branch; do not push directly to `main` and do not merge unless asked.
