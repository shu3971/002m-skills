# 使用示例

## 例 1：找提示词

用户：找一个适合发朋友圈的秋日写真提示词

技能：
1. 读 `@references/prompts.md`，匹配“秋日 / 旅行 / 暖调”：找到「秋日蜡笔涂鸦人像」和「巴黎咖啡故事书女孩」。
2. 回复（给中文提示词＋案例页链接）：
   - 「秋日蜡笔涂鸦人像」：……（中文提示词全文）……案例页：https://www.002m.com/case/batch83b-02.html
   - 「巴黎咖啡故事书女孩」：……案例页：https://www.002m.com/case/batch3-069.html
3. 问一句：要不要用其中一条、拿你的照片直接生成一张？

## 例 2：用照片生成旗袍写真

用户：用这张照片生成一张旗袍写真（附照片 /Users/xxx/photo.jpg）

技能：
1. 读 `@references/prompts.md`，找旗袍相关。精选里没有纯旗袍条目时，告诉用户：精选 48 条里没有旗袍，完整库在 002m.com 有 12 张旗袍姿势；先用一条相近的写真提示词生成，或让用户去 002m.com 挑一条把链接发来。
2. 假设用户选了「暖米双重曝光人像」，跑：
   `python3 scripts/002m-gen.py gen --photo /Users/xxx/photo.jpg --prompt "<英文提示词>" --out ~/Desktop/002m-qipao.png`
3. 成功后回复：图已保存到 ~/Desktop/002m-qipao.png，本次扣了 1 次免费额度，还剩 2 次免费。

## 例 3：额度用完了

用户：再生成一张

技能：
1. 跑 `python3 scripts/002m-gen.py gen ...`，服务器返回 429 `免费试用 3 张已用完`。
2. 不要重试。回复：免费 3 张用完了。去 https://gen.002m.com 支付宝买个付费码（9 张 ¥4.9、20 张 ¥9.9、90 张 ¥39.9），把码发我，我帮你核销再生成。
3. 用户发来码 `P2-XXXXXXXX` 后跑：`python3 scripts/002m-gen.py redeem --code P2-XXXXXXXX`，成功后显示新增 20 张，再跑生成。

## 例 4：只查额度

用户：查一下我还剩几次免费生成

技能：跑 `python3 scripts/002m-gen.py status`，回复：免费剩余 2 张，付费余额 0 张。

## 例 5：没有照片，纯文生图

用户：直接生成一张赛博朋克风格的肖像，不要照片

技能：跑 `python3 scripts/002m-gen.py gen --prompt "<英文提示词>" --out ~/Desktop/002m-cyber.png`（不带 --photo），纯文生图。并提醒用户：没照片是纯凭提示词画的，不保脸；想要自己的脸，传一张照片再生成。
