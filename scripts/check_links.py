# -*- coding: utf-8 -*-
"""巡检 plugins/*.json 指向的仓库和入口文件是否还能访问。

失败时生成 link-report.md，由 workflow 开 issue 提醒。
"""

from __future__ import print_function

import io
import json
import os
import sys

try:
    from urllib.error import HTTPError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
except ImportError:  # Python 2
    from urllib2 import HTTPError, Request, urlopen
    from urllib import quote

API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = os.path.join(ROOT, "plugins")


def api(path):
    request = Request(API + path, headers={
        "Authorization": "Bearer %s" % TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "maya-node-plugin-index-link-check",
    })
    try:
        response = urlopen(request, timeout=30)
        try:
            return json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
    except HTTPError as exc:
        raise IOError("HTTP %s" % exc.code)
    except Exception as exc:
        raise IOError(str(exc))


def main():
    problems = []
    checked = 0

    for name in sorted(os.listdir(PLUGINS)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(PLUGINS, name)
        try:
            with io.open(path, "r", encoding="utf-8") as handle:
                item = json.load(handle)
        except Exception as exc:
            problems.append("- `%s`：JSON 读不出来（%s）" % (name, exc))
            continue

        repo = str(item.get("repo") or "")
        entry = str(item.get("entry") or "")
        subpath = str(item.get("subpath") or "").strip("/\\")
        branch = str(item.get("branch") or "main")
        if not repo:
            continue

        checked += 1
        try:
            info = api("/repos/%s" % repo)
        except Exception as exc:
            problems.append("- `%s`：仓库 `%s` 无法访问（%s）" % (name, repo, exc))
            continue
        if info.get("archived") or info.get("disabled"):
            problems.append("- `%s`：仓库 `%s` 已归档或禁用" % (name, repo))
            continue
        if item.get("asset"):
            continue
        if not entry:
            problems.append("- `%s`：缺少 entry" % name)
            continue
        entry_path = (subpath + "/" if subpath else "") + entry
        try:
            api("/repos/%s/contents/%s?ref=%s" % (
                repo, quote(entry_path, safe="/"), quote(branch, safe="")))
        except Exception as exc:
            problems.append("- `%s`：入口文件 `%s` 读不到（%s）" % (name, entry_path, exc))

    print("checked %d entries, %d problems" % (checked, len(problems)))
    if problems:
        text = ("## 插件来源检查失败\n\n" + "\n".join(problems) +
                "\n\n请作者更新仓库地址 / 分支，或由维护者下线对应条目。\n")
        with io.open("link-report.md", "w", encoding="utf-8") as handle:
            handle.write(text)
        print(text)
        sys.exit(1)
    print("all links ok")


if __name__ == "__main__":
    main()
