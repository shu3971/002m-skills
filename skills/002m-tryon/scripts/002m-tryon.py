#!/usr/bin/env python3
"""002M 试衣间 (AI Try-On) - gen.002m.com try-on client for the 002M-tryon WorkBuddy skill.

Replicates the tryon.002m.com frontend flow: composite the person photo, optional
pose reference, and clothing image(s) into ONE image, then POST it to
gen.002m.com/api/gen with a Chinese try-on prompt.

Usage:
  python3 002m-tryon.py status
  python3 002m-tryon.py gen --photo <person.jpg> [--pose <pose.jpg>] --cloth <cloth.jpg> [--cloth <bottom.jpg>] [--scene "<scene>"] --out <out.png>
  python3 002m-tryon.py redeem --code P2-XXXXXXXX

Modes:
  --cloth given once      -> single garment try-on (person + 1 cloth)
  --cloth given twice     -> combo set (person + top + bottom), --combo implied
  --pose given            -> use the pose reference (pose-*.jpg lineart or any pose image)
  --scene                 -> optional background/atmosphere description

Credits are shared with the 002M gen station (额度跨站通用). One gen = one credit.
A failed generation does NOT deduct a credit.
"""
import base64
import io
import json
import mimetypes
import os
import secrets
import sys
import urllib.error
import urllib.request

try:
    from PIL import Image
except ImportError:
    sys.exit("this script needs Pillow: pip install Pillow")

BASE = "https://gen.002m.com"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ID_FILE = os.path.join(os.path.expanduser("~"), ".002m", "device-id")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# --- Prompt templates (mirror tryon.002m.com buildTryonPrompt) ---
TRYON_PROMPT = ("左图是人物，右图是服装。让左图中的人物穿上右图中的服装，输出一张逼真的全身照片。\n"
                "严格要求：\n"
                "1. 人物身份完全一致：同一张脸、五官、肤色、发型、身材比例，不得改变人物是谁。\n"
                "2. 将右图服装原样穿到人物身上：忠实保留颜色、面料质感、图案、领型、袖长、下摆和廓形，不得重新设计或简化。\n"
                "3. 服装自然垂坠贴合身体曲线，按原光照产生真实褶皱、阴影和高光。\n"
                "4. 保留人物照片原有的背景、光线和整体氛围。\n"
                "5. 逼真、高细节、专业时尚大片质感。\n"
                "仅输出最终的换装照片。")
TRYON_BG_CLAUSE = "保留人物照片原有的背景、光线和整体氛围"

TRYON_PROMPT_COMBO = ("左图是人物，第二张图是上衣，第三张图是下装。让左图中的人物穿上第二张图的上衣和第三张图的下装（整套搭配），输出一张逼真的全身照片。\n"
                      "严格要求：\n"
                      "1. 人物身份完全一致：同一张脸、五官、肤色、发型、身材比例，不得改变人物是谁。\n"
                      "2. 将上衣和下装原样穿到人物身上：忠实保留颜色、面料质感、图案、领型、袖长、下摆和廓形，不得重新设计或简化；上衣和下装按原搭配穿着。\n"
                      "3. 服装自然垂坠贴合身体曲线，按原光照产生真实褶皱、阴影和高光。\n"
                      "4. 保留人物照片原有的背景、光线和整体氛围。\n"
                      "5. 逼真、高细节、专业时尚大片质感。\n"
                      "仅输出最终的换装照片。")

ATLAS_PROMPT_UPLOAD = ("左图是本人（脸、发型、衣服全保留），右图是姿势参考图（只取姿势：身体朝向、手脚位置、触地点，不取参考图里的人脸、衣服、身材与场景）。"
                       "生成同一人该姿势的写实全身肖像，成年女性，脸/发型/衣服不变，纯白影棚背景，柔和均匀光，竖图 3:4，全身居中，无文字、无水印。")
ATLAS_PROMPT_UPLOAD_COSTUME = ("左图是本人（脸、发型保留），右图是姿势参考图（只取姿势：身体朝向、手脚位置、触地点，不取参考图里的人脸、衣服、身材与场景）。"
                               "生成同一人该姿势的写实全身肖像，成年女性，脸/发型不变，穿第三张图那身衣服（端庄优雅的正式服装），纯白影棚背景，柔和均匀光，竖图 3:4，全身居中，无文字、无水印。")
ATLAS_PROMPT_UPLOAD_COMBO = ("左图是本人（脸、发型保留），右图是姿势参考图（只取姿势：身体朝向、手脚位置、触地点，不取参考图里的人脸、衣服、身材与场景）。"
                             "生成同一人该姿势的写实全身肖像，成年女性，脸/发型不变，穿第三张图那件上衣和第四张图那条下装（整套搭配），纯白影棚背景，柔和均匀光，竖图 3:4，全身居中，无文字、无水印。")
TRYON_STYLE_CLAUSE = "纯白影棚背景，柔和均匀光"
ATLAS_COSTUME_CLAUSE = "第三张图是这身衣服，只换衣服穿上它，脸、发型、身材不变。"
ATLAS_COSTUME_COMBO_CLAUSE = "第三张图是上衣，第四张图是下装，只换衣服穿上它们，脸、发型、身材不变。"


def get_device_id():
    try:
        with open(ID_FILE, "r", encoding="utf-8") as f:
            did = f.read().strip()
        if 8 <= len(did) <= 40 and all(c.isalnum() or c == "-" for c in did):
            return did
    except OSError:
        pass
    did = "".join(secrets.choice(ALPHABET) for _ in range(12))
    os.makedirs(os.path.dirname(ID_FILE), exist_ok=True)
    with open(ID_FILE, "w", encoding="utf-8") as f:
        f.write(did)
    return did


def call(method, path, payload=None, timeout=180):
    did = get_device_id()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "gb_id=" + did)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"error": "HTTP %d" % e.code}
        return e.code, body
    except Exception as e:
        return 0, {"error": "network error: %s" % e}


def load_image(path):
    if not os.path.isfile(path):
        return None, "file not found: %s" % path
    try:
        im = Image.open(path)
        im.load()
        if im.mode != "RGB":
            im = im.convert("RGB")
        return im, None
    except Exception as e:
        return None, "cannot read image %s: %s" % (path, e)


def stitch_tryon(photo_path, pose_path, cloth_paths):
    """Composite person + [pose] + cloth(s) into one JPEG, like tryon's stitchTryon.
    Height 800, horizontal layout, white background, 8px gaps, scale to max width 1024."""
    imgs = []
    part = None
    im, err = load_image(photo_path)
    if im is None:
        return None, "base", err
    imgs.append(im)
    if pose_path:
        im, err = load_image(pose_path)
        if im is None:
            return None, "pose", err
        imgs.append(im)
    for c in cloth_paths:
        im, err = load_image(c)
        if im is None:
            return None, "costume", err
        imgs.append(im)
    try:
        H = 800.0
        ws = []
        total = 0.0
        for im in imgs:
            w = im.width * H / im.height
            ws.append(w)
            total += w
        total += 8 * (len(imgs) - 1)
        sc = min(1.0, 1024.0 / total)
        W = int(round(total * sc))
        HH = int(round(H * sc))
        canvas = Image.new("RGB", (W, HH), (255, 255, 255))
        px = 0
        gap = int(round(8 * sc))
        for i, im in enumerate(imgs):
            w = int(round(ws[i] * sc))
            h = HH
            resized = im.resize((w, h), Image.LANCZOS)
            canvas.paste(resized, (px, 0))
            px += w + gap
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), None, None
    except Exception as e:
        return None, "canvas", str(e)


def build_tryon_prompt(pose_given, cloth_count, scene):
    scene = (scene or "").strip()[:500]
    # Combo = 2 cloths (top + bottom)
    if cloth_count == 2:
        if pose_given:
            base = ATLAS_PROMPT_UPLOAD_COMBO
            if scene:
                base = base.replace(TRYON_STYLE_CLAUSE, scene)
            return base + "\n" + ATLAS_COSTUME_COMBO_CLAUSE
        base = TRYON_PROMPT_COMBO
        if scene:
            base = base.replace(TRYON_BG_CLAUSE, scene)
        return base
    if pose_given and cloth_count == 1:
        base = ATLAS_PROMPT_UPLOAD_COSTUME
        if scene:
            base = base.replace(TRYON_STYLE_CLAUSE, scene)
        return base + "\n" + ATLAS_COSTUME_CLAUSE
    if pose_given:
        base = ATLAS_PROMPT_UPLOAD
        if scene:
            base = base.replace(TRYON_STYLE_CLAUSE, scene)
        return base
    base = TRYON_PROMPT
    if scene:
        base = base.replace(TRYON_BG_CLAUSE, scene)
    return base


def cmd_status():
    status, body = call("GET", "/api/status", timeout=30)
    if status != 200:
        print("status failed: %s" % (body.get("error") or body), file=sys.stderr)
        return 1
    print("free_left=%s credit=%s" % (body.get("trialLeft", "?"), body.get("credit", "?")))
    print(json.dumps(body, ensure_ascii=False))
    return 0


def cmd_redeem(code):
    code = (code or "").strip().upper()
    if not code:
        print("redeem failed: missing --code", file=sys.stderr)
        return 1
    status, body = call("POST", "/api/redeem", {"code": code}, timeout=30)
    if status != 200 or not body.get("ok"):
        print("redeem failed: %s" % (body.get("error") or body), file=sys.stderr)
        return 1
    st = body.get("state") or {}
    print("redeemed: +%s images, credit now %s" % (body.get("added"), st.get("credit")))
    print(json.dumps(body, ensure_ascii=False))
    return 0


def cmd_gen(photo, pose, cloths, scene, out):
    if not photo:
        print("gen failed: missing --photo", file=sys.stderr)
        return 1
    if not cloths and not pose:
        print("gen failed: need at least one --cloth or a --pose to try on", file=sys.stderr)
        return 1
    if len(cloths) > 2:
        print("gen failed: at most 2 --cloth (single or top+bottom combo) per call", file=sys.stderr)
        return 1

    composite, part, err = stitch_tryon(photo, pose, cloths)
    if composite is None:
        hint = {"base": "人物照片没读到，换一张 JPG/PNG 再试。",
                "pose": "姿势图没读到，换一张姿势图再试。",
                "costume": "服装图没读到，换一件服装再试。",
                "canvas": "拼图失败：%s" % (err or "图片处理出错")}.get(part, "拼图失败")
        print("gen failed: %s 失败不扣额度。" % hint, file=sys.stderr)
        return 1

    prompt = build_tryon_prompt(bool(pose), len(cloths), scene)
    payload = {
        "prompt": prompt,
        "image": base64.b64encode(composite).decode("ascii"),
        "mime": "image/jpeg",
        "size": "1152x1536",
    }
    status, body = call("POST", "/api/gen", payload, timeout=180)
    if status != 200 or not body.get("image"):
        print("gen failed: %s" % (body.get("error") or body), file=sys.stderr)
        return 1
    try:
        img_bytes = base64.b64decode(body["image"])
    except Exception as e:
        print("gen failed: bad image data: %s" % e, file=sys.stderr)
        return 1
    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out, "wb") as f:
        f.write(img_bytes)
    st = body.get("state") or {}
    print("saved: %s (%d bytes)" % (out, len(img_bytes)))
    if body.get("imgKey"):
        print("online: %s/img/%s (30 days)" % (BASE, body["imgKey"]))
    print("free_left=%s credit=%s" % (st.get("trialLeft", "?"), st.get("credit", "?")))
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    args = {}
    i = 2
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and i + 1 < len(argv):
            k = a[2:]
            if k not in args:
                args[k] = []
            args[k].append(argv[i + 1])
            i += 2
        else:
            i += 1
    if cmd == "status":
        return cmd_status()
    if cmd == "redeem":
        return cmd_redeem(args.get("code", [""])[0] if args.get("code") else "")
    if cmd == "gen":
        photo = args.get("photo", [""])[0] if args.get("photo") else ""
        pose = args.get("pose", [""])[0] if args.get("pose") else ""
        cloths = args.get("cloth", []) or []
        scene = args.get("scene", [""])[0] if args.get("scene") else ""
        out = args.get("out", [""])[0] if args.get("out") else ""
        return cmd_gen(photo, pose, cloths, scene, out)
    print("unknown command: %s (status | gen | redeem)" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
