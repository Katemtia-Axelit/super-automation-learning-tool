# -*- coding: utf-8 -*-
from pathlib import Path
from collections import Counter
import hashlib
from PIL import Image

ROOT = Path(r"D:\Axelit\工作\trae\超级自动化学习工具")
IMG_ROOT = ROOT / "src" / "notes" / "vault" / "extracted_pics"
REPORT = ROOT / "data" / "image_filter_report.md"

MIN_FILE_SIZE = 5000
MIN_DIM = 80
MAX_CORNER_RATIO = 0.18
MAX_ASPECT_RATIO = 6.0


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def image_info(path: Path):
    try:
        with Image.open(path) as img:
            w, h = img.size
            return w, h
    except Exception:
        return None, None


def classify(path: Path, dup_counts: Counter):
    size = path.stat().st_size
    dims = image_info(path)
    if dims == (None, None):
        return 'bad_file'
    w, h = dims
    short_edge = min(w, h)
    long_edge = max(w, h)
    aspect_ratio = long_edge / max(short_edge, 1)

    reasons = []
    if size < MIN_FILE_SIZE:
        reasons.append('small_file')
    if short_edge < MIN_DIM:
        reasons.append('small_dim')
    if aspect_ratio > MAX_ASPECT_RATIO:
        reasons.append('odd_ratio')

    corner_like = False
    if w and h:
        if w < 220 and h < 220:
            corner_like = True
        elif w < 320 and h < 180:
            corner_like = True
    if corner_like:
        reasons.append('corner_like')

    digest = sha1(path)
    if dup_counts[digest] >= 4:
        reasons.append('high_duplicate')

    keep = not reasons
    return 'keep' if keep else ','.join(reasons)


def main():
    files = sorted(IMG_ROOT.rglob('*.png'))
    digest_map = Counter(sha1(p) for p in files if p.is_file())
    rows = []
    kept = 0
    removed = 0
    for path in files:
        verdict = classify(path, digest_map)
        rows.append((path, verdict, path.stat().st_size, image_info(path)))
        if verdict == 'keep':
            kept += 1
        else:
            removed += 1

    lines = [
        '# Image Filter Report',
        '',
        f'- total: {len(rows)}',
        f'- keep: {kept}',
        f'- flagged: {removed}',
        '',
        '## Flagged files',
        ''
    ]
    for path, verdict, size, dims in rows:
        if verdict == 'keep':
            continue
        lines.append(f'- `{path.relative_to(ROOT)}` | {size} bytes | {dims} | {verdict}')

    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(f'Wrote report: {REPORT}')


if __name__ == '__main__':
    main()
