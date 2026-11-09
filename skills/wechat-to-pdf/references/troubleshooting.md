# 排障手册(wechat-to-pdf)

按现象查,不用从头读。先看脚本最后一行:

- 停在 `fetching ...` → 网络/抓取,看 §1、§2
- 输出 `ok pages=... images=n/m` → 生成成功,看 n/m 和 §3、§6
- 直接抛异常 → 对照下面的速查表

## 速查表

| 现象 | 最可能原因 | 处置 |
|---|---|---|
| `Temporary failure in name resolution` | AAAA(IPv6)查询超时,导致 `getaddrinfo` 整体失败 | 脚本已优先 IPv4 并重试 3 次;仍失败见 §1 |
| `没拿到正文(可能是反爬/验证页)` | 微信风控返回「环境异常」 | 浏览器打开后另存 HTML,用 `--html`(§2) |
| `找不到正文容器` | 链接不是图文页(话题页/视频号/已删除) | 换正确文章链接 |
| `images=0/0` | 图片全在 `data-src`,且被提前清掉;或正文里没有 `<img>` | 见 §3.1 |
| `images=0/28`,每张都 403 | 缺 Referer 或图片链接过期 | 见 §3.2 |
| 部分图缺失,日志有 `img skip` | 单张超时/CDN 抖动 | 重跑一次即可,已下载的会复用 |
| 正文很窄、整体居中 | 微信内联 `max-width`/`padding`/`text-align` 没清干净 | 见 §4.1 |
| 页与页之间大片空白 | 空 `section` + 连续 `<br>` | 见 §4.2 |
| 代码块挤成一行、没有换行 | 微信用逐行 `div` 而不是 `<pre>` | 见 §4.3 |
| 表格错位/消失 | 微信表格是 `section` 拼的,不是 `<table>` | 见 §4.4 |
| 中文全是方块 | 缺 CJK 字体 | 见 §5 |
| 页数明显偏少 | 图片没下、正文被截断 | 用 `pdftotext` 比字数(§6) |
| 生成很慢(30 页约 20–40 s) | WeasyPrint 单线程渲染,属正常 | 见 §7 |

## 1. DNS 与网络

本机实测过:同一网络里 `getent hosts` 能解析,但 Python/ssh 默认 `AF_UNSPEC` 会同时查 AAAA,AAAA 超时后整个解析失败。

脚本已内置两层保护:

1. 把 `socket.getaddrinfo` 临时改成 **只查 IPv4**,失败再回退原逻辑;
2. `fetch()` 做 3 次退避重试(0.6s / 1.2s)。

手工确认:

```bash
getent hosts mp.weixin.qq.com      # 能出 IPv4 就说明只是 AAAA 的问题
cat /etc/resolv.conf               # 看 nameserver 是否可用
```

仍不通时换 DNS(需要 root):

```bash
printf 'nameserver 223.5.5.5\nnameserver 119.29.29.29\n' > /etc/resolv.conf
```

## 2. 反爬/验证页

微信对高频访问会返回「环境异常,完成验证后即可继续访问」。特征是 `og:title` 为空,正文里没有 `#js_content`。脚本会直接失败,**不会生成半成品**。

绕法(推荐):用手机或电脑浏览器打开文章 → 菜单里「保存网页/另存为」→ 得到 `xxx.html` → 本地转换:

```bash
python3 scripts/wx2pdf.py --html ~/Download/xxx.html \
  --page-url "https://mp.weixin.qq.com/s/原始链接" \
  --out ~/Download/article.pdf
```

- `--page-url` 用来给图片带 Referer,不填默认 `https://mp.weixin.qq.com/`,大多数情况够用。
- 浏览器另存后,很多 `data-src` 会被改写成 `src`,脚本两者都读,不用手工改。

## 3. 图片

### 3.1 `images=0/0`

说明正文里一张可下载的图都没有,常见两种:

- 图片在 `<picture><source>` 里而不是 `<img src>` —— 目前不支持,需要手工补 `<img>`;
- 样式清洗先于图片下载,`data-*` 已被删掉。这是历史 bug,现已固定为**先下图、后清洗**(见 SKILL.md 第 4 步)。

用 `--keep-html` 打开 `clean.html` 看 `<img>` 是否还在。

### 3.2 全部 403

`mmbiz.qpic.cn` 校验 Referer。脚本下载时会带 `Referer: <page_url>`,如果仍然 403:

- 确认 `--page-url` 是文章原始地址(而不是 `file://`);
- 图片链接带时效签名,过期后只能重新抓文章;
- 代理/镜像站改写过图片域名的,需要相应调整 Referer。

### 3.3 动图与视频

GIF 只保留首帧,`<video>`、`<mp-common-videosnap>` 会被删掉。重要动图建议单独截图后补进 PDF。

## 4. 排版

### 4.1 正文窄、居中

微信正文常被 `max-width:677px; margin:0 auto` 之类限制。脚本的 `DROP_STYLE` 会去掉 `width / max-width / margin / padding / text-align / display / position` 等布局属性,只保留 `color / font-weight / font-size`。

如果还有残留,把对应属性名加进 `scripts/wx2pdf.py` 的 `DROP_STYLE` 再重跑。注意**不要**把 `border`、`color` 也 drop 掉,会丢公式卡片的视觉区分。

### 4.2 大片空白

两个来源:空 `section`(微信编辑器会留),以及连续 `<br>`。空块已自动删除;`<br>` 堆叠没有自动处理,需要在 `normalize()` 后追加:

```python
for br in content.find_all("br"):
    if not br.find_next_sibling() or br.find_next_sibling().name == "br":
        br.decompose()
```

### 4.3 代码块丢换行

微信的代码块经常是每行一个 `div`/`section`,不是 `<pre>`。表现是 PDF 里代码挤成一段。

处理:在 `normalize()` 前,把连续的 `section`(class 含 `code-snippet__line`)包进 `<pre>`,或者直接对这类文章保留原文截图。

### 4.4 表格

微信表格由 `section` + `flex` 拼成,清洗掉 `display` 后会退化成竖排段落。数据表建议改由 `wechat-article` 的图卡方案处理,或接受线性化结果。

## 5. 字体

```bash
fc-list | grep -ic "cjk"     # 应为非 0
apt-get install -y fonts-noto-cjk
```

缺字体时 WeasyPrint 会 fallback 到无中文字形的字体,PDF 里显示为方块,但 `pdftotext` 仍能提取文字——所以**不能只靠文本验收**,必须看图。

## 6. 验收阈值

```bash
pdfinfo out.pdf | grep Pages
pdftotext out.pdf - | tr -d '[:space:]' | wc -m
```

- 字数比原文少 5%–10% 属正常(`pdftotext` 会丢空格、连字、列表符号);
- 少 30% 以上说明内容被截断,回到 §3/§4 查;
- 页数异常多,通常是图片没被缩放或空段落没删干净。

抽三页看图最稳:首页(标题/作者/日期)、中间正文页、含图页。

## 7. 性能

WeasyPrint 是单线程渲染,30 页带 28 张图大约 20–40 秒,属正常。想快可以:

- `--no-images` 先出文字版;
- 图片过多时预压缩(微信原图常有 1–3 MB);
- 不要指望多进程,WeasyPrint 的瓶颈在布局而不是 IO。

## 8. 兜底:Chrome 打印

WeasyPrint 搞不定的复杂 CSS(强依赖 grid/flex 的排版),退回浏览器打印:

```bash
chrome --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=out.pdf "https://mp.weixin.qq.com/s/xxx"
```

代价是会带上微信的导航和推荐位,需要在打印样式里隐藏 `.rich_media_tool`、`.qr_code_pc` 等;而且本 skill 默认不依赖 Chrome。
