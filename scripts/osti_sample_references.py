#!/usr/bin/env python
"""
Pull OSTI.GOV references related to a neutron-reflectometry sample description.

Companion to ``arxiv_sample_references.py``: same idea (extract keywords from
a free-text sample description, search a public scientific index, render the
results), but targets the U.S. Department of Energy's OSTI.GOV catalog via
its public JSON API (https://www.osti.gov/api/v1/records). No API key is
required.

Usage
-----
    # Free-text sample description
    python scripts/osti_sample_references.py \\
        "Polymer brush on silicon with D2O contrast, neutron reflectometry"

    # Read description from a file
    python scripts/osti_sample_references.py --from-file sample.txt

    # Adjust result count and output format
    python scripts/osti_sample_references.py "lipid bilayer reflectometry" \\
        --max-results 8 --format bibtex

    # Also download each record's full text and save as markdown
    python scripts/osti_sample_references.py "polymer brush D2O" \\
        --download-markdown osti_md/

Output formats: ``markdown`` (default), ``bibtex``, ``json``.

Markdown body extraction
------------------------
With ``--download-markdown DIR`` the script writes one ``.md`` file per
record to ``DIR``. Each file contains a YAML front-matter block with the
record metadata followed by the extracted body text.

The body text is taken from, in order of preference:

1. The ``description`` / ``abstract`` field returned by the OSTI API.
2. Full text from a linked PDF when one of the optional dependencies
   ``pypdf`` or ``pdfminer.six`` is installed (``pip install pypdf``).
3. The Poppler ``pdftotext`` command-line tool, if available on ``PATH``.

If none of the above work the file still contains the abstract plus a note
that the full body was not retrievable.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from pathlib import Path

OSTI_API = "https://www.osti.gov/api/v1/records"

# Words that are too generic to help an OSTI search.
_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "onto", "this", "that",
    "have", "has", "are", "was", "were", "will", "would", "could", "should",
    "a", "an", "of", "on", "in", "to", "by", "as", "is", "it", "or", "at",
    "be", "we", "our", "their", "its", "than", "then", "but", "not", "no",
    "sample", "samples", "data", "measurement", "measurements", "experiment",
}


@dataclass
class Paper:
    osti_id: str
    title: str
    authors: list[str]
    year: str
    abstract: str
    url: str
    doi: str
    publisher: str
    product_type: str
    fulltext_url: str = ""
    extra_links: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        authors = ", ".join(self.authors[:4])
        if len(self.authors) > 4:
            authors += ", et al."
        doi = f"  \nDOI: [{self.doi}](https://doi.org/{self.doi})" if self.doi else ""
        ft = f"  \nFull text: [{self.fulltext_url}]({self.fulltext_url})" if self.fulltext_url else ""
        return (
            f"### {self.title} ({self.year})\n\n"
            f"{authors}  \n"
            f"*{self.product_type}* — {self.publisher}  \n"
            f"OSTI: [{self.osti_id}]({self.url}){doi}{ft}\n\n"
            f"**Abstract:** {self.abstract.strip() or '(no abstract)'}\n"
        )

    def to_bibtex(self) -> str:
        first_author = self.authors[0].split()[-1] if self.authors else "anon"
        key = f"{first_author.lower()}{self.year}_osti{self.osti_id}"
        key = re.sub(r"[^A-Za-z0-9_]", "", key)
        authors = " and ".join(self.authors) if self.authors else "Unknown"
        entry_type = "article" if self.doi else "techreport"
        fields = [
            f"  title  = {{{self.title}}}",
            f"  author = {{{authors}}}",
            f"  year   = {{{self.year}}}",
            f"  url    = {{{self.url}}}",
        ]
        if self.doi:
            fields.append(f"  doi    = {{{self.doi}}}")
        if self.publisher:
            fields.append(f"  institution = {{{self.publisher}}}")
        if self.abstract:
            fields.append(f"  abstract = {{{self.abstract.strip()}}}")
        fields.append(f"  note   = {{OSTI ID {self.osti_id}}}")
        return f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}"


def extract_keywords(description: str, max_terms: int = 8) -> list[str]:
    """Pull simple keyword candidates from a sample description."""
    chem = re.findall(r"\b[A-Z][A-Za-z0-9/]{1,}\b", description)
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", description.lower())
    words = [w for w in words if w not in _STOPWORDS]

    seen: set[str] = set()
    keywords: list[str] = []
    for term in chem + words:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(term)
        if len(keywords) >= max_terms:
            break
    return keywords


def build_query(keywords: list[str]) -> str:
    """Build an OSTI ``q`` string from keywords.

    OSTI uses Lucene-style boolean syntax. We anchor on neutron reflectometry
    so general DOE noise doesn't crowd out on-topic results.
    """
    base = '("neutron reflectometry" OR "neutron reflectivity")'
    if keywords:
        # Quote multi-character chemistry tokens; otherwise plain term.
        terms = [f'"{kw}"' if " " in kw else kw for kw in keywords]
        base += " AND (" + " OR ".join(terms) + ")"
    return base


def _http_get(url: str, *, accept: str = "application/json",
              retries: int = 4, backoff: float = 3.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "analyzer-osti-example/1.0",
            "Accept": accept,
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 429 and exc.code < 500:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                wait = float(retry_after) if retry_after else backoff * (2 ** attempt)
            except ValueError:
                wait = backoff * (2 ** attempt)
            print(f"OSTI returned HTTP {exc.code}; retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            wait = backoff * (2 ** attempt)
            print(f"OSTI request failed ({exc}); retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"OSTI request failed after {retries} attempts: {last_error}")


def _first(value):
    """OSTI fields can be scalar or list; return a flat string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _author_names(record: dict) -> list[str]:
    # The v1 API returns either a list of strings or list of dicts under
    # ``authors``; older payloads use ``creator``.
    raw = record.get("authors") or record.get("creator") or []
    if isinstance(raw, str):
        # Semicolon- or "and"-separated string
        parts = re.split(r";| and ", raw)
        return [p.strip() for p in parts if p.strip()]
    out: list[str] = []
    for a in raw:
        if isinstance(a, dict):
            name = a.get("name") or " ".join(
                x for x in (a.get("first_name"), a.get("last_name")) if x
            )
            if name:
                out.append(name.strip())
        elif isinstance(a, str) and a.strip():
            out.append(a.strip())
    return out


def _record_links(record: dict) -> tuple[str, list[str]]:
    """Return (best fulltext URL, all candidate links)."""
    candidates: list[str] = []
    fulltext = ""
    for key in ("links", "fulltext"):
        value = record.get(key)
        if not value:
            continue
        if isinstance(value, str):
            candidates.append(value)
            continue
        for entry in value:
            if isinstance(entry, dict):
                href = entry.get("href") or entry.get("url") or ""
                rel = (entry.get("rel") or entry.get("type") or "").lower()
                if not href:
                    continue
                candidates.append(href)
                if not fulltext and ("fulltext" in rel or href.lower().endswith(".pdf")):
                    fulltext = href
            elif isinstance(entry, str):
                candidates.append(entry)
    if not fulltext and candidates:
        # Prefer PDF-looking URL if any
        for c in candidates:
            if c.lower().endswith(".pdf"):
                fulltext = c
                break
    return fulltext, candidates


def search_osti(query: str, max_results: int = 10) -> list[Paper]:
    params = urllib.parse.urlencode({
        "q": query,
        "rows": max_results,
        "page": 0,
        "sort": "relevance",
    })
    url = f"{OSTI_API}?{params}"
    body = _http_get(url, accept="application/json")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OSTI returned non-JSON response: {exc}") from exc

    # The endpoint may return either a bare list or {"records": [...]}.
    records = data.get("records", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise RuntimeError(f"Unexpected OSTI payload shape: {type(records).__name__}")

    papers: list[Paper] = []
    for rec in records:
        osti_id = str(_first(rec.get("osti_id") or rec.get("id") or ""))
        title = re.sub(r"\s+", " ", str(_first(rec.get("title") or "")).strip())
        abstract = re.sub(
            r"\s+", " ",
            str(_first(rec.get("description") or rec.get("abstract") or "")).strip(),
        )
        date = str(_first(rec.get("publication_date") or rec.get("date") or ""))
        year = date[:4] if date else "n.d."
        doi = str(_first(rec.get("doi") or "")).strip()
        publisher = str(_first(
            rec.get("publisher") or rec.get("research_org") or ""
        )).strip()
        product_type = str(_first(
            rec.get("product_type") or rec.get("type") or ""
        )).strip()
        page_url = (
            str(_first(rec.get("osti_url") or rec.get("url") or "")).strip()
            or (f"https://www.osti.gov/biblio/{osti_id}" if osti_id else "")
        )
        fulltext, all_links = _record_links(rec)

        papers.append(Paper(
            osti_id=osti_id,
            title=title,
            authors=_author_names(rec),
            year=year,
            abstract=abstract,
            url=page_url,
            doi=doi,
            publisher=publisher,
            product_type=product_type,
            fulltext_url=fulltext,
            extra_links=all_links,
        ))
    return papers


# ---------------------------------------------------------------------------
# PDF -> text extraction (best effort, optional dependencies)
# ---------------------------------------------------------------------------

def _extract_with_pypdf(pdf_bytes: bytes) -> str | None:
    try:
        import pypdf  # type: ignore
    except ImportError:
        return None
    import io
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - best-effort extraction
        print(f"  pypdf extraction failed: {exc}", file=sys.stderr)
        return None


def _extract_with_pdfminer(pdf_bytes: bytes) -> str | None:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except ImportError:
        return None
    import io
    try:
        return extract_text(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        print(f"  pdfminer extraction failed: {exc}", file=sys.stderr)
        return None


def _extract_with_pdftotext(pdf_bytes: bytes) -> str | None:
    if shutil.which("pdftotext") is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "doc.pdf"
        pdf_path.write_bytes(pdf_bytes)
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                check=True, capture_output=True, timeout=120,
            )
            return result.stdout.decode("utf-8", errors="replace")
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"  pdftotext failed: {exc}", file=sys.stderr)
            return None


def fetch_pdf_text(url: str) -> str | None:
    try:
        pdf_bytes = _http_get(url, accept="application/pdf")
    except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError) as exc:
        print(f"  could not download {url}: {exc}", file=sys.stderr)
        return None
    if not pdf_bytes.startswith(b"%PDF"):
        # Not a PDF -- might be an HTML landing page redirect.
        return None
    for extractor in (_extract_with_pypdf, _extract_with_pdfminer,
                      _extract_with_pdftotext):
        text = extractor(pdf_bytes)
        if text and text.strip():
            return _clean_extracted_text(text)
    return None


def _clean_extracted_text(text: str) -> str:
    # Collapse multi-space artefacts but preserve paragraph breaks.
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in text.splitlines()]
    cleaned: list[str] = []
    blank = False
    for ln in lines:
        if ln:
            cleaned.append(ln)
            blank = False
        elif not blank:
            cleaned.append("")
            blank = True
    return "\n".join(cleaned).strip()


def _safe_filename(stem: str, max_len: int = 80) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return (stem or "paper")[:max_len]


def write_markdown_files(papers: list[Paper], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for paper in papers:
        stem = _safe_filename(f"osti_{paper.osti_id or paper.year}_{paper.title[:60]}")
        path = out_dir / f"{stem}.md"

        body_source = "abstract"
        body = paper.abstract.strip()
        if paper.fulltext_url:
            print(f"Fetching full text for OSTI {paper.osti_id}: {paper.fulltext_url}",
                  file=sys.stderr)
            extracted = fetch_pdf_text(paper.fulltext_url)
            if extracted:
                body = extracted
                body_source = f"pdf:{paper.fulltext_url}"
            else:
                print("  full-text extraction unavailable; falling back to abstract",
                      file=sys.stderr)

        front_matter = [
            "---",
            f"osti_id: {json.dumps(paper.osti_id)}",
            f"title: {json.dumps(paper.title)}",
            f"authors: {json.dumps(paper.authors)}",
            f"year: {json.dumps(paper.year)}",
            f"doi: {json.dumps(paper.doi)}",
            f"publisher: {json.dumps(paper.publisher)}",
            f"product_type: {json.dumps(paper.product_type)}",
            f"url: {json.dumps(paper.url)}",
            f"fulltext_url: {json.dumps(paper.fulltext_url)}",
            f"body_source: {json.dumps(body_source)}",
            "---",
            "",
            f"# {paper.title}",
            "",
        ]
        if paper.authors:
            front_matter.append("**Authors:** " + ", ".join(paper.authors))
            front_matter.append("")
        if not body:
            body = "_No abstract or full-text body was available for this record._"
        front_matter.append(body)
        path.write_text("\n".join(front_matter) + "\n", encoding="utf-8")
        written.append(path)
    return written


def format_output(papers: list[Paper], fmt: str, query: str,
                  keywords: list[str]) -> str:
    if fmt == "json":
        return json.dumps(
            {"query": query, "keywords": keywords,
             "papers": [asdict(p) for p in papers]},
            indent=2,
        )
    if fmt == "bibtex":
        return "\n\n".join(p.to_bibtex() for p in papers)

    # markdown
    lines = [
        "# OSTI.GOV references for sample",
        "",
        f"**Keywords:** {', '.join(keywords) if keywords else '(none)'}  ",
        f"**Query:** `{query}`",
        "",
        f"Found {len(papers)} result(s).",
        "",
    ]
    lines.extend(p.to_markdown() for p in papers)
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("description", nargs="?",
                   help="Free-text sample description.")
    p.add_argument("--from-file", type=Path,
                   help="Read the sample description from a text file.")
    p.add_argument("--max-results", type=int, default=10,
                   help="Maximum number of OSTI results to return (default: 10).")
    p.add_argument("--format", choices=("markdown", "bibtex", "json"),
                   default="markdown", help="Output format (default: markdown).")
    p.add_argument("--max-keywords", type=int, default=6,
                   help="Maximum keywords to extract (default: 6).")
    p.add_argument("--download-markdown", type=Path, metavar="DIR",
                   help="Also save each record as a markdown file in DIR, "
                        "attempting to extract the full body text from a "
                        "linked PDF when possible.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.from_file:
        description = args.from_file.read_text(encoding="utf-8")
    elif args.description:
        description = args.description
    else:
        print("error: provide a description or --from-file", file=sys.stderr)
        return 2

    keywords = extract_keywords(description, max_terms=args.max_keywords)
    query = build_query(keywords)
    try:
        papers = search_osti(query, max_results=args.max_results)
    except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_output(papers, args.format, query, keywords))

    if args.download_markdown:
        written = write_markdown_files(papers, args.download_markdown)
        print(f"\nWrote {len(written)} markdown file(s) to "
              f"{args.download_markdown}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
