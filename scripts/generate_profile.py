"""Writes the profile panel SVGs and PROFILE_README.md from me.sql and live GitHub and WakaTime numbers. Standard library only.

GitHub strips style, class and script from a README and can only link a whole image, so the page is one SVG panel
cut into slices that stack without a gap. Only the email slice has a link.

The profile repo holds only a copy of PROFILE_README.md, whose images load from this repo, so daily commits stay here.

Run with a token in GITHUB_TOKEN: python scripts/generate_profile.py
"""
import json
import os
import re
import sqlite3
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from type_svg import Sheet, width, wrap

LOGIN = "developedByAshu"
EMAIL = "ashutoshanandworkmail@gmail.com"
WAKATIME_BADGE = "https://wakatime.com/badge/user/e553e66b-4ac1-40d7-a4f3-f28f49793dba.svg"
WAKATIME_STATS = "https://wakatime.com/api/v1/users/ashutoshanand139/stats/all_time"
VIEWS_COUNTER = f"https://komarev.com/ghpvc/?username={LOGIN}"
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS_URL = f"https://raw.githubusercontent.com/{LOGIN}/profile-panel/main/assets"
API_URL = "https://api.github.com/graphql"
IST = timezone(timedelta(hours=5, minutes=30))
TOP_LANGUAGES = 6
ALWAYS_SHOWN = {"Rust": 0.01}
NOT_LANGUAGES = {"Markdown", "JSON", "Text", "Other", "Java Properties", "YAML", "TOML", "XML", "Log", "Git Config", "Ignore List"}
WIDTH, PAD = 1000, 44
INNER = WIDTH - PAD * 2
EMAIL_LEFT, EMAIL_RIGHT, EMAIL_TOP, EMAIL_BOTTOM = 40, 360, 138, 170
INTRO_Y, WASH_HEIGHT = 228, 300
ORANGE, INK, BODY, MUTED, LINE, PANEL, EMPTY, TILE = "#FF7A1A", "#F4F2EE", "#B9BCC2", "#7E828A", "#26292F", "#0B0D11", "#181B20", "#12151B"
HEAT = ["#6B2E0A", "#B24A0E", "#EE6A14", "#FF8F33"]
BLENDS = ["#FF7A1A", "#CF6216", "#A04C13", "#7A3A10", "#58290C", "#3D1D09"]
GLOW = '<filter id="glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3.2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
PULSE = '<animate attributeName="opacity" values="1;0.3;1" dur="2.4s" repeatCount="indefinite"/>'

PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 1) {
      totalCount
    }
  }
}"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def run_query(query, variables):
    """Runs one GitHub GraphQL query and returns its data."""
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(API_URL, body, {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": LOGIN})
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    if reply.get("errors"):
        raise RuntimeError(reply["errors"])
    return reply["data"]


def read_contributions(start_year, today):
    """Returns every day's contribution count from the account's first year to today."""
    days = {}
    for year in range(start_year, today.year + 1):
        variables = {"login": LOGIN, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"}
        calendar = run_query(YEAR_QUERY, variables)["user"]["contributionsCollection"]["contributionCalendar"]
        for week in calendar["weeks"]:
            for day in week["contributionDays"]:
                days[date.fromisoformat(day["date"])] = day["contributionCount"]
    return {day: count for day, count in days.items() if day <= today}


def read_public_text(url):
    """Returns the text labels of a public SVG badge."""
    request = urllib.request.Request(url, headers={"User-Agent": LOGIN})
    with urllib.request.urlopen(request, timeout=30) as response:
        return re.findall(r">([^<>]+)</text>", response.read().decode("utf-8", "ignore"))


def coding_hours():
    """Returns total hours coded, like 3,884, from the public WakaTime badge."""
    return next(match.group(1) for text in read_public_text(WAKATIME_BADGE) if (match := re.match(r"([\d,]+) hrs?", text.strip())))


def profile_views():
    """Returns the profile view count, like 228. Reading the public counter adds 1 view, so this runs once a day."""
    return next(text.strip() for text in reversed(read_public_text(VIEWS_COUNTER)) if re.fullmatch(r"[\d,.]+[kKmM]?", text.strip()))


def longest_streak(days):
    """Returns the longest run of active days."""
    longest = run = 0
    for day in sorted(days):
        run = run + 1 if days[day] else 0
        longest = max(longest, run)
    return longest


def coding_languages():
    """Returns the top programming languages by real editor time from public WakaTime stats, as (name, share)."""
    request = urllib.request.Request(WAKATIME_STATS, headers={"User-Agent": LOGIN})
    with urllib.request.urlopen(request, timeout=30) as response:
        languages = json.load(response)["data"]["languages"]
    kept = [(item["name"], item["percent"] / 100) for item in languages if item["name"] not in NOT_LANGUAGES]
    shares = dict(kept[:TOP_LANGUAGES - len(ALWAYS_SHOWN)]) | ALWAYS_SHOWN
    return sorted(shares.items(), key=lambda item: -item[1])


def open_card(sheet):
    """Starts the dark rounded panel. Every slice draws it at the same size, so the slices line up."""
    sheet.defs.append(
        '<clipPath id="panel"><rect width="1000" height="%HEIGHT%" rx="16"/></clipPath>'
        f'<radialGradient id="wash" cx="1" cy="0" r="0.9"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0.2"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></radialGradient>'
    )
    sheet.raw(f'<g clip-path="url(#panel)"><rect width="{WIDTH}" height="%HEIGHT%" fill="{PANEL}"/><rect width="{WIDTH}" height="{WASH_HEIGHT}" fill="url(#wash)"/>')


def close_card(sheet):
    """Ends the panel with its hairline border."""
    sheet.raw(f'</g><rect x="0.5" y="0.5" width="{WIDTH - 1}" height="%INNER%" rx="16" fill="none" stroke="{LINE}"/>')


def draw_top(sheet, engineer):
    """Draws the name and role, with a light travelling along the top edge."""
    sheet.defs.append(
        '<filter id="neon" x="-5%" y="-900%" width="110%" height="1900%"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="0.55" stop-color="{ORANGE}" stop-opacity="0.35"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="spark" x1="0" x2="1"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0"/><stop offset="0.8" stop-color="#FFC48F"/><stop offset="1" stop-color="#FFF1E3"/></linearGradient>'
    )
    sheet.raw('<rect x="0" y="1" width="1000" height="2" fill="url(#edge)" filter="url(#neon)"/>')
    sheet.raw('<rect x="-260" y="1" width="260" height="2" fill="url(#spark)" filter="url(#neon)"><animate attributeName="x" values="-260;1000;1000" keyTimes="0;0.6;1" dur="6s" repeatCount="indefinite"/></rect>')
    sheet.text(PAD, 92, engineer["name"], 54, INK, "semibold", tracking=-0.8)
    role = f"{engineer['role']} / {engineer['city']}".lower()
    sheet.text(PAD, 126, role, 16, ORANGE, "mono")
    sheet.raw(f'<rect x="{PAD + width(role, "mono", 16) + 5:.1f}" y="113" width="9" height="15" fill="{ORANGE}"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></rect>')


def draw_email(sheet):
    """Draws the email row, which is the only slice with a link."""
    sheet.raw(f'<g fill="none" stroke="{ORANGE}" stroke-width="1.4" stroke-linejoin="round"><rect x="{PAD + 0.7}" y="143" width="17" height="12" rx="2"/><path d="M{PAD + 1} 144.5 l8 6 l8 -6"/></g>')
    email_x = PAD + 26
    sheet.text(email_x, 154, EMAIL, 15, INK, "mono")
    sheet.raw(f'<rect x="{email_x}" y="159" width="{width(EMAIL, "mono", 15):.0f}" height="1" fill="{ORANGE}"/>')


def section_heading(sheet, y, label, note="", pulse=False):
    """Draws a section's orange label and hairline, with an optional note at the right. Returns where the content starts."""
    text = label.upper()
    sheet.text(PAD, y, text, 13, ORANGE, "mono", tracking=1.8)
    start = PAD + width(text, "mono", 13, 1.8) + 16
    note_width = width(note, "mono", 12.5) if note else 0
    end = WIDTH - PAD - (note_width + 18 if note else 0) - (16 if pulse else 0)
    sheet.raw(f'<rect x="{start:.0f}" y="{y - 5}" width="{end - start:.0f}" height="1" fill="{LINE}"/>')
    if pulse:
        sheet.raw(f'<circle cx="{WIDTH - PAD - note_width - 14:.1f}" cy="{y - 4}" r="3.5" fill="{ORANGE}" filter="url(#glow)">{PULSE}</circle>')
    if note:
        sheet.text(WIDTH - PAD, y, note, 12.5, MUTED, "mono", anchor="end")
    return y + 22


def tile(sheet, x, y, tile_width, height):
    """Draws one raised tile with an orange accent at its left edge."""
    sheet.raw(f'<rect x="{x:.1f}" y="{y}" width="{tile_width:.1f}" height="{height}" rx="10" fill="{TILE}" stroke="{LINE}"/>')
    sheet.raw(f'<rect x="{x:.1f}" y="{y + 18}" width="3" height="20" fill="{ORANGE}"/>')


def draw_intro(sheet, engineer):
    """Draws the intro under the email row. Returns where the next section starts."""
    y = INTRO_Y
    for line in wrap(engineer["intro"], "regular", 20, INNER):
        sheet.text(PAD, y, line, 20, BODY)
        y += 30
    return y + 34


def heatmap(sheet, y, days, today):
    """Draws the last 53 weeks of real contributions, the busiest days glowing."""
    pitch = INNER / 53
    size = pitch - 3.2
    start = today - timedelta(days=(today.weekday() + 1) % 7 + 52 * 7)
    active = sorted(count for count in days.values() if count)
    def level(count):
        if not active:
            return 0
        rank = sum(1 for value in active if value <= count) / len(active)
        return min(3, int(rank * 4 - 0.001))
    plain, bright, seen = [], [], None
    for week in range(53):
        first = start + timedelta(days=week * 7)
        if first.month != seen and week < 51:
            if seen is not None:
                sheet.text(PAD + week * pitch, y - 8, first.strftime("%b"), 12, MUTED, "mono")
            seen = first.month
        for weekday in range(7):
            day = first + timedelta(days=weekday)
            if day > today:
                continue
            x, cell_y = PAD + week * pitch, y + weekday * pitch
            count = days.get(day, 0)
            colour = HEAT[level(count)] if count else EMPTY
            rect = f'<rect x="{x:.1f}" y="{cell_y:.1f}" width="{size:.1f}" height="{size:.1f}" rx="2.5" fill="{colour}"/>'
            (bright if count and level(count) >= 2 else plain).append(rect)
    sheet.raw("".join(plain))
    sheet.raw(f'<g filter="url(#glow)">{"".join(bright)}</g>')
    return y + 7 * pitch


def draw_live(sheet, y, facts, days, languages, today):
    """Draws the numbers, the orange heatmap and the language bar. Returns where the next section starts."""
    stamp = f"updated {datetime.now(IST):%d %b %Y}"
    y = section_heading(sheet, y, "Live", stamp, pulse=True) + 14
    figures = [
        (f"{facts['all_time']:,}", "total contributions"), (facts["coding_hours"], "hours coded"), (f"{facts['this_year']:,}", f"{today.year} contributions"),
        (facts["views"], "profile views"), (f"{facts['repositories']}", "public repos"), (f"{facts['longest']}", "day best streak"),
    ]
    cell = INNER / len(figures)
    for position, (value, label) in enumerate(figures):
        centre = PAD + cell * (position + 0.5)
        sheet.text(centre - width(value, "medium", 36, -0.5) / 2, y + 26, value, 36, INK, "medium", tracking=-0.5)
        sheet.text(centre - width(label, "regular", 14) / 2, y + 52, label, 14, MUTED)
        if position:
            sheet.raw(f'<rect x="{PAD + cell * position:.1f}" y="{y - 6}" width="1" height="64" fill="{LINE}"/>')
    y = heatmap(sheet, y + 100, days, today) + 24
    left, listed = PAD, sum(share for _, share in languages) or 1
    for index, (name, share) in enumerate(languages):
        segment = share / listed * INNER
        sheet.raw(f'<rect x="{left:.1f}" y="{y}" width="{max(segment - 2, 1.5):.1f}" height="7" fill="{BLENDS[index]}"/>')
        left += segment
    x = PAD
    for index, (name, share) in enumerate(languages):
        label = f"{name} {share * 100:.0f}%"
        sheet.raw(f'<rect x="{x:.1f}" y="{y + 25}" width="9" height="9" rx="2" fill="{BLENDS[index]}"/>')
        sheet.text(x + 15, y + 34, label, 14, BODY)
        x += 15 + width(label, "regular", 14) + 26
    return y + 34 + 54


def draw_work(sheet, y, work):
    """Draws the selected work items as tiles, two to a row. Returns where the next section starts."""
    y = section_heading(sheet, y, "Selected work", "figures from test runs")
    gap = 16
    column = (INNER - gap) / 2
    for start in range(0, len(work), 2):
        pair = work[start:start + 2]
        wrapped = [wrap(row["what"], "regular", 15, column - 36) for row in pair]
        height = 56 + max(len(lines) for lines in wrapped) * 22 + 12
        for offset, (row, lines) in enumerate(zip(pair, wrapped)):
            x = PAD + offset * (column + gap)
            tile(sheet, x, y, column, height)
            sheet.text(x + 22, y + 34, row["title"], 18, INK, "semibold")
            for number, line in enumerate(lines):
                sheet.text(x + 22, y + 62 + number * 22, line, 15, BODY)
        y += height + gap
    return y + 36


def draw_skills(sheet, y, skills):
    """Draws each skill group as a label and a row of tags that wrap at the panel edge. Returns where the next section starts."""
    y = section_heading(sheet, y, "Skills")
    tags_start, tag_height = PAD + 124, 30
    for kind, names in skills:
        sheet.text(PAD, y + 20, kind, 15.5, INK, "medium")
        x = tags_start
        for name in names.split(", "):
            tag_width = width(name, "regular", 14) + 20
            if x + tag_width > WIDTH - PAD:
                x, y = tags_start, y + tag_height + 8
            sheet.raw(f'<rect x="{x:.1f}" y="{y}" width="{tag_width:.1f}" height="{tag_height}" rx="7" fill="{TILE}" stroke="{LINE}"/>')
            sheet.text(x + 10, y + 20, name, 14, BODY)
            x += tag_width + 6
        y += tag_height + 14
    return y + 38


def draw_now(sheet, y, now):
    """Draws what I am on right now as three tiles side by side. Returns the bottom of the panel."""
    y = section_heading(sheet, y, "Now")
    gap = 16
    column = (INNER - gap * (len(now) - 1)) / len(now)
    wrapped = [wrap(row["what"], "regular", 15, column - 36) for row in now]
    height = 56 + max(len(lines) for lines in wrapped) * 22 + 12
    for position, (row, lines) in enumerate(zip(now, wrapped)):
        x = PAD + position * (column + gap)
        tile(sheet, x, y, column, height)
        sheet.text(x + 22, y + 34, row["label"], 18, INK, "semibold")
        sheet.raw(f'<circle cx="{x + column - 22:.1f}" cy="{y + 28}" r="3.5" fill="{ORANGE}" filter="url(#glow)">{PULSE}</circle>')
        for number, line in enumerate(lines):
            sheet.text(x + 22, y + 62 + number * 22, line, 15, BODY)
    return y + height + 34


def draw_panel(engineer, facts, days, languages, work, skills, now, today):
    """Draws one panel, saved as 4 slices that stack without a gap, because GitHub can only link a whole image."""
    top, email, blank, rest = (Sheet(WIDTH, title) for title in (engineer["name"], EMAIL, "Panel", "Panel"))
    for sheet in (top, email, blank, rest):
        open_card(sheet)
    rest.defs.append(GLOW)
    draw_top(top, engineer)
    draw_email(email)
    y = draw_intro(rest, engineer)
    y = draw_live(rest, y, facts, days, languages, today)
    y = draw_work(rest, y, work)
    y = draw_skills(rest, y, skills)
    height = draw_now(rest, y, now)
    for sheet in (top, email, blank, rest):
        close_card(sheet)
    row = EMAIL_BOTTOM - EMAIL_TOP
    top.save(ASSETS / "panel_top.svg", height, (0, 0, WIDTH, EMAIL_TOP))
    blank.save(ASSETS / "panel_left.svg", height, (0, EMAIL_TOP, EMAIL_LEFT, row))
    email.save(ASSETS / "panel_email.svg", height, (EMAIL_LEFT, EMAIL_TOP, EMAIL_RIGHT - EMAIL_LEFT, row))
    blank.save(ASSETS / "panel_right.svg", height, (EMAIL_RIGHT, EMAIL_TOP, WIDTH - EMAIL_RIGHT, row))
    rest.save(ASSETS / "panel_rest.svg", height, (0, EMAIL_BOTTOM, WIDTH, height - EMAIL_BOTTOM))


def slice_image(name, alt, percent):
    """Returns one panel slice. align=top removes the space an image otherwise keeps under itself."""
    return f'<img src="{ASSETS_URL}/{name}.svg" alt="{escape(alt)}" width="{percent}%" align="top">'


def still(name, image):
    """Wraps an image in a named anchor, which stops GitHub linking it to its raw file, so a click does nothing."""
    return f'<a name="{name}">{image}</a>'


def write_readme(engineer, work, skills, now):
    """Writes the README for the profile repo: the panel slices on one line with no spaces. Only the email slice has a link."""
    rest_alt = " ".join([
        engineer["intro"],
        "Selected work.", *(f"{row['title']}: {row['what']}" for row in work),
        "Skills.", *(f"{kind}: {names}." for kind, names in skills),
        "Now.", *(f"{row['label']}: {row['what']}" for row in now),
    ])
    left_percent = EMAIL_LEFT * 100 // WIDTH
    email_percent = (EMAIL_RIGHT - EMAIL_LEFT) * 100 // WIDTH
    # A heading has the smallest line height GitHub offers, so the short email row sits without a gap.
    panel = "".join([
        "<h6>",
        still("panel_top", slice_image("panel_top", f"{engineer['name']}, {engineer['role']}, {engineer['city']}", 100)),
        still("panel_left", slice_image("panel_left", "", left_percent)),
        f'<a href="mailto:{EMAIL}">{slice_image("panel_email", f"Email {EMAIL}", email_percent)}</a>',
        still("panel_right", slice_image("panel_right", "", 100 - left_percent - email_percent)),
        still("panel_rest", slice_image("panel_rest", rest_alt, 100)),
        "</h6>",
    ])
    blocks = [panel, f'<img src="{VIEWS_COUNTER}" alt="" width="1" height="1">']
    (ROOT / "PROFILE_README.md").write_text("\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")


def main():
    today = datetime.now(timezone.utc).date()
    user = run_query(PROFILE_QUERY, {"login": LOGIN})["user"]
    days = read_contributions(int(user["createdAt"][:4]), today)
    facts = {
        "this_year": sum(count for day, count in days.items() if day.year == today.year),
        "all_time": sum(days.values()), "longest": longest_streak(days), "repositories": user["repositories"]["totalCount"],
        "coding_hours": coding_hours(), "views": profile_views(),
    }
    languages = coding_languages()
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript((ROOT / "me.sql").read_text(encoding="utf-8"))
    engineer = connection.execute("SELECT * FROM engineer").fetchone()
    work = connection.execute("SELECT title, what FROM work ORDER BY id").fetchall()
    skills = connection.execute("SELECT kind, group_concat(name, ', ') FROM skill GROUP BY kind ORDER BY min(id)").fetchall()
    now = connection.execute("SELECT label, what FROM now ORDER BY id").fetchall()
    ASSETS.mkdir(exist_ok=True)
    draw_panel(engineer, facts, days, languages, work, skills, now, today)
    write_readme(engineer, work, skills, now)
    print(json.dumps(facts), languages)


if __name__ == "__main__":
    main()
