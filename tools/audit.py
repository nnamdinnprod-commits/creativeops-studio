#!/usr/bin/env python3
"""
audit.py — read-only checks for CreativeOps Studio against docs/REVIEW_02.md

Changes nothing. Reads the repository, optionally fetches the live site, and
reports what still fails.

Usage
-----
    python tools/audit.py                             # repo checks only
    python tools/audit.py --url http://localhost:8000 # repo + live site
    python tools/audit.py --url https://your-app.onrender.com --deep

    --deep   also searches git history for forbidden brand names (slower)

Exit codes: 0 = no failures, 1 = at least one FAIL.

Findings are WARN unless a false positive is very unlikely. A WARN means
"look at this", not "this is broken".
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

# --------------------------------------------------------------------------
# Configuration — edit these if your names or thresholds differ
# --------------------------------------------------------------------------

FORBIDDEN_BRANDS = ["albelli", "photobox", "hofmann"]
# REVIEW_02.md's own suggested replacements (Printhuis, Kadora) and its own listed
# alternates (Lumera, Bindwell, Papeterie, Momentbox, Foldhaus) all turned out to collide
# with real, active companies on a plain search — Printhuis in the exact same wall-art
# category the review assigned it to. Halveth and Cassenvale replaced them after a clean
# search each; see docs/DECISIONS.md for the full list of what was checked and rejected.
EXPECTED_BRANDS = ["Fotomera", "Halveth", "Cassenvale"]

# Words that belong in a database, not in an interface
DB_VOCABULARY = ["rows", "records", "entity", "entities", "null", "nan", "foreign key"]

DISCLAIMER_MARKERS = ["fictional", "prototype", "demonstration data"]

MAX_PLAUSIBLE_PCT = 150     # above this, an allocation figure is almost certainly a bug
ABSURD_PCT = 250            # above this it is definitely a bug
MAX_DAYS_BEHIND = 5         # after relative date anchoring, nothing should exceed this
SLOW_PAGE_SECONDS = 5.0     # a page slower than this will look broken to a cold visitor

# Capitalised words that are interface furniture rather than people's names.
# Add your own project or brand words here if they produce false positives.
NAME_STOPWORDS = {w.lower() for w in """
dashboard pipeline resources resource brief assistant creative intelligence
localisation localization timeline assumptions project projects active blocked
risk track team capacity aggregate utilisation utilization available tight
overloaded contracted allocated allocation status owner deadline deadlines
priority market markets brand brands campaign total approved review reviews
delivered ready assigned production senior designer producer motion copywriter
translator external internal role name person people days working behind queue
flight rows records phase phases schedule client insight insights confidence
recommendation recommended estimated suggested prototype concept fictional
demonstration data note notes overall moving cleared current period reporting
monday tuesday wednesday thursday friday saturday sunday
jan feb mar apr may jun jul aug sep oct nov dec
january february march april june july august september october november december
germany france spain netherlands kingdom europe german french spanish dutch
""".split()}

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9_\-]{20,}", "OpenAI-style API key"),
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "Anthropic-style API key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub personal access token"),
]

TEXT_SUFFIXES = {".py", ".html", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build"}


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

FAIL, WARN, OK, INFO = "FAIL", "WARN", "OK", "INFO"


@dataclass
class Report:
    findings: list[tuple[str, str, str, str]] = field(default_factory=list)

    def add(self, level: str, section: str, message: str, detail: str = "") -> None:
        self.findings.append((level, section, message, detail))

    def fail(self, s, m, d=""): self.add(FAIL, s, m, d)
    def warn(self, s, m, d=""): self.add(WARN, s, m, d)
    def ok(self, s, m, d=""):   self.add(OK, s, m, d)
    def info(self, s, m, d=""): self.add(INFO, s, m, d)

    def render(self) -> int:
        icons = {FAIL: "✗", WARN: "!", OK: "✓", INFO: "·"}
        order = {FAIL: 0, WARN: 1, INFO: 2, OK: 3}
        current_section = None
        for level, section, message, detail in sorted(
            self.findings, key=lambda f: (f[1], order[f[0]])
        ):
            if section != current_section:
                print(f"\n{section}")
                print("-" * len(section))
                current_section = section
            print(f"  {icons[level]} {message}")
            for line in detail.splitlines():
                if line.strip():
                    print(f"      {line}")

        counts = {lvl: sum(1 for f in self.findings if f[0] == lvl)
                  for lvl in (FAIL, WARN, OK)}
        print(f"\n{'=' * 60}")
        print(f"{counts[FAIL]} failed · {counts[WARN]} to check · {counts[OK]} passed")
        return 1 if counts[FAIL] else 0


# --------------------------------------------------------------------------
# HTML helpers
# --------------------------------------------------------------------------

class TextExtractor(HTMLParser):
    """Visible text plus internal hrefs. Ignores script and style content."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.links: list[str] = []
        self._suppress = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._suppress += 1
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._suppress:
            self._suppress -= 1

    def handle_data(self, data):
        if not self._suppress:
            self.chunks.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.chunks)).strip()


def parse_page(html: str) -> tuple[str, list[str]]:
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.text, p.links


# --------------------------------------------------------------------------
# Repository checks
# --------------------------------------------------------------------------

def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_brand_names(root: Path, rep: Report) -> None:
    section = "P0 · Brand names"
    hits: list[str] = []
    for path in iter_text_files(root):
        text = read(path).lower()
        for brand in FORBIDDEN_BRANDS:
            if brand in text:
                count = text.count(brand)
                hits.append(f"{path.relative_to(root)} — '{brand}' ×{count}")
    if hits:
        rep.fail(section, f"Forbidden brand names in {len(hits)} file(s)",
                 "\n".join(sorted(hits)[:25]))
    else:
        rep.ok(section, "No forbidden brand names in working tree")

    found = [b for b in EXPECTED_BRANDS
             if any(b.lower() in read(p).lower() for p in iter_text_files(root))]
    if found:
        rep.ok(section, f"Replacement brands present: {', '.join(found)}")
    else:
        rep.warn(section, "None of the expected replacement brand names found",
                 f"Looked for: {', '.join(EXPECTED_BRANDS)}. "
                 "Edit EXPECTED_BRANDS at the top of this script if you chose others.")


def check_git_history(root: Path, rep: Report) -> None:
    section = "P0 · Brand names"
    if not (root / ".git").exists():
        rep.info(section, "Not a git repository — skipping history search")
        return
    try:
        revs = subprocess.run(["git", "rev-list", "--all"], cwd=root,
                              capture_output=True, text=True, timeout=60)
        if revs.returncode != 0 or not revs.stdout.strip():
            rep.info(section, "No commits to search")
            return
        dirty = []
        for brand in FORBIDDEN_BRANDS:
            res = subprocess.run(
                ["git", "grep", "-il", brand] + revs.stdout.split(),
                cwd=root, capture_output=True, text=True, timeout=180)
            if res.stdout.strip():
                n = len(set(res.stdout.strip().splitlines()))
                dirty.append(f"'{brand}' appears in {n} historical blob(s)")
        if dirty:
            rep.warn(section, "Forbidden brand names remain in git history",
                     "\n".join(dirty) +
                     "\nHistory is only a problem if you publish the repository. "
                     "If you do, consider starting a fresh repo rather than rewriting history.")
        else:
            rep.ok(section, "Git history clean of forbidden brand names")
    except (subprocess.SubprocessError, OSError) as exc:
        rep.info(section, f"History search skipped ({exc.__class__.__name__})")


def check_hardcoded_dates(root: Path, rep: Report) -> None:
    section = "P1 · Date anchoring"
    iso = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
    offenders: list[str] = []
    for path in iter_text_files(root):
        if path.suffix != ".py":
            continue
        name = path.name.lower()
        if "seed" not in name and "fixture" not in name and "demo" not in name:
            continue
        found = iso.findall(read(path))
        if found:
            offenders.append(f"{path.relative_to(root)} — {len(found)} literal date(s), "
                             f"e.g. {', '.join(sorted(set(found))[:3])}")
    if offenders:
        rep.fail(section, "Literal dates in seed data",
                 "\n".join(offenders) +
                 "\nSeed dates must be offsets from the run date so the demo never goes stale.")
    else:
        rep.ok(section, "No literal dates found in seed files")


def check_capacity_sources(root: Path, rep: Report) -> None:
    section = "P2 · Capacity single source"
    signals = re.compile(
        r"(allocation_pct|allocated_pct|capacity_pct)\s*(/|\*|\+|-)|"
        r"sum\([^)]*alloc|utilisation\s*=|utilization\s*=",
        re.IGNORECASE)
    offenders: list[str] = []
    for path in iter_text_files(root):
        if path.suffix != ".py" or "test" in path.parts:
            continue
        if path.name == "capacity.py":
            continue
        text = read(path)
        for i, line in enumerate(text.splitlines(), 1):
            if signals.search(line):
                offenders.append(f"{path.relative_to(root)}:{i} — {line.strip()[:90]}")
    if offenders:
        rep.warn(section, f"Allocation arithmetic outside capacity.py in {len(offenders)} place(s)",
                 "\n".join(offenders[:20]) +
                 "\nCLAUDE.md requires capacity.py to be the only place this is computed. "
                 "Some of these may be display formatting — check each.")
    else:
        rep.ok(section, "No allocation arithmetic found outside capacity.py")


def check_secrets(root: Path, rep: Report) -> None:
    section = "Security"
    tracked: set[str] = set()
    if (root / ".git").exists():
        try:
            res = subprocess.run(["git", "ls-files"], cwd=root,
                                 capture_output=True, text=True, timeout=60)
            tracked = set(res.stdout.split())
        except (subprocess.SubprocessError, OSError):
            pass

    if tracked and ".env" in tracked:
        rep.fail(section, ".env is tracked by git",
                 "Run: git rm --cached .env   (and confirm .gitignore excludes it)")
    elif tracked:
        rep.ok(section, ".env is not tracked by git")

    hits: list[str] = []
    for path in iter_text_files(root):
        rel = str(path.relative_to(root))
        if tracked and rel not in tracked:
            continue
        text = read(path)
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, text):
                hits.append(f"{rel} — {label}")
    if hits:
        rep.fail(section, "Possible credential in a tracked file", "\n".join(hits))
    else:
        rep.ok(section, "No credential patterns in tracked files")


def check_db_vocabulary(root: Path, rep: Report) -> None:
    section = "P7 · Copy"
    offenders: list[str] = []
    for path in iter_text_files(root):
        if path.suffix != ".html":
            continue
        text, _ = parse_page(read(path))
        low = text.lower()
        for word in DB_VOCABULARY:
            if re.search(rf"\b{re.escape(word)}\b", low):
                snippet = next(
                    (m.group(0) for m in
                     re.finditer(rf".{{0,45}}\b{re.escape(word)}\b.{{0,45}}", text, re.I)),
                    word)
                offenders.append(f"{path.relative_to(root)} — “…{snippet.strip()}…”")
    if offenders:
        rep.warn(section, f"Database vocabulary in template text ({len(offenders)} instance(s))",
                 "\n".join(offenders[:20]))
    else:
        rep.ok(section, "No database vocabulary in template visible text")


def check_docs_updated(root: Path, rep: Report) -> None:
    section = "P0 · Brand names"
    for name in ("DEMO_DATA.md", "POSITIONING.md"):
        path = root / "docs" / name
        if not path.exists():
            rep.warn(section, f"docs/{name} not found")
            continue
        text = read(path).lower()
        if any(b in text for b in FORBIDDEN_BRANDS):
            rep.fail(section, f"docs/{name} still names real brands",
                     "Amend the rule to 'invented brands only', or a future session "
                     "will reintroduce them.")
        elif "invented brand" in text or "no real company" in text:
            rep.ok(section, f"docs/{name} carries the invented-brands-only rule")
        else:
            rep.warn(section, f"docs/{name} has no explicit invented-brands-only rule")


# --------------------------------------------------------------------------
# Live site checks
# --------------------------------------------------------------------------

def fetch(url: str, timeout: float = 30.0) -> tuple[int, str, float]:
    req = urllib.request.Request(url, headers={"User-Agent": "creativeops-audit/1.0"})
    started = datetime.now()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, (datetime.now() - started).total_seconds()
    except urllib.error.HTTPError as exc:
        return exc.code, "", (datetime.now() - started).total_seconds()
    except Exception:
        return 0, "", (datetime.now() - started).total_seconds()


def discover_pages(base: str, rep: Report) -> dict[str, str]:
    """Fetch the start page and follow its internal navigation links."""
    start = base if urlparse(base).path not in ("", "/") else urljoin(base, "/dashboard")
    status, html, elapsed = fetch(start)
    if status != 200 or not html:
        rep.fail("Live site", f"Could not load {start} (HTTP {status or 'no response'})",
                 "If this is a Render free-tier app, it may be waking up. Try again in a minute.")
        return {}

    pages = {start: html}
    _, links = parse_page(html)
    origin = f"{urlparse(start).scheme}://{urlparse(start).netloc}"
    seen = {urlparse(start).path}
    for href in links:
        full = urljoin(start, href)
        parsed = urlparse(full)
        if not full.startswith(origin) or parsed.path in seen:
            continue
        if "/projects/" in parsed.path or parsed.path.count("/") > 1:
            continue
        seen.add(parsed.path)
        s, body, el = fetch(full)
        if s == 200 and body:
            pages[full] = body
            if el > SLOW_PAGE_SECONDS:
                rep.warn("P7 · Deployment", f"{parsed.path} took {el:.1f}s to load",
                         "A cold visitor will see a spinner. Move AI calls off page load.")
        elif s:
            rep.warn("Live site", f"{parsed.path} returned HTTP {s}")
    rep.info("Live site", f"Checked {len(pages)} page(s)",
             "\n".join(sorted(urlparse(u).path for u in pages)))
    return pages


def check_live_brands(pages: dict[str, str], rep: Report) -> None:
    section = "P0 · Brand names"
    bad = []
    for url, html in pages.items():
        text, _ = parse_page(html)
        for brand in FORBIDDEN_BRANDS:
            if brand in text.lower():
                bad.append(f"{urlparse(url).path} — '{brand}'")
    if bad:
        rep.fail(section, "Forbidden brand names visible on the deployed site",
                 "\n".join(bad))
    else:
        rep.ok(section, "No forbidden brand names on the deployed site")


def check_live_disclaimer(pages: dict[str, str], rep: Report) -> None:
    section = "Positioning"
    missing = []
    for url, html in pages.items():
        text, _ = parse_page(html)
        low = text.lower()
        if not any(marker in low for marker in DISCLAIMER_MARKERS):
            missing.append(urlparse(url).path)
    if missing:
        rep.fail(section, "Disclaimer missing on some pages", "\n".join(missing))
    else:
        rep.ok(section, "Disclaimer present on every page checked")


def check_live_percentages(pages: dict[str, str], rep: Report) -> None:
    section = "P2 · Capacity single source"
    absurd, high = [], []
    for url, html in pages.items():
        text, _ = parse_page(html)
        for match in re.finditer(r"(\d{1,4})\s?%", text):
            value = int(match.group(1))
            context = text[max(0, match.start() - 60):match.end() + 20].strip()
            if value >= ABSURD_PCT:
                absurd.append(f"{urlparse(url).path} — {value}% — “…{context}…”")
            elif value > MAX_PLAUSIBLE_PCT:
                high.append(f"{urlparse(url).path} — {value}% — “…{context}…”")
    if absurd:
        rep.fail(section, f"Implausible percentage(s) displayed ({len(absurd)})",
                 "\n".join(absurd[:10]))
    if high:
        rep.warn(section, f"High percentage(s) worth checking ({len(high)})",
                 "\n".join(high[:10]))
    if not absurd and not high:
        rep.ok(section, "No implausible percentages displayed")


def check_person_consistency(pages: dict[str, str], rep: Report) -> None:
    """The 540% bug: one person showing different allocations on different pages.

    For each percentage, take the nearest preceding capitalised word that is not
    a known interface term. That is usually the person the figure belongs to.
    """
    section = "P2 · Capacity single source"
    word = re.compile(r"\b([A-Z][a-z]{2,15})\b")
    per_person: dict[str, dict[str, set[int]]] = {}

    for url, html in pages.items():
        text, _ = parse_page(html)
        path = urlparse(url).path
        for match in re.finditer(r"(\d{1,4})\s?%", text):
            window = text[max(0, match.start() - 80):match.start()]
            candidates = [w for w in word.findall(window)
                          if w.lower() not in NAME_STOPWORDS]
            if not candidates:
                continue
            name = candidates[-1]
            per_person.setdefault(name, {}).setdefault(path, set()).add(int(match.group(1)))

    conflicts = []
    for name, by_page in per_person.items():
        values = {v for vs in by_page.values() for v in vs}
        if len(by_page) > 1 and len(values) > 1 and max(values) - min(values) > 20:
            detail = "; ".join(f"{page}: {sorted(vs)}" for page, vs in sorted(by_page.items()))
            conflicts.append(f"{name} — {detail}")
    if conflicts:
        rep.warn(section, f"Same name showing different percentages across pages ({len(conflicts)})",
                 "\n".join(conflicts[:10]) +
                 "\nSome of these will be coincidence (a market name next to a metric). "
                 "A person's allocation differing between pages is the 540% bug.")
    else:
        rep.ok(section, "No cross-page percentage conflicts detected")


def check_over_capacity_claim(pages: dict[str, str], rep: Report) -> None:
    section = "P2 · Capacity single source"
    claim = None
    for url, html in pages.items():
        text, _ = parse_page(html)
        m = re.search(r"(\d+)\s+of\s+(\d+)\s+over capacity", text, re.I)
        if m:
            claim = (int(m.group(1)), int(m.group(2)), urlparse(url).path)
            break
    if not claim:
        rep.info(section, "No 'N of M over capacity' summary found")
        return

    count, total, page = claim

    # Contradiction signal 1: the summary says nobody is over capacity, yet a
    # percentage above 100% is displayed somewhere.
    over_hundred: list[str] = []
    for url, html in pages.items():
        text, _ = parse_page(html)
        for m in re.finditer(r"(\d{1,4})\s?%", text):
            if int(m.group(1)) > 100:
                context = text[max(0, m.start() - 55):m.end()].strip()
                over_hundred.append(f"{urlparse(url).path} — “…{context}…”")

    # Contradiction signal 2: an explicit overloaded status on the resources page.
    labelled = 0
    for url, html in pages.items():
        if "resource" not in url:
            continue
        text, _ = parse_page(html)
        labelled = len(re.findall(r"over ?loaded|over capacity", text, re.I))

    if count == 0 and over_hundred:
        rep.fail(section,
                 f"'{count} of {total} over capacity' on {page} contradicts figures above 100%",
                 "\n".join(over_hundred[:6]) +
                 "\nTwo parts of the app are computing capacity differently.")
    elif count == 0 and labelled > 1:
        rep.fail(section,
                 f"'{count} of {total} over capacity' contradicts the resources page",
                 f"An over-capacity state is mentioned {labelled} time(s) there.")
    else:
        rep.ok(section, f"Over-capacity summary reads '{count} of {total}' with no contradiction")


def check_days_behind(pages: dict[str, str], rep: Report) -> None:
    section = "P1 · Date anchoring"
    bad = []
    for url, html in pages.items():
        text, _ = parse_page(html)
        for m in re.finditer(r"(\d+)\s+working days behind", text, re.I):
            days = int(m.group(1))
            if days > MAX_DAYS_BEHIND:
                context = text[max(0, m.start() - 60):m.end()].strip()
                bad.append(f"{urlparse(url).path} — {days} days — “…{context}…”")
    if bad:
        rep.fail(section, "Projects far behind schedule — dates are not anchored to today",
                 "\n".join(bad[:10]))
    else:
        rep.ok(section, f"No project more than {MAX_DAYS_BEHIND} working days behind")


def check_stale_dates(pages: dict[str, str], rep: Report) -> None:
    section = "P1 · Date anchoring"
    today = date.today()
    oldest = None
    for url, html in pages.items():
        text, _ = parse_page(html)
        for m in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text):
            try:
                found = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if oldest is None or found < oldest:
                oldest = found
    if oldest is None:
        rep.info(section, "No ISO dates found on the live pages")
        return
    age = (today - oldest).days
    if age > 45:
        rep.warn(section, f"Oldest date on the site is {oldest} ({age} days ago)",
                 "Expected after relative anchoring, but worth a glance if it keeps growing.")
    else:
        rep.ok(section, f"Oldest date on the site is {oldest} ({age} days ago)")


def check_project_links(pages: dict[str, str], rep: Report) -> None:
    section = "P5.1 · Project links"
    without = []
    for url, html in pages.items():
        path = urlparse(url).path
        if path.rstrip("/").endswith(("assumptions",)):
            continue
        _, links = parse_page(html)
        if not any("/projects/" in href for href in links):
            without.append(path)
    if without:
        rep.fail(section, "Pages with no link to any project page", "\n".join(without) +
                 "\nEvery project name should link to its project page.")
    else:
        rep.ok(section, "Every page checked links to at least one project")


def check_db_vocabulary_live(pages: dict[str, str], rep: Report) -> None:
    section = "P7 · Copy"
    hits = []
    for url, html in pages.items():
        text, _ = parse_page(html)
        for word in DB_VOCABULARY:
            for m in re.finditer(rf"\b{re.escape(word)}\b", text, re.I):
                context = text[max(0, m.start() - 45):m.end() + 30].strip()
                hits.append(f"{urlparse(url).path} — “…{context}…”")
    if hits:
        rep.fail(section, f"Database vocabulary visible to users ({len(hits)})",
                 "\n".join(hits[:12]))
    else:
        rep.ok(section, "No database vocabulary in visible page text")


def check_timeline_coverage(pages: dict[str, str], rep: Report) -> None:
    section = "P5.2 · Timeline coverage"
    timeline = next((h for u, h in pages.items() if "timeline" in u), None)
    pipeline = next((h for u, h in pages.items() if "pipeline" in u), None)
    if not timeline or not pipeline:
        rep.info(section, "Timeline or pipeline page not found — skipping")
        return
    _, tl_links = parse_page(timeline)
    _, pl_links = parse_page(pipeline)
    tl = {h for h in tl_links if "/projects/" in h}
    pl = {h for h in pl_links if "/projects/" in h}
    if not pl:
        rep.info(section, "No project links on the pipeline page to compare against")
        return
    if len(tl) < len(pl) * 0.5:
        rep.fail(section, f"Timeline shows {len(tl)} projects, pipeline shows {len(pl)}",
                 "The timeline should show every project from Ready onwards.")
    else:
        rep.ok(section, f"Timeline shows {len(tl)} projects against {len(pl)} on the pipeline")


def check_blocked_tile(pages: dict[str, str], rep: Report) -> None:
    section = "P6.3 · Blocked tile"
    for url, html in pages.items():
        text, _ = parse_page(html)
        m = re.search(r"(\d+)\s*(?:\n|\s)*blocked", text, re.I)
        if m:
            if int(m.group(1)) == 0:
                rep.warn(section, "Blocked count is 0",
                         "Fine if nothing is genuinely blocked. A permanent 0 means the "
                         "derivation in P6.3 is not implemented.")
            else:
                rep.ok(section, f"Blocked count is {m.group(1)} — derivation appears live")
            return
    rep.info(section, "No blocked tile found")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit against docs/REVIEW_02.md")
    parser.add_argument("--repo", default=".", help="path to the project (default: .)")
    parser.add_argument("--url", help="base URL of the running app, e.g. http://localhost:8000")
    parser.add_argument("--deep", action="store_true", help="also search git history")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    rep = Report()
    print(f"Auditing {root}")
    if args.url:
        print(f"Live site: {args.url}")

    check_brand_names(root, rep)
    check_docs_updated(root, rep)
    check_hardcoded_dates(root, rep)
    check_capacity_sources(root, rep)
    check_secrets(root, rep)
    check_db_vocabulary(root, rep)
    if args.deep:
        check_git_history(root, rep)

    if args.url:
        pages = discover_pages(args.url.rstrip("/"), rep)
        if pages:
            check_live_brands(pages, rep)
            check_live_disclaimer(pages, rep)
            check_live_percentages(pages, rep)
            check_person_consistency(pages, rep)
            check_over_capacity_claim(pages, rep)
            check_days_behind(pages, rep)
            check_stale_dates(pages, rep)
            check_project_links(pages, rep)
            check_db_vocabulary_live(pages, rep)
            check_timeline_coverage(pages, rep)
            check_blocked_tile(pages, rep)

    return rep.render()


if __name__ == "__main__":
    sys.exit(main())
