# Maya Node Plugin Index

Maya 节点插件市场的公共索引，作者：**詹康明 (Kangming Zhan)**。

这个仓库不是插件市场应用本身，而是市场读取的**在线目录**。市场打开时会拉取 `catalog.json`，在“在线”页展示、搜索、分类和一键安装。

- 目录地址（国内优先）：`https://cdn.jsdelivr.net/gh/MengXingXiaoMing/maya-node-plugin-index@main/catalog.json`
- 备用地址：`https://raw.githubusercontent.com/MengXingXiaoMing/maya-node-plugin-index/main/catalog.json`
- 市场应用：https://github.com/MengXingXiaoMing/maya-node-plugin-market

## 目录结构

```text
plugins/0x00141488.json     一个插件一个条目
categories.json             分类 id -> 中英文名称
scripts/build_catalog.py    把 plugins/*.json 合成 catalog.json
catalog.json                市场读取的构建产物
version.json                市场客户端用来判断有没有新版本
```

## 添加一个插件

插件代码统一放在**作者自己的公开仓库**，索引仓库只存一条 JSON 元数据：

- `repo` 填你自己的仓库，`subpath` 指向仓库里的插件目录（可以为空）。
- 索引仓库不再托管插件代码（历史 `packages/` 已迁到市场仓库 `nodes/`）。

### 贡献者三步

1. 把插件放到**你自己的公开仓库**（可以直接抄
   [maya-node-plugin-sample](https://github.com/MengXingXiaoMing/maya-node-plugin-sample)）。
   入口 `.py` 里写 `NODE_INFO`，节点的 `node_id` / `node` / `version` 要和条目一致。
2. Fork 本仓库，新建 `plugins/<node_id>.json`，`repo` 填你的仓库。
3. 开 PR。GitHub Actions 自动校验，通过后直接 squash 合并，并自动重建 `catalog.json`，
   不需要等人工审核；市场刷新「在线」页就能看到。

只改 `plugins/*.json` 的 PR 才会自动合并；动 `scripts/`、`.github/`、`catalog.json`
的 PR 需要人工处理。

在 `plugins/` 下新建 `<node_id>.json`：

```json
{
  "name": "魔方绑定",
  "description": "程序化生成任意尺寸的魔方绑定。",
  "author": "作者名",
  "version": "2.0.0",
  "node_id": "0x00141488",
  "node_name": "rubikCubeNode",
  "category": "rigging",
  "tags": ["绑定", "程序化"],
  "repo": "owner/repo",
  "subpath": "nodes/0x00141488",
  "entry": "rubikCube.py",
  "branch": "main",
  "maya_versions": ["2022", "2023", "2024", "2025", "2026"],
  "added": "2026-10-29",
  "updated": "2026-10-29"
}
```

3. 生成目录：

```bash
python scripts/build_catalog.py
```

4. 提 PR。构建脚本会检查：

- `node_id` 格式和全局唯一
- 包目录名是否等于 `node_id`
- `entry` 文件是否存在
- `NODE_INFO` 的 `node` / `node_id` 是否和条目一致
- 分类是否存在于 `categories.json`

合并后 GitHub Actions 会自动重建 `catalog.json`（`auto-merge-plugin-pr` 合并完立即重建，`build-catalog` 也支持手动 `workflow_dispatch`），市场下一次刷新「在线」页即可看到。

## 自动合并规则

`plugins/*.json` 的 PR 会触发自动校验，通过后直接 squash 合并，不需要人工审核：

- 一个 PR 最多 3 个条目，只允许新增 / 修改 `plugins/<node_id>.json`。
- `repo` 必须是 **PR 作者自己的公开仓库**，且仓库未归档。
- `node_id` 必须和文件名一致，且在索引里唯一。
- 市场会读取作者仓库里的 `entry` 文件，要求 `NODE_INFO` 的 `node_id`、`node`、`version` 与条目一致。
- 分类必须在 `categories.json` 里，标签和 Maya 版本必须是数组。
- 修改 `.github/`、`scripts/`、`README.md`、`catalog.json` 等文件的 PR 不自动合并，需要人工处理。
- `updated` 必须是 `YYYY-MM-DD`；如果填了 `sha256`，必须是 64 位十六进制。
- PR 全局串行处理，合并后立即重建 `catalog.json` 并清理 jsDelivr 缓存，最后在 PR 里留言告知结果。
- 校验失败会在 PR 里留言并保留 PR，不会合并。

自动合并依赖仓库的 GitHub Actions（`.github/workflows/auto-merge-plugin-pr.yml`）。它使用 `pull_request_target`，只通过 API 读取 PR 里的 JSON，不会执行 PR 代码。

自动合并只解决“元数据可信 + 能下载”的问题，不保证插件代码安全；用户安装第三方插件前仍应确认作者和来源。

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `name` | 市场卡片标题 |
| `description` | 卡片详情，建议一句话说明功能 |
| `author` | 作者名 |
| `version` | 插件版本；市场用它判断是否需要更新 |
| `node_id` | 节点注册序号，同时是安装目录名 |
| `node_name` | `registerNode` 的节点类型名 |
| `category` | `categories.json` 里的分类 id |
| `tags` | 标签，会进入市场的标签栏 |
| `repo` | `owner/repo`，安装时下载这个仓库 |
| `subpath` | 插件在仓库里的相对目录 |
| `entry` | 注册节点的 `.py` 文件（相对 `subpath`） |
| `branch` | 下载分支，默认 `main` |
| `maya_versions` | 兼容的 Maya 版本 |
| `updated` | 最近更新时间，`YYYY-MM-DD`，市场在线页会显示 |
| `sha256` | 可选，插件发布包的摘要，安装时会校验 |
| `icon` | 可选，GitHub 上可直接访问的图片 URL |

## 安装方式

市场会优先按 `repo` + `subpath` 下载 GitHub 仓库 zip，找到包目录，校验节点序号和 `NODE_INFO`，然后复制到本地 `nodes/<node_id>/`。如果条目提供 `asset`（GitHub Release 的 zip/tgz），则优先使用预构建包。

## 注意

- 在线目录只负责索引，不运行任何代码；安装的是作者仓库里的插件。
- 节点序号是 Maya 的全局标识，请不要重复使用别人的序号。
- 插件是第三方代码，市场会显示来源和版本，但请只安装你信任的作者。
