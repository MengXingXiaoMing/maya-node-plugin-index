# -*- coding: utf-8 -*-
"""Build catalog.json from plugins/*.json.

Runs in CI on every push under plugins/ and locally with:

    python scripts/build_catalog.py

No third-party dependencies: the index stays editable on any machine.
"""

from __future__ import print_function

import ast
import datetime
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(ROOT, "plugins")
CATEGORIES_PATH = os.path.join(ROOT, "categories.json")
CATALOG_PATH = os.path.join(ROOT, "catalog.json")

NODE_ID_RE = re.compile(r"^0x[0-9A-Fa-f]{1,8}$")
REQUIRED = ("name", "node_id", "node_name", "repo", "entry", "version")
INDEX_REPO = "MengXingXiaoMing/maya-node-plugin-index"


def read_json(path):
    with io.open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def node_id_value(text):
    return int(text, 16) if str(text).lower().startswith("0x") else int(text)


def read_node_info(entry_path):
    """Read NODE_INFO from the plugin without importing Maya."""
    try:
        with io.open(entry_path, "r", encoding="utf-8-sig") as handle:
            source = handle.read()
    except UnicodeDecodeError:
        with io.open(entry_path, "r", encoding="gbk") as handle:
            source = handle.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "NODE_INFO":
                    try:
                        value = ast.literal_eval(stmt.value)
                    except Exception:
                        return {}
                    return value if isinstance(value, dict) else {}
    return {}


def main():
    categories = read_json(CATEGORIES_PATH)
    plugins = []
    errors = []
    seen_ids = {}

    for path in sorted(glob.glob(os.path.join(PLUGINS_DIR, "*.json"))):
        try:
            item = read_json(path)
        except Exception as exc:
            errors.append("%s: %s" % (os.path.basename(path), exc))
            continue

        missing = [key for key in REQUIRED if not item.get(key)]
        if missing:
            errors.append("%s: missing %s" % (os.path.basename(path), ", ".join(missing)))
            continue
        if not NODE_ID_RE.match(str(item["node_id"])):
            errors.append("%s: node_id must look like 0x00141488" % os.path.basename(path))
            continue
        if item.get("category") not in categories:
            errors.append("%s: unknown category %s" % (os.path.basename(path), item.get("category")))
            continue

        node_value = node_id_value(item["node_id"])
        if node_value in seen_ids:
            errors.append("%s: node_id %s already used by %s" % (
                os.path.basename(path), item["node_id"], seen_ids[node_value]))
            continue
        seen_ids[node_value] = os.path.basename(path)

        subpath = str(item.get("subpath") or "").strip("/\\")
        index_hosted = str(item.get("repo", "")).lower() == INDEX_REPO.lower()

        # 索引托管的包做完整本地校验；作者自己仓库的条目只校验元数据，
        # 安装时由市场下载作者仓库并解析 NODE_INFO。
        if index_hosted:
            if not subpath:
                errors.append("%s: index-hosted entries need subpath" % os.path.basename(path))
                continue
            package_dir = os.path.join(ROOT, subpath)
            entry_path = os.path.join(package_dir, item["entry"])
            if not os.path.isdir(package_dir):
                errors.append("%s: package folder missing: %s" % (os.path.basename(path), subpath))
                continue
            if not os.path.isfile(entry_path):
                errors.append("%s: entry file missing: %s" % (os.path.basename(path), item["entry"]))
                continue
            if os.path.basename(package_dir).lower() != str(item["node_id"]).lower():
                errors.append("%s: package folder must be named after node_id" % os.path.basename(path))
                continue

            info = read_node_info(entry_path)
            if info:
                info_id = info.get("node_id") or info.get("id")
                if info_id and node_id_value(info_id) != node_value:
                    errors.append("%s: NODE_INFO.node_id does not match catalog node_id" % os.path.basename(path))
                    continue
                if info.get("node") and info.get("node") != item["node_name"]:
                    errors.append("%s: NODE_INFO.node does not match node_name" % os.path.basename(path))
                    continue
                if info.get("version") and str(info.get("version")) != str(item["version"]):
                    print("warning: %s: NODE_INFO.version %s != catalog version %s" % (
                        os.path.basename(path), info.get("version"), item["version"]))

        item["subpath"] = subpath
        item["github"] = "https://github.com/%s" % item["repo"]
        item["maya_versions"] = item.get("maya_versions") or []
        item["tags"] = item.get("tags") or []
        plugins.append(item)

    if errors:
        for error in errors:
            print("ERROR:", error)
        sys.exit(1)

    plugins.sort(key=lambda item: (item.get("category", ""), item.get("name", "").lower()))
    catalog = {
        "name": "maya-node-plugin-index",
        "url": "https://github.com/MengXingXiaoMing/maya-node-plugin-index",
        "source": "https://github.com/MengXingXiaoMing/maya-node-plugin-index",
        "updated": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "count": len(plugins),
        "categories": categories,
        "plugins": plugins,
    }
    with io.open(CATALOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(catalog, ensure_ascii=False, indent=2))
        handle.write("\n")
    print("catalog.json: %d plugins" % len(plugins))


if __name__ == "__main__":
    main()
