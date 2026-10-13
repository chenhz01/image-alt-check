# -*- coding: utf-8 -*-
"""image-alt-check — three-tier alt-text accessibility grading for HTML/Markdown.

Pure standard library. Scans .html/.htm files (HTMLParser) and .md files
(markdown image syntax + embedded <img> tags) and classifies every image:
  - missing-alt   (error): no alt attribute at all
  - decorative    (info):  alt="" or whitespace — intentional, passes
  - filename-alt  (warn):  alt is the file name or contains an extension
  - generic-alt   (warn):  alt is a placeholder word like "image"/"photo"
  - pass: anything else
Exit codes: 0 = no errors, 1 = errors found (warnings too with --strict),
2 = input error.
"""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
FILENAMEISH = re.compile(r"\.(png|jpe?g|gif|svg|webp|bmp|ico|avif)\s*$", re.IGNORECASE)
GENERIC = {"image", "photo", "picture", "graphic", "icon", "screenshot", "img",
           "logo", "banner", "chart", "diagram", "figure", "fig", "pic"}
MD_EXTENSIONS = (".md", ".markdown")
HTML_EXTENSIONS = (".html", ".htm")


class _ImgCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            d = dict(attrs)
            line = self.getpos()[0]
            self.images.append({"line": line, "src": d.get("src", ""),
                                "alt": d.get("alt", None)})
        # void tag; no endtag handling needed


def classify(alt, src, markdown=False):
    """Return (kind, severity) for one image.

    In Markdown there is no 'absent attribute' — empty alt text is how an
    author skips alt entirely, so `![]()` grades as missing-alt (error).
    In HTML, alt="" is a deliberate decorative marker (info), while no
    alt attribute at all is missing-alt (error).
    """
    if alt is None or (markdown and alt == ""):
        return "missing-alt", "error"
    stripped = alt.strip()
    if stripped == "":
        return "decorative", "info"
    if FILENAMEISH.search(stripped) or (src and stripped == os.path.basename(src)):
        return "filename-alt", "warning"
    if stripped.lower() in GENERIC:
        return "generic-alt", "warning"
    return "pass", "info"


def scan_text(text, is_markdown):
    findings = []
    if is_markdown:
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in MD_IMAGE.finditer(line):
                kind, sev = classify(m.group(1), m.group(2), markdown=True)
                findings.append({"line": lineno, "kind": kind, "severity": sev,
                                 "src": m.group(2), "alt": m.group(1)})
    collector = _ImgCollector()
    try:
        collector.feed(text)
        collector.close()
    except Exception:
        pass  # tolerate malformed HTML; scan what parsed
    if is_markdown:
        md_lines = {f["line"] for f in findings}
        for img in collector.images:
            if img["line"] in md_lines:
                continue
            kind, sev = classify(img["alt"], img["src"])
            findings.append({"line": img["line"], "kind": kind, "severity": sev,
                             "src": img["src"], "alt": img["alt"]})
    else:
        for img in collector.images:
            kind, sev = classify(img["alt"], img["src"])
            findings.append({"line": img["line"], "kind": kind, "severity": sev,
                             "src": img["src"], "alt": img["alt"]})
    findings.sort(key=lambda f: f["line"])
    return findings


def score_of(findings):
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    return max(0, 100 - 20 * errors - 5 * warnings)


def analyze(paths):
    report = {"tool": "image-alt-check", "files": [], "summary":
              {"files": 0, "images": 0, "errors": 0, "warnings": 0, "score": 100}}
    total_findings = []
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        is_md = ext in MD_EXTENSIONS
        if ext not in MD_EXTENSIONS and ext not in HTML_EXTENSIONS:
            raise ValueError("unsupported file type: %r (use .md/.markdown/.html/.htm)" % path)
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                text = fh.read()
        except OSError as exc:
            raise ValueError("cannot read %s: %s" % (path, exc))
        findings = scan_text(text, is_md)
        errors = sum(1 for f in findings if f["severity"] == "error")
        warnings = sum(1 for f in findings if f["severity"] == "warning")
        report["files"].append({"path": path, "images": len(findings),
                                "errors": errors, "warnings": warnings,
                                "score": score_of(findings), "findings": findings})
        total_findings.extend(findings)
    s = report["summary"]
    s["files"] = len(report["files"])
    s["images"] = len(total_findings)
    s["errors"] = sum(1 for f in total_findings if f["severity"] == "error")
    s["warnings"] = sum(1 for f in total_findings if f["severity"] == "warning")
    s["score"] = score_of(total_findings)
    report["verdict"] = ("FAIL: %d image(s) missing alt text" % s["errors"]
                         if s["errors"] else
                         ("pass with %d warning(s)" % s["warnings"] if s["warnings"]
                          else "all images have alt text"))
    return report


def render_text(report):
    lines = ["image-alt-check report", "=" * 24]
    for fr in report["files"]:
        lines.append("%s  score=%d  (%d images, %d errors, %d warnings)"
                     % (fr["path"], fr["score"], fr["images"], fr["errors"], fr["warnings"]))
        for f in fr["findings"]:
            if f["severity"] in ("error", "warning"):
                lines.append("  %-6s line %3d  %-13s src=%s alt=%r"
                             % (f["severity"].upper(), f["line"], f["kind"],
                                str(f["src"])[:40], str(f["alt"])[:40]))
    s = report["summary"]
    lines.append("summary: %d file(s), %d image(s), %d error(s), %d warning(s), score %d/100"
                 % (s["files"], s["images"], s["errors"], s["warnings"], s["score"]))
    lines.append("verdict: %s" % report["verdict"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="image-alt-check",
        description="Three-tier alt-text accessibility check for HTML and Markdown files.")
    parser.add_argument("files", nargs="+", help="one or more .md/.html files")
    parser.add_argument("--strict", action="store_true",
                        help="warnings also cause exit 1")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        report = analyze(args.files)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    if report["summary"]["errors"]:
        return 1
    return 1 if (args.strict and report["summary"]["warnings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
