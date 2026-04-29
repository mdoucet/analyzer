#!/usr/bin/env python
"""
Pull arXiv references related to a neutron-reflectometry sample description.

This is an example of applying the `literature-search` skill from
https://gitlab.osti.gov/genesis/genesis-skills/-/blob/main/skills/literature-search/SKILL.md

The skill describes a four-step workflow (Search -> Evaluate -> Synthesize ->
Format) across arXiv, PubMed, Semantic Scholar, and Google Scholar. This
script implements the arXiv slice of that workflow programmatically using
arXiv's public Atom API (https://export.arxiv.org/api/query), so no API key
is required.

Usage
-----
    # Free-text sample description
    python scripts/arxiv_sample_references.py \\
        "Polymer brush on silicon with D2O contrast, neutron reflectometry"

    # Read description from a file
    python scripts/arxiv_sample_references.py --from-file sample.txt

    # Adjust result count and output format
    python scripts/arxiv_sample_references.py "lipid bilayer reflectometry" \\
        --max-results 8 --format bibtex

Output formats: ``markdown`` (default), ``bibtex``, ``json``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom",
           "arxiv": "http://arxiv.org/schemas/atom"}

# Words that are too generic to help an arXiv search.
_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "onto", "this", "that",
    "have", "has", "are", "was", "were", "will", "would", "could", "should",
    "a", "an", "of", "on", "in", "to", "by", "as", "is", "it", "or", "at",
    "be", "we", "our", "their", "its", "than", "then", "but", "not", "no",
    "sample", "samples", "data", "measurement", "measurements", "experiment",
}


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    year: str
    summary: str
    url: str
    primary_category: str

    def to_markdown(self) -> str:
        authors = ", ".join(self.authors[:4])
        if len(self.authors) > 4:
            authors += ", et al."
        return (
            f"### {self.title} ({self.year})\n\n"
            f"{authors}  \n"
            f"*{self.primary_category}* — [{self.arxiv_id}]({self.url})\n\n"
            f"**Abstract:** {self.summary.strip()}\n"
        )

    def to_bibtex(self) -> str:
        first_author = self.authors[0].split()[-1] if self.authors else "anon"
        key = f"{first_author.lower()}{self.year}_{self.arxiv_id.split('/')[-1]}"
        key = re.sub(r"[^A-Za-z0-9_]", "", key)
        authors = " and ".join(self.authors)
        return (
            f"@misc{{{key},\n"
            f"  title  = {{{self.title}}},\n"
            f"  author = {{{authors}}},\n"
            f"  year   = {{{self.year}}},\n"
            f"  eprint = {{{self.arxiv_id}}},\n"
            f"  archivePrefix = {{arXiv}},\n"
            f"  primaryClass  = {{{self.primary_category}}},\n"
            f"  url    = {{{self.url}}},\n"
            f"  abstract = {{{self.summary.strip()}}}\n"
            f"}}"
        )


def extract_keywords(description: str, max_terms: int = 8) -> list[str]:
    """Pull simple keyword candidates from a sample description.

    Picks multi-word capitalised phrases first (e.g. ``D2O``, ``Si/SiO2``),
    then falls back to non-stopword tokens of length >= 4.
    """
    # Preserve chemistry-like tokens (D2O, SiO2, Au, PEG, etc.)
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
    """Build an arXiv API search_query string from keywords.

    Always anchors on neutron reflectometry to keep results on-topic.
    """
    base_terms = ['"neutron reflectometry"', '"neutron reflectivity"']
    base = "(" + " OR ".join(f"all:{t}" for t in base_terms) + ")"
    extra = " AND (" + " OR ".join(f"all:{kw}" for kw in keywords) + ")" if keywords else ""
    return base + extra


def search_arxiv(query: str, max_results: int = 10,
                 retries: int = 4, backoff: float = 3.0) -> list[Paper]:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "analyzer-arxiv-example/1.0"})

    body: bytes | None = None
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            # 429 = rate limited, 5xx = transient server error -> retry with backoff.
            if exc.code != 429 and exc.code < 500:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                wait = float(retry_after) if retry_after else backoff * (2 ** attempt)
            except ValueError:
                wait = backoff * (2 ** attempt)
            print(f"arXiv returned HTTP {exc.code}; retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(wait)
        except urllib.error.URLError as exc:
            last_error = exc
            wait = backoff * (2 ** attempt)
            print(f"arXiv request failed ({exc}); retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(wait)
        except (TimeoutError, OSError) as exc:
            last_error = exc
            wait = backoff * (2 ** attempt)
            print(f"arXiv request timed out ({exc}); retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(wait)

    if body is None:
        raise RuntimeError(
            f"arXiv API request failed after {retries} attempts: {last_error}"
        )

    root = ET.fromstring(body)
    papers: list[Paper] = []
    for entry in root.findall("a:entry", ATOM_NS):
        arxiv_url = entry.findtext("a:id", default="", namespaces=ATOM_NS)
        arxiv_id = arxiv_url.rsplit("/abs/", 1)[-1]
        title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("a:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = entry.findtext("a:published", default="", namespaces=ATOM_NS)
        year = published[:4] if published else "n.d."
        authors = [
            (a.findtext("a:name", default="", namespaces=ATOM_NS) or "").strip()
            for a in entry.findall("a:author", ATOM_NS)
        ]
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        primary_category = primary.get("term", "") if primary is not None else ""

        papers.append(Paper(
            arxiv_id=arxiv_id,
            title=re.sub(r"\s+", " ", title),
            authors=[a for a in authors if a],
            year=year,
            summary=re.sub(r"\s+", " ", summary),
            url=arxiv_url,
            primary_category=primary_category,
        ))
    return papers


def format_output(papers: list[Paper], fmt: str, query: str, keywords: list[str]) -> str:
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
        "# arXiv references for sample",
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
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("description", nargs="?",
                   help="Free-text sample description.")
    p.add_argument("--from-file", type=Path,
                   help="Read the sample description from a text file.")
    p.add_argument("--max-results", type=int, default=10,
                   help="Maximum number of arXiv results to return (default: 10).")
    p.add_argument("--format", choices=("markdown", "bibtex", "json"),
                   default="markdown", help="Output format (default: markdown).")
    p.add_argument("--max-keywords", type=int, default=6,
                   help="Maximum keywords to extract from the description (default: 6).")
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
        papers = search_arxiv(query, max_results=args.max_results)
    except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_output(papers, args.format, query, keywords))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
