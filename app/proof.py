"""Signed evidence packs.

The final PDF bytes are hashed (SHA-256); a canonical manifest binding case, facts, PDF hash,
issue time, expiry and key id is signed with Ed25519. The verifier checks the signature AND
recomputes the hash of the PDF it is given. Editing one digit in the PDF breaks it.

What a VALID result proves: this PDF is byte-identical to what this Kavach instance issued.
It does NOT prove the sale was genuine, the merchant is innocent, or that Paytm signed it
(the demo key is a local key, not a Paytm key).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import qrcode
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
INSTANCE = ROOT / "instance"
KEY = INSTANCE / "kavach-demo-signing-key.pem"
PACKS = INSTANCE / "packs"
KEY_ID = "kavach-demo-ed25519-1"


def _key() -> Ed25519PrivateKey:
    INSTANCE.mkdir(exist_ok=True)
    if KEY.exists():
        return serialization.load_pem_private_key(KEY.read_bytes(), password=None)  # type: ignore[return-value]
    k = Ed25519PrivateKey.generate()
    KEY.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    KEY.chmod(0o600)
    return k


def public_key() -> Ed25519PublicKey:
    return _key().public_key()


def fingerprint() -> str:
    raw = public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


_FONT_OK = False


def _fonts() -> str:
    global _FONT_OK
    if not _FONT_OK:
        pdfmetrics.registerFont(TTFont("Noto", str(ROOT / "assets" / "NotoSansDevanagari.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu", str(ROOT / "assets" / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuB", str(ROOT / "assets" / "DejaVuSans-Bold.ttf")))
        _FONT_OK = True
    return "DejaVu"


def build_pdf(case: dict[str, Any], verify_url: str) -> bytes:
    _fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Kavach evidence pack {case['case_id']}", author="Kavach (synthetic demo)",
                            creator="Kavach", producer="Kavach", subject="Synthetic", keywords="synthetic")
    s = lambda size=9.5, font="DejaVu", color=colors.HexColor("#1b2230"), lead=None: ParagraphStyle(
        "x", fontName=font, fontSize=size, leading=lead or size * 1.38, textColor=color)
    hi = ParagraphStyle("hi", fontName="Noto", fontSize=10, leading=15, textColor=colors.HexColor("#1b2230"), shaping=1)
    story: list[Any] = [
        Paragraph("SYNTHETIC DEMO — NOT A PAYTM DOCUMENT · NOT LEGAL ADVICE", s(8, "DejaVuB", colors.HexColor("#b42318"))),
        Spacer(1, 4),
        Paragraph(f"Kavach evidence pack · {case['case_id']}", s(17, "DejaVuB")),
        Paragraph(f"Merchant: {case['merchant']} · Issued {case['issued_at']}", s(9, color=colors.HexColor("#5b6474"))),
        Spacer(1, 10),
        Paragraph("Disputed payment named in the notice", s(11, "DejaVuB")),
    ]
    cell = s(8.5)
    rows = [["Fact", "Value", "Source", "Tier"]] + [[Paragraph(f["label"], cell), Paragraph(f["value"], cell), Paragraph(f["source"], cell), f["tier"]] for f in case["facts"]]
    t = Table(rows, colWidths=[42 * mm, 46 * mm, 62 * mm, 14 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "DejaVu", 8.5), ("FONT", (0, 0), (-1, 0), "DejaVuB", 8.5),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d1dc")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [t, Spacer(1, 6),
              Paragraph("T1 = Paytm system record (synthetic here) · T2 = independent supporting signal · T3 = merchant's own statement (never upgraded).", s(8, color=colors.HexColor("#5b6474"))),
              Spacer(1, 10), Paragraph("SOP route (MHA/I4C SOP for NCRP-CFCFRMS, 02.01.2026)", s(11, "DejaVuB"))]
    for r in case["route"]:
        story.append(Paragraph(f"<b>{r['id']} · para {r['para']}</b> — {r['next']}", s(9)))
    story += [Spacer(1, 10), Paragraph("What this pack does not establish", s(11, "DejaVuB")),
              Paragraph("It does not establish that the merchant is innocent, that the payer acted lawfully or unlawfully, or that "
                        "the hold is improper. Payer identity is masked because the payer may be a fraud victim. Decisions on the hold "
                        "belong to the bank and the investigating officer.", s(9)),
              Spacer(1, 10), Paragraph("शाखा के लिए (Branch kit)", ParagraphStyle("h", fontName="Noto", fontSize=11, leading=16, shaping=1)),
              Paragraph("1. बैंक शाखा में लिखित शिकायत दें और दिनांक वाली पावती (acknowledgement) लें।", hi),
              Paragraph("2. यह पैक दिखाएँ: विवादित भुगतान " + case["disputed_amount_text"] + " का है।", hi),
              Paragraph("3. SOP के अनुसार बैंक को 7 दिन के भीतर शिकायत आगे भेजनी है। कोई भी पैसे माँगे तो न दें।", hi),
              Spacer(1, 12)]
    qr = qrcode.make(verify_url)
    qb = io.BytesIO(); qr.save(qb, "PNG"); qb.seek(0)
    story.append(Table([[Image(qb, 30 * mm, 30 * mm), Paragraph(
        f"Verify this pack: scan the QR or open<br/>{verify_url}<br/>Demo signing key fingerprint (SHA-256):<br/>{fingerprint()[:32]}<br/>{fingerprint()[32:]}",
        s(8, color=colors.HexColor("#5b6474")))]], colWidths=[34 * mm, 130 * mm]))
    doc.build(story)
    return buf.getvalue()


def issue(case: dict[str, Any], base_url: str) -> dict[str, Any]:
    PACKS.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(9)
    verify_url = f"{base_url.rstrip('/')}/verify/{token}"
    pdf = build_pdf(case, verify_url)
    issued = datetime.fromisoformat(case["issued_at_iso"])
    manifest = {"v": 1, "token": token, "case_id": case["case_id"], "key_id": KEY_ID, "issued_at": issued.isoformat(),
                "expires_at": (issued + timedelta(days=120)).isoformat(), "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                "facts": {f["label"]: f["value"] for f in case["facts"] if f["tier"] == "T1"}, "provenance": "SYNTHETIC_DEMO"}
    sig = _key().sign(_canon(manifest))
    rec = {"manifest": manifest, "signature": base64.b64encode(sig).decode(), "revoked": False, "case": case, "verify_url": verify_url}
    (PACKS / f"{token}.json").write_text(json.dumps(rec, indent=1))
    (PACKS / f"{token}.pdf").write_bytes(pdf)
    return {"token": token, "verify_url": verify_url, "pdf_sha256": manifest["pdf_sha256"], "pdf_path": str(PACKS / f"{token}.pdf")}


def load(token: str) -> tuple[dict | None, bytes | None]:
    j, p = PACKS / f"{token}.json", PACKS / f"{token}.pdf"
    if not j.exists():
        return None, None
    return json.loads(j.read_text()), (p.read_bytes() if p.exists() else None)


def verify(token: str, pdf: bytes | None, now: datetime, expected_case: str | None = None) -> dict[str, Any]:
    rec, stored = load(token)
    if not rec:
        return {"result": "UNKNOWN", "why": "No pack with this token was issued by this Kavach instance."}
    m = rec["manifest"]
    try:
        public_key().verify(base64.b64decode(rec["signature"]), _canon(m))
    except InvalidSignature:
        return {"result": "INVALID_SIGNATURE", "why": "The manifest signature does not verify against the pinned demo key."}
    if rec.get("revoked"):
        return {"result": "REVOKED", "why": "This pack was revoked by its issuer."}
    if expected_case and expected_case != m["case_id"]:
        return {"result": "WRONG_CASE", "why": f"This pack belongs to {m['case_id']}, not {expected_case}."}
    if now > datetime.fromisoformat(m["expires_at"]):
        return {"result": "EXPIRED", "why": "This pack is past its expiry."}
    body = pdf if pdf is not None else stored
    actual = hashlib.sha256(body or b"").hexdigest()
    if actual != m["pdf_sha256"]:
        return {"result": "TAMPERED", "why": "The PDF's bytes do not match the signed hash. It was changed after issue.",
                "expected": m["pdf_sha256"], "actual": actual, "manifest": m}
    return {"result": "VALID", "why": "Signature verifies and the PDF is byte-identical to the issued pack.", "manifest": m,
            "fingerprint": fingerprint(), "limits": "Proves integrity against this demo key only. Not innocence, not a Paytm signature, not admissibility."}


def tampered_copy(token: str) -> bytes | None:
    """What a forger would do: re-render the pack with one digit of the disputed amount changed,
    keeping the same QR/verify link. Visibly different, and the hash no longer matches."""
    rec, _pdf = load(token)
    if not rec or "case" not in rec:
        return None
    case = json.loads(json.dumps(rec["case"]))
    for f in case["facts"]:
        if f["label"].startswith("Amount"):
            f["value"] = f["value"].replace("2,4", "2,9", 1) if "2,4" in f["value"] else f["value"].replace("0", "9", 1)
    case["disputed_amount_text"] = case["disputed_amount_text"].replace("2,4", "2,9", 1)
    return build_pdf(case, rec["verify_url"])
