#!/usr/bin/env python3
"""Build both static download pages from one published DPN release."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "DeeperNetwork/dpn-app"
OFFICIAL = "https://downloads.deeper.network/DPN/release/"
MAC_ARCHES = {"arm-64": "mac_arm", "x86-64": "mac_intel"}
FORMATS = {"windows": "EXE", "mac_arm": "DMG", "mac_intel": "DMG", "linux": "DEB", "android": "APK"}
HREF = re.compile(r'(\bdata-download="([\w-]+)"\s+href=")[^"]*(")')
VERSION = re.compile(r'(<strong data-version="([\w-]+)">)[^<]*(</strong>)')


def published_downloads(release, raw):
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag):
        raise ValueError("Expected a published stable release")
    uploaded = {a["name"]: a for a in release["assets"]}
    if "sha256:" + hashlib.sha256(raw).hexdigest() != uploaded["download-manifest.json"]["digest"]:
        raise ValueError("Manifest differs from the published GitHub asset")
    manifest = json.loads(raw)
    if manifest["repository"] != REPOSITORY or manifest["tag"] != tag:
        raise ValueError("Manifest identifies a different release")

    downloads = {}
    for asset in manifest["assets"]:
        platform, arch = asset["platform"], asset["arch"]
        if platform == "mac":
            key = MAC_ARCHES.get(arch)
        elif platform in ("windows", "linux") and arch == "x86-64":
            key = platform
        elif platform == "android":
            key = platform
        else:
            continue
        if key is None:
            continue
        name, version = asset["fileName"], asset["version"]
        if (key in downloads or not re.fullmatch(r"DPN-[A-Za-z0-9.+_-]+", name)
                or not name.lower().endswith("." + FORMATS[key].lower())
                or not re.fullmatch(r"\d+(?:\.\d+)+(?:\+[A-Za-z0-9.-]+)?", version)
                or not name.startswith("DPN-" + version + "-")):
            raise ValueError(f"Unexpected installer for {key}: {name}")
        if asset["url"] not in (OFFICIAL + name, OFFICIAL + quote(name, safe="")):
            raise ValueError(f"Unexpected source for {name}")
        remote = uploaded.get(name, {})
        if (not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])
                or remote.get("digest") != "sha256:" + asset["sha256"]
                or not isinstance(asset["size"], int) or asset["size"] <= 0
                or remote.get("size") != asset["size"]):
            raise ValueError(f"Published size or digest mismatch for {name}")
        downloads[key] = {
            "github": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{quote(name, safe='')}",
            "official": asset["url"], "version": version, "size": asset["size"],
        }
    if downloads.keys() != FORMATS.keys():
        raise ValueError(f"Missing platform installers: {sorted(FORMATS.keys() - downloads.keys())}")
    return downloads


def replace_markers(html, pattern, values):
    unused = dict(values)

    def replace(match):
        key = match[2]
        if key not in unused:
            raise ValueError(f"Unexpected or duplicate page marker: {key}")
        return match[1] + escape(unused.pop(key), quote=True) + match[3]

    result = pattern.sub(replace, html)
    if unused:
        raise ValueError(f"Missing page markers: {sorted(unused)}")
    return result


def render(html, downloads, russian):
    links = {key: a["github"] for key, a in downloads.items()}
    versions = {}
    if russian:
        links["android-official"] = downloads["android"]["official"]
        versions = {key: f'{FORMATS[key]} · {a["version"]}' for key, a in downloads.items()}
    return replace_markers(replace_markers(html, HREF, links), VERSION, versions)


def probe(item):
    url, size = item
    req = Request(url, headers={"Range": "bytes=0-0", "User-Agent": "DPN-Pages-build"})
    with urlopen(req, timeout=30) as response:
        if response.status == 206:
            valid_size = response.headers.get("Content-Range") == f"bytes 0-0/{size}"
        else:
            valid_size = response.status == 200 and response.headers.get("Content-Length") == str(size)
        if not valid_size or len(response.read(1)) != 1:
            raise ValueError(f"Download returned an unexpected byte range or size: {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Directory for the deployable site")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("Choose an empty directory for the generated site")
    release = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPOSITORY}/releases/latest"]))
    manifest_url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == "download-manifest.json")
    with urlopen(manifest_url, timeout=30) as response:
        downloads = published_downloads(release, response.read())
    urls = {a["github"]: a["size"] for a in downloads.values()}
    urls[downloads["android"]["official"]] = downloads["android"]["size"]
    with ThreadPoolExecutor(max_workers=len(urls)) as workers:
        list(workers.map(probe, urls.items()))

    output.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "ru"):
        shutil.copytree(ROOT / directory, output / directory)
    shutil.copyfile(ROOT / ".nojekyll", output / ".nojekyll")
    revision = os.environ.get("GITHUB_SHA", "")
    for name in ("index.html", "ru/index.html"):
        html = render((ROOT / name).read_bytes().decode(), downloads, russian=name.startswith("ru/"))
        if revision:
            html += f"\n<!-- Site revision {revision} -->\n"
        (output / name).write_bytes(html.encode())
    print(f"Built both pages for {release['tag_name']}. Verified {len(urls)} download URLs.")


if __name__ == "__main__":
    main()
