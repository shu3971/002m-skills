# 002M Skills — 002M 画境官方 Agent Skills

[English](#english) | [中文](#中文)

Official Agent Skills from [002M 画境](https://002m.com) — a Chinese AI portrait prompt library (266 portrait cases) with paid image generation at [gen.002m.com](https://gen.002m.com).

| Skill | What it does |
| --- | --- |
| `skills/002m-gen/` | 002M 主页生图：按场景找写真提示词，用一张照片生成同款写真照；查额度、核销付费码 |
| `skills/002m-tryon/` | 002M 试衣间：传一张人物照片 + 一件/一套衣服（可选姿势），生成换装照 |

## Install / 安装

**Claude Code (plugin marketplace)**

```
/plugin marketplace add shu3971/002m-skills
/plugin install 002m@002m-skills
```

**Any agent (skills.sh CLI)**

```bash
npx skills add shu3971/002m-skills
```

**Manual / 手动安装**

```bash
git clone https://github.com/shu3971/002m-skills.git
cp -r 002m-skills/skills/002m-gen ~/.claude/skills/
cp -r 002m-skills/skills/002m-tryon ~/.claude/skills/
```

## Quota & pricing / 额度与收费

- Skills are **free to install**. 技能本身免费安装。
- Image generation runs on [gen.002m.com](https://gen.002m.com): **3 free images per device (once)**. After that, pay codes: 9 images ¥4.9 / 20 images ¥9.9 / 90 images ¥39.9. Codes never expire and can be transferred between browsers.
- 生成走 gen.002m.com：每设备免费 3 张（一次性）；之后用付费码：9 张 ¥4.9 / 20 张 ¥9.9 / 90 张 ¥39.9，永久有效、可跨浏览器转移。
- Photos are sent only when you hit Generate; the site does not store your original photos. 照片只在点生成时发送，本站不保存原照片。

## Links / 链接

- 画境主页：https://002m.com
- 生图：https://gen.002m.com
- 试衣间：https://tryon.002m.com

## License

MIT — see [LICENSE](LICENSE).

---

<a id="english"></a>
## English

002M (002m.com) is a Chinese AI portrait prompt library: 266 portrait cases with full bilingual prompts and remix variables. These two skills bring it into your AI agent:

- **002m-gen** — find a portrait prompt by scene and generate a portrait photo from your picture (face preserved).
- **002m-tryon** — AI clothing try-on: upload a photo and a garment (or a full outfit, optionally a pose) and get a dressed-up portrait.

Install with `npx skills add shu3971/002m-skills`, or in Claude Code via `/plugin marketplace add shu3971/002m-skills`.

<a id="中文"></a>
## 中文

002M 画境（002m.com）是中文 AI 人像提示词与视觉灵感库，全库 266 条人像案例，带完整中英提示词与 Remix 变量。这两个技能把它带进你的 AI Agent：

- **002m-gen（主页生图）**——按场景找写真提示词，用一张照片生成同款写真照（保脸），还能查额度、核销付费码。
- **002m-tryon（试衣间）**——传一张人物照片和一件/一套衣服（可选姿势），生成换装照。

安装：`npx skills add shu3971/002m-skills`，或在 Claude Code 里 `/plugin marketplace add shu3971/002m-skills`。
