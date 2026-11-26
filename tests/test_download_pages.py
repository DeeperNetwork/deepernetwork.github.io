import hashlib
import json
import re
import unittest
from urllib.parse import quote

from scripts.build_download_pages import FORMATS, OFFICIAL, REPOSITORY, ROOT, published_downloads, render


def fixture():
    builds = [
        ("windows", "x86-64", "windows-x86-64.exe"),
        ("mac", "arm-64", "macos-arm-64.dmg"),
        ("mac", "x86-64", "macos-x86-64.dmg"),
        ("linux", "x86-64", "linux-x86-64.deb"),
        ("android", "", "android.apk"),
    ]
    assets = []
    uploaded = []
    for index, (platform, arch, suffix) in enumerate(builds):
        version = f"5.1.{index}+abcdef"
        name = f"DPN-{version}-{suffix}"
        assets.append(dict(platform=platform, arch=arch, version=version, fileName=name,
                           url=OFFICIAL + quote(name), size=42, sha256="a" * 64))
        uploaded.append(dict(name=name, size=42, digest="sha256:" + "a" * 64))
    raw = json.dumps(dict(repository=REPOSITORY, tag="downloads-test", assets=assets)).encode()
    uploaded.append(dict(name="download-manifest.json", digest="sha256:" + hashlib.sha256(raw).hexdigest()))
    return dict(tag_name="downloads-test", draft=False, prerelease=False, assets=uploaded), raw


class DownloadPagesTests(unittest.TestCase):
    def test_new_release_updates_only_managed_links_and_versions(self):
        downloads = published_downloads(*fixture())
        for path, russian in [("index.html", False), ("ru/index.html", True)]:
            old = (ROOT / path).read_bytes().decode()
            new = render(old, downloads, russian=russian)
            self.assertEqual(new, render(new, downloads, russian=russian))
            for key, asset in downloads.items():
                self.assertIn(f'data-download="{key}" href="{asset["github"]}"', new)
                if russian:
                    self.assertIn(f'{FORMATS[key]} · {asset["version"]}</strong>', new)
            if russian:
                self.assertIn(f'data-download="android-official" href="{downloads["android"]["official"]}"', new)
            preserved = r'<a\b[^>]*href="(?:https://(?:storage\.yandexcloud\.net|testflight\.apple\.com|apps\.apple\.com)/|#iphone-guide)[^"]*"[^>]*>[^<]*'
            self.assertEqual(re.findall(preserved, new), re.findall(preserved, old))

    def test_missing_or_duplicate_markers_fail(self):
        downloads = published_downloads(*fixture())
        en = (ROOT / "index.html").read_text()
        with self.assertRaises(ValueError):
            render(en.replace('data-download="linux"', 'data-download="windows"'), downloads, False)
        with self.assertRaises(ValueError):
            render(en.replace('data-download="linux"', 'data-unmanaged="linux"'), downloads, False)

    def test_incomplete_or_corrupted_release_is_rejected(self):
        for kind in ("missing", "digest", "manifest", "draft"):
            release, raw = fixture()
            if kind == "missing":
                release["assets"].pop(0)
            elif kind == "digest":
                release["assets"][0]["digest"] = "sha256:" + "b" * 64
            elif kind == "manifest":
                raw += b" "
            else:
                release["draft"] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                published_downloads(release, raw)
