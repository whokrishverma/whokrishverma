"""
generate_heatmap.py

Fetches the last year of GitHub contribution data for a user via the
GraphQL API, then draws it as a terminal-styled SVG (dark background,
green squares) and saves it to contrib-heatmap.svg in the repo root.

Run manually:
    GH_TOKEN=your_token GH_USERNAME=your_username python scripts/generate_heatmap.py

In GitHub Actions, GH_TOKEN and GH_USERNAME are injected automatically
(see .github/workflows/heatmap.yml).
"""

import os
import sys
import requests

# ---------------------------------------------------------------------------
# STEP 1: Ask GitHub's GraphQL API for contribution data
# ---------------------------------------------------------------------------

GRAPHQL_QUERY = """
query($userName: String!) {
  user(login: $userName) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""


def fetch_contributions(username: str, token: str) -> dict:
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": GRAPHQL_QUERY, "variables": {"userName": username}},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")

    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


# ---------------------------------------------------------------------------
# STEP 2: Turn that data into SVG squares
# ---------------------------------------------------------------------------

# Color scale from "no contributions" to "very active day"
COLOR_SCALE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

CELL_SIZE = 11
CELL_GAP = 3
LEFT_PADDING = 30   # room for Mon/Wed/Fri labels
TOP_PADDING = 40     # room for month labels + header


def color_for_count(count: int, max_count: int) -> str:
    if count == 0:
        return COLOR_SCALE[0]
    # Split non-zero contributions into 4 buckets
    ratio = count / max(max_count, 1)
    if ratio <= 0.25:
        return COLOR_SCALE[1]
    elif ratio <= 0.5:
        return COLOR_SCALE[2]
    elif ratio <= 0.75:
        return COLOR_SCALE[3]
    else:
        return COLOR_SCALE[4]


def build_svg(calendar: dict, username: str) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    max_count = max(
        (day["contributionCount"] for week in weeks for day in week["contributionDays"]),
        default=0,
    )

    width = LEFT_PADDING + len(weeks) * (CELL_SIZE + CELL_GAP) + 20
    height = TOP_PADDING + 7 * (CELL_SIZE + CELL_GAP) + 40

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#0d1117" rx="6"/>',
        # Terminal-style header line
        f'<text x="20" y="24" font-family="monospace" font-size="13" fill="#c9d1d9">'
        f'<tspan fill="#39d353">{username}@github</tspan> ~ $ ./contributions.sh</text>',
    ]

    # Day-of-week labels (Mon / Wed / Fri only, GitHub-style)
    day_labels = {1: "Mon", 3: "Wed", 5: "Fri"}
    for weekday, label in day_labels.items():
        y = TOP_PADDING + weekday * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 2
        svg_parts.append(
            f'<text x="0" y="{y}" font-family="monospace" font-size="9" fill="#8b949e">{label}</text>'
        )

    # Month labels along the top, printed whenever a new month starts
    last_month = None
    for week_index, week in enumerate(weeks):
        first_day = week["contributionDays"][0]
        month = first_day["date"][:7]  # "YYYY-MM"
        if month != last_month:
            month_name = first_day["date"][5:7]
            x = LEFT_PADDING + week_index * (CELL_SIZE + CELL_GAP)
            svg_parts.append(
                f'<text x="{x}" y="{TOP_PADDING - 8}" font-family="monospace" '
                f'font-size="9" fill="#8b949e">{MONTH_NAMES[int(month_name) - 1]}</text>'
            )
            last_month = month

    # The actual contribution squares
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = LEFT_PADDING + week_index * (CELL_SIZE + CELL_GAP)
            y = TOP_PADDING + day["weekday"] * (CELL_SIZE + CELL_GAP)
            color = color_for_count(day["contributionCount"], max_count)
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
                f'rx="2" fill="{color}"><title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>'
            )

    # Footer line with the total
    footer_y = height - 14
    svg_parts.append(
        f'<text x="20" y="{footer_y}" font-family="monospace" font-size="12" fill="#c9d1d9">'
        f'{total:,} contributions in the last year</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------------------
# STEP 3: Wire it together
# ---------------------------------------------------------------------------

def main():
    username = os.environ.get("GH_USERNAME")
    token = os.environ.get("GH_TOKEN")

    if not username or not token:
        print("ERROR: set GH_USERNAME and GH_TOKEN environment variables.", file=sys.stderr)
        sys.exit(1)

    calendar = fetch_contributions(username, token)
    svg = build_svg(calendar, username)

    output_path = os.path.join(os.path.dirname(__file__), "..", "contrib-heatmap.svg")
    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Wrote {output_path} ({calendar['totalContributions']} total contributions)")


if __name__ == "__main__":
    main()
