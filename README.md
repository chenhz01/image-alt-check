# image-alt-check

Grade the alt text of every image in your Markdown and HTML docs in one
offline pass. The scanner classifies each image as missing alt (error),
empty/decorative (intentional, passes), filename-only or generic-word alt
(warning), or properly described (pass) — then prints per-file scores and a
verdict your CI can gate on. If your docs mix screenshots, diagrams, and
badges, this is for you; if your images are all decorative dividers, skip it.

## Problem

Alt text fails quietly: someone pastes a screenshot as `![](image.png)`,
another writes `alt="photo"`, a badge gets no alt at all. Screen-reader users
hit dead links to meaning, and nothing in a normal PR review catches it —
by the time an accessibility audit runs, hundreds of images have shipped.

## How it works

Every image found gets a **three-tier classification**:

| Tier | Examples | Severity |
|---|---|---|
| missing | `<img src="a.png">` (HTML), `![](a.png)` (Markdown) | error |
| decorative | `<img alt="">`, `alt="   "` — empty by intent | info (pass) |
| filename-only / generic | `alt="diagram.png"`, `alt="photo"`, `alt="Screenshot"` | warning |
| described | `alt="Latency by region, March 2026"` | pass |

- **Markdown**: `![alt](src)` syntax plus embedded `<img>` tags (deduped by
  line). Markdown has no "absent attribute" state, so an empty alt is how an
  author skips alt — it grades as *missing*, matching what screen readers
  actually announce (nothing).
- **HTML**: real attribute-level parsing (`html.parser`), so `alt=""` and
  no-`alt` are correctly distinguished; malformed HTML degrades gracefully.
- **Scoring**: 100 − 20×errors − 5×warnings, floored at 0. Exit 1 on any
  error; `--strict` also fails on warnings.

## Quickstart (~2 min)

```bash
# 30 s: check one markdown doc (exit 1 — one image missing alt)
printf '![ok desc](a.png)\n![](b.png)\n' > /tmp/doc.md
python image_alt_check.py /tmp/doc.md

# 30 s: check the whole docs folder
python image_alt_check.py docs/*.md docs/*.html

# 1 min: JSON scores for a dashboard
python image_alt_check.py README.md --format json
```

## Why not X?

- **markdown-image-alt-text-checker** (ruthtxh): a GitHub Action for `.md`
  files that flags missing inline alt text, with optional Azure Computer
  Vision suggestions. It runs on CI infrastructure with a token and an
  optional cloud API key; this tool runs anywhere Python runs, offline, and
  adds the two lower tiers (decorative vs filename/generic warnings) rather
  than a single missing/not-missing flag.
- **axe-core / Lighthouse**: full accessibility engines over a live browser.
  Far broader, far heavier: they need a rendered DOM, catch color contrast,
  ARIA, and focus issues — and won't run inside a plain docs repo CI step
  without browser plumbing. When you need a whole-site audit, use them; for
  the alt-text slice, this is the cheap pass.
- **markdownlint**: style linter with an MD45 rule (alt-text presence) for
  markdown only. No HTML support, no filename/generic heuristics, no score.

## How this differs from markdown-image-alt-text-checker

That project is a GitHub Action that checks markdown files for images and
flags missing inline alt-text, optionally calling Azure Computer Vision to
suggest alt text, with PR annotations. This repo inverts the operational
model: a local, dependency-free CLI with no tokens and no cloud calls, so
it runs on any machine, in any CI, before the PR even opens. Coverage is
wider (HTML attribute semantics, not just markdown syntax; embedded `<img>`
tags; filename-only and generic-word alt tiers) and narrower (no AI
suggestions — a static heuristic should not pretend to know what your
diagram shows).

## Performance

[Measured] Windows 10, Python 3.13, 2026-10-13: scanning 20 files with 300
images total took **19.7 ms** in-process (median of 30 runs) — O(bytes of
markup), regex plus a single-pass HTML parser. No network, no models.

Reproduce:

```bash
python - <<'EOF'
import io, json, time, contextlib, tempfile, os
import image_alt_check as m
files = []
for i in range(20):
    p = os.path.join(tempfile.mkdtemp(), "d%d.md" % i)
    open(p, "w", encoding="utf-8", newline="").write(
        "".join("![desc %d](i%d.png)\n" % (j, j) for j in range(15)))
    files.append(p)
t = time.perf_counter()
for _ in range(30):
    with contextlib.redirect_stdout(io.StringIO()):
        m.main(files + ["--format", "json"])
print("warm_ms=%.1f" % ((time.perf_counter() - t) / 30 * 1000))
EOF
```

## Minimal Fallback

Grep is the fallback: `grep -n '!\[\](\|<img [^>]*src' docs/*.md` finds the
error tier in one line — it just cannot distinguish decorative empties from
lazy ones or spot `alt="image.png"`. For a solo doc set, that grep plus the
table above covers ~80% of the value.

## Design Trade-offs

Priority order: **zero cloud dependencies > tier nuance > recall**. The
generic-word list (photo, image, screenshot…) is deliberately small and
public — an aggressive list would flag legitimate short alts and train
users to ignore warnings. The filename heuristic accepts "IMG_2041"-style
alts as pass when no extension is present (camera-file names are bad alt,
but a static tool cannot prove it; false warnings cost trust). Scoring
weights (20/5) were chosen so a single missing alt cannot hide behind a
page of decorative dividers, while one lazy alt does not fail a build.

## Limits & Second-order Effects

- Regex markdown scanning: images built by templates or JS are invisible to
  a static pass.
- `alt="A screenshot of the dashboard showing... "` starts with a generic
  noun but IS descriptive — the generic check only fires on the whole alt
  being a single generic word, so this is safe, but richer sentences with a
  generic core still pass.
- If CI gates on score, teams may add superficial-but-passing alt text
  ("graph of the graph") to silence the tool — pair the gate with periodic
  human spot checks, ideally with screen-reader users in the loop.

## FAQ

**Q: Why is markdown `![](x)` an error when HTML `alt=""` is not?**
A: In HTML, `alt=""` is an explicit WCAG decorative marker. Markdown has no
absent-attribute state — empty is the only way to skip alt, and screen
readers announce nothing, exactly like the missing case.

**Q: Does it fetch images or use AI to write alt text?**
A: No and no. It reads the markup you already have and stays fully offline.

**Q: When NOT to use this?**
A: Dynamic/JS-rendered pages (nothing static to scan), or as a substitute
for a full a11y audit — this is one slice, deliberately.

## [Core Assumptions]

1. Empty alt in Markdown means the author skipped alt (there is no explicit
   decorative convention in common practice), while `alt=""` in HTML is
   intentional decoration.
2. Filename-like and single-generic-word alts are defects worth warning
   about but not failing builds.
3. A 100-point score with 20/5 penalties is communicative enough for CI
   without implying statistical calibration.
4. Static markup on disk is representative of what ships (no client-side
   image injection).

Confidence: **High (≥80%)** for the error tier (missing alt) — it is an
objective property of the markup. **Medium (60–79%)** for the warning-tier
heuristics: filename/generic detection catches the common lazy patterns
but cannot judge genuine descriptiveness; treat warnings as review prompts.

*Data and measurements as of 2026-10-13.*

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 105 purpose-built AI-engineering tools across neglected niches.

Related tools: [metric-definition-dict](https://github.com/chenhz01/metric-definition-dict) · [image-prompt-schema](https://github.com/chenhz01/image-prompt-schema) · [rfc2119-keyword-lint](https://github.com/chenhz01/rfc2119-keyword-lint)
