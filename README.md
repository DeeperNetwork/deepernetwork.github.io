# DPN download pages

GitHub Actions publishes the English and Russian pages from the [latest DPN release](https://github.com/DeeperNetwork/dpn-app/releases/latest). The release mirror checks the official catalog at 00:17, 06:17, 12:17 and 18:17 UTC. The site checks the published manifest 30 minutes later. A push to `main` or a manual **Sync DPN download pages** run also builds and deploys the site.

The checked-in HTML provides working links for local previews. At build time, `data-download` marks the links to replace and `data-version` marks the Russian version labels. The Android button on the Russian page uses the official APK and the backup uses the matching GitHub asset. The build validates the published digests, file sizes and download URLs before deploying both pages as one artifact.

To build into an empty directory locally, use Python 3.9 or later and an authenticated GitHub CLI.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_download_pages.py /tmp/dpn-pages
```
