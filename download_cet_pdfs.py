#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


USER_AGENT = "CodexDownloader"


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")


def log(message: str, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream)


def request_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_repo_tree(owner: str, repo: str, ref: str) -> list[dict]:
    commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{urllib.parse.quote(ref, safe='')}"
    commit = request_json(commit_url)
    tree_sha = commit["commit"]["tree"]["sha"]
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
    tree = request_json(tree_url)
    return tree["tree"]


def build_raw_url(owner: str, repo: str, ref: str, relative_path: str) -> str:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in relative_path.split("/"))
    return f"https://github.com/{owner}/{repo}/raw/{urllib.parse.quote(ref, safe='')}/{encoded}"


def is_valid_pdf(path: Path, min_bytes: int) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size < min_bytes:
        return False
    try:
        with path.open("rb") as fh:
            return fh.read(4) == b"%PDF"
    except OSError:
        return False


def should_keep(path: str, scope: str) -> bool:
    if not path.lower().endswith(".pdf"):
        return False
    if scope == "all":
        return True
    if scope == "cet6":
        return path.startswith("CET6_")
    if scope == "cet4":
        return path.startswith("CET4_")
    return False


def download_file(url: str, destination: Path, retries: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req) as resp, destination.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if destination.exists():
                destination.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(1.5 * attempt)
    assert last_error is not None
    raise last_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download PDF files from a GitHub repo via raw URLs, bypassing Git LFS pointer downloads."
    )
    parser.add_argument("--owner", default="YinsinSirius", help="GitHub owner/org")
    parser.add_argument("--repo", default="CET6-Resources", help="GitHub repository name")
    parser.add_argument("--ref", default="master", help="Branch, tag, or commit to use")
    parser.add_argument(
        "--output-dir",
        default=str(Path.cwd() / "CET6-Resources"),
        help="Target directory for downloaded files",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "cet6", "cet4"),
        default="all",
        help="Limit downloads to all PDFs, only CET6 PDFs, or only CET4 PDFs",
    )
    parser.add_argument("--force", action="store_true", help="Redownload even if a valid local PDF already exists")
    parser.add_argument("--min-valid-bytes", type=int, default=1024, help="Minimum size to treat a local file as valid")
    return parser.parse_args()


def main() -> int:
    configure_console_output()
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()

    log(f"Listing PDFs from {args.owner}/{args.repo} ({args.ref}) ...")
    try:
        tree_items = fetch_repo_tree(args.owner, args.repo, args.ref)
    except urllib.error.URLError as exc:
        log(f"Failed to query GitHub API: {exc}", error=True)
        return 1

    pdfs = sorted((item for item in tree_items if item.get("type") == "blob" and should_keep(item.get("path", ""), args.scope)), key=lambda x: x["path"])
    if not pdfs:
        log(f"No PDF files matched scope '{args.scope}'.", error=True)
        return 1

    downloaded = 0
    skipped = 0
    failed: list[tuple[str, str]] = []

    for index, item in enumerate(pdfs, start=1):
        relative_path = item["path"]
        destination = output_dir / relative_path

        if not args.force and is_valid_pdf(destination, args.min_valid_bytes):
            skipped += 1
            log(f"[{index}/{len(pdfs)}] Skip  {relative_path}")
            continue

        url = build_raw_url(args.owner, args.repo, args.ref, relative_path)
        try:
            download_file(url, destination)
            if not is_valid_pdf(destination, args.min_valid_bytes):
                raise ValueError("downloaded file is not a valid PDF")
            downloaded += 1
            log(f"[{index}/{len(pdfs)}] Done  {relative_path}")
        except Exception as exc:  # noqa: BLE001
            if destination.exists():
                destination.unlink(missing_ok=True)
            failed.append((relative_path, str(exc)))
            log(f"[{index}/{len(pdfs)}] Fail  {relative_path}", error=True)

    log("\nSummary")
    log(f"  Scope      : {args.scope}")
    log(f"  OutputDir  : {output_dir}")
    log(f"  Total      : {len(pdfs)}")
    log(f"  Downloaded : {downloaded}")
    log(f"  Skipped    : {skipped}")
    log(f"  Failed     : {len(failed)}")

    if failed:
        log("\nFailed items:", error=True)
        for path, error in failed[:20]:
            log(f"  {path} -> {error}", error=True)
        if len(failed) > 20:
            log(f"  ... and {len(failed) - 20} more", error=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
