#!/usr/bin/env python3
"""Update GitHub profile README with top 10 public release-asset download counts."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OWNER = "boyl"
START = "<!-- RELEASE_DOWNLOADS_START -->"
END = "<!-- RELEASE_DOWNLOADS_END -->"
TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "boyl-release-downloads", "X-GitHub-Api-Version": "2022-11-28"}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN

def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 3)
                continue
            raise

def pages(endpoint):
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        data = get(f"https://api.github.com{endpoint}{sep}per_page=100&page={page}")
        if not isinstance(data, list):
            raise RuntimeError("Unexpected GitHub API response")
        yield from data
        if len(data) < 100:
            break
        page += 1

def main():
    repos = list(pages(f"/users/{OWNER}/repos?type=owner&sort=updated"))
    stats = []
    for repo in repos:
        if repo.get("private") or repo.get("fork") or repo.get("archived"):
            continue
        name = repo["name"]
        total = 0
        releases = 0
        for release in pages(f"/repos/{OWNER}/{urllib.parse.quote(name)}/releases"):
            if release.get("draft"):
                continue
            assets = release.get("assets", [])
            total += sum(int(asset.get("download_count", 0)) for asset in assets)
            if assets:
                releases += 1
        if releases:
            stats.append((name, total, releases))
    stats.sort(key=lambda x: (-x[1], x[0].lower()))
    top = stats[:10]
    lines = [
        "| 排名 | 仓库 | 累计下载量 |",
        "| ---: | --- | ---: |",
    ]
    for rank, (name, count, _) in enumerate(top, 1):
        safe_name = name.replace("|", r"\|")
        lines.append(f"| {rank} | [{safe_name}](https://github.com/{OWNER}/{urllib.parse.quote(name)}) | {count:,} |")
    if not top:
        lines.append("| — | 暂无包含附件的 Releases | — |")
    lines.extend(["", f"共统计 {len(stats)} 个有 Release 附件的公开仓库；数据来源：GitHub REST API。"])
    path = Path("README.md")
    original = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    replacement = START + "\n\n" + "\n".join(lines) + "\n\n" + END
    updated, n = pattern.subn(lambda _: replacement, original, count=1)
    if n != 1:
        raise RuntimeError("Missing README markers")
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print("Updated ranking:", top)
    else:
        print("Ranking unchanged")

if __name__ == "__main__":
    main()
