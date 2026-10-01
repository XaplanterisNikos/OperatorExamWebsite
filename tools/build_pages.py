#!/usr/bin/env python3
"""
Static page generator for operator-exam-quiz.web.app.

Reads the app's question bank (questions.json + exam_config.json) and generates:
  - public/erotiseis/index.html             -> list of all 15 chapters
  - public/erotiseis/<slug>/index.html      -> one page per chapter with every question
  - public/sitemap.xml                      -> home + list + chapter pages
  - the chapter list inside public/index.html, between the
    <!-- CHAPTERS:START --> and <!-- CHAPTERS:END --> markers

The same JSON files ship inside the Android app, so site and app stay in sync:
edit questions.json, re-run this script, deploy.

Usage (from the repository root):
    python tools/build_pages.py
    python tools/build_pages.py --questions ../operator-exam-quiz/app/src/main/assets/questions.json \
                                --config ../operator-exam-quiz/app/src/main/assets/exam_config.json

No third-party packages required (Python 3.9+).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Site-wide constants
# ---------------------------------------------------------------------------

SITE_URL = "https://operator-exam-quiz.web.app"
PLAY_URL = "https://play.google.com/store/apps/details?id=com.foxnks.xeiristisexamquiz"

# Bump together with the ?v= in index.html / 404.html whenever style.css changes
CSS_VERSION = "3"

# Markers in public/index.html that delimit the auto-generated chapter list
HOME_START = "<!-- CHAPTERS:START -->"
HOME_END = "<!-- CHAPTERS:END -->"

# Descriptive Greeklish URL slugs per chapter id.
# Slugs are part of the public URLs: never change one after it has been indexed.
CHAPTER_SLUGS: dict[int, str] = {
    1: "genikes-erotiseis-xamilis-dyskolias",
    2: "genikes-erotiseis-metrias-dyskolias",
    3: "genikes-erotiseis-ypsilis-dyskolias",
    4: "eidikotita-1-ekskafi-xomatourgika",
    5: "eidikotita-2-anypsosi-metafora-fortion",
    6: "eidikotita-3-odostrosia",
    7: "eidikotita-4-eksypiretisi-odon-aerodromion",
    8: "eidikotita-5-ypogeia-erga-metalleia",
    9: "eidikotita-6-ergasies-elksis",
    10: "eidikotita-7-diatrisi-kopi-edafon",
    11: "eidikotita-8-anypsosi-eidikon-ergasion",
    12: "asfaleia-ergasias",
    13: "oikonomika-themata",
    14: "gnosi-ypologiston",
    15: "texniki-orologia-agglika",
}

# Chapter groups shown on the list page (title, chapter ids)
CHAPTER_GROUPS: list[tuple[str, list[int]]] = [
    ("Γενικές ερωτήσεις", [1, 2, 3]),
    ("Ειδικότητες", [4, 5, 6, 7, 8, 9, 10, 11]),
    ("Λοιπά θέματα", [12, 13, 14, 15]),
]

# Option ids in the JSON are latin letters a..o; show them as Greek letters
GREEK_LETTERS = dict(zip("abcdefghijklmno", "αβγδεζηθικλμνξο"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(text: str) -> str:
    """Escapes text for safe use inside HTML content and attributes."""
    return html.escape(text.strip(), quote=True)


def play_link(medium: str) -> str:
    """
    Builds a Google Play link with an install referrer, so Play Console can
    attribute installs to the page/button they came from.
    The referrer value is URL-encoded and '&' is HTML-escaped as '&amp;'.
    """
    return f"{PLAY_URL}&amp;referrer=utm_source%3Dwebsite%26utm_medium%3D{medium}"


def chapter_url(chapter_id: int) -> str:
    """Returns the root-relative URL of a chapter page (with trailing slash)."""
    return f"/erotiseis/{CHAPTER_SLUGS[chapter_id]}/"


def file_date(path: Path) -> str:
    """Returns a file's last-modified date as YYYY-MM-DD (used for sitemap <lastmod>)."""
    return dt.date.fromtimestamp(path.stat().st_mtime).isoformat()


def plural_questions(n: int) -> str:
    """Greek singular/plural for 'question'."""
    return f"{n} ερώτηση" if n == 1 else f"{n} ερωτήσεις"


def breadcrumb_jsonld(items: list[tuple[str, str]]) -> str:
    """
    Builds a schema.org BreadcrumbList so Google can show
    'Αρχική › Ερωτήσεις › Κεφάλαιο' instead of the raw URL in results.
    items: list of (name, root-relative url).
    """
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": f"{SITE_URL}{url}"}
            for i, (name, url) in enumerate(items, start=1)
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def breadcrumb_html(items: list[tuple[str, str]]) -> str:
    """Visible breadcrumb; the last item is the current page (not a link)."""
    parts = []
    for i, (name, url) in enumerate(items):
        if i == len(items) - 1:
            parts.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            parts.append(f'<li><a href="{url}">{esc(name)}</a></li>')
    return f'<nav class="breadcrumb" aria-label="Διαδρομή"><ol>{"".join(parts)}</ol></nav>'


# ---------------------------------------------------------------------------
# Shared page shell
# ---------------------------------------------------------------------------

def page_shell(*, title: str, description: str, path: str, body: str, jsonld: str) -> str:
    """
    Wraps page content in the shared <head>, header and footer.
    path: root-relative canonical path of the page (e.g. '/erotiseis/').
    """
    canonical = f"{SITE_URL}{path}"
    return f"""<!doctype html>
<html lang="el">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />

    <!-- Generated by tools/build_pages.py. Do not edit by hand: edit the script or questions.json and re-run it -->
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(description)}" />
    <link rel="canonical" href="{canonical}" />

    <link rel="icon" type="image/png" href="/images/icon.png" />
    <link rel="apple-touch-icon" href="/images/icon.png" />
    <meta name="theme-color" content="#172033" />

    <!-- Open Graph: preview card when the page is shared -->
    <meta property="og:type" content="website" />
    <meta property="og:locale" content="el_GR" />
    <meta property="og:site_name" content="Operator Exam Quiz" />
    <meta property="og:url" content="{canonical}" />
    <meta property="og:title" content="{esc(title)}" />
    <meta property="og:description" content="{esc(description)}" />
    <meta property="og:image" content="{SITE_URL}/images/og-image.png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />

    <link rel="stylesheet" href="/style.css?v={CSS_VERSION}" />

    <!-- Breadcrumb structured data -->
    <script type="application/ld+json">
{jsonld}
    </script>
  </head>

  <body>
    <!-- Slim header shared by all sub-pages -->
    <header class="site-header">
      <div class="container site-header-inner">
        <a href="/" class="site-brand" aria-label="Operator Exam Quiz – Αρχική">
          <img src="/images/icon.png" alt="" width="512" height="512" />
          <!-- Text hidden on small phones (icon stays); still read by screen readers via aria-label -->
          <span class="site-brand-name">Operator Exam Quiz</span>
        </a>
        <nav class="site-nav" aria-label="Κύριο μενού">
          <a href="/erotiseis/">Ερωτήσεις</a>
          <a href="{play_link('header')}" target="_blank" rel="noopener" class="site-nav-cta">Εφαρμογή</a>
        </nav>
      </div>
    </header>

    <main class="subpage">
{body}
    </main>

    <footer>
      <div class="container footer-content">
        <div>
          <strong>Operator Exam Quiz</strong>
          <p>Εφαρμογή προετοιμασίας για θεωρητικές εξετάσεις χειριστών μηχανημάτων έργου.</p>
          <!-- Independence notice: the site is not an official government source -->
          <p class="footer-note">
            Ανεξάρτητο εργαλείο εξάσκησης. Δεν σχετίζεται με το Υπουργείο ή τις Περιφέρειες
            που διενεργούν τις εξετάσεις.
          </p>
        </div>
        <div class="footer-links">
          <a href="/">Αρχική</a>
          <a href="/erotiseis/">Ερωτήσεις ανά κεφάλαιο</a>
          <a href="mailto:xaplanterisnikos@gmail.com">Email</a>
        </div>
      </div>
      <div class="copyright">© {dt.date.today().year} Νίκος Ξαπλαντέρης · Operator Exam Quiz</div>
    </footer>
  </body>
</html>
"""


def app_cta(medium: str) -> str:
    """Call-to-action box that sends readers to the app for timed practice."""
    return f"""
        <aside class="cta-box">
          <h2>Εξασκήσου με χρονόμετρο</h2>
          <p>
            Στην εφαρμογή απαντάς τις ερωτήσεις με άμεση διόρθωση και κάνεις το Τελικό Τεστ:
            80 ερωτήσεις σε 90 λεπτά, όπως στις εξετάσεις. Δωρεάν, χωρίς διαφημίσεις, και offline.
          </p>
          <a href="{play_link(medium)}" target="_blank" rel="noopener" class="play-button">
            Λήψη από Google Play
          </a>
        </aside>"""


# ---------------------------------------------------------------------------
# Chapter page
# ---------------------------------------------------------------------------

def render_question(number: int, question: dict) -> str:
    """
    Renders one question: text, all options, and the correct answer(s)
    hidden inside <details> (no JavaScript; content stays indexable).
    """
    options = question["options"]
    correct = [o for o in options if o["isCorrect"]]
    is_multiple = question["type"] == "MULTIPLE"

    # All options are always visible so the reader can think before revealing
    option_items = "\n".join(
        f'              <li><span class="option-letter">{GREEK_LETTERS[o["id"]]}</span>'
        f'<span>{esc(o["text"])}</span></li>'
        for o in options
    )

    # Answer block: one line per correct option
    answer_label = "Σωστές απαντήσεις" if len(correct) > 1 else "Σωστή απάντηση"
    answer_items = "\n".join(
        f'                <li><span class="option-letter">{GREEK_LETTERS[o["id"]]}</span>'
        f'<span>{esc(o["text"])}</span></li>'
        for o in correct
    )

    # Optional explanation (currently null for every question, rendered if ever added)
    explanation = ""
    if question.get("explanation"):
        explanation = f'\n              <p class="answer-explanation">{esc(question["explanation"])}</p>'

    multiple_hint = (
        '\n            <p class="question-hint">Πολλαπλές σωστές απαντήσεις</p>' if is_multiple else ""
    )

    # id="q-N" lets anyone link to a specific question (e.g. .../#q-12)
    return f"""
          <article class="question" id="q-{number}">
            <h2 class="question-text"><span class="question-number">{number}.</span> {esc(question["text"])}</h2>{multiple_hint}
            <ul class="options">
{option_items}
            </ul>
            <details class="answer">
              <summary>Δες την απάντηση</summary>
              <p class="answer-label">{answer_label}:</p>
              <ul class="options correct">
{answer_items}
              </ul>{explanation}
            </details>
          </article>"""


def render_chapter_page(chapter: dict, questions: list[dict], exam_count: int,
                        prev_ch: dict | None, next_ch: dict | None) -> str:
    """Builds the full HTML of one chapter page."""
    cid = chapter["id"]
    name = chapter["title"]
    count = len(questions)
    path = chapter_url(cid)

    crumbs = [("Αρχική", "/"), ("Ερωτήσεις", "/erotiseis/"), (name, path)]

    # Exam-weight sentence: unique, useful info per page (from exam_config.json)
    exam_sentence = (
        f"Στο Τελικό Τεστ της εφαρμογής επιλέγονται {plural_questions(exam_count)} από αυτό το κεφάλαιο."
        if exam_count else ""
    )

    questions_html = "".join(render_question(i, q) for i, q in enumerate(questions, start=1))

    # Previous / next chapter navigation keeps readers (and crawlers) moving through the site
    pager = []
    if prev_ch:
        pager.append(f'<a href="{chapter_url(prev_ch["id"])}" class="pager-prev">'
                     f'<span>Προηγούμενο κεφάλαιο</span>{esc(prev_ch["title"])}</a>')
    if next_ch:
        pager.append(f'<a href="{chapter_url(next_ch["id"])}" class="pager-next">'
                     f'<span>Επόμενο κεφάλαιο</span>{esc(next_ch["title"])}</a>')

    body = f"""      <div class="container narrow">
        {breadcrumb_html(crumbs)}

        <h1>{esc(name)}</h1>
        <p class="lead">
          Όλες οι {plural_questions(count)} του κεφαλαίου για τις θεωρητικές εξετάσεις χειριστών
          μηχανημάτων έργου. {exam_sentence} Σκέψου την απάντηση και πάτησε «Δες την απάντηση»
          για να ελέγξεις αν είναι σωστή.
        </p>

        <div class="question-list">{questions_html}
        </div>
{app_cta(f"chapter_{cid}")}

        <nav class="pager" aria-label="Κεφάλαια">
          {"".join(pager)}
        </nav>
      </div>"""

    return page_shell(
        title=f"{name} – Ερωτήσεις χειριστή μηχανημάτων έργου",
        description=(f"Όλες οι {plural_questions(count)} του κεφαλαίου «{name}» για τις θεωρητικές "
                     f"εξετάσεις χειριστών μηχανημάτων έργου, με τις σωστές απαντήσεις."),
        path=path,
        body=body,
        jsonld=breadcrumb_jsonld(crumbs),
    )


# ---------------------------------------------------------------------------
# Chapter list (used on /erotiseis/ and on the home page)
# ---------------------------------------------------------------------------

def chapter_list_html(chapters: dict[int, dict], counts: dict[int, int],
                      exam_counts: dict[int, int], heading_tag: str) -> str:
    """
    Grouped list of chapter links with question counts.
    heading_tag: 'h2' on the list page, 'h3' on the home page (inside an existing h2 section).
    """
    groups = []
    for group_title, ids in CHAPTER_GROUPS:
        items = "\n".join(
            f'            <li><a href="{chapter_url(cid)}">{esc(chapters[cid]["title"])}</a>'
            f'<span>{plural_questions(counts[cid])}, {exam_counts.get(cid, 0)} στο τελικό τεστ</span></li>'
            for cid in ids if cid in chapters
        )
        groups.append(f"""
          <div class="chapter-group">
            <{heading_tag}>{esc(group_title)}</{heading_tag}>
            <ul class="chapter-list">
{items}
            </ul>
          </div>""")
    return "".join(groups)


def render_list_page(chapters, counts, exam_counts, total: int) -> str:
    """Builds /erotiseis/ — the hub page linking to every chapter."""
    crumbs = [("Αρχική", "/"), ("Ερωτήσεις", "/erotiseis/")]
    body = f"""      <div class="container narrow">
        {breadcrumb_html(crumbs)}

        <h1>Ερωτήσεις εξετάσεων χειριστή μηχανημάτων έργου</h1>
        <p class="lead">
          Και οι {total} ερωτήσεις της θεωρητικής εξέτασης, οργανωμένες σε {len(chapters)} κεφάλαια,
          με τις σωστές απαντήσεις. Διάλεξε κεφάλαιο για να ξεκινήσεις.
        </p>
{chapter_list_html(chapters, counts, exam_counts, "h2")}
{app_cta("list_page")}
      </div>"""

    return page_shell(
        title="Ερωτήσεις εξετάσεων χειριστή μηχανημάτων έργου – Όλα τα κεφάλαια",
        description=(f"Όλες οι {total} ερωτήσεις των θεωρητικών εξετάσεων χειριστών μηχανημάτων έργου "
                     f"σε {len(chapters)} κεφάλαια, με τις σωστές απαντήσεις."),
        path="/erotiseis/",
        body=body,
        jsonld=breadcrumb_jsonld(crumbs),
    )


# ---------------------------------------------------------------------------
# Sitemap and home page
# ---------------------------------------------------------------------------

def render_sitemap(entries: list[tuple[str, str]]) -> str:
    """entries: list of (root-relative path, lastmod YYYY-MM-DD)."""
    urls = "\n".join(
        f"    <url>\n        <loc>{SITE_URL}{p}</loc>\n        <lastmod>{d}</lastmod>\n    </url>"
        for p, d in entries
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by tools/build_pages.py. lastmod = last change of the source file -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""


def update_home(index_path: Path, list_html: str) -> None:
    """Replaces the content between the CHAPTERS markers in public/index.html."""
    content = index_path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(HOME_START) + r".*?" + re.escape(HOME_END), re.S)
    if not pattern.search(content):
        raise SystemExit(f"Markers {HOME_START} / {HOME_END} not found in {index_path}")
    # Lambda avoids backslash interpretation in the replacement string
    content = pattern.sub(lambda _: f"{HOME_START}{list_html}\n          {HOME_END}", content)
    index_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Parses arguments, validates the data and writes all generated files."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Generate chapter pages from questions.json")
    parser.add_argument("--questions", type=Path, default=root / "data" / "questions.json")
    parser.add_argument("--config", type=Path, default=root / "data" / "exam_config.json")
    parser.add_argument("--public", type=Path, default=root / "public")
    args = parser.parse_args()

    bank = json.loads(args.questions.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))

    chapters = {c["id"]: c for c in sorted(bank["chapters"], key=lambda c: c["order"])}
    exam_counts = {int(k): v for k, v in config.get("questionsPerChapter", {}).items()}

    # Fail fast on data the site cannot represent
    missing_slugs = set(chapters) - set(CHAPTER_SLUGS)
    if missing_slugs:
        raise SystemExit(f"Add a slug in CHAPTER_SLUGS for chapter id(s): {sorted(missing_slugs)}")

    by_chapter: dict[int, list[dict]] = {cid: [] for cid in chapters}
    for q in bank["questions"]:
        if not any(o["isCorrect"] for o in q["options"]):
            raise SystemExit(f"Question {q['id']} has no correct option")
        unknown = [o["id"] for o in q["options"] if o["id"] not in GREEK_LETTERS]
        if unknown:
            raise SystemExit(f"Question {q['id']} has option ids without a Greek letter: {unknown}")
        by_chapter[q["chapterId"]].append(q)

    counts = {cid: len(qs) for cid, qs in by_chapter.items()}
    total = sum(counts.values())
    data_date = file_date(args.questions)
    ordered = list(chapters.values())

    # Chapter pages
    for i, chapter in enumerate(ordered):
        cid = chapter["id"]
        out = args.public / "erotiseis" / CHAPTER_SLUGS[cid] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            render_chapter_page(
                chapter, by_chapter[cid], exam_counts.get(cid, 0),
                ordered[i - 1] if i > 0 else None,
                ordered[i + 1] if i < len(ordered) - 1 else None,
            ),
            encoding="utf-8",
        )

    # Hub page
    list_out = args.public / "erotiseis" / "index.html"
    list_out.write_text(render_list_page(chapters, counts, exam_counts, total), encoding="utf-8")

    # Home page chapter list (h3 because it sits inside the home page's h2 section)
    home = args.public / "index.html"
    update_home(home, chapter_list_html(chapters, counts, exam_counts, "h3"))

    # Sitemap: home uses index.html's date, generated pages use the data file's date
    entries = [("/", file_date(home)), ("/erotiseis/", data_date)]
    entries += [(chapter_url(c["id"]), data_date) for c in ordered]
    (args.public / "sitemap.xml").write_text(render_sitemap(entries), encoding="utf-8")

    print(f"Generated {len(ordered)} chapter pages + list page ({total} questions), "
          f"updated index.html and sitemap.xml ({len(entries)} URLs)")


if __name__ == "__main__":
    main()
