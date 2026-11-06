# gen.002m.com API 规范

供 `scripts/002m-gen.py` 调用。Base URL：`https://gen.002m.com`。全部是 HTTPS + JSON，不需要注册、不需要 API key。

## 设备身份（device id）

- 生成额度按设备算。身份是一枚 Cookie：`gb_id=<12 位字符>`。
- 字符集：`ABCDEFGHJKMNPQRSTUVWXYZ23456789`（大写字母＋数字，去掉了容易混淆的 I、L、O、0、1）。
- 格式要求：8–40 位，只含字母、数字、连字符。脚本在 `~/.002m/device-id` 存一份，第一次运行生成，之后一直用同一枚——换了 id 就等于换设备，免费 3 张会重新算、付费余额也对不上。
- 每次请求都带 `Cookie: gb_id=<id>`。服务器没收到合法 id 时会自己生成一枚并通过 `Set-Cookie` 返回，但脚本不要依赖这个行为，要自己固定 id。

## GET /api/status — 查额度

请求：`GET https://gen.002m.com/api/status`，带 Cookie。

返回 JSON：

```json
{
  "id": "设备 id",
  "trialLeft": 3,
  "freeLeft": 3,
  "unlockLeft": 0,
  "code": null,
  "codeLeft": 0,
  "credit": 0
}
```

- `trialLeft` / `freeLeft`：免费剩余张数（每设备一次性 3 张）。
- `credit`：付费余额（核销付费码后增加）。
- `unlockLeft`：邀请解锁额度，一般是 0，不用管。

## POST /api/gen — 生成一张图

请求：`POST https://gen.002m.com/api/gen`，`Content-Type: application/json`，带 Cookie。

请求体：

```json
{
  "prompt": "英文提示词（必填）",
  "image": "照片的 base64（可选，有照片时传）",
  "mime": "image/jpeg",
  "size": "1152x1536",
  "code": "付费码（可选，一般不传）"
}
```

- `prompt`：必填。英文提示词效果最好；中文提示词也可以，模型能读。
- `image`：有照片时传 base64（不带 `data:` 前缀）。有照片走 image-to-image（保脸、保衣服）；没照片走纯文生图。
- `mime`：照片的 MIME，`image/jpeg` 或 `image/png`。
- `size`：只能是 `1024x1536`、`1152x1536`、`1024x1024`、`1536x1024` 四档；不传或传错时服务器默认 `1024x1536`。写真用 `1152x1536`（3:4）。
- `code`：一般不传。额度不够时服务器自动按 free → credit → unlock 顺序扣；传了 code 才走邀请码通道。

成功返回 JSON：

```json
{
  "image": "生成图的 base64 PNG",
  "mime": "image/png",
  "imgKey": "gXXXXXXXXXXXXXX",
  "state": { "trialLeft": 2, "freeLeft": 2, "credit": 0 }
}
```

- `image` 是 base64 PNG，直接存文件就是成图，不用二次请求。
- `imgKey` 是服务器存图键，30 天有效；在线地址是 `https://gen.002m.com/img/<imgKey>`。
- `state` 是生成后的最新额度。

失败返回 JSON（HTTP 状态码同时提示）：

| 状态 | 含义 | 处理 |
| --- | --- | --- |
| 400 | 请求格式错 / 缺提示词 | 检查请求体 |
| 403 | 邀请码无效/过期/绑定了别的设备 | 告诉用户码有问题 |
| 429 `免费试用 3 张已用完` | 免费额度没了，付费余额也是 0 | 引导用户买付费码核销 |
| 429 `今日全站额度已满` | 全站每天 100 张用完了 | 让用户明天再来 |
| 502 `上游未出图` | 上游模型没出图 | 稍后重试，不扣额度 |

关键：只有出图成功才扣额度。失败（包括 502）不扣。

## POST /api/redeem — 核销付费码

请求：`POST https://gen.002m.com/api/redeem`，`Content-Type: application/json`，带 Cookie。

请求体：`{ "code": "P2-XXXXXXXX" }`（付费码不区分大小写，脚本先转大写）。

成功返回：`{ "ok": true, "added": 20, "state": { ... } }`，`added` 是本次新增的额度张数。

失败返回 `{ "error": "..." }`，常见：`付费码不存在`、`该付费码已退款`、`这个付费码已在当前浏览器核销`、`该付费码的额度已用完`。

注意：一个码如果已经在别的设备核销过，再在新设备核销会把旧设备的剩余额度转移过来（`transferred: true`）。这是 002M 的跨设备转移功能，不是 bug。

## 买付费码（用户在网页上操作，不走 API）

- 网址：https://gen.002m.com ，点「支付宝付款 · 买码」。
- 档位：9 张 ¥4.9、20 张 ¥9.9、90 张 ¥39.9（主推）。支付宝支付，付款后页面直接显示付费码。
- 付费码格式：`P2-` 开头，后跟 8 位大写字母数字。码永久有效，退款凭未核销的码。

## 限额与成本（给技能作者看的，不用告诉用户细节）

- 免费：每设备 3 张，一次性；同一 IP 每天最多 9 张免费（防刷）。
- 全站：每天 100 张。
- 上游成本约 ¥0.20/张（gpt-image-2），付费码定价已覆盖。
