# Maya Node Plugin Index

Maya 节点插件市场的公共索引，作者：**詹康明 (Kangming Zhan)**。

这个仓库不是插件市场应用本身，而是市场读取的**在线目录**。市场打开时会拉取 `catalog.json`，在“在线”页展示、搜索、分类和一键安装。

- 目录地址（国内优先）：`https://cdn.jsdelivr.net/gh/MengXingXiaoMing/maya-node-plugin-index@main/catalog.json`
- 备用地址：`https://raw.githubusercontent.com/MengXingXiaoMing/maya-node-plugin-index/main/catalog.json`
- 市场应用：https://github.com/MengXingXiaoMing/maya-node-plugin-market

## 目录结构

```text
plugins/0x00141488.json     一个插件一个条目
packages/0x00141488/        插件包（安装时复制到 nodes/<node_id>/）
categories.json             分类 id -> 中英文名称
scripts/build_catalog.py    把 plugins/*.json 合成 catalog.json
catalog.json                市场读取的构建产物
```

## 添加一个插件

有两种方式，推荐第一种，因为索引仓库不会随着插件变多而变成巨型仓库：

- **作者仓库托管（推荐）**：`repo` 填你自己的 GitHub 仓库，`subpath` 指向仓库里的插件目录（可以为空）。索引仓库只存一条 JSON。
- **索引仓库托管**：把插件文件夹放进 `packages/<node_id>/`，`subpath` 填 `packages/<node_id>`，`repo` 填 `MengXingXiaoMing/maya-node-plugin-index`。当前 4 个示例用这种方式，方便直接演示。

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
  "subpath": "packages/0x00141488",
  "entry": "rubikCube.py",
  "branch": "main",
  "maya_versions": ["2022", "2023", "2024", "2025", "2026"],
  "added": "2026-10-29"
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

合并后重新运行构建脚本（或配置 GitHub Actions）生成 `catalog.json`，市场下一次刷新即可看到。

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
| `icon` | 可选，GitHub 上可直接访问的图片 URL |

## 安装方式

市场会优先按 `repo` + `subpath` 下载 GitHub 仓库 zip，找到包目录，校验节点序号和 `NODE_INFO`，然后复制到本地 `nodes/<node_id>/`。如果条目提供 `asset`（GitHub Release 的 zip/tgz），则优先使用预构建包。

## 注意

- 在线目录只负责索引，不运行任何代码；安装的是作者仓库里的插件。
- 节点序号是 Maya 的全局标识，请不要重复使用别人的序号。
- 插件是第三方代码，市场会显示来源和版本，但请只安装你信任的作者。
