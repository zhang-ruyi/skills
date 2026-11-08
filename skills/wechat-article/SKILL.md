---
name: wechat-article
description: 把 Markdown 长文做成微信公众号原生文章:表格转内联 CSS 图卡、中文字号/标点排版、390px 预览、封面素材上传、draft/add 与 draft/update(只建草稿不发布)。Use when 用户要求把文章发公众号、把表格改成 CSS 图、检查微信排版、上传或更新草稿箱。
---

# WeChat Article(公众号原生文章)

微信公众号会剥离 `<style>`、`class`、`<script>`、`<iframe>`,表格在手机上也很丑。本 skill 的路线是:

- **不用图片**(优先):把数据视图做成逐元素内联样式的 HTML 图卡。
- **不用表格**:层叠、流向、字段、对照、placement 都用 `div` 卡片 + 文字箭头。
- **只建草稿**:`draft/add` / `draft/update`,不调用群发/发布接口。
- **发布前预览**:390px 宽度渲染,检查断行、字号、标点、代码 span。

不适用:必须 100% 还原网页排版、依赖复杂 CSS 动效的文章。此时退化为“组件截图 + 图片上传”,但仍建议正文保持原生 HTML。

## 目录

```
wechat-article/
├── SKILL.md
├── assets/visuals.py          # 内联 CSS 组件助手
├── scripts/build_html.py      # Markdown → 微信内联 HTML
├── scripts/preview.py         # 390px 截图 + 分块
├── scripts/wechat_draft.py    # token/权限/封面/草稿 add/update
└── references/
    ├── typography.md          # 字号、标点、代码 span 规则
    └── wechat-api.md          # 接口、payload、错误码
```

## 工作流

### 1. 写源文件

正文用 Markdown;数据视图用 `:::html` 包一段内联样式 HTML。表格不要留在最终稿里。

```markdown
## 二、页缓存:文件偏移 → folio

`address_space` 里的 `i_pages` 用文件页号做键。

:::html
<div style="margin:18px 0;padding:14px;border:1px solid #e2e8f0;border-radius:14px;background:#fbfdff;">
  <div style="font-size:16px;font-weight:700;color:#0f172a;">页缓存里的一次查表</div>
  <div style="margin-top:10px;">
    <span style="...">offset 0</span> → <span style="...">index 0</span> → <span style="...">folio 0</span>
  </div>
</div>
:::
```

组件助手见 `assets/visuals.py`;把它放到脚本同目录,或 `PYTHONPATH=assets`。常用形态:

| 场景 | 组件 |
|---|---|
| 分层/流程 | 纵向 `card` + `↓` 连接,连接文字写“下一步动作” |
| 多介质数据视图 | 每个介质一张 `card`,内部放 unit pills,卡间写 `store_kv` / `L2 读` |
| 字段/元数据 | 每个字段一张小卡(左色条 + 等宽标签 + 说明),不要两列表格 |
| 两态对照 | 每层一张卡,卡内 READ/WRITE 两条浅色条 |
| 映射 | `offset → index → folio` 用 pill + 文字箭头 |
| 回载/循环 | 2×2 路径块,行间用 `↓`,避免箭头吊在行尾 |

### 2. 构建

```bash
python3 scripts/build_html.py article.md --strict
# 输出 article 同目录 html/article.html;--strict 发现 <table> 直接失败
```

构建器会自动:

- 支持 `:::html` 原样输出;
- 中文正文全角标点、中文引号、含中文括号;
- 跳过 `<code>` 和 URL;
- 组件字号整体上调(正文 16px 不变);
- 短代码 `white-space:nowrap`(≤40 字符),长代码才允许断行,避免 `bi_vc/nt` 这种断词。

### 3. 预览

```bash
python3 scripts/preview.py html/article.html --prefix /tmp/opencode/article
# 生成 /tmp/opencode/article.png 和 article-01.png ...
```

检查清单:

- 390px 下无横向溢出;标题不孤字、代码不断词。
- 组件标题不要和 H2 完全重复。
- 字段清单不能看起来像“无边框表格”;用卡片。
- 文字与颜色语义一致;若连接线是灰色,就不要写“蓝线/黄线”。
- `content` 中 `table=0, img=0, class=0, script=0, style 标签=0`。
- 图片不是必须;只有 CSS 实在无法还原时才用截图。

### 4. 凭证与权限

凭证只放文件,不发聊天、不写进仓库:

```bash
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/wechat.env <<'EOF'
WECHAT_APPID=wx...
WECHAT_APPSECRET=...
EOF
chmod 600 ~/.config/opencode/wechat.env
```

到公众号后台 → 设置与开发 → 基本配置 → IP 白名单,加入当前**直连出口 IP**。脚本默认 `trust_env=False` 直连,避免代理 IP 不在白名单。

先测权限(不创建内容):

```bash
python3 scripts/wechat_draft.py test
# token OK / draft/count / material/get_materialcount
```

- `draft/count` 失败:没有草稿箱接口权限。
- `material/get_materialcount` 失败:没有永久素材权限;封面可能传不上去。
- `40164`:IP 不在白名单。
- `48001`:接口未授权(账号类型/认证问题)。

### 5. 建草稿 / 更新草稿

```bash
# 新建:必须有封面;正文 H1 会被移除,标题单独传给微信
python3 scripts/wechat_draft.py create \
  --html html/article.html \
  --cover /path/cover.jpg \
  --digest "一句话摘要" \
  --source https://example.com/article.html

# 更新:沿用原草稿的封面/摘要/来源,只换正文和标题
python3 scripts/wechat_draft.py update \
  --media-id <DRAFT_MEDIA_ID> \
  --html html/article.html
```

- `draft/add` 的 `articles` 是**数组**;`draft/update` 的 `articles` 是**对象**,写错会报 `47001 data format error`。
- 封面作为永久图片素材上传(`material/add_material?type=image`),拿 `media_id` 填 `thumb_media_id`;不要用临时 media。
- 标题从正文 H1 读取;H1 不放进 `content`,否则微信标题会和正文标题重复。
- 脚本只调用草稿接口;**绝不自动群发**。用户在后台预览后自行决定。

## 关键约束

1. 微信正文只认内联样式;`<style>`、class、script、iframe 都会被剥离。
2. 数据视图不要用 `<table>`;用卡片/流向/字段卡。
3. 组件字号不要低于 11px;正文 16px/1.8,面板标题 16px,卡标题 14.5px,说明 12.5px。
4. 中文标点全角;代码 span 内保持 ASCII;URL 不转换。
5. 代码 span 短词不拆;长词才允许 `overflow-wrap`。
6. 不要打印 AppSecret/access_token;token 缓存文件 `chmod 600`。
7. 只建草稿;`freepublish` / `mass` 接口不在本 skill 范围内。
8. `content_source_url` 必须可访问;更新前用 `curl` 确认 200。

## 组件示例

```python
from visuals import panel, card, pill, down, field_cards

inner = card("GPU HBM", "paged KV block", pill("B0", "blue") + pill("B1", "blue"), "blue")
inner += down("store_kv · GPU→CPU 拷贝")
inner += card("L1 DRAM", "MemoryObj", pill("c0/g0/r0", "violet"), "violet")
html = panel("block → MemoryObj → 文件/slot", "同一段 KV 的不同视图", inner)
```

字段卡:

```python
field_cards([("shape / dtype", "逻辑张量形状"), ("address", "L1 介质地址")], "violet")
```

## 参考

- [references/typography.md](references/typography.md):字号、标点、代码 span、常见断行问题。
- [references/wechat-api.md](references/wechat-api.md):接口、payload、错误码、权限测试。

## 依赖

- Python 3.10+,`requests`,Pillow(预览脚本)。
- Chrome/Chromium headless(`ARCHIFY_CHROME` 或 `CHROME` 环境变量)。
