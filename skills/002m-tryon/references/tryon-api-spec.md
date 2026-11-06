# 002M 试衣间 (AI Try-On) API 规范

供 `scripts/002m-tryon.py` 调用。试衣间复用 gen 站的接口与额度（额度跨站通用），Base URL 同样是 `https://gen.002m.com`。不需要注册、不需要 API key，凭设备 Cookie `gb_id=<id>`（与 gen 站同一枚，存于 `~/.002m/device-id`）。

## 生成一张换装照 POST /api/gen

前端 tryon.002m.com 的做法：先把「人物照片 + 可选姿势图 + 服装图（1 张单件 / 2 张套装）」**拼成一张复合图**，再连同中文换装提示词一起发给 gen 接口。

请求体：

```json
{
  "prompt": "中文换装提示词（见下）",
  "image": "复合图的 base64（JPEG，无 data: 前缀）",
  "mime": "image/jpeg",
  "size": "1152x1536"
}
```

### 复合图怎么拼（stitchTryon，脚本已复刻）

- 目标高固定 800。
- 每张图按宽/高比例缩放到高 800；总宽 = 各图宽之和 + 8×(图数−1)。
- 若总宽超过 1024，整体等比缩小到宽 ≤ 1024。
- 白底，图与图之间留 8px 白色间隔，从左到右依次：人物照片 → 姿势图（可选）→ 服装图。
- 输出 JPEG（quality 85）后 base64。

### 提示词怎么选（buildTryonPrompt，脚本已复刻）

| 场景 | 提示词模板 | 背景子句替换 |
| --- | --- | --- |
| 仅服装（1 件） | TRYON_PROMPT | 用场景替换「保留人物照片原有的背景、光线和整体氛围」 |
| 套装（上衣+下装，2 张） | TRYON_PROMPT_COMBO | 同上 |
| 姿势 + 服装（1 件） | ATLAS_PROMPT_UPLOAD_COSTUME + 追加「第三张图是这身衣服…」 | 用场景替换「纯白影棚背景，柔和均匀光」 |
| 姿势 + 套装（2 件） | ATLAS_PROMPT_UPLOAD_COMBO + 追加「第三张图是上衣，第四张图是下装…」 | 同上 |
| 仅姿势 | ATLAS_PROMPT_UPLOAD | 同上 |

提示词为中文，模板全文在 `scripts/002m-tryon.py` 的常量里（与 tryon 站前端一致，未改动）。

### 成功/失败返回

- 成功：`{ "image": "<base64 PNG>", "imgKey": "gXXXXX", "state": { "trialLeft": ..., "credit": ... } }`，成图在线地址 `https://gen.002m.com/img/<imgKey>`，存 30 天。
- 失败（HTTP 状态码 + JSON）：400 请求格式错、429 `免费试用 3 张已用完`（免费额度用尽）、429 `今日全站额度已满`（全站每天 100 张）、502 `上游未出图`（稍后重试）。
- **只有出图成功才扣额度**；失败（含 502、451 内容拦截）不扣。

## 查额度 GET /api/status

同 gen 站，返回 `trialLeft`（免费剩余）、`credit`（付费余额）等。

## 核销付费码 POST /api/redeem

同 gen 站，请求体 `{ "code": "P2-XXXXXXXX" }`。额度与 gen 站共享。

## 买付费码（用户在网页操作，不走 API）

- https://gen.002m.com 点「支付宝付款 · 买码」；档位 9 张 ¥4.9、20 张 ¥9.9、90 张 ¥39.9。
- 付费码格式 `P2-` + 8 位大写字母数字。

## 姿势图来源（可选，供用户挑选姿势用）

- 姿势线稿图在 `https://www.002m.com/images/atlas/pose-*.jpg`（pose-01 ~ pose-6x，Shisei CC0 线稿，仅作生成参考）。脚本接受本地姿势图路径，也接受用户给的姿势图 URL（先用 curl/下载工具取到本地再传 `--pose`）。

## 隐私口径（沿用 002M 站的说明）

- 照片只在点「生成」时发送到 gen.002m.com 用于本次生成；本技能不存原照片。
- 成图在服务器存 30 天；只记额度与使用记录（设备号、日期、次数、是否成功）。
- 不要把用户照片上传到任何其他地方。
