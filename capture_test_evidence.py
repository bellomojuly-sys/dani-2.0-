"""Screenshots of the Dani 2.0 tests for the Notion page
"Dani 2.0 — Test inventory and critical review (November 2026)".

Each image is named after the screenshot box it goes into (A, B, C, D, E).
test_answer.py is left out of every run, so the totals match the page (299 tests, 18 files).

Usage, from the root of the dani-2.0- repository:

    pip install -r requirements-dev.txt pillow
    python capture_test_evidence.py                        # A, B, C  (no API calls)
    python capture_test_evidence.py --evals                # + E: live evaluation run (uses DEEPSEEK_API_KEY)
    python capture_test_evidence.py --mutation             # + D: mutation testing (slow, several minutes)
    python capture_test_evidence.py --evals --mutation     # everything

Output: docs/evidence/<YYYY-MM-DD>/  (PNG to paste in Notion + .txt with the full output).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EXCLUDED_TEST_FILE = "test_answer.py"
CORE_MODULES = ["tools", "agent", "skill", "tracing", "main"]
LINES_PER_IMAGE = 55
MAX_LINE_CHARS = 140
PADDING = 24
BG, FG, HEADER_FG = (30, 30, 36), (225, 225, 230), (150, 200, 255)
GREEN, RED = (120, 220, 140), (255, 120, 120)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",  # macOS
    "/System/Library/Fonts/SFNSMono.ttf",
    "C:/Windows/Fonts/consola.ttf",  # Windows
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  # Linux
]


def load_font(size: int = 15):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).rstrip()


def git(*args: str) -> str:
    code, out = run(["git", *args])
    return out.strip() if code == 0 else "unknown"


def line_colour(line: str):
    if re.search(r"\b(failed|error|FAIL|survived)\b", line, re.IGNORECASE) and not re.search(r"\b0 (failed|survived)\b", line):
        return RED
    if re.search(r"\b(passed|PASSED|PASS|killed|100%)\b", line):
        return GREEN
    return FG


def render_png(header: list[str], body: list[str], path: Path, font) -> None:
    lines = header + [""] + [line[:MAX_LINE_CHARS] for line in body]
    line_h = int(getattr(font, "size", 12) * 1.35)
    char_w = font.getlength("M") if hasattr(font, "getlength") else 8
    width = max(700, int(PADDING * 2 + char_w * max(len(line) for line in lines)))
    image = Image.new("RGB", (width, PADDING * 2 + line_h * len(lines)), BG)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        colour = HEADER_FG if i < len(header) else line_colour(line)
        draw.text((PADDING, PADDING + i * line_h), line, font=font, fill=colour)
    image.save(path)


def save(name: str, title: str, shown_cmd: str, code: int, output: str, out_dir: Path, meta: dict, font,
         last_lines: int | None = None) -> None:
    header = [
        f"Dani 2.0 — {title}",
        f"$ {shown_cmd}",
        f"{meta['date']} · branch {meta['branch']} · commit {meta['commit']} · exit code {code}",
    ]
    (out_dir / f"{name}.txt").write_text("\n".join(header) + "\n\n" + output + "\n")
    lines = output.splitlines() or ["(no output)"]
    if last_lines:
        lines = lines[-last_lines:]
    pages = [lines[i:i + LINES_PER_IMAGE] for i in range(0, len(lines), LINES_PER_IMAGE)]
    for n, page in enumerate(pages, start=1):
        suffix = f"-{n}of{len(pages)}" if len(pages) > 1 else ""
        render_png(header, page, out_dir / f"{name}{suffix}.png", font)
    print(f"  {name}: exit code {code}, {len(pages)} image(s)")


def capture(name: str, title: str, cmd: list[str], out_dir: Path, meta: dict, font, last_lines=None) -> int:
    code, output = run(cmd)
    shown = " ".join("python" if part == sys.executable else part for part in cmd)
    save(name, title, shown, code, output, out_dir, meta, font, last_lines)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Screenshots of the Dani 2.0 tests")
    parser.add_argument("--evals", action="store_true", help="screenshot E: live evaluation run (calls the model)")
    parser.add_argument("--mutation", action="store_true", help="screenshot D: mutation testing (slow)")
    args = parser.parse_args()

    if not Path("evals.py").exists() or not list(Path(".").glob("test_*.py")):
        print("Run this from the root of the dani-2.0- repository.")
        return 2

    meta = {
        "date": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "--short", "HEAD"),
    }
    out_dir = Path("docs/evidence") / dt.date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    font = load_font()
    py = sys.executable
    skip = ["--ignore", EXCLUDED_TEST_FILE, "-p", "no:cacheprovider"]
    print(f"Saving screenshots in {out_dir}/")

    status = capture("A-full-test-run", "full test run",
                     [py, "-m", "pytest", "-q", *skip], out_dir, meta, font, last_lines=12)
    capture("B-every-test-by-name", "every test by name",
            [py, "-m", "pytest", "-v", "--no-header", *skip], out_dir, meta, font)
    capture("C-core-coverage", "line and branch coverage of the core modules",
            [py, "-m", "pytest", "-q", *skip, *[f"--cov={m}" for m in CORE_MODULES],
             "--cov-branch", "--cov-report=term-missing"], out_dir, meta, font, last_lines=25)

    if args.mutation:
        # mutmut needs a fresh .coverage of the core and leaves a mutants/ folder behind.
        run([py, "-m", "pytest", "-q", *skip, *[f"--cov={m}" for m in CORE_MODULES]])
        code_run, out_run = run(["mutmut", "run"])
        code_res, out_res = run(["mutmut", "results"])
        summary = "\n".join(out_run.splitlines()[-15:]) + "\n\n$ mutmut results\n" + (out_res or "(no surviving mutants listed)")
        save("D-mutation-testing", "mutation testing of the core", "mutmut run && mutmut results",
             code_run or code_res, summary, out_dir, meta, font)
        shutil.rmtree("mutants", ignore_errors=True)  # otherwise pytest reports a collection clash

    if args.evals:
        capture("E-live-evaluation-run", "live evaluation run (five questions)",
                [py, "evals.py"], out_dir, meta, font)

    print("Done. Paste each PNG into the Notion box with the same letter (A, B, C, D, E).")
    return status


if __name__ == "__main__":
    sys.exit(main())
