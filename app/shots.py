"""Payment screenshots: rendering (for the simulation) and OCR extraction (what Kavach actually reads).

The agent never sees the World's screenshot record. It receives an image and runs
Tesseract OCR over it, so a doctored screenshot is read exactly as a human would see it.
Screens are a generic, unbranded 'UPI app' look and are watermarked SYNTHETIC.
"""
from __future__ import annotations

import io
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT = ASSETS / "DejaVuSans.ttf"
FONT_B = ASSETS / "DejaVuSans-Bold.ttf"


def _f(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(str(FONT_B if bold else FONT), size)
    except OSError:
        return ImageFont.load_default()


def render(shot: dict[str, Any]) -> bytes:
    W, H = 720, 1280
    img = Image.new("RGB", (W, H), (246, 248, 251))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 360], fill=(22, 128, 86))
    d.ellipse([W // 2 - 70, 70, W // 2 + 70, 210], fill=(255, 255, 255))
    d.line([W // 2 - 32, 142, W // 2 - 8, 168, W // 2 + 38, 112], fill=(22, 128, 86), width=12)
    d.text((W // 2, 262), shot["status_text"], font=_f(44, True), fill="white", anchor="mm")
    d.text((W // 2, 318), shot["time"], font=_f(26), fill=(220, 240, 230), anchor="mm")
    d.text((W // 2, 450), f"Rs {shot['amount']:,}", font=_f(84, True), fill=(20, 24, 33), anchor="mm")
    y = 560
    rows = [("Paid to", shot["payee_name"]), ("UPI ID", shot["payee_vpa"]), ("From", f"{shot['payer']} (bank a/c ..2291)"),
            ("UPI Ref No", shot["utr"] or "—")]
    for label, value in rows:
        d.text((70, y), label, font=_f(28), fill=(110, 118, 132))
        d.text((70, y + 40), str(value), font=_f(34, True), fill=(20, 24, 33))
        y += 120
    d.rounded_rectangle([60, H - 190, W - 60, H - 110], radius=20, outline=(22, 128, 86), width=3)
    d.text((W // 2, H - 150), "Share receipt", font=_f(30, True), fill=(22, 128, 86), anchor="mm")
    d.text((W // 2, H - 60), "SYNTHETIC DEMO SCREEN - NOT A REAL APP", font=_f(22), fill=(190, 60, 60), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def extract(png: bytes) -> dict[str, Any]:
    """OCR the image and pull out the claim it makes. Output is a *claim*, never evidence."""
    if not ocr_available():
        return {"ok": False, "engine": "none", "error": "Tesseract OCR is not installed (brew install tesseract). Ask the merchant to type the UPI Ref No."}
    import pytesseract
    img = Image.open(io.BytesIO(png)).convert("L")
    text = pytesseract.image_to_string(img, config="--psm 4")
    return parse_text(text) | {"engine": "tesseract", "raw_text": text}


_AMT = re.compile(r"(?:Rs\.?|INR|₹|%|z)\s*([\d][\d,]*(?:\.\d{1,2})?)", re.I)


def parse_text(text: str) -> dict[str, Any]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    joined = "\n".join(lines)
    out: dict[str, Any] = {"ok": True, "status_text": None, "amount": None, "utr": None, "payee_vpa": None, "payee_name": None,
                           "fields_found": []}
    if re.search(r"success|successful|paid", joined, re.I):
        out["status_text"] = "Payment Successful"
    m = _AMT.search(joined)
    if m:
        out["amount"] = int(float(m.group(1).replace(",", "")))
    for i, l in enumerate(lines):
        if re.search(r"UPI\s*Ref", l, re.I):
            m2 = re.search(r"(\d{12})", l) or (re.search(r"(\d{12})", lines[i + 1]) if i + 1 < len(lines) else None)
            if m2:
                out["utr"] = m2.group(1)
        if re.search(r"^UPI\s*ID", l, re.I) and i + 1 < len(lines):
            out["payee_vpa"] = lines[i + 1].replace(" ", "").lower()
        if re.search(r"^Paid\s*to", l, re.I) and i + 1 < len(lines):
            out["payee_name"] = lines[i + 1]
    if not out["utr"]:
        m3 = re.search(r"\b(\d{12})\b", joined)
        out["utr"] = m3.group(1) if m3 else None
    out["fields_found"] = [k for k in ("status_text", "amount", "utr", "payee_vpa", "payee_name") if out.get(k)]
    if re.search(r"ignore (all |previous )?instructions|mark (this|as) (paid|cleared)", joined, re.I):
        out["injection_detected"] = True
    return out


# ------------------------------------------------------------------ notices as photos (Freeze Reader)
def render_notice(text: str, sms: str | None = None) -> bytes:
    """A photographed police notice: off-white paper on a dark table, typed lines. SYNTHETIC."""
    W, H = 1100, 1400
    img = Image.new("RGB", (W, H), (58, 52, 46))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 40, H - 40], fill=(247, 244, 236))
    d.text((80, 80), "GOVERNMENT OF BIHAR - POLICE DEPARTMENT", font=_f(30, True), fill=(30, 30, 30))
    d.text((80, 122), "NOTICE U/S 106 BNSS (SYNTHETIC SPECIMEN)", font=_f(24), fill=(60, 60, 60))
    d.line([80, 168, W - 80, 168], fill=(120, 120, 120), width=2)
    y = 200
    for line in text.splitlines():
        if not line.strip():
            continue
        d.text((80, y), line, font=_f(27, line.startswith("SYNTHETIC")), fill=(150, 40, 40) if line.startswith("SYNTHETIC") else (25, 25, 25))
        y += 52
    if sms:
        y += 30
        d.rounded_rectangle([80, y, W - 80, y + 190], radius=18, fill=(230, 236, 245))
        words, line, yy = sms.split(), "", y + 24
        for w in words:
            if len(line) + len(w) > 62:
                d.text((104, yy), line, font=_f(24), fill=(30, 40, 60)); yy += 36; line = ""
            line += w + " "
        d.text((104, yy), line, font=_f(24), fill=(30, 40, 60))
    d.text((80, H - 110), "SYNTHETIC DEMO DOCUMENT - NOT ISSUED BY ANY AUTHORITY", font=_f(22), fill=(170, 50, 50))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def ocr_text(png: bytes) -> str:
    if not ocr_available():
        return ""
    import pytesseract
    return pytesseract.image_to_string(Image.open(io.BytesIO(png)).convert("L"), config="--psm 4")


def screenshot_png(shot: dict[str, Any]) -> bytes:
    return shot["png"] if shot.get("png") else render(shot)
