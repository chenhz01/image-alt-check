# -*- coding: utf-8 -*-
"""self_test for image-alt-check — inherits v2 template four defenses."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

import image_alt_check as mod

TMP = tempfile.mkdtemp(prefix="iac_selftest_")
_n = [0]


def write_file(text, ext=".md"):
    _n[0] += 1
    path = os.path.join(TMP, "doc_%d%s" % (_n[0], ext))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def run_cli(argv):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            code = mod.main(argv) or 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


class TestAFunctional(unittest.TestCase):
    def test_md_missing_alt_error(self):
        p = write_file("![](pic.png)\n")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 1)
        self.assertIn("missing-alt", out)

    def test_md_decorative_empty_alt_is_missing(self):
        # markdown has no absent-attribute state; empty alt = skipped alt = error
        p = write_file("![](pic.png)\n")
        _, out, _ = run_cli([p, "--format", "json"])
        rep = json.loads(out)
        self.assertEqual(rep["files"][0]["findings"][0]["kind"], "missing-alt")

    def test_md_filename_alt_warns(self):
        p = write_file("![diagram.png](assets/diagram.png)\n")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("filename-alt", out)

    def test_md_generic_alt_warns(self):
        p = write_file("![image](assets/foo.png)\n")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("generic-alt", out)

    def test_md_descriptive_passes(self):
        p = write_file("![Team standup in the Berlin office](standup.jpg)\n")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("score=100", out)

    def test_html_img_missing_alt(self):
        p = write_file('<html><img src="a.png"></html>', ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 1)
        self.assertIn("missing-alt", out)

    def test_html_img_empty_alt_decorative(self):
        p = write_file('<img src="divider.png" alt="">', ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["files"][0]["findings"][0]["kind"], "decorative")

    def test_html_img_whitespace_alt_is_decorative(self):
        p = write_file('<img src="divider.png" alt="   ">', ".html")
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["files"][0]["findings"][0]["kind"], "decorative")

    def test_html_img_filename_alt(self):
        p = write_file('<img src="img/logo.png" alt="logo.png">', ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("filename-alt", out)

    def test_html_img_generic_alt(self):
        p = write_file('<img src="x.jpg" alt="Photo">', ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("generic-alt", out)

    def test_html_img_descriptive_pass(self):
        p = write_file('<img src="chart.png" alt="Revenue by quarter, 2025">', ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("score=100", out)

    def test_score_penalties(self):
        p = write_file('<img src="a.png"><img src="b.png" alt="photo"><img src="c.png" alt="ok thing">',
                       ".html")
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["summary"]["score"], 75)  # -20 error -5 warn

    def test_strict_fails_on_warning(self):
        p = write_file("![image](x.png)\n")
        code, _, _ = run_cli([p, "--strict"])
        self.assertEqual(code, 1)

    def test_strict_zero_on_clean(self):
        p = write_file("![A real description](x.png)\n")
        code, _, _ = run_cli([p, "--strict"])
        self.assertEqual(code, 0)

    def test_multiple_files_aggregated(self):
        p1 = write_file("![good desc](a.png)\n")
        p2 = write_file("![](b.png)\n")
        code, out, _ = run_cli([p1, p2, "--format", "json"])
        rep = json.loads(out)
        self.assertEqual(rep["summary"]["files"], 2)
        self.assertEqual(rep["summary"]["errors"], 1)

    def test_md_embedded_img_tag(self):
        p = write_file('text <img src="z.png"> more\n')
        code, out, _ = run_cli([p])
        self.assertEqual(code, 1)
        self.assertIn("missing-alt", out)

    def test_line_numbers_reported(self):
        p = write_file("line1\n\n![](x.png)\n")
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["files"][0]["findings"][0]["line"], 3)

    def test_verdict_fail_word(self):
        p = write_file("![](x.png)\n")
        _, out, _ = run_cli([p])
        self.assertIn("verdict: FAIL", out)

    def test_verdict_clean_word(self):
        p = write_file("![nice chart of latency](x.png)\n")
        _, out, _ = run_cli([p])
        self.assertIn("all images have alt text", out)

    def test_markdown_multiple_images(self):
        p = write_file("![a](1.png)\n![b](2.png)\n![](3.png)\n")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 1)

    def test_classify_filename_vs_generic(self):
        self.assertEqual(mod.classify("photo.png", "photo.png")[0], "filename-alt")
        self.assertEqual(mod.classify("photo", "photo.png")[0], "generic-alt")

    def test_classify_none_is_missing(self):
        self.assertEqual(mod.classify(None, "x.png")[0], "missing-alt")

    def test_classify_case_insensitive_generic(self):
        self.assertEqual(mod.classify("IMAGE", "x.png")[0], "generic-alt")


class TestBErrors(unittest.TestCase):
    def test_missing_file_exit2(self):
        code, _, err = run_cli([os.path.join(TMP, "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_unsupported_extension(self):
        p = os.path.join(TMP, "data.txt")
        open(p, "w", encoding="utf-8", newline="").write("hello")
        code, _, err = run_cli([p])
        self.assertEqual(code, 2)
        self.assertIn("unsupported", err)

    def test_no_files_exit2(self):
        self.assertEqual(run_cli([])[0], 2)

    def test_directory_input_exit2(self):
        self.assertEqual(run_cli([TMP])[0], 2)

    def test_unknown_format_exit2(self):
        p = write_file("![a](b.png)\n")
        self.assertEqual(run_cli([p, "--format", "csv"])[0], 2)

    def test_html_error_does_not_crash(self):
        p = write_file('<img src="a.png" alt="<b>weird</b>', ".html")
        code, _, _ = run_cli([p])
        self.assertIn(code, (0, 1))

    def test_markdown_extension_variant(self):
        p = write_file("![](x.png)\n", ".markdown")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 1)

    def test_summary_counts_match_findings(self):
        p = write_file("![a](1.png)\n![](2.png)\n![image](3.png)\n")
        _, out, _ = run_cli([p, "--format", "json"])
        rep = json.loads(out)
        self.assertEqual(rep["summary"]["images"], 3)
        self.assertEqual(rep["summary"]["errors"] + rep["summary"]["warnings"] + 1,
                         3)  # 1 error + 1 warn + 1 pass

    def test_file_score_in_text(self):
        p = write_file("![](x.png)\n")
        _, out, _ = run_cli([p])
        self.assertIn("score=80", out)


class TestCEdge(unittest.TestCase):
    def test_unicode_alt(self):
        p = write_file("![\u56e2\u961f\u7ad9\u4f1a\u7167\u7247](team.png)\n")
        code, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("\u56e2\u961f", out)

    def test_empty_file(self):
        p = write_file("", ".html")
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        self.assertIn("0 images", out)

    def test_very_long_alt(self):
        p = write_file("![%s](x.png)\n" % ("d" * 100000))
        code, _, _ = run_cli([p])
        self.assertEqual(code, 0)

    def test_bom_file(self):
        _n[0] += 1
        p = os.path.join(TMP, "bom_%d.md" % _n[0])
        with open(p, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("![](x.png)\n")
        self.assertEqual(run_cli([p])[0], 1)

    def test_crlf_file(self):
        p = write_file("a\r\n\r\n![](x.png)\r\n")
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["files"][0]["findings"][0]["line"], 3)

    def test_many_images(self):
        p = write_file("".join("![desc %d](i%d.png)\n" % (i, i) for i in range(300)))
        code, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["summary"]["images"], 300)
        self.assertEqual(code, 0)

    def test_img_uppercase_tag(self):
        p = write_file('<IMG SRC="a.png">', ".html")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 1)

    def test_alt_with_quotes(self):
        p = write_file('<img src="a.png" alt=\'A "quoted" phrase\'>', ".html")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 0)

    def test_data_uri_src(self):
        p = write_file('<img src="data:image/png;base64,AAAA" alt="inline pixel">',
                       ".html")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 0)

    def test_nested_markdown_link_image(self):
        p = write_file("[![Build status](badge.svg)](https://example.invalid)\n")
        code, out, _ = run_cli([p, "--format", "json"])
        rep = json.loads(out)
        # inner image alt "Build status" is descriptive; no error
        self.assertEqual(code, 0)
        self.assertEqual(rep["files"][0]["findings"][0]["kind"], "pass")

    def test_score_floor_zero(self):
        p = write_file("".join("![](x%d.png)\n" % i for i in range(10)))
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["summary"]["score"], 0)


CASES = [
    (mod.classify("A graph of monthly revenue", "rev.png"), "pass"),
    (mod.classify("", "rev.png"), "decorative"),
    (mod.classify("  ", "rev.png"), "decorative"),
    (mod.classify(None, "rev.png"), "missing-alt"),
    (mod.classify("rev.png", "img/rev.png"), "filename-alt"),
    (mod.classify("photo.jpg", "other.jpg"), "filename-alt"),
    (mod.classify("screenshot", "x.png"), "generic-alt"),
    (mod.classify("Diagram", "x.png"), "generic-alt"),
    (mod.classify("icon", "x.svg"), "generic-alt"),
    (mod.classify("Chart of latency by region", "chart.png"), "pass"),
    (mod.classify("IMG_2041", "IMG_2041.jpg"), "pass"),  # no ext in alt, src differs
    (mod.classify("graph.png", ""), "filename-alt"),     # no src, alt has ext
    (mod.classify("Pic", "x.png"), "generic-alt"),
    (mod.classify("a photo of the team", "x.png"), "pass"),  # sentence, not single word
    (mod.classify("FIG", "x.png"), "generic-alt"),
    (mod.classify("banner", "x.svg"), "generic-alt"),
    (mod.classify("\u56e2\u961f\u7ad9\u4f1a", "team.png"), "pass"),
]


def _mk(case):
    got, want = case

    def test(self):
        self.assertEqual(got[0], want)
    return test


for _i, _c in enumerate(CASES):
    setattr(TestCEdge, "test_table_%02d" % _i, _mk(_c))


class TestDMore(unittest.TestCase):
    def test_html_multiple_missing_all_counted(self):
        p = write_file('<img src="a.png"><img src="b.png"><img src="c.png">', ".html")
        _, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["summary"]["errors"], 3)

    def test_mixed_md_and_html_args(self):
        p1 = write_file("![good alt](a.png)\n")
        p2 = write_file('<img src="b.png">', ".html")
        code, out, _ = run_cli([p1, p2, "--format", "json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["summary"]["files"], 2)

    def test_generic_word_case_sensitive_files(self):
        p = write_file("![Screenshot](a.png)\n")
        code, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(json.loads(out)["files"][0]["findings"][0]["kind"], "generic-alt")

    def test_score_all_decorative_full(self):
        p = write_file('<img alt="" src="d1.png"><img alt="" src="d2.png">', ".html")
        code, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual((code, json.loads(out)["summary"]["score"]), (0, 100))

    def test_warnings_only_exit_zero_without_strict(self):
        p = write_file("![image](a.png)\n![photo](b.png)\n")
        code, _, _ = run_cli([p])
        self.assertEqual(code, 0)

    def test_two_warnings_strict_fail(self):
        p = write_file("![image](a.png)\n![photo](b.png)\n")
        code, _, _ = run_cli([p, "--strict"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    print("SUMMARY: PASS %d/%d" % (total - fails, total))
    sys.exit(0 if fails == 0 else 1)
