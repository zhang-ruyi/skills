# zhang-ruyi/skills

可复用的 opencode skill 归档。每个目录是一个独立 skill,可直接复制到项目的 `.opencode/skills/` 或全局 `~/.config/opencode/skills/`,重启 opencode 后生效。

## Skills

| Skill | 用途 | 依赖 |
|---|---|---|
| [kernel-diagrams](skills/kernel-diagrams/SKILL.md) | 分析 Linux 内核等大型 C 源码,用 Archify 生成交互原理图并构建画廊 | Archify、Chrome headless、Node ≥ 18 |
| [layout-map](skills/layout-map/SKILL.md) | 用 HTML/CSS 画磁盘块组、地址空间、内存区间等布局图,替代 ASCII | 无;引入 `assets/layout-map.css` |
| [tree-map](skills/tree-map/SKILL.md) | 用 HTML/CSS 画对象包含、资源树、决策树等层级结构,替代 ASCII 的 ├──/└── | 无;引入 `assets/tree-map.css` |
| [wechat-article](skills/wechat-article/SKILL.md) | 把 Markdown 长文做成公众号原生内联样式文章:表格转 CSS 图卡、中文字号/标点、390px 预览、建/更新草稿 | Python requests/Pillow、Chrome headless、公众号草稿权限 |

## Agents

| Agent | 用途 |
|---|---|
| [kernel-diagrammer](agents/kernel-diagrammer.md) | 内核源码图解 agent,配合 kernel-diagrams skill 使用 |

## 安装

项目级:

```bash
mkdir -p .opencode/skills .opencode/agents
cp -r skills/layout-map .opencode/skills/
cp -r skills/tree-map .opencode/skills/
cp -r skills/kernel-diagrams .opencode/skills/
cp -r skills/wechat-article .opencode/skills/
cp agents/kernel-diagrammer.md .opencode/agents/
```

全局:复制到 `~/.config/opencode/skills/` 与 `~/.config/opencode/agents/`,然后重启 opencode。

## 依赖

- **Archify**(仅 kernel-diagrams):
  ```bash
  npx -y skills@latest add https://github.com/tt-a1i/archify \
    --skill archify --agent opencode --global --copy --yes
  ```
- **Python 3.10+**(wechat-article):
  ```bash
  pip install requests pillow
  ```
- **Chrome / Chromium**(Archify 的 browser-check 与 wechat-article 的 390px 预览):
  ```bash
  export ARCHIFY_CHROME=/path/to/chrome-headless-shell
  export ARCHIFY_CHROME_NO_SANDBOX=1
  ```

## 说明

- `kernel-diagrams` 默认内核源码路径为 `~/workspace/Git/git.kernel.org/linux`,可在任务中指定其他路径。
- `layout-map` 是示意性组件;精确布局以 `dumpe2fs`、`/proc/<pid>/maps` 等工具输出为准。
- `tree-map` 用于层级/包含/决策;带 `path:line` 的调用链建议保留代码块或 Archify 图。
- `wechat-article` 只创建/更新草稿,不自动发布;凭证放 `~/.config/opencode/wechat.env`(`chmod 600`),并把直连出口 IP 加入公众号后台白名单。
- 内容版权与使用限制:未经作者书面许可,请勿用于商业用途或直接转载。
