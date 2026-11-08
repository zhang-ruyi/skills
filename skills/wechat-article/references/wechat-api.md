# 微信公众号草稿接口备忘

只使用草稿接口,**不要自动发布**。发布/群发需要用户明确授权。

## 凭证与网络

- 凭证文件:`~/.config/opencode/wechat.env`,`chmod 600`
- 变量:`WECHAT_APPID`、`WECHAT_APPSECRET`
- IP 白名单:公众号后台 → 设置与开发 → 基本配置 → IP 白名单
- 脚本用 `requests.Session(); trust_env=False` 直连,避免代理出口 IP 不在白名单
- 不要打印 AppSecret / access_token;token 缓存 `chmod 600`

## Token

```http
GET https://api.weixin.qq.com/cgi-bin/token
  ?grant_type=client_credential&appid=APPID&secret=SECRET
```

返回 `access_token` 与 `expires_in`(秒)。缓存到文件,提前 120 秒过期。

## 先测权限

```bash
python3 scripts/wechat_draft.py test
```

- `GET /cgi-bin/draft/count`:草稿总数;失败通常没有草稿箱权限
- `GET /cgi-bin/material/get_materialcount`:素材数;失败通常没有永久素材权限

常见错误:

| errcode | 含义 |
|---|---|
| 40164 | 出口 IP 不在白名单 |
| 40013 | AppID 无效 |
| 40125 | AppSecret 无效 |
| 48001 | 接口未授权(账号类型/认证) |
| 47001 | payload 格式错误 |
| 45002 | 内容长度/大小超限 |
| 40007 | media_id 无效 |

## 封面

草稿 `thumb_media_id` 必须是**永久素材** media_id:

```http
POST /cgi-bin/material/add_material?access_token=TOKEN&type=image
Content-Type: multipart/form-data
media=@cover.jpg
```

返回 `media_id`。脚本会先试 `type=image`,失败再试 `type=thumb`。
封面建议 2.35:1(如 760×323),正文字号小,不要放太多字。

## 新建草稿

```http
POST /cgi-bin/draft/add?access_token=TOKEN
Content-Type: application/json
```

```json
{
  "articles": [
    {
      "title": "标题",
      "author": "作者",
      "digest": "摘要",
      "content": "<section>...</section>",
      "content_source_url": "https://example.com/post.html",
      "thumb_media_id": "PERMANENT_MEDIA_ID",
      "need_open_comment": 0,
      "only_fans_can_comment": 0
    }
  ]
}
```

注意:`articles` 是**数组**。

## 更新草稿

```http
POST /cgi-bin/draft/update?access_token=TOKEN
```

```json
{
  "media_id": "DRAFT_MEDIA_ID",
  "index": 0,
  "articles": {
    "title": "标题",
    "author": "作者",
    "digest": "摘要",
    "content": "<section>...</section>",
    "content_source_url": "https://example.com/post.html",
    "thumb_media_id": "PERMANENT_MEDIA_ID",
    "need_open_comment": 0,
    "only_fans_can_comment": 0
  }
}
```

注意:`articles` 是**对象**,不是数组;写成数组会 `47001 data format error`。

## 读取草稿

```json
POST /cgi-bin/draft/get?access_token=TOKEN
{ "media_id": "DRAFT_MEDIA_ID" }
```

返回 `news_item[]`,可取 `title`、`digest`、`thumb_media_id`、`content_source_url`。

列表:

```json
POST /cgi-bin/draft/batchget?access_token=TOKEN
{ "offset": 0, "count": 20, "no_content": 1 }
```

## 内容格式

- `content` 必须是 HTML;微信会剥离 `<style>`、`class`、`<script>`、`<iframe>`
- 所有样式内联;不要 `<link>`、不要外部 CSS
- 不要把 H1 放进 `content`;标题用 `title` 字段,正文从导语开始
- 内容长度实测 34K 字符可接受;仍建议精简重复的内联样式
- `content_source_url` 要可访问;更新前 `curl --noproxy '*' -I` 确认 200

## 安全

- 只调用 `/cgi-bin/draft/*`、`/cgi-bin/material/*`、`/cgi-bin/token`
- 不调用 `freepublish/submit`、`message/mass/*` 等发布接口
- 不在聊天、日志、仓库里出现 AppSecret/token
- 草稿建好后让用户在后台预览、确认、手动群发
