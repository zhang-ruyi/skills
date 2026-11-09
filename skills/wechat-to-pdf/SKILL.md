---
name: wechat-to-pdf
description: 把微信公众号文章或普通网页导出为 A4 PDF:提取正文、还原 data-src 懒加载图片、清洗微信内联样式、WeasyPrint 渲染、页脚页码。Use when 用户给出文章链接要求导出 PDF、存档或打印版。
---

# WeChat → PDF(文章存档)

公众号文章没有「打印」入口,直接 `Ctrl+P` 会带上导航、推荐位和一堆内联样式。本 skill 走一条更稳的路:**抓正文 → 本地化图片 → 去掉微信的容器样式 → 用 WeasyPrint 排成 A4**。

不适用:需要 100% 还原网页视觉的文章(动效、视频、复杂 CSS 布局)。那种情况应退化为浏览器打印或截图。

## 依赖

```bash
apt-get install -y fonts-noto-cjk libpango-1.0-0 libpangoft2-1.0-0 \
  libcairo2 libgdk-pixbuf-2.0-0 libffi8 poppler-utils
pip install weasyprint beautifulsoup4 lxml
```

- `fonts-noto-cjk` 提供中文字形,没有它 PDF 里中文会变成方块。
- `poppler-utils` 只用于验收(`pdfinfo` / `pdftotext` / `pdftoppm`),可选但强烈建议。
- 不需要 Chrome/Chromium。

## 用法

```bash
python3 scripts/wx2pdf.py "https://mp.weixin.qq.com/s/XXXXXXXX" \
  --out ~/Downloads/article.pdf
```

| 参数 | 作用 |
|---|---|
| `--out` | 输出 PDF 路径;不填则用标题命名,放在工作目录里 |
| `--dir` | 工作目录(图片、可选 clean.html);默认 `.wx2pdf/<标题>-<时间>/` |
| `--html` | 不抓取,改读本地保存的 HTML(反爬页兜底) |
| `--page-url` | 配合 `--html`:图片 Referer 与相对地址基准,默认 `https://mp.weixin.qq.com/` |
| `--no-images` | 不下载配图,只要文字 |
| `--keep-html` | 额外保留清洗后的 `clean.html`,方便调 CSS |

成功时输出一行:

```
ok  pages=28  images=28/28  size=3518410  out=/path/article.pdf
```

## 脚本做了什么(顺序不能乱)

1. **抓 HTML**:带移动端 UA 请求,识别 `mp.weixin.qq.com`。部分网络对 AAAA(IPv6)查询超时,会让 `getaddrinfo` 整体失败,所以脚本优先只查 IPv4,并对抓取做 3 次退避重试。
2. **反爬校验**:标题为空或命中「环境异常」直接报错,不生成半成品。
3. **选正文**:`#js_content` → `article` → `main` → `body` 逐级降级;走 `body` 时先删 `header/nav/footer/aside`。
4. **先下图片,再清样式**。微信图片真实地址在 `data-src`,而清洗阶段会删掉所有 `data-*`;顺序反了就会得到一本没有图的 PDF。下载时带 `Referer: https://mp.weixin.qq.com/`,否则 `mmbiz.qpic.cn` 返回 403。
5. **清洗内联样式**:去掉 `background / padding / margin / width / max-width / text-align / display / position` 等布局属性,保留 `color / font-weight / font-size`。微信正文常见的灰底卡片、窄栏居中就是被这些属性撑出来的。
6. **删空块**:纯空白且不含图片/表格/代码的 `p/section/div/span` 直接删,否则会留下整屏空白。
7. **渲染**:A4、17/15mm 页边距、正文 10.5pt、行高 1.8、页脚 `当前页 / 总页数`。

## 验收

```bash
pdfinfo out.pdf | grep -E "Pages|Page size"     # 页数、A4
pdftotext out.pdf - | wc -m                     # 文字量,和原文比对
pdftoppm -png -r 80 -f 1 -l 1 out.pdf page      # 抽首页
pdftoppm -png -r 80 -f 8 -l 8 out.pdf mid       # 抽一页正文
```

重点看三页:**首页**(标题/作者/日期)、**正文页**(段落宽度、列表缩进)、**图页**(图片是否完整、有没有被裁)。页面偏窄或出现大片留白,通常是样式清洗没生效。

## 排障

失败时先查 [references/troubleshooting.md](references/troubleshooting.md),按现象定位。最常见的三类:

- **DNS 解析失败**:`Temporary failure in name resolution`,多为 AAAA 超时;脚本已优先 IPv4 并重试,仍失败则改 DNS 或走 `--html`。
- **「环境异常」反爬页**:脚本直接失败不产出半成品;用浏览器另存 HTML 后 `--html` 转换。
- **图片 0 张或全 403**:`data-src` 被提前清掉(顺序 bug,已修)、缺 Referer、或图片签名过期。

## 已知限制

- **反爬页**:微信偶尔返回「环境异常」验证页,脚本会直接失败。此时用浏览器打开确认能看,再重试;必要时人工另存 HTML 后走 `--dir` 流程。
- **动图与视频**:GIF 只保留首帧,`<video>` 会被删除。
- **复杂排版**:CSS grid/flex 在 WeasyPrint 里会降级为线性布局,公式图片不受影响,但纯 CSS 画的图可能错位。
- **文件名**:默认按标题生成,标题里的 `/ : * ?` 等字符会被替换。
- **版权**:导出的 PDF 仅用于个人存档,转载需作者许可。

## 输出约定

- 中间产物(HTML、img/)都留在 `--dir` 里,方便复现和二次调整。
- 给用户的成品建议放到手机下载目录(如 `/sdcard/Download/DSH-Go/`)或 `~/Downloads/`,文件名用 `<标题>.pdf`,不要带空格。
