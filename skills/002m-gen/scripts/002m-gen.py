#!/usr/bin/env python3
"""002M Photo Studio - gen.002m.com client for the 002M WorkBuddy skill.

Stdlib only (urllib / json / base64 / os / sys). No pip packages.
Usage:
  python3 002m-gen.py status
  python3 002m-gen.py gen --prompt "<prompt>" [--photo /path/to/photo.jpg] --out /path/to/save.png [--size 1152x1536]
  python3 002m-gen.py faceswap --avatar /path/to/face.jpg --ref /path/to/ref1.jpg [--ref ref2.png ...] --out /path/to/dir
  python3 002m-gen.py redeem --code P2-XXXXXXXX

Device identity: a stable 12-char id stored in ~/.002m/device-id, sent as
Cookie gb_id=<id>. Same id = same device (free trial 3/device, pay-code
credit is per device). Do NOT delete the file or the device identity resets.
"""
import base64
import http.client
import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

BASE = "https://gen.002m.com"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ID_FILE = os.path.join(os.path.expanduser("~"), ".002m", "device-id")
SIZES = ("1024x1536", "1152x1536", "1024x1024", "1536x1024")


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
    url = BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    # Cloudflare Browser Integrity Check (error 1010) blocks the default
    # "Python-urllib/3.x" User-Agent. Use a browser UA: this script is the
    # user's own agent calling the user's own service.
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "gb_id=" + did)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except http.client.IncompleteRead:
        # Large base64 image response truncated mid-body. The generation
        # itself usually succeeded server-side (and was already counted);
        # do NOT retry /api/gen (that would spend another credit).
        return 0, {"error": "incomplete_response"}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"error": "HTTP %d" % e.code}
        return e.code, body
    except Exception as e:
        return 0, {"error": "network error: %s" % e}


def _is_complete_png(data):
    return bool(data) and data[:8] == b"\x89PNG\r\n\x1a\n" and data[-12:] == bytes.fromhex("0000000049454e44ae426082")


def _is_complete_jpeg(data):
    return bool(data) and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"


def _looks_complete(data):
    if not data:
        return False
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return _is_complete_png(data)
    if data[:2] == b"\xff\xd8":
        return _is_complete_jpeg(data)
    return False


def _fetch_urllib(path, timeout=120):
    """One urllib GET. Returns (ok, bytes). ok=False on truncation."""
    did = get_device_id()
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    req.add_header("Cookie", "gb_id=" + did)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            want = resp.headers.get("Content-Length")
            chunks = []
            total = 0
            while True:
                try:
                    chunk = resp.read(65536)
                except http.client.IncompleteRead as e:
                    chunks.append(e.partial or b"")
                    total += len(e.partial or b"")
                    break
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            data = b"".join(chunks)
        # A truncated body can look like a clean EOF (proxy closes early
        # without raising), so verify size AND the image trailer.
        if want is not None and total != int(want):
            return False, data
        return _looks_complete(data), data
    except Exception:
        return False, None


def _fetch_curl(path, timeout=120):
    """Fallback: curl (handles large bodies where urllib gets truncated)."""
    import subprocess
    import tempfile
    did = get_device_id()
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".img")
        os.close(fd)
        r = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(timeout),
             "-H", "Cookie: gb_id=" + did,
             "-o", tmp, BASE + path],
            capture_output=True, timeout=timeout + 10)
        if r.returncode != 0:
            return False, None
        with open(tmp, "rb") as f:
            data = f.read()
        return _looks_complete(data), data
    except Exception:
        return False, None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def fetch_binary(path, timeout=120, tries=3):
    """GET a binary URL (e.g. /img/<key>). Returns (status, bytes|None).
    Retries the whole GET (pure GET, no credit consumed). Falls back to
    curl if urllib keeps truncating the body."""
    for _ in range(tries):
        ok, data = _fetch_urllib(path, timeout)
        if ok:
            return 200, data
    ok, data = _fetch_curl(path, timeout)
    if ok:
        return 200, data
    return 0, None


# ---- faceswap（套图换脸）：参考图为底图，只换脸；每张参考图各出一张 ----
# 与 gen.002m.com 网页「套图模式」同一提示词、同一请求结构：
# images 数组按「参考图在前、头像在后」传，mimes 一一对应；
# size 由参考图方向决定（竖 1024x1536 / 横 1536x1024 / 方 1024x1024）。
FACESWAP_PROMPT = ("以第一张图片为底图，只把图中人物的脸换成第二张图片中人物的脸。"
                   "脸部以外的所有内容必须保持原样：服装、姿势、背景、光线、构图、画幅都不要动，"
                   "不要重新生成整张图。")


def _png_dims(raw):
    if raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR":
        return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    return None


def _jpeg_dims(raw):
    i = 2
    n = len(raw)
    while i + 9 < n:
        if raw[i] != 0xFF:
            i += 1
            continue
        marker = raw[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = int.from_bytes(raw[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h = int.from_bytes(raw[i + 5:i + 7], "big")
            w = int.from_bytes(raw[i + 7:i + 9], "big")
            return w, h
        i += 2 + seg_len
    return None


def image_info(path):
    """(mime, width, height) from the file header; stdlib only."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        dims = _png_dims(raw)
        return ("image/png", dims[0], dims[1]) if dims else ("image/png", 0, 0)
    if raw[:2] == b"\xff\xd8":
        dims = _jpeg_dims(raw)
        return ("image/jpeg", dims[0], dims[1]) if dims else ("image/jpeg", 0, 0)
    return None


def size_for(width, height):
    if width and height:
        if width > height:
            return "1536x1024"
        if width == height:
            return "1024x1024"
    return "1024x1536"


def _read_b64(path, max_mb=20):
    info = image_info(path)
    if not info:
        return None
    mime, w, h = info
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw or len(raw) > max_mb * 1024 * 1024:
        return None
    return {"b64": base64.b64encode(raw).decode("ascii"), "mime": mime,
            "w": w, "h": h, "bytes": len(raw)}


def recover_faceswap(start_ms, out):
    """The POST may time out while the image is still generated server-side.
    Look it up in /api/history (same device) and download it."""
    for _ in range(6):
        status, body = call("GET", "/api/history", timeout=30)
        items = (body or {}).get("items") or []
        if status == 200:
            for it in items:
                key = it.get("k") or ""
                if key and (it.get("p") or "")[:40] == FACESWAP_PROMPT[:40] and int(it.get("t") or 0) >= start_ms - 1500:
                    st, data = fetch_binary("/img/" + key)
                    if st == 200 and data and _looks_complete(data):
                        with open(out, "wb") as f:
                            f.write(data)
                        print("saved (recovered from history): %s (%d bytes)" % (out, len(data)))
                        print("      online: %s/img/%s (30 days)" % (BASE, key))
                        return True
        time.sleep(15)
    return False


def cmd_faceswap(avatar, refs, out_dir):
    if not avatar or not refs or not out_dir:
        print("faceswap failed: --avatar, at least one --ref and --out <directory> are required", file=sys.stderr)
        return 1
    av = _read_b64(avatar)
    if not av:
        print("faceswap failed: cannot read avatar (JPG/PNG, <= 20 MB): %s" % avatar, file=sys.stderr)
        return 1
    os.makedirs(out_dir, exist_ok=True)
    total, done, skipped = len(refs), 0, 0
    for idx, ref in enumerate(refs, 1):
        rf = _read_b64(ref)
        if not rf:
            print("[%d/%d] skip %s: not a readable JPG/PNG (or over 20 MB), not charged" % (idx, total, ref), file=sys.stderr)
            skipped += 1
            continue
        stem = os.path.splitext(os.path.basename(ref))[0]
        ext = ".png" if rf["mime"] == "image/png" else ".jpg"
        out = os.path.join(out_dir, stem + "-faceswap" + ext)
        payload = {
            "prompt": FACESWAP_PROMPT,
            # reference first, avatar last - same order as the website
            "images": [rf["b64"], av["b64"]],
            "mimes": [rf["mime"], av["mime"]],
            "size": size_for(rf["w"], rf["h"]),
            "source": "skill-gen",
        }
        start_ms = int(time.time() * 1000)
        status, body = call("POST", "/api/gen", payload, timeout=240)
        img_bytes = None
        if status == 200 and body.get("image"):
            try:
                img_bytes = base64.b64decode(body["image"])
            except Exception:
                img_bytes = None
        if img_bytes and _looks_complete(img_bytes):
            if body.get("mime") == "image/png" or img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                out = os.path.join(out_dir, stem + "-faceswap.png")
            with open(out, "wb") as f:
                f.write(img_bytes)
            done += 1
            print("[%d/%d] saved: %s (%d bytes)" % (idx, total, out, len(img_bytes)))
            if body.get("imgKey"):
                print("      online: %s/img/%s (30 days)" % (BASE, body["imgKey"]))
            continue
        # Either a truncated/empty response or an error: the image may still
        # exist server-side. History check is free, so try it once per image.
        reason = body.get("error") or ("HTTP %s" % status)
        print("[%d/%d] %s: %s - checking history..." % (idx, total, os.path.basename(ref), reason), file=sys.stderr)
        if recover_faceswap(start_ms, out):
            done += 1
            continue
        print("[%d/%d] skip %s: no image in history; if it was generated, 1 credit may be used (check https://gen.002m.com)"
              % (idx, total, os.path.basename(ref)), file=sys.stderr)
        skipped += 1
    status, body = call("GET", "/api/status", timeout=30)
    print("faceswap done: %d, skipped: %d, total: %d (each generated image costs 1 credit)" % (done, skipped, total))
    if status == 200:
        print("free_left=%s credit=%s" % (body.get("trialLeft", "?"), body.get("credit", "?")))
    return 0 if done else 1


def recover_from_history(prompt, out):
    """The /api/gen response was truncated, but the image was generated and
    stored. Find it in /api/history and download via /img/<key>."""
    for _ in range(3):
        status, body = call("GET", "/api/history", timeout=30)
        items = (body or {}).get("items") or []
        if status == 200 and items:
            top = items[0]
            key = top.get("k") or ""
            # Only trust the newest entry if it matches our prompt (or is
            # very recent); otherwise we might grab someone else's image.
            if key and (not prompt or (top.get("p") or "")[:40] == prompt[:40]):
                st, data = fetch_binary("/img/" + key)
                if st == 200 and data:
                    out_dir = os.path.dirname(os.path.abspath(out))
                    if out_dir:
                        os.makedirs(out_dir, exist_ok=True)
                    with open(out, "wb") as f:
                        f.write(data)
                    print("saved (recovered): %s (%d bytes)" % (out, len(data)))
                    print("online: %s/img/%s (30 days)" % (BASE, key))
                    return True
        time.sleep(2)
    return False


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


def cmd_gen(prompt, photo, out, size):
    if not prompt:
        print("gen failed: missing --prompt", file=sys.stderr)
        return 1
    if size not in SIZES:
        print("gen failed: --size must be one of %s" % (", ".join(SIZES)), file=sys.stderr)
        return 1
    payload = {"prompt": prompt, "size": size, "source": "skill-gen"}
    if photo:
        mime, _ = mimetypes.guess_type(photo)
        if mime not in ("image/jpeg", "image/png"):
            mime = "image/jpeg"
        try:
            with open(photo, "rb") as f:
                raw = f.read()
        except OSError as e:
            print("gen failed: cannot read photo: %s" % e, file=sys.stderr)
            return 1
        if len(raw) > 20 * 1024 * 1024:
            print("gen failed: photo over 20 MB", file=sys.stderr)
            return 1
        payload["image"] = base64.b64encode(raw).decode("ascii")
        payload["mime"] = mime
    status, body = call("POST", "/api/gen", payload, timeout=180)
    if status == 0 and body.get("error") == "incomplete_response":
        print("gen response truncated (large image); recovering from history...", file=sys.stderr)
        if recover_from_history(prompt, out):
            return 0
        print("gen failed: response truncated and recovery failed; the image was generated (1 credit used) - check https://gen.002m.com history", file=sys.stderr)
        return 1
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
    refs = []
    i = 2
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and i + 1 < len(argv):
            key = a[2:]
            if key == "ref":
                refs.append(argv[i + 1])
            else:
                args[key] = argv[i + 1]
            i += 2
        else:
            i += 1
    args["ref"] = refs
    if cmd == "status":
        return cmd_status()
    if cmd == "redeem":
        return cmd_redeem(args.get("code", ""))
    if cmd == "gen":
        return cmd_gen(args.get("prompt", ""), args.get("photo", ""),
                       args.get("out", ""), args.get("size", "1152x1536"))
    if cmd == "faceswap":
        return cmd_faceswap(args.get("avatar", ""), args.get("ref") or [], args.get("out", ""))
    print("unknown command: %s (status | gen | faceswap | redeem)" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
