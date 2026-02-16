#!/usr/bin/env python3
"""
Generate GitHub profile SVG cards by calling the GitHub API directly.
Replaces the rate-limited public github-readme-stats.vercel.app instance.

Generates: stats.svg, top-langs.svg, pin-rank-analysis.svg
Style matches the original github-readme-stats dark theme.
"""

import json
import math
import os
import sys
import urllib.request
import urllib.error

TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER = os.environ.get("GITHUB_USER", "wnzzer")
OUTPUT = os.environ.get("OUTPUT_DIR", "dist")

# Theme
BG = "#0D1117"
TITLE_CLR = "#00D9FF"
ICON_CLR = "#00ffa3"
TEXT_CLR = "#8B949E"
BOLD_CLR = "#C9D1D9"
BR = 15
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

# ── GitHub API helpers ───────────────────────────────────────────────

def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def rest(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def esc(s):
    """Escape XML special characters."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt(n):
    """Format a number (1234 -> 1.2k)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ── Data fetching ────────────────────────────────────────────────────

def fetch_user_data():
    q = """
    {
      user(login: "%s") {
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
        }
        repositoriesContributedTo(
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) { totalCount }
        pullRequests { totalCount }
        issues { totalCount }
        repositories(
          first: 100
          ownerAffiliations: OWNER
          orderBy: { field: STARGAZERS, direction: DESC }
        ) {
          nodes {
            stargazerCount
            languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
              edges {
                size
                node { name color }
              }
            }
          }
        }
      }
    }
    """ % USER

    u = graphql(q)["user"]
    cc = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]

    # Aggregate language sizes
    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            c = e["node"]["color"] or "#858585"
            langs.setdefault(n, {"color": c, "size": 0})
            langs[n]["size"] += e["size"]

    total_size = sum(v["size"] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: -x[1]["size"])[:8]
    lang_list = [
        {"name": n, "color": d["color"], "pct": round(d["size"] / total_size * 100, 1)}
        for n, d in top
    ]

    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contribs": u["repositoriesContributedTo"]["totalCount"],
        "langs": lang_list,
    }


def fetch_repo(name):
    return rest(f"/repos/{USER}/{name}")


# ── SVG icon paths (16×16 viewBox, from Octicons) ───────────────────

ICONS = {
    "star": '<path fill-rule="evenodd" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"/>',
    "commit": '<path fill-rule="evenodd" d="M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z"/>',
    "pr": '<path fill-rule="evenodd" d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/>',
    "issue": '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z"/>',
    "repo": '<path fill-rule="evenodd" d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1h-8a1 1 0 00-1 1v6.708A2.486 2.486 0 014.5 9h8.5V1.5zm-3.25 7h-.5a.75.75 0 010-1.5h.5a.75.75 0 010 1.5zm-3-4h3.5a.75.75 0 010 1.5h-3.5a.75.75 0 010-1.5z"/>',
    "fork": '<path fill-rule="evenodd" d="M5 3.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm0 2.122a2.25 2.25 0 10-1.5 0v.878A2.25 2.25 0 005.75 8.5h1.5v2.128a2.251 2.251 0 101.5 0V8.5h1.5a2.25 2.25 0 002.25-2.25v-.878a2.25 2.25 0 10-1.5 0v.878a.75.75 0 01-.75.75h-4.5A.75.75 0 015 6.25v-.878zm3.75 7.378a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm3-8.75a.75.75 0 100-1.5.75.75 0 000 1.5z"/>',
}


def icon(name, color=ICON_CLR):
    return f'<svg width="16" height="16" viewBox="0 0 16 16" fill="{color}">{ICONS[name]}</svg>'


# ── Card generators ──────────────────────────────────────────────────

def stats_card(data):
    """GitHub stats card (similar to github-readme-stats default)."""
    W, H = 495, 195

    rows_data = [
        ("star",   "Total Stars Earned", data["stars"]),
        ("commit", "Total Commits",      data["commits"]),
        ("pr",     "Total PRs",          data["prs"]),
        ("issue",  "Total Issues",       data["issues"]),
        ("repo",   "Contributed to",     data["contribs"]),
    ]

    rows = ""
    for i, (ic, label, val) in enumerate(rows_data):
        y = 48 + i * 25
        rows += f"""
    <g transform="translate(0, {y})">
      <g transform="translate(25, 0)">{icon(ic)}</g>
      <text x="50" y="12.5" fill="{TEXT_CLR}" font-size="14" font-family="{FONT}">{label}:</text>
      <text x="350" y="12.5" fill="{BOLD_CLR}" font-size="14" font-weight="700" font-family="{FONT}" text-anchor="end">{fmt(val)}</text>
    </g>"""

    # Rank circle (decorative)
    rank_x, rank_y, rank_r = 430, 100, 40
    circle = f"""
    <g transform="translate({rank_x}, {rank_y})">
      <circle r="{rank_r}" fill="none" stroke="{TITLE_CLR}" stroke-width="6" opacity="0.2"/>
      <circle r="{rank_r}" fill="none" stroke="{TITLE_CLR}" stroke-width="6"
              stroke-dasharray="{int(2 * math.pi * rank_r * 0.7)} {int(2 * math.pi * rank_r)}"
              transform="rotate(-90)" stroke-linecap="round"/>
      <text x="0" y="8" fill="{TITLE_CLR}" font-size="24" font-weight="700"
            font-family="{FONT}" text-anchor="middle">A</text>
    </g>"""

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="{BR}"/>
  <text x="25" y="30" fill="{TITLE_CLR}" font-size="18" font-weight="700" font-family="{FONT}">{esc(USER)}&apos;s GitHub Stats</text>
  {rows}
  {circle}
</svg>
"""


def langs_card(langs):
    """Top languages card (donut-vertical layout)."""
    if not langs:
        return '<svg xmlns="http://www.w3.org/2000/svg"/>'

    W = 350
    cx, cy, r = 175, 130, 70
    stroke_w = 30
    circumference = 2 * math.pi * r

    # Donut segments
    segments = ""
    offset = 0
    for lang in langs:
        length = circumference * lang["pct"] / 100
        segments += f"""
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
              stroke="{lang['color']}" stroke-width="{stroke_w}"
              stroke-dasharray="{length:.2f} {circumference - length:.2f}"
              stroke-dashoffset="{-offset:.2f}"
              transform="rotate(-90, {cx}, {cy})"/>"""
        offset += length

    # Legend below donut
    legend_y_start = cy + r + stroke_w // 2 + 30
    cols = 2
    col_width = W // cols
    legend = ""
    for i, lang in enumerate(langs):
        col = i % cols
        row = i // cols
        x = 25 + col * col_width
        y = legend_y_start + row * 22
        legend += f"""
      <g transform="translate({x}, {y})">
        <circle cx="6" cy="-4" r="6" fill="{lang['color']}"/>
        <text x="18" y="0" fill="{TEXT_CLR}" font-size="12" font-family="{FONT}">{esc(lang['name'])} {lang['pct']:.1f}%</text>
      </g>"""

    legend_rows = math.ceil(len(langs) / cols)
    H = legend_y_start + legend_rows * 22 + 15

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="{BR}"/>
  <text x="25" y="30" fill="{TITLE_CLR}" font-size="18" font-weight="700" font-family="{FONT}">Most Used Languages</text>
  <g>{segments}
  </g>
  <g>{legend}
  </g>
</svg>
"""


def pin_card(repo):
    """Repository pin card (similar to github-readme-stats pin)."""
    W, H = 400, 150
    name = esc(repo["name"])
    desc = esc(repo.get("description") or "No description provided.")
    stars = repo["stargazers_count"]
    forks = repo["forks_count"]
    lang = repo.get("language") or ""
    lang_color = get_lang_color(lang)

    # Truncate long descriptions
    if len(desc) > 60:
        desc = desc[:57] + "..."

    lang_section = ""
    if lang:
        lang_section = f"""
      <circle cx="25" cy="0" r="6" fill="{lang_color}"/>
      <text x="37" y="4" fill="{TEXT_CLR}" font-size="12" font-family="{FONT}">{esc(lang)}</text>"""

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="{BR}"/>
  <g transform="translate(0, 25)">
    <g transform="translate(25, 0)">{icon("repo", ICON_CLR)}</g>
    <text x="48" y="13" fill="{TITLE_CLR}" font-size="16" font-weight="700" font-family="{FONT}">{name}</text>
  </g>
  <text x="25" y="70" fill="{TEXT_CLR}" font-size="13" font-family="{FONT}">{desc}</text>
  <g transform="translate(0, 120)">
    {lang_section}
    <g transform="translate({155 if lang else 25}, 0)">
      {icon("star", TEXT_CLR)}
      <text x="20" y="4" fill="{TEXT_CLR}" font-size="12" font-family="{FONT}">{fmt(stars)}</text>
    </g>
    <g transform="translate({215 if lang else 85}, 0)">
      {icon("fork", TEXT_CLR)}
      <text x="20" y="4" fill="{TEXT_CLR}" font-size="12" font-family="{FONT}">{fmt(forks)}</text>
    </g>
  </g>
</svg>
"""


# ── Language color lookup ────────────────────────────────────────────

LANG_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051",
    "Vue": "#41b883", "C": "#555555", "C++": "#f34b7d",
    "C#": "#178600", "Ruby": "#701516", "PHP": "#4F5D95",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Dart": "#00B4AB",
    "Lua": "#000080", "Makefile": "#427819", "Dockerfile": "#384d54",
    "SCSS": "#c6538c", "Svelte": "#ff3e00", "Jupyter Notebook": "#DA5B0B",
}


def get_lang_color(lang):
    return LANG_COLORS.get(lang, "#858585")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT, exist_ok=True)

    print("Fetching user data from GitHub API...")
    data = fetch_user_data()
    print(f"  Stars: {data['stars']}, Commits: {data['commits']}, "
          f"PRs: {data['prs']}, Issues: {data['issues']}, "
          f"Contributed to: {data['contribs']}")
    print(f"  Top langs: {', '.join(l['name'] for l in data['langs'])}")

    print("Generating stats.svg...")
    with open(os.path.join(OUTPUT, "stats.svg"), "w") as f:
        f.write(stats_card(data))

    print("Generating top-langs.svg...")
    with open(os.path.join(OUTPUT, "top-langs.svg"), "w") as f:
        f.write(langs_card(data["langs"]))

    print("Fetching repo data for rank-analysis...")
    repo = fetch_repo("rank-analysis")
    print(f"  {repo['name']}: ★{repo['stargazers_count']} 🍴{repo['forks_count']} ({repo.get('language', 'N/A')})")

    print("Generating pin-rank-analysis.svg...")
    with open(os.path.join(OUTPUT, "pin-rank-analysis.svg"), "w") as f:
        f.write(pin_card(repo))

    print("✅ All cards generated successfully!")


if __name__ == "__main__":
    main()
