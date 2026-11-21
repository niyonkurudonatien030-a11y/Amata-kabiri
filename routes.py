"""All JSON API routes (/api/...). Business rules live here, so read this file to learn how AmataShield works."""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_file, session

from . import database as db
from . import schemas
from .ai import gemini, prompts
from .auth import ApiError, hash_password, login_required, verify_login

bp = Blueprint("api", __name__, url_prefix="/api")

LIVE = ("agreed", "in_transit", "delivered", "received")        # states where work/evidence/payment happen
EVIDENCE_OK = LIVE + ("completed", "disputed")
SELLER_ROLES = ("farmer", "coop_admin")


# ----------------------------------------------------------------- helpers
def body():
    return request.get_json(silent=True) or {}


def validated(fn, *args):
    try:
        return fn(*args)
    except schemas.ValidationError as exc:
        raise ApiError(str(exc), 400)


def audit(deal_id, user_id, action, detail=None):
    db.execute("INSERT INTO audit_log (deal_id,user_id,action,detail,created_at) VALUES (?,?,?,?,?)",
               (deal_id, user_id, action, detail, db.now()))


def user_by_id(uid):
    return db.one("SELECT * FROM users WHERE id = ?", (uid,)) if uid else None


def public_user(u, reveal_phone=False):
    if not u:
        return None
    out = {"id": u["id"], "full_name": u["full_name"], "role": u["role"],
           "district": u["district"], "organisation": u["organisation"]}
    if reveal_phone:
        out["phone"] = u["phone"]
    return out


def own_user(u):
    return {k: u[k] for k in ("id", "role", "full_name", "phone", "email", "district", "organisation", "created_at")}


def load_deal(deal_id):
    deal = db.one("SELECT * FROM deals WHERE id = ?", (deal_id,))
    if not deal:
        raise ApiError("Transaction not found", 404)
    return deal


def role_in_deal(deal, user):
    if user["id"] == deal["seller_id"]:
        return "seller"
    if user["id"] == deal["buyer_id"]:
        return "buyer"
    if user["id"] == deal["driver_id"]:
        return "driver"
    if user["role"] == "admin":
        return "oversight"
    if user["role"] == "coop_admin" and user["district"] and user["district"] == deal["district"]:
        return "oversight"
    return None


def require_access(deal, user):
    role = role_in_deal(deal, user)
    if not role:
        raise ApiError("You are not part of this transaction", 403)
    return role


def open_dispute_for(deal_id):
    return db.one("SELECT * FROM disputes WHERE deal_id = ? AND status = 'open'", (deal_id,))


def set_deal(deal_id, **fields):
    fields["updated_at"] = db.now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE deals SET {cols} WHERE id = ?", (*fields.values(), deal_id))


def maybe_complete(deal_id):
    d = load_deal(deal_id)
    if d["status"] == "received" and d["payment_status"] == "confirmed":
        set_deal(deal_id, status="completed")
        audit(deal_id, None, "deal_completed", "Milk received and payment confirmed by both parties")


def allowed_actions(deal, role, user):
    a, s = [], deal["status"]
    if role is None and s == "open" and deal["creator_id"] != user["id"]:
        if (deal["deal_type"] == "sell" and user["role"] == "buyer") or \
           (deal["deal_type"] == "buy" and user["role"] in SELLER_ROLES):
            a.append("join")
    if role in ("seller", "buyer"):
        creator = user["id"] == deal["creator_id"]
        if s == "pending_acceptance":
            a += ["confirm", "decline"] if creator else ["withdraw"]
        if s in ("open", "pending_acceptance", "agreed"):
            a.append("cancel")
        if s == "agreed" and not deal["driver_id"]:
            a.append("approve_driver")
        if s in EVIDENCE_OK:
            a.append("add_evidence")
        if role == "seller" and s == "agreed":
            a.append("pickup")
        if role == "seller" and s == "in_transit" and not deal["driver_id"]:
            a.append("deliver")
        if role == "buyer" and s == "in_transit":
            a.append("deliver")
        if role == "buyer" and s == "delivered":
            a.append("receive")
        if role == "buyer" and s in LIVE and deal["payment_status"] in ("unconfirmed", "disputed"):
            a.append("report_payment")
        if s in LIVE + ("completed",) and not open_dispute_for(deal["id"]):
            a.append("open_dispute")
    if role == "driver":
        if s in EVIDENCE_OK:
            a.append("add_evidence")
        if s == "agreed":
            a.append("pickup")
        if s == "in_transit":
            a.append("deliver")
    if role is None and user["role"] == "driver" and s == "agreed" and not deal["driver_id"]:
        if not db.one("SELECT 1 FROM driver_applications WHERE deal_id=? AND driver_id=?", (deal["id"], user["id"])):
            a.append("apply_driver")
    if role == "oversight" and open_dispute_for(deal["id"]):
        a.append("mediate")
    return a


def deal_dict(deal, user, detail=False):
    role = role_in_deal(deal, user)
    reveal = role is not None
    out = {k: deal[k] for k in (
        "id", "public_id", "deal_type", "creator_id", "litres", "price_per_litre", "total_value", "location",
        "district", "delivery_at", "quality_requirements", "terms", "status", "payment_status",
        "seller_accepted_at", "buyer_accepted_at", "terms_hash", "driver_fee", "created_at", "updated_at")}
    out["seller"] = public_user(user_by_id(deal["seller_id"]), reveal)
    out["buyer"] = public_user(user_by_id(deal["buyer_id"]), reveal)
    out["driver"] = public_user(user_by_id(deal["driver_id"]), reveal)
    out["my_role"] = role
    out["actions"] = allowed_actions(deal, role, user)
    if detail:
        did = deal["id"]
        out["timeline"] = db.query(
            "SELECT a.action, a.detail, a.created_at, u.full_name AS who FROM audit_log a "
            "LEFT JOIN users u ON u.id = a.user_id WHERE a.deal_id = ? ORDER BY a.id", (did,))
        out["payments"] = db.query(
            "SELECT p.*, u.full_name AS reporter FROM payments p JOIN users u ON u.id=p.reported_by "
            "WHERE p.deal_id=? ORDER BY p.id", (did,))
        out["disputes"] = db.query("SELECT id, status, reason, created_at, final_outcome FROM disputes WHERE deal_id=? ORDER BY id", (did,))
        if "approve_driver" in out["actions"]:
            out["driver_applications"] = db.query(
                "SELECT a.id, a.proposed_fee, a.message, a.status, u.full_name, u.phone, u.district "
                "FROM driver_applications a JOIN users u ON u.id=a.driver_id WHERE a.deal_id=? AND a.status='pending'", (did,))
    return out


def terms_fingerprint(d):
    keys = ("deal_type", "seller_id", "buyer_id", "litres", "price_per_litre", "total_value",
            "location", "delivery_at", "quality_requirements", "terms")
    return hashlib.sha256(json.dumps({k: d[k] for k in keys}, sort_keys=True).encode()).hexdigest()


# ----------------------------------------------------------------- errors
@bp.errorhandler(ApiError)
def handle_api_error(exc):
    return jsonify(error=exc.message), exc.status


# ----------------------------------------------------------------- auth & profile
@bp.post("/auth/register")
def register():
    data = validated(schemas.registration, body())
    if db.one("SELECT 1 FROM users WHERE phone = ?", (data["phone"],)):
        raise ApiError("This phone number is already registered", 409)
    uid = db.execute(
        "INSERT INTO users (role,full_name,phone,email,password_hash,district,organisation,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (data["role"], data["full_name"], data["phone"], data["email"], hash_password(data["password"]),
         data["district"], data["organisation"], db.now()))
    session.clear()
    session["uid"] = uid
    return jsonify(user=own_user(user_by_id(uid))), 201


@bp.post("/auth/login")
def login():
    d = body()
    phone = validated(schemas.phone, d.get("phone"))
    user = verify_login(phone, d.get("password"))
    session.clear()
    session["uid"] = user["id"]
    return jsonify(user=own_user(user))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/auth/me")
@login_required()
def me(user):
    return jsonify(user=own_user(user), ai_enabled=gemini.configured())


@bp.patch("/auth/me")
@login_required()
def update_me(user):
    d = body()
    name = validated(schemas.text, d, "full_name", False, 120) or user["full_name"]
    email = validated(schemas.text, d, "email", False, 120)
    district = validated(schemas.text, d, "district", False, 60)
    org = validated(schemas.text, d, "organisation", False, 120)
    db.execute("UPDATE users SET full_name=?, email=?, district=?, organisation=? WHERE id=?",
               (name, email, district, org, user["id"]))
    return jsonify(user=own_user(user_by_id(user["id"])))


@bp.post("/auth/password")
@login_required()
def change_password(user):
    from werkzeug.security import check_password_hash
    d = body()
    if not check_password_hash(user["password_hash"], d.get("current_password") or ""):
        raise ApiError("Current password is wrong", 403)
    new = validated(schemas.password, d.get("new_password"))
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), user["id"]))
    return jsonify(ok=True)


# ----------------------------------------------------------------- deals
@bp.post("/deals")
@login_required("farmer", "coop_admin", "buyer")
def create_deal(user):
    data = validated(schemas.deal, body())
    if data["deal_type"] == "sell" and user["role"] not in SELLER_ROLES:
        raise ApiError("Only farmers or cooperatives can post milk for sale", 403)
    if data["deal_type"] == "buy" and user["role"] != "buyer":
        raise ApiError("Only buyers can post a purchase request", 403)
    data["district"] = data["district"] or user["district"]
    public_id = "AS-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + secrets.token_hex(2).upper()
    sell = data["deal_type"] == "sell"
    ts = db.now()
    did = db.execute(
        "INSERT INTO deals (public_id,deal_type,creator_id,seller_id,buyer_id,litres,price_per_litre,total_value,location,"
        "district,delivery_at,quality_requirements,terms,status,seller_accepted_at,buyer_accepted_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?,?,?)",
        (public_id, data["deal_type"], user["id"], user["id"] if sell else None, None if sell else user["id"],
         data["litres"], data["price_per_litre"], data["total_value"], data["location"], data["district"],
         data["delivery_at"], data["quality_requirements"], data["terms"],
         ts if sell else None, None if sell else ts, ts, ts))
    audit(did, user["id"], "deal_posted", f"{data['litres']:g} L at {data['price_per_litre']:g} RWF/L")
    return jsonify(deal=deal_dict(load_deal(did), user, True)), 201


@bp.get("/deals")
@login_required()
def my_deals(user):
    status = request.args.get("status")
    if user["role"] == "admin":
        where, args = "1=1", []
    elif user["role"] == "coop_admin":
        where = "(seller_id=? OR buyer_id=? OR driver_id=? OR district=?)"
        args = [user["id"], user["id"], user["id"], user["district"]]
    else:
        where, args = "(creator_id=? OR seller_id=? OR buyer_id=? OR driver_id=?)", [user["id"]] * 4
    if status:
        where += " AND status = ?"
        args.append(status)
    rows = db.query(f"SELECT * FROM deals WHERE {where} ORDER BY updated_at DESC LIMIT 200", args)
    return jsonify(deals=[deal_dict(r, user) for r in rows])


@bp.get("/deals/open")
@login_required()
def market(user):
    """Marketplace: open posts from other users, with the filters sketched in the project notebook."""
    where, args = ["status='open'", "creator_id != ?"], [user["id"]]
    if user["role"] == "buyer":
        where.append("deal_type='sell'")
    elif user["role"] in SELLER_ROLES:
        where.append("deal_type='buy'")
    elif request.args.get("deal_type") in ("sell", "buy"):
        where.append("deal_type=?")
        args.append(request.args["deal_type"])
    if request.args.get("district"):
        where.append("district = ?")
        args.append(request.args["district"])
    for key, col, op in (("min_litres", "litres", ">="), ("max_litres", "litres", "<="),
                         ("min_price", "price_per_litre", ">="), ("max_price", "price_per_litre", "<=")):
        if request.args.get(key):
            try:
                args.append(float(request.args[key]))
            except ValueError:
                raise ApiError(f"Invalid {key}")
            where.append(f"{col} {op} ?")
    order = {"price_asc": "price_per_litre ASC", "price_desc": "price_per_litre DESC",
             "litres_desc": "litres DESC"}.get(request.args.get("sort"), "created_at DESC")
    rows = db.query(f"SELECT * FROM deals WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 100", args)
    return jsonify(deals=[deal_dict(r, user) for r in rows])


@bp.get("/deals/delivery-jobs")
@login_required("driver")
def delivery_jobs(user):
    rows = db.query("SELECT * FROM deals WHERE status='agreed' AND driver_id IS NULL ORDER BY delivery_at, created_at LIMIT 100")
    return jsonify(deals=[deal_dict(r, user) for r in rows])


@bp.get("/deals/<int:deal_id>")
@login_required()
def get_deal(user, deal_id):
    deal = load_deal(deal_id)
    role = role_in_deal(deal, user)
    if role is None and deal["status"] != "open" and not (user["role"] == "driver" and deal["status"] == "agreed"):
        raise ApiError("You are not part of this transaction", 403)
    return jsonify(deal=deal_dict(deal, user, detail=role is not None))


@bp.post("/deals/<int:deal_id>/join")
@login_required("farmer", "coop_admin", "buyer")
def join_deal(user, deal_id):
    deal = load_deal(deal_id)
    if deal["status"] != "open" or deal["creator_id"] == user["id"]:
        raise ApiError("This post is no longer available", 409)
    ts = db.now()
    if deal["deal_type"] == "sell":
        if user["role"] != "buyer":
            raise ApiError("Only buyers can accept a sale post", 403)
        set_deal(deal_id, buyer_id=user["id"], buyer_accepted_at=ts, status="pending_acceptance")
    else:
        if user["role"] not in SELLER_ROLES:
            raise ApiError("Only farmers or cooperatives can answer a purchase request", 403)
        set_deal(deal_id, seller_id=user["id"], seller_accepted_at=ts, status="pending_acceptance")
    audit(deal_id, user["id"], "counterparty_accepted_terms", "Joined the post and accepted the displayed terms")
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


@bp.post("/deals/<int:deal_id>/confirm")
@login_required()
def confirm_deal(user, deal_id):
    deal = load_deal(deal_id)
    if deal["creator_id"] != user["id"] or deal["status"] != "pending_acceptance":
        raise ApiError("Nothing to confirm", 409)
    ts = db.now()
    fields = {"status": "agreed"}
    fields["seller_accepted_at" if deal["deal_type"] == "sell" else "buyer_accepted_at"] = ts
    set_deal(deal_id, **fields)
    d = load_deal(deal_id)
    set_deal(deal_id, terms_hash=terms_fingerprint(d))
    audit(deal_id, user["id"], "agreement_confirmed", "Both parties accepted. Terms fingerprint stored.")
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


@bp.post("/deals/<int:deal_id>/decline")
@bp.post("/deals/<int:deal_id>/withdraw")
@login_required()
def decline_deal(user, deal_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    if deal["status"] != "pending_acceptance" or role not in ("seller", "buyer"):
        raise ApiError("Nothing to decline", 409)
    if deal["deal_type"] == "sell":
        set_deal(deal_id, buyer_id=None, buyer_accepted_at=None, status="open")
    else:
        set_deal(deal_id, seller_id=None, seller_accepted_at=None, status="open")
    audit(deal_id, user["id"], "counterparty_removed", "Post returned to the marketplace")
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


@bp.post("/deals/<int:deal_id>/cancel")
@login_required()
def cancel_deal(user, deal_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    if role not in ("seller", "buyer") or deal["status"] not in ("open", "pending_acceptance", "agreed"):
        raise ApiError("This transaction can no longer be cancelled", 409)
    set_deal(deal_id, status="cancelled")
    audit(deal_id, user["id"], "deal_cancelled", (body().get("reason") or "")[:300])
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


# ----------------------------------------------------------------- drivers & stages
@bp.post("/deals/<int:deal_id>/drivers")
@login_required("driver")
def apply_driver(user, deal_id):
    deal = load_deal(deal_id)
    if deal["status"] != "agreed" or deal["driver_id"]:
        raise ApiError("This delivery job is not open", 409)
    d = body()
    fee = validated(schemas.number, d, "proposed_fee", 0.0, False)
    msg = validated(schemas.text, d, "message", False, 300)
    try:
        db.execute("INSERT INTO driver_applications (deal_id,driver_id,proposed_fee,message,created_at) VALUES (?,?,?,?,?)",
                   (deal_id, user["id"], fee, msg, db.now()))
    except Exception:
        raise ApiError("You already applied for this job", 409)
    audit(deal_id, user["id"], "driver_applied", f"Proposed fee: {fee if fee is not None else 'not stated'}")
    return jsonify(ok=True), 201


@bp.post("/deals/<int:deal_id>/drivers/<int:app_id>/approve")
@login_required("farmer", "coop_admin", "buyer")
def approve_driver(user, deal_id, app_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    if role not in ("seller", "buyer") or deal["status"] != "agreed" or deal["driver_id"]:
        raise ApiError("A driver cannot be assigned now", 409)
    app_row = db.one("SELECT * FROM driver_applications WHERE id=? AND deal_id=? AND status='pending'", (app_id, deal_id))
    if not app_row:
        raise ApiError("Application not found", 404)
    db.execute("UPDATE driver_applications SET status='approved' WHERE id=?", (app_id,))
    db.execute("UPDATE driver_applications SET status='rejected' WHERE deal_id=? AND id != ? AND status='pending'", (deal_id, app_id))
    set_deal(deal_id, driver_id=app_row["driver_id"], driver_fee=app_row["proposed_fee"])
    audit(deal_id, user["id"], "driver_assigned", f"Driver #{app_row['driver_id']} approved")
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


@bp.post("/deals/<int:deal_id>/stage")
@login_required()
def stage(user, deal_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    name = body().get("stage")
    note = (body().get("note") or "")[:300]
    allowed = allowed_actions(deal, role, user)
    if name not in ("pickup", "deliver", "receive") or name not in allowed:
        raise ApiError("This step is not available right now", 409)
    if name == "pickup":
        has_quality = db.one("SELECT 1 FROM evidence WHERE deal_id=? AND category IN ('lactometer_photo','quality_measurement')", (deal_id,))
        if not has_quality:
            raise ApiError("Add a lactometer photo or quality measurement before pickup", 422)
        set_deal(deal_id, status="in_transit")
        audit(deal_id, user["id"], "pickup_recorded", note or "Milk collected; quality evidence on file")
    elif name == "deliver":
        set_deal(deal_id, status="delivered")
        audit(deal_id, user["id"], "arrival_recorded", note or "Milk arrived at the buyer")
    else:
        set_deal(deal_id, status="received")
        audit(deal_id, user["id"], "buyer_received", note or "Buyer checked the milk and accepted the delivery")
        maybe_complete(deal_id)
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True))


# ----------------------------------------------------------------- evidence
def _file_kind(head):
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if head.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    return None, None


@bp.post("/deals/<int:deal_id>/evidence")
@login_required()
def add_evidence(user, deal_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    if role == "oversight" or deal["status"] not in EVIDENCE_OK:
        raise ApiError("Evidence cannot be added in the current state", 409)
    category = request.form.get("category", "")
    if category not in schemas.EVIDENCE_CATEGORIES:
        raise ApiError("Invalid evidence category")
    if category == "payment_receipt" and role == "driver":
        raise ApiError("Drivers cannot submit payment receipts", 403)
    upload = request.files.get("file")
    measurement = (request.form.get("measurement") or "").strip()[:60] or None
    note = (request.form.get("note") or "").strip()[:500] or None
    if not upload and not measurement:
        raise ApiError("Attach a file or enter a measurement")
    stored = original = mime = digest = None
    size = 0
    if upload:
        data = upload.read()
        mime, ext = _file_kind(data[:16])
        if not mime:
            raise ApiError("Only JPG, PNG, WEBP or PDF files are accepted")
        stored = secrets.token_hex(16) + ext
        with open(os.path.join(current_app.config["UPLOAD_DIR"], stored), "wb") as fh:
            fh.write(data)
        original = os.path.basename(upload.filename or "capture")[:120]
        size, digest = len(data), hashlib.sha256(data).hexdigest()
    eid = db.execute(
        "INSERT INTO evidence (deal_id,submitted_by,category,stored_name,original_name,mime_type,size_bytes,sha256,note,measurement,captured_at,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (deal_id, user["id"], category, stored or "", original or "(typed measurement)", mime or "text/plain", size,
         digest or "", note, measurement, (request.form.get("captured_at") or "")[:40] or None, db.now()))
    audit(deal_id, user["id"], "evidence_added", f"{category} (#{eid})")
    return jsonify(evidence=evidence_dict(db.one("SELECT * FROM evidence WHERE id=?", (eid,)))), 201


def evidence_dict(e):
    out = {k: e[k] for k in ("id", "deal_id", "category", "original_name", "mime_type", "size_bytes", "sha256",
                              "note", "measurement", "captured_at", "created_at")}
    out["has_file"] = bool(e["stored_name"])
    u = user_by_id(e["submitted_by"])
    out["submitted_by"] = {"id": u["id"], "full_name": u["full_name"], "role": u["role"]}
    return out


@bp.get("/deals/<int:deal_id>/evidence")
@login_required()
def list_evidence(user, deal_id):
    deal = load_deal(deal_id)
    require_access(deal, user)
    rows = db.query("SELECT * FROM evidence WHERE deal_id=? ORDER BY id", (deal_id,))
    return jsonify(evidence=[evidence_dict(r) for r in rows])


@bp.get("/evidence/<int:evidence_id>/file")
@login_required()
def evidence_file(user, evidence_id):
    e = db.one("SELECT * FROM evidence WHERE id=?", (evidence_id,))
    if not e or not e["stored_name"]:
        raise ApiError("File not found", 404)
    require_access(load_deal(e["deal_id"]), user)
    return send_file(os.path.join(current_app.config["UPLOAD_DIR"], e["stored_name"]), mimetype=e["mime_type"],
                     download_name=e["original_name"])


# ----------------------------------------------------------------- payments (records only; no money moves here)
@bp.post("/deals/<int:deal_id>/payments")
@login_required("buyer")
def report_payment(user, deal_id):
    deal = load_deal(deal_id)
    if role_in_deal(deal, user) != "buyer" or "report_payment" not in allowed_actions(deal, "buyer", user):
        raise ApiError("A payment cannot be reported now", 409)
    data = validated(schemas.payment, body())
    if data["evidence_id"]:
        ev = db.one("SELECT deal_id FROM evidence WHERE id=?", (data["evidence_id"],))
        if not ev or ev["deal_id"] != deal_id:
            raise ApiError("Evidence does not belong to this transaction")
    pid = db.execute(
        "INSERT INTO payments (deal_id,reported_by,amount,method,reference,evidence_id,created_at) VALUES (?,?,?,?,?,?,?)",
        (deal_id, user["id"], data["amount"], data["method"], data["reference"], data["evidence_id"], db.now()))
    set_deal(deal_id, payment_status="reported")
    audit(deal_id, user["id"], "payment_reported", f"{data['amount']:g} RWF via {data['method']} (payment #{pid}) - self-reported by buyer")
    return jsonify(deal=deal_dict(load_deal(deal_id), user, True)), 201


def _payment_for_seller(user, payment_id):
    p = db.one("SELECT * FROM payments WHERE id=?", (payment_id,))
    if not p:
        raise ApiError("Payment not found", 404)
    deal = load_deal(p["deal_id"])
    if role_in_deal(deal, user) != "seller" or p["status"] != "reported":
        raise ApiError("You cannot respond to this payment", 409)
    return p, deal


@bp.post("/payments/<int:payment_id>/confirm")
@login_required()
def confirm_payment(user, payment_id):
    p, deal = _payment_for_seller(user, payment_id)
    db.execute("UPDATE payments SET status='confirmed', responded_by=?, responded_at=?, response_note=? WHERE id=?",
               (user["id"], db.now(), (body().get("note") or "")[:300], payment_id))
    set_deal(deal["id"], payment_status="confirmed")
    audit(deal["id"], user["id"], "payment_confirmed", f"Seller confirmed receiving payment #{payment_id}")
    maybe_complete(deal["id"])
    return jsonify(deal=deal_dict(load_deal(deal["id"]), user, True))


@bp.post("/payments/<int:payment_id>/reject")
@login_required()
def reject_payment(user, payment_id):
    p, deal = _payment_for_seller(user, payment_id)
    reason = validated(schemas.text, body(), "reason", True, 500)
    db.execute("UPDATE payments SET status='disputed', responded_by=?, responded_at=?, response_note=? WHERE id=?",
               (user["id"], db.now(), reason, payment_id))
    set_deal(deal["id"], payment_status="disputed")
    audit(deal["id"], user["id"], "payment_disputed", f"Seller did not accept payment #{payment_id}: {reason}")
    _open_dispute(load_deal(deal["id"]), user, "Payment not accepted by seller: " + reason)
    return jsonify(deal=deal_dict(load_deal(deal["id"]), user, True))


# ----------------------------------------------------------------- disputes
def _open_dispute(deal, user, reason):
    existing = open_dispute_for(deal["id"])
    if existing:
        return existing["id"]
    if deal["status"] != "disputed":
        set_deal(deal["id"], status_before_dispute=deal["status"], status="disputed")
    did = db.execute("INSERT INTO disputes (deal_id,opened_by,reason,created_at) VALUES (?,?,?,?)",
                     (deal["id"], user["id"], reason, db.now()))
    audit(deal["id"], user["id"], "dispute_opened", reason[:300])
    return did


@bp.post("/deals/<int:deal_id>/disputes")
@login_required()
def open_dispute(user, deal_id):
    deal = load_deal(deal_id)
    role = require_access(deal, user)
    if role not in ("seller", "buyer") or "open_dispute" not in allowed_actions(deal, role, user):
        raise ApiError("A dispute cannot be opened now", 409)
    reason = validated(schemas.text, body(), "reason", True, 1500)
    did = _open_dispute(deal, user, reason)
    return jsonify(dispute_id=did), 201


def load_dispute(dispute_id, user):
    disp = db.one("SELECT * FROM disputes WHERE id=?", (dispute_id,))
    if not disp:
        raise ApiError("Dispute not found", 404)
    deal = load_deal(disp["deal_id"])
    return disp, deal, require_access(deal, user)


@bp.get("/disputes/<int:dispute_id>")
@login_required()
def get_dispute(user, dispute_id):
    disp, deal, role = load_dispute(dispute_id, user)
    events = db.query(
        "SELECT e.*, u.full_name, u.role AS user_role FROM dispute_events e JOIN users u ON u.id=e.user_id "
        "WHERE e.dispute_id=? ORDER BY e.id", (dispute_id,))
    evidence = db.query("SELECT * FROM evidence WHERE deal_id=? ORDER BY id", (deal["id"],))
    return jsonify(dispute=disp, my_role=role, events=events, deal=deal_dict(deal, user),
                   evidence=[evidence_dict(e) for e in evidence])


@bp.post("/disputes/<int:dispute_id>/events")
@login_required()
def dispute_event(user, dispute_id):
    disp, deal, role = load_dispute(dispute_id, user)
    if disp["status"] != "open":
        raise ApiError("This dispute is already resolved", 409)
    d = body()
    kind = d.get("kind")
    if kind not in ("comment", "proposal", "agree", "evidence"):
        raise ApiError("Invalid event type")
    if role == "driver":
        raise ApiError("Drivers cannot take part in the dispute", 403)
    text_body = validated(schemas.text, d, "body", kind not in ("agree",), 1500)
    evidence_id = d.get("evidence_id")
    if kind == "evidence":
        ev = db.one("SELECT deal_id FROM evidence WHERE id=?", (evidence_id,)) if evidence_id else None
        if not ev or ev["deal_id"] != deal["id"]:
            raise ApiError("Choose evidence from this transaction")
    ref = None
    if kind == "agree":
        if role not in ("seller", "buyer"):
            raise ApiError("Only the parties can agree to a proposal", 403)
        prop = db.one("SELECT * FROM dispute_events WHERE id=? AND dispute_id=? AND kind='proposal'", (d.get("ref_event_id"), dispute_id))
        if not prop:
            raise ApiError("Choose a proposal to agree to")
        if prop["user_id"] == user["id"]:
            raise ApiError("The other party must agree to your proposal", 409)
        ref = prop["id"]
    db.execute("INSERT INTO dispute_events (dispute_id,user_id,kind,body,evidence_id,ref_event_id,created_at) VALUES (?,?,?,?,?,?,?)",
               (dispute_id, user["id"], kind, text_body, evidence_id if kind == "evidence" else None, ref, db.now()))
    audit(deal["id"], user["id"], f"dispute_{kind}", (text_body or "")[:200])
    if kind == "agree":
        _resolve(disp, deal, user, prop["body"], "Both parties agreed")
    return jsonify(ok=True), 201


def _resolve(disp, deal, user, outcome, how):
    db.execute("UPDATE disputes SET status='resolved', final_outcome=?, resolved_by=?, resolved_at=? WHERE id=?",
               (outcome, user["id"], db.now(), disp["id"]))
    db.execute("INSERT INTO dispute_events (dispute_id,user_id,kind,body,created_at) VALUES (?,?,'resolution',?,?)",
               (disp["id"], user["id"], f"{how}: {outcome}", db.now()))
    back = deal["status_before_dispute"] or "agreed"
    fields = {"status": back, "status_before_dispute": None}
    if deal["payment_status"] == "disputed":
        fields["payment_status"] = "unconfirmed"   # parties must record any new payment explicitly
    set_deal(deal["id"], **fields)
    audit(deal["id"], user["id"], "dispute_resolved", f"{how}: {outcome}"[:300])
    maybe_complete(deal["id"])


@bp.post("/disputes/<int:dispute_id>/resolve")
@login_required("coop_admin", "admin")
def mediator_resolve(user, dispute_id):
    disp, deal, role = load_dispute(dispute_id, user)
    if disp["status"] != "open":
        raise ApiError("This dispute is already resolved", 409)
    outcome = validated(schemas.text, body(), "outcome", True, 1500)
    _resolve(disp, deal, user, outcome, "Recorded by mediator " + user["full_name"])
    return jsonify(ok=True)


# ----------------------------------------------------------------- AI (drafts that humans must review)
def _save_ai(deal_id, evidence_id, kind, user, output, language):
    aid = db.execute(
        "INSERT INTO ai_analyses (deal_id,evidence_id,kind,model,language,output_json,requested_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (deal_id, evidence_id, kind, current_app.config["GEMINI_MODEL"], language, json.dumps(output), user["id"], db.now()))
    audit(deal_id, user["id"], "ai_draft_created", f"{kind} (#{aid}) - pending human review")
    return aid


def ai_dict(a):
    return {"id": a["id"], "deal_id": a["deal_id"], "evidence_id": a["evidence_id"], "kind": a["kind"], "model": a["model"],
            "language": a["language"], "output": json.loads(a["output_json"]),
            "confirmed": json.loads(a["confirmed_json"]) if a["confirmed_json"] else None,
            "review_status": a["review_status"], "created_at": a["created_at"], "disclaimer": prompts.DISCLAIMER}


def _lang(d):
    return d.get("language") if d.get("language") in ("en", "rw") else "en"


@bp.post("/ai/evidence/<int:evidence_id>/analyse")
@login_required()
def ai_evidence(user, evidence_id):
    e = db.one("SELECT * FROM evidence WHERE id=?", (evidence_id,))
    if not e:
        raise ApiError("Evidence not found", 404)
    deal = load_deal(e["deal_id"])
    if role_in_deal(deal, user) not in ("seller", "buyer", "driver"):
        raise ApiError("Only people in this transaction can request AI help", 403)
    kind = {"payment_receipt": "receipt", "lactometer_photo": "lactometer"}.get(e["category"])
    if not kind or not e["stored_name"] or not e["mime_type"].startswith("image/"):
        raise ApiError("AI reading is available for receipt and lactometer photos (JPG/PNG/WEBP)", 422)
    language = _lang(body())
    with open(os.path.join(current_app.config["UPLOAD_DIR"], e["stored_name"]), "rb") as fh:
        raw = fh.read()
    try:
        output = gemini.generate_json(prompts.build(kind, language), image_bytes=raw, mime_type=e["mime_type"])
    except gemini.AIError as exc:
        raise ApiError(str(exc), 503)
    aid = _save_ai(deal["id"], evidence_id, kind, user, output, language)
    return jsonify(analysis=ai_dict(db.one("SELECT * FROM ai_analyses WHERE id=?", (aid,)))), 201


def _deal_facts(deal):
    """Structured, minimal data given to the AI for text analyses (no phone numbers or passwords)."""
    facts = {k: deal[k] for k in ("public_id", "litres", "price_per_litre", "total_value", "location", "delivery_at",
                                  "quality_requirements", "terms", "status", "payment_status")}
    facts["evidence"] = [{"id": e["id"], "category": e["category"], "by": e["submitted_by"], "measurement": e["measurement"],
                          "note": e["note"], "has_file": bool(e["stored_name"]), "recorded_at": e["created_at"]}
                         for e in db.query("SELECT * FROM evidence WHERE deal_id=? ORDER BY id", (deal["id"],))]
    facts["payments"] = db.query("SELECT amount, method, reference, status FROM payments WHERE deal_id=?", (deal["id"],))
    facts["human_confirmed_ai_readings"] = [json.loads(a["confirmed_json"]) for a in db.query(
        "SELECT confirmed_json FROM ai_analyses WHERE deal_id=? AND review_status='confirmed' AND confirmed_json IS NOT NULL", (deal["id"],))]
    facts["disputes"] = db.query("SELECT reason, status, final_outcome FROM disputes WHERE deal_id=?", (deal["id"],))
    return facts


@bp.post("/ai/deals/<int:deal_id>/<kind>")
@login_required()
def ai_deal(user, deal_id, kind):
    if kind not in ("summary", "consistency", "dispute_help"):
        raise ApiError("Unknown AI task", 404)
    deal = load_deal(deal_id)
    if role_in_deal(deal, user) not in ("seller", "buyer", "driver", "oversight"):
        raise ApiError("You are not part of this transaction", 403)
    language = _lang(body())
    try:
        output = gemini.generate_json(prompts.build(kind, language), user_text=json.dumps(_deal_facts(deal), default=str))
    except gemini.AIError as exc:
        raise ApiError(str(exc), 503)
    aid = _save_ai(deal_id, None, kind, user, output, language)
    return jsonify(analysis=ai_dict(db.one("SELECT * FROM ai_analyses WHERE id=?", (aid,)))), 201


@bp.get("/deals/<int:deal_id>/ai")
@login_required()
def list_ai(user, deal_id):
    deal = load_deal(deal_id)
    require_access(deal, user)
    return jsonify(analyses=[ai_dict(a) for a in db.query("SELECT * FROM ai_analyses WHERE deal_id=? ORDER BY id DESC", (deal_id,))])


@bp.post("/ai/<int:analysis_id>/review")
@login_required()
def review_ai(user, analysis_id):
    """Human confirmation step: the person checks the AI draft against the original evidence and may correct it."""
    a = db.one("SELECT * FROM ai_analyses WHERE id=?", (analysis_id,))
    if not a:
        raise ApiError("Analysis not found", 404)
    deal = load_deal(a["deal_id"])
    if role_in_deal(deal, user) not in ("seller", "buyer", "driver"):
        raise ApiError("Only people in this transaction can review AI drafts", 403)
    d = body()
    if d.get("action") not in ("confirm", "reject"):
        raise ApiError("action must be 'confirm' or 'reject'")
    values = d.get("values") if isinstance(d.get("values"), dict) else json.loads(a["output_json"])
    status = "confirmed" if d["action"] == "confirm" else "rejected"
    db.execute("UPDATE ai_analyses SET review_status=?, confirmed_json=?, reviewed_by=?, reviewed_at=? WHERE id=?",
               (status, json.dumps(values) if status == "confirmed" else None, user["id"], db.now(), analysis_id))
    audit(deal["id"], user["id"], f"ai_{status}", f"AI draft #{analysis_id} ({a['kind']}) {status} by a person")
    return jsonify(analysis=ai_dict(db.one("SELECT * FROM ai_analyses WHERE id=?", (analysis_id,))))


# ----------------------------------------------------------------- dashboard & admin
@bp.get("/dashboard")
@login_required()
def dashboard(user):
    deals = [r for r in db.query("SELECT * FROM deals ORDER BY updated_at DESC")
             if role_in_deal(r, user) or (r["creator_id"] == user["id"])]
    by_status, by_payment = {}, {}
    for d in deals:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
        by_payment[d["payment_status"]] = by_payment.get(d["payment_status"], 0) + 1
    done = [d for d in deals if d["status"] == "completed"]
    needs_action = [deal_dict(d, user) for d in deals if allowed_actions(d, role_in_deal(d, user), user) and d["status"] not in ("completed", "cancelled")
                    and set(allowed_actions(d, role_in_deal(d, user), user)) & {"confirm", "receive", "pickup", "deliver", "approve_driver", "mediate"}]
    out = {
        "counts": {"active": sum(by_status.get(s, 0) for s in ("agreed", "in_transit", "delivered", "received")),
                   "completed": len(done), "pending_acceptance": by_status.get("pending_acceptance", 0),
                   "pending_delivery": by_status.get("agreed", 0) + by_status.get("in_transit", 0),
                   "open_posts": by_status.get("open", 0), "disputed": by_status.get("disputed", 0)},
        "by_status": by_status, "by_payment": by_payment,
        "completed_litres": round(sum(d["litres"] for d in done), 2),
        "completed_value": round(sum(d["total_value"] for d in done), 2),
        "needs_action": needs_action[:10],
        "recent": [deal_dict(d, user) for d in deals[:5]],
    }
    if user["role"] == "admin":
        out["system"] = {"users_by_role": {r["role"]: r["n"] for r in db.query("SELECT role, COUNT(*) n FROM users GROUP BY role")},
                         "deals_total": db.one("SELECT COUNT(*) n FROM deals")["n"],
                         "evidence_total": db.one("SELECT COUNT(*) n FROM evidence")["n"],
                         "open_disputes": db.one("SELECT COUNT(*) n FROM disputes WHERE status='open'")["n"]}
    return jsonify(out)


@bp.get("/disputes")
@login_required()
def list_disputes(user):
    rows = db.query("SELECT di.*, d.public_id, d.district, d.seller_id, d.buyer_id FROM disputes di JOIN deals d ON d.id=di.deal_id ORDER BY di.id DESC")
    visible = [r for r in rows if user["id"] in (r["seller_id"], r["buyer_id"]) or user["role"] == "admin"
               or (user["role"] == "coop_admin" and user["district"] and user["district"] == r["district"])]
    return jsonify(disputes=visible)


@bp.get("/admin/users")
@login_required("admin")
def admin_users(user):
    return jsonify(users=db.query("SELECT id, role, full_name, phone, district, organisation, is_active, created_at FROM users ORDER BY id"))


@bp.post("/admin/users")
@login_required("admin")
def admin_create_user(user):
    d = body()
    role = d.get("role")
    if role not in schemas.ROLES_ALL:
        raise ApiError("Invalid role")
    data = validated(schemas.registration, {**d, "role": "farmer"})
    if db.one("SELECT 1 FROM users WHERE phone=?", (data["phone"],)):
        raise ApiError("This phone number is already registered", 409)
    uid = db.execute("INSERT INTO users (role,full_name,phone,email,password_hash,district,organisation,created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (role, data["full_name"], data["phone"], data["email"], hash_password(data["password"]),
                      data["district"], data["organisation"], db.now()))
    return jsonify(user=own_user(user_by_id(uid))), 201


@bp.patch("/admin/users/<int:uid>")
@login_required("admin")
def admin_update_user(user, uid):
    if uid == user["id"]:
        raise ApiError("You cannot disable your own account", 409)
    if not user_by_id(uid):
        raise ApiError("User not found", 404)
    db.execute("UPDATE users SET is_active=? WHERE id=?", (1 if body().get("is_active") else 0, uid))
    return jsonify(ok=True)
