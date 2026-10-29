# -*- coding: utf-8 -*-
"""Validate a plugin-metadata PR for auto-merge.

Runs from the base branch under pull_request_target. It never checks out or
executes PR code: only the changed JSON is read through the GitHub API.

Exit 0 -> workflow may squash-merge the PR.
Exit 1 -> workflow comments validation.md and leaves the PR open.
"""

from __future__ import print_function

import ast
import base64
import io
import json
import os
import re
import sys

try:
    from urllib.error import HTTPError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
except ImportError:  # Python 2
    from urllib2 import HTTPError, Request, urlopen
    from urllib import quote

API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PR_NUMBER = os.environ.get("PR_NUMBER", "")
BASE_REF = os.environ.get("BASE_REF", "main")

MAX_FILES = 3
INDEX_REPO = REPOSITORY.lower()
ALLOWED_PATH = re.compile(r"^plugins/(0x[0-9A-Fa-f]{1,8})\.json$", re.I)
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NODE_ID_RE = re.compile(r"^0x[0-9A-Fa-f]{1,8}$")
REQUIRED = ("name", "author", "node_id", "node_name", "repo", "entry", "version")


class ApiError(Exception):
    pass


def api(path):
    url = path if path.startswith("http") else API + path
    request = Request(url, headers={
        "Authorization": "Bearer %s" % TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "maya-node-plugin-index-validator",
    })
    try:
        response = urlopen(request, timeout=30)
        try:
            return json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise ApiError("GitHub API HTTP %s：%s" % (exc.code, detail[:300]))
    except Exception as exc:
        raise ApiError("GitHub API 请求失败：%s" % exc)


def read_payload(url, label):
    payload = api(url)
    if not isinstance(payload, dict):
        raise ApiError("%s 不是文件内容" % label)
    content = payload.get("content")
    if not content or payload.get("encoding") != "base64":
        raise ApiError("%s 文件过大或无法读取" % label)
    try:
        return base64.b64decode(content).decode("utf-8-sig")
    except Exception as exc:
        raise ApiError("%s 不是 UTF-8 JSON：%s" % (label, exc))


def read_text_payload(url, label):
    payload = api(url)
    if not isinstance(payload, dict):
        raise ApiError("%s 不是文件内容" % label)
    content = payload.get("content")
    if not content or payload.get("encoding") != "base64":
        raise ApiError("%s 文件过大或无法读取" % label)
    raw = base64.b64decode(content)
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    raise ApiError("%s 不是 UTF-8/GBK 文本" % label)


def read_node_info(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    for statement in getattr(tree, "body", []):
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and target.id == "NODE_INFO":
                try:
                    value = ast.literal_eval(statement.value)
                except Exception:
                    return {}
                return value if isinstance(value, dict) else {}
    return {}


def read_base_json(path):
    url = "%s/repos/%s/contents/%s?ref=%s" % (
        API, REPOSITORY, quote(path, safe="/"), quote(BASE_REF, safe=""))
    return json.loads(read_payload(url, path))


def node_value(value):
    text = str(value or "").strip()
    if not NODE_ID_RE.match(text):
        raise ValueError("node_id 必须是 0x 开头的十六进制序号")
    return int(text, 16)


def fail(errors):
    lines = ["## 自动合并未通过", ""]
    for error in errors:
        lines.append("- " + error)
    lines.append("")
    lines.append("这个 PR 没有自动合并。修正后重新提交即可；涉及 `packages/`、"
                 "`.github/`、`scripts/` 或其它文件的 PR 需要人工审核。")
    text = "\n".join(lines) + "\n"
    with io.open("validation.md", "w", encoding="utf-8") as handle:
        handle.write(text)
    print(text)
    sys.exit(1)


def main():
    if not (REPOSITORY and TOKEN and PR_NUMBER):
        fail(["缺少 GITHUB_REPOSITORY / GITHUB_TOKEN / PR_NUMBER 环境变量"])

    pr = api("/repos/%s/pulls/%s" % (REPOSITORY, PR_NUMBER))
    if pr.get("draft"):
        fail(["草稿 PR 不参与自动合并"])
    if not pr.get("head", {}).get("repo"):
        fail(["PR 的 head 仓库不存在，无法读取提交内容"])

    base_ref = pr.get("base", {}).get("ref") or BASE_REF
    author = (pr.get("user") or {}).get("login") or ""
    author_key = author.lower()

    catalog = read_base_json("catalog.json")
    categories = read_base_json("categories.json")
    base_plugins = catalog.get("plugins") or []
    base_by_id = {}
    base_path_by_id = {}
    for item in base_plugins:
        try:
            value = node_value(item.get("node_id"))
        except Exception:
            continue
        base_by_id[value] = item
        base_path_by_id[value] = "plugins/%s.json" % str(item.get("node_id")).lower()

    # catalog.json 可能比分支晚一拍，插件文件名是更直接的占用检查。
    plugin_dir = api("/repos/%s/contents/plugins?ref=%s" % (
        REPOSITORY, quote(base_ref, safe="")))
    base_files_by_id = {}
    if isinstance(plugin_dir, list):
        for item in plugin_dir:
            name = item.get("name") or ""
            match = ALLOWED_PATH.match("plugins/" + name)
            if item.get("type") == "file" and match:
                base_files_by_id[int(match.group(1), 16)] = "plugins/" + name

    files = api("/repos/%s/pulls/%s/files?per_page=100" % (REPOSITORY, PR_NUMBER))
    if not isinstance(files, list) or not files:
        fail(["PR 没有文件变更"])
    if len(files) > MAX_FILES:
        fail(["一个 PR 最多修改 %d 个插件条目" % MAX_FILES])

    errors = []
    accepted = []
    seen_ids = set()

    for item in files:
        filename = item.get("filename") or ""
        status = item.get("status") or ""
        if status not in ("added", "modified"):
            errors.append("%s：只允许新增或修改 JSON，不允许 %s" % (filename, status))
            continue
        match = ALLOWED_PATH.match(filename)
        if not match:
            errors.append("%s：自动合并只允许修改 plugins/<node_id>.json" % filename)
            continue
        path_id = int(match.group(1), 16)
        contents_url = item.get("contents_url")
        if not contents_url:
            errors.append("%s：无法读取 PR 文件内容" % filename)
            continue
        try:
            data = json.loads(read_payload(contents_url, filename))
        except Exception as exc:
            errors.append("%s：JSON 解析失败（%s）" % (filename, exc))
            continue
        if not isinstance(data, dict):
            errors.append("%s：条目必须是 JSON 对象" % filename)
            continue

        missing = [key for key in REQUIRED if not data.get(key)]
        if missing:
            errors.append("%s：缺少字段 %s" % (filename, ", ".join(missing)))
            continue
        try:
            value = node_value(data.get("node_id"))
        except Exception as exc:
            errors.append("%s：%s" % (filename, exc))
            continue
        if value != path_id:
            errors.append("%s：文件名和 node_id 不一致" % filename)
            continue
        if value in seen_ids:
            errors.append("%s：同一个 PR 里 node_id 重复" % filename)
            continue
        seen_ids.add(value)

        if value in base_path_by_id and base_path_by_id[value].lower() != filename.lower():
            errors.append("%s：node_id 已被 plugins/%s 占用" % (
                filename, os.path.basename(base_path_by_id[value])))
            continue
        if value in base_files_by_id and base_files_by_id[value].lower() != filename.lower():
            errors.append("%s：node_id 已被 %s 占用" % (filename, base_files_by_id[value]))
            continue

        repo = str(data.get("repo") or "")
        if not REPO_RE.match(repo):
            errors.append("%s：repo 必须是 owner/name" % filename)
            continue
        if repo.lower() == INDEX_REPO:
            errors.append("%s：自动合并不接受索引仓库自托管，请填作者自己的仓库" % filename)
            continue
        repo_owner = repo.split("/")[0].lower()
        if repo_owner != author_key:
            errors.append("%s：repo owner 必须和 PR 作者（%s）一致" % (filename, author))
            continue
        try:
            repo_info = api("/repos/%s" % repo)
        except Exception as exc:
            errors.append("%s：仓库无法访问（%s）" % (filename, exc))
            continue
        if repo_info.get("private"):
            errors.append("%s：仓库必须是公开仓库" % filename)
            continue
        if repo_info.get("archived") or repo_info.get("disabled"):
            errors.append("%s：仓库已归档或禁用" % filename)
            continue

        category = data.get("category")
        if category not in categories:
            errors.append("%s：category 必须是 categories.json 里的 id" % filename)
            continue
        if not str(data.get("entry")).lower().endswith(".py"):
            errors.append("%s：entry 必须是 .py 文件" % filename)
            continue
        entry = str(data.get("entry")).replace("\\", "/")
        if "/../" in ("/" + entry) or entry.startswith("/"):
            errors.append("%s：entry 路径不合法" % filename)
            continue
        subpath = str(data.get("subpath") or "").replace("\\", "/").strip("/")
        if "/../" in ("/" + subpath) or subpath.startswith("/"):
            errors.append("%s：subpath 路径不合法" % filename)
            continue
        asset = str(data.get("asset") or "")
        if asset and not (asset.startswith("https://github.com/")
                          or asset.startswith("https://objects.githubusercontent.com/")):
            errors.append("%s：asset 必须指向 GitHub Release 文件" % filename)
            continue
        tags = data.get("tags") or []
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            errors.append("%s：tags 必须是字符串数组" % filename)
            continue
        if len(tags) > 10 or any(len(tag) > 30 for tag in tags):
            errors.append("%s：tags 最多 10 个，每个不超过 30 字" % filename)
            continue
        updated = str(data.get("updated") or "")
        if updated and not re.match(r"^\d{4}-\d{2}-\d{2}$", updated):
            errors.append("%s：updated 必须是 YYYY-MM-DD" % filename)
            continue
        digest = str(data.get("sha256") or "")
        if digest and not re.match(r"^[0-9a-fA-F]{64}$", digest):
            errors.append("%s：sha256 必须是 64 位十六进制" % filename)
            continue
        versions = data.get("maya_versions") or []
        if not isinstance(versions, list):
            errors.append("%s：maya_versions 必须是数组" % filename)
            continue
        if len(str(data.get("name"))) > 60 or len(str(data.get("version"))) > 32:
            errors.append("%s：name/version 太长" % filename)
            continue

        # 外部仓库条目：直接读作者仓库里的入口文件，校验 NODE_INFO。
        # asset 条目在安装时校验，这里只校验 GitHub Release 地址。
        if not asset:
            try:
                branch = str(data.get("branch") or repo_info.get("default_branch") or "main")
                entry_path = (subpath + "/" if subpath else "") + entry
                url = "%s/repos/%s/contents/%s?ref=%s" % (
                    API, repo, quote(entry_path, safe="/"), quote(branch, safe=""))
                source = read_text_payload(url, entry_path)
                info = read_node_info(source)
            except Exception as exc:
                errors.append("%s：无法读取入口文件（%s）" % (filename, exc))
                continue
            if not info:
                errors.append("%s：入口文件没有 NODE_INFO" % filename)
                continue
            info_id = info.get("node_id") or info.get("id")
            try:
                if info_id is None or node_value(info_id) != value:
                    errors.append("%s：NODE_INFO.node_id 与条目不一致" % filename)
                    continue
            except Exception:
                errors.append("%s：NODE_INFO.node_id 格式不正确" % filename)
                continue
            info_node = info.get("node") or info.get("node_name")
            if not info_node or str(info_node) != str(data.get("node_name")):
                errors.append("%s：NODE_INFO.node 与 node_name 不一致" % filename)
                continue
            if str(info.get("version") or "") != str(data.get("version")):
                errors.append("%s：NODE_INFO.version 与条目 version 不一致" % filename)
                continue

        accepted.append((filename, data))

    if errors:
        fail(errors)

    lines = ["## 自动校验通过", ""]
    lines.append("这个 PR 只修改插件元数据，且通过节点序号、作者仓库、分类和路径检查，准备自动合并：")
    lines.append("")
    for filename, data in accepted:
        lines.append("- `%s` · %s · v%s · %s" % (
            filename, data.get("name"), data.get("version"), data.get("repo")))
    lines.append("")
    lines.append("合并后 `build-catalog` 会自动重建 `catalog.json`。")
    text = "\n".join(lines) + "\n"
    with io.open("validation.md", "w", encoding="utf-8") as handle:
        handle.write(text)
    print(text)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(["校验器异常：%s" % exc])
