"""Automated tests. Run with:  python -m unittest discover -s tests -v
The Gemini network call is replaced by a fake function, so these tests do NOT prove the real Gemini API works."""
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from backend.app import create_app
from backend import database
from backend.auth import hash_password

H = {"X-Requested-With": "AmataShield"}
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"DATABASE": os.path.join(self.tmp, "t.db"), "UPLOAD_DIR": os.path.join(self.tmp, "up"),
                               "TESTING": True, "GEMINI_API_KEY": "fake-key"})
        with self.app.app_context():
            for role, phone, name, district in [("admin", "+250788000001", "Admin", None),
                                                ("coop_admin", "+250788000002", "Coop", "Kayonza")]:
                database.execute("INSERT INTO users (role,full_name,phone,password_hash,district,created_at) VALUES (?,?,?,?,?,?)",
                                 (role, name, phone, hash_password("Secret123"), district, database.now()))
        self.c = {n: self.app.test_client() for n in ("farmer", "buyer", "driver", "other", "admin", "coop")}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, who, method, url, **kw):
        kw.setdefault("headers", H)
        return getattr(self.c[who], method)(url, **kw)

    def register(self, who, role, phone, district="Kayonza"):
        r = self.call(who, "post", "/api/auth/register", json={
            "role": role, "full_name": who.title(), "phone": phone, "password": "Secret123", "district": district})
        self.assertEqual(r.status_code, 201, r.get_json())

    def login(self, who, phone):
        r = self.call(who, "post", "/api/auth/login", json={"phone": phone, "password": "Secret123"})
        self.assertEqual(r.status_code, 200, r.get_json())

    def setup_users(self):
        self.register("farmer", "farmer", "0788111111")
        self.register("buyer", "buyer", "0788222222")
        self.register("driver", "driver", "0788333333")
        self.register("other", "buyer", "0788444444")
        self.login("admin", "0788000001")
        self.login("coop", "0788000002")

    def new_deal(self):
        r = self.call("farmer", "post", "/api/deals", json={
            "deal_type": "sell", "litres": 200, "price_per_litre": 350, "location": "Kayonza centre",
            "quality_requirements": "Lactometer 1.028-1.034"})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()["deal"]["id"]

    def agreed_deal(self):
        did = self.new_deal()
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/join").status_code, 200)
        r = self.call("farmer", "post", f"/api/deals/{did}/confirm")
        self.assertEqual(r.get_json()["deal"]["status"], "agreed")
        return did

    def upload(self, who, did, category="lactometer_photo", **extra):
        data = {"category": category, "file": (io.BytesIO(JPEG), "photo.jpg"), **extra}
        return self.call("" + who, "post", f"/api/deals/{did}/evidence", data=data, content_type="multipart/form-data")


class AuthTests(Base):
    def test_register_login_logout_and_hash(self):
        self.register("farmer", "farmer", "0788111111")
        self.assertEqual(self.call("farmer", "get", "/api/auth/me").status_code, 200)
        self.call("farmer", "post", "/api/auth/logout")
        self.assertEqual(self.call("farmer", "get", "/api/auth/me").status_code, 401)
        self.login("farmer", "+250788111111")
        with self.app.app_context():
            row = database.one("SELECT password_hash FROM users WHERE phone='+250788111111'")
            self.assertNotIn("Secret123", row["password_hash"])

    def test_validation_and_duplicates(self):
        bad = self.call("farmer", "post", "/api/auth/register", json={"role": "farmer", "full_name": "X", "phone": "123", "password": "Secret123"})
        self.assertEqual(bad.status_code, 400)
        weak = self.call("farmer", "post", "/api/auth/register", json={"role": "farmer", "full_name": "X", "phone": "0788111111", "password": "abc"})
        self.assertEqual(weak.status_code, 400)
        admin_try = self.call("farmer", "post", "/api/auth/register", json={"role": "admin", "full_name": "X", "phone": "0788111111", "password": "Secret123"})
        self.assertEqual(admin_try.status_code, 400)
        self.register("farmer", "farmer", "0788111111")
        dup = self.call("buyer", "post", "/api/auth/register", json={"role": "buyer", "full_name": "Y", "phone": "0788111111", "password": "Secret123"})
        self.assertEqual(dup.status_code, 409)

    def test_wrong_password_and_lockout(self):
        self.register("farmer", "farmer", "0788111111")
        for _ in range(5):
            r = self.call("buyer", "post", "/api/auth/login", json={"phone": "0788111111", "password": "Wrong1234"})
            self.assertEqual(r.status_code, 401)
        r = self.call("buyer", "post", "/api/auth/login", json={"phone": "0788111111", "password": "Secret123"})
        self.assertEqual(r.status_code, 429)

    def test_csrf_header_required(self):
        r = self.c["farmer"].post("/api/auth/login", json={"phone": "0788111111", "password": "x"})
        self.assertEqual(r.status_code, 403)

    def test_only_admin_creates_coop_admin(self):
        self.setup_users()
        payload = {"role": "coop_admin", "full_name": "New Coop", "phone": "0788555555", "password": "Secret123", "district": "Nyagatare"}
        self.assertEqual(self.call("farmer", "post", "/api/admin/users", json=payload).status_code, 403)
        self.assertEqual(self.call("admin", "post", "/api/admin/users", json=payload).status_code, 201)


class DealFlowTests(Base):
    def test_role_restrictions_on_posting(self):
        self.setup_users()
        r = self.call("buyer", "post", "/api/deals", json={"deal_type": "sell", "litres": 10, "price_per_litre": 300, "location": "x"})
        self.assertEqual(r.status_code, 403)
        r = self.call("driver", "post", "/api/deals", json={"deal_type": "sell", "litres": 10, "price_per_litre": 300, "location": "x"})
        self.assertEqual(r.status_code, 403)

    def test_two_party_acceptance_and_totals(self):
        self.setup_users()
        did = self.new_deal()
        d = self.call("farmer", "get", f"/api/deals/{did}").get_json()["deal"]
        self.assertEqual(d["total_value"], 70000)
        self.assertEqual(d["status"], "open")
        self.assertIsNotNone(d["seller_accepted_at"])
        self.assertIsNone(d["buyer_accepted_at"])
        # market is visible to a buyer, not to the creator's own list
        self.assertEqual(len(self.call("buyer", "get", "/api/deals/open").get_json()["deals"]), 1)
        self.assertEqual(len(self.call("farmer", "get", "/api/deals/open").get_json()["deals"]), 0)
        # farmers cannot join a sell post
        self.assertEqual(self.call("driver", "post", f"/api/deals/{did}/join").status_code, 403)
        j = self.call("buyer", "post", f"/api/deals/{did}/join").get_json()["deal"]
        self.assertEqual(j["status"], "pending_acceptance")
        self.assertIsNotNone(j["buyer_accepted_at"])
        # buyer cannot confirm for the farmer
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/confirm").status_code, 409)
        c = self.call("farmer", "post", f"/api/deals/{did}/confirm").get_json()["deal"]
        self.assertEqual(c["status"], "agreed")
        self.assertEqual(len(c["terms_hash"]), 64)
        self.assertIsNotNone(c["seller_accepted_at"])

    def test_decline_returns_post_to_market(self):
        self.setup_users()
        did = self.new_deal()
        self.call("buyer", "post", f"/api/deals/{did}/join")
        r = self.call("farmer", "post", f"/api/deals/{did}/decline").get_json()["deal"]
        self.assertEqual(r["status"], "open")
        self.assertIsNone(r["buyer"])

    def test_outsider_cannot_see_agreed_deal_or_phones(self):
        self.setup_users()
        did = self.agreed_deal()
        self.assertEqual(self.call("other", "get", f"/api/deals/{did}").status_code, 403)
        mine = self.call("buyer", "get", f"/api/deals/{did}").get_json()["deal"]
        self.assertIn("phone", mine["seller"])
        self.assertEqual(self.call("coop", "get", f"/api/deals/{did}").status_code, 200)   # same district oversight

    def test_buy_request_answered_by_farmer(self):
        self.setup_users()
        r = self.call("buyer", "post", "/api/deals", json={"deal_type": "buy", "litres": 500, "price_per_litre": 340, "location": "Kigali"})
        did = r.get_json()["deal"]["id"]
        self.assertEqual(self.call("farmer", "post", f"/api/deals/{did}/join").status_code, 200)
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/confirm").get_json()["deal"]["status"], "agreed")

    def test_full_happy_path_with_driver_and_payment(self):
        self.setup_users()
        did = self.agreed_deal()
        # pickup is blocked without quality evidence
        self.assertEqual(self.call("farmer", "post", f"/api/deals/{did}/stage", json={"stage": "pickup"}).status_code, 422)
        # driver applies, party approves
        jobs = self.call("driver", "get", "/api/deals/delivery-jobs").get_json()["deals"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(self.call("driver", "post", f"/api/deals/{did}/drivers", json={"proposed_fee": 5000}).status_code, 201)
        apps = self.call("buyer", "get", f"/api/deals/{did}").get_json()["deal"]["driver_applications"]
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/drivers/{apps[0]['id']}/approve").status_code, 200)
        # evidence by driver (photo) and farmer (typed measurement)
        r = self.upload("driver", did)
        self.assertEqual(r.status_code, 201, r.get_json())
        ev = r.get_json()["evidence"]
        self.assertEqual(len(ev["sha256"]), 64)
        r = self.call("farmer", "post", f"/api/deals/{did}/evidence", data={"category": "quality_measurement", "measurement": "1.030"},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.call("driver", "post", f"/api/deals/{did}/stage", json={"stage": "pickup"}).get_json()["deal"]["status"], "in_transit")
        self.assertEqual(self.call("driver", "post", f"/api/deals/{did}/stage", json={"stage": "deliver"}).get_json()["deal"]["status"], "delivered")
        # driver cannot receive on behalf of the buyer
        self.assertEqual(self.call("driver", "post", f"/api/deals/{did}/stage", json={"stage": "receive"}).status_code, 409)
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/stage", json={"stage": "receive"}).get_json()["deal"]["status"], "received")
        # payment: unconfirmed -> reported -> confirmed => completed
        d = self.call("buyer", "get", f"/api/deals/{did}").get_json()["deal"]
        self.assertEqual(d["payment_status"], "unconfirmed")
        pay = self.call("buyer", "post", f"/api/deals/{did}/payments", json={"amount": 70000, "method": "mobile_money", "reference": "MP123"})
        self.assertEqual(pay.get_json()["deal"]["payment_status"], "reported")
        pid = pay.get_json()["deal"]["payments"][0]["id"]
        self.assertEqual(self.call("buyer", "post", f"/api/payments/{pid}/confirm").status_code, 409)   # buyer cannot self-confirm
        done = self.call("farmer", "post", f"/api/payments/{pid}/confirm").get_json()["deal"]
        self.assertEqual(done["payment_status"], "confirmed")
        self.assertEqual(done["status"], "completed")
        actions = [t["action"] for t in done["timeline"]]
        self.assertIn("agreement_confirmed", actions)
        self.assertIn("deal_completed", actions)
        dash = self.call("farmer", "get", "/api/dashboard").get_json()
        self.assertEqual(dash["counts"]["completed"], 1)
        self.assertEqual(dash["completed_litres"], 200)

    def test_cancel_only_before_transit(self):
        self.setup_users()
        did = self.agreed_deal()
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/cancel", json={"reason": "changed plan"}).status_code, 200)
        self.assertEqual(self.call("buyer", "post", f"/api/deals/{did}/cancel").status_code, 409)


class EvidenceTests(Base):
    def test_file_type_check_and_access(self):
        self.setup_users()
        did = self.agreed_deal()
        bad = self.call("farmer", "post", f"/api/deals/{did}/evidence",
                        data={"category": "other", "file": (io.BytesIO(b"MZ not an image"), "evil.jpg")}, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        ok = self.upload("farmer", did, "delivery_photo")
        eid = ok.get_json()["evidence"]["id"]
        self.assertEqual(self.call("buyer", "get", f"/api/evidence/{eid}/file").data, JPEG)
        self.assertEqual(self.call("other", "get", f"/api/evidence/{eid}/file").status_code, 403)
        # evidence is kept unchanged and listed for both parties
        self.assertEqual(len(self.call("buyer", "get", f"/api/deals/{did}/evidence").get_json()["evidence"]), 1)
        # driver cannot submit payment receipts
        self.assertEqual(self.upload("driver", did, "payment_receipt").status_code, 403)

    def test_evidence_blocked_before_agreement(self):
        self.setup_users()
        did = self.new_deal()
        self.assertEqual(self.upload("farmer", did).status_code, 409)


class PaymentDisputeTests(Base):
    def to_received(self):
        self.setup_users()
        did = self.agreed_deal()
        self.upload("farmer", did)
        self.call("farmer", "post", f"/api/deals/{did}/stage", json={"stage": "pickup"})
        self.call("farmer", "post", f"/api/deals/{did}/stage", json={"stage": "deliver"})
        self.call("buyer", "post", f"/api/deals/{did}/stage", json={"stage": "receive"})
        return did

    def test_seller_rejects_payment_opens_dispute_and_both_parties_resolve(self):
        did = self.to_received()
        pay = self.call("buyer", "post", f"/api/deals/{did}/payments", json={"amount": 60000, "method": "bank"}).get_json()["deal"]
        pid = pay["payments"][0]["id"]
        r = self.call("farmer", "post", f"/api/payments/{pid}/reject", json={"reason": "Only 60,000 received"}).get_json()["deal"]
        self.assertEqual(r["payment_status"], "disputed")
        self.assertEqual(r["status"], "disputed")
        disp = r["disputes"][0]
        self.assertEqual(disp["status"], "open")
        c = self.call("buyer", "post", f"/api/disputes/{disp['id']}/events", json={"kind": "comment", "body": "I sent 60,000 as agreed after deductions"})
        self.assertEqual(c.status_code, 201)
        prop = self.call("buyer", "post", f"/api/disputes/{disp['id']}/events", json={"kind": "proposal", "body": "Buyer pays remaining 10,000 RWF by Friday"})
        self.assertEqual(prop.status_code, 201)
        view = self.call("farmer", "get", f"/api/disputes/{disp['id']}").get_json()
        prop_id = [e["id"] for e in view["events"] if e["kind"] == "proposal"][0]
        # proposer cannot agree to own proposal
        self.assertEqual(self.call("buyer", "post", f"/api/disputes/{disp['id']}/events", json={"kind": "agree", "ref_event_id": prop_id}).status_code, 409)
        self.assertEqual(self.call("farmer", "post", f"/api/disputes/{disp['id']}/events", json={"kind": "agree", "ref_event_id": prop_id}).status_code, 201)
        final = self.call("farmer", "get", f"/api/disputes/{disp['id']}").get_json()
        self.assertEqual(final["dispute"]["status"], "resolved")
        self.assertIn("10,000", final["dispute"]["final_outcome"])
        d = self.call("buyer", "get", f"/api/deals/{did}").get_json()["deal"]
        self.assertEqual(d["status"], "received")          # restored
        self.assertEqual(d["payment_status"], "unconfirmed")  # a new payment must be recorded explicitly
        self.assertIn("report_payment", d["actions"])

    def test_mediator_can_record_outcome(self):
        did = self.to_received()
        r = self.call("buyer", "post", f"/api/deals/{did}/disputes", json={"reason": "Milk was sour on arrival"})
        self.assertEqual(r.status_code, 201)
        dispute_id = r.get_json()["dispute_id"]
        self.assertEqual(self.call("other", "get", f"/api/disputes/{dispute_id}").status_code, 403)
        self.assertEqual(self.call("farmer", "post", f"/api/disputes/{dispute_id}/resolve", json={"outcome": "x"}).status_code, 403)
        ok = self.call("coop", "post", f"/api/disputes/{dispute_id}/resolve", json={"outcome": "Price reduced by 5%"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.call("buyer", "post", f"/api/disputes/{dispute_id}/events", json={"kind": "comment", "body": "late"}).status_code, 409)

    def test_cannot_report_payment_before_agreement(self):
        self.setup_users()
        did = self.new_deal()
        r = self.call("buyer", "post", f"/api/deals/{did}/payments", json={"amount": 1, "method": "bank"})
        self.assertEqual(r.status_code, 409)


class AITests(Base):
    def test_ai_requires_review_and_never_changes_payment(self):
        self.setup_users()
        did = self.agreed_deal()
        up = self.upload("buyer", did, "payment_receipt")
        eid = up.get_json()["evidence"]["id"]
        fake = {"amount": 70000, "currency": "RWF", "reference": "MP123", "legible": True, "warnings": [], "notes": ""}
        with mock.patch("backend.ai.gemini.generate_json", return_value=fake) as m:
            r = self.call("buyer", "post", f"/api/ai/evidence/{eid}/analyse", json={"language": "en"})
            self.assertEqual(r.status_code, 201, r.get_json())
            self.assertTrue(m.call_args.kwargs["image_bytes"].startswith(b"\xff\xd8"))
        a = r.get_json()["analysis"]
        self.assertEqual(a["review_status"], "pending_review")
        self.assertIn("not proof", a["disclaimer"])
        d = self.call("buyer", "get", f"/api/deals/{did}").get_json()["deal"]
        self.assertEqual(d["payment_status"], "unconfirmed")      # AI alone changes nothing
        self.assertEqual(self.call("other", "post", f"/api/ai/{a['id']}/review", json={"action": "confirm"}).status_code, 403)
        rv = self.call("buyer", "post", f"/api/ai/{a['id']}/review", json={"action": "confirm", "values": {**fake, "amount": 69000}})
        self.assertEqual(rv.get_json()["analysis"]["confirmed"]["amount"], 69000)   # human correction kept
        self.assertEqual(rv.get_json()["analysis"]["output"]["amount"], 70000)      # raw draft preserved

    def test_ai_text_tasks_and_errors(self):
        self.setup_users()
        did = self.agreed_deal()
        fake = {"summary": "s", "missing_information": [], "possible_inconsistencies": [], "questions_for_parties": []}
        with mock.patch("backend.ai.gemini.generate_json", return_value=fake) as m:
            self.assertEqual(self.call("farmer", "post", f"/api/ai/deals/{did}/summary", json={"language": "rw"}).status_code, 201)
            sent = m.call_args.kwargs["user_text"]
            self.assertNotIn("+250", sent)                       # no phone numbers leave the server
        self.assertEqual(self.call("other", "post", f"/api/ai/deals/{did}/summary").status_code, 403)
        from backend.ai.gemini import AIError
        with mock.patch("backend.ai.gemini.generate_json", side_effect=AIError("down")):
            self.assertEqual(self.call("farmer", "post", f"/api/ai/deals/{did}/consistency").status_code, 503)

    def test_ai_refuses_non_image_categories(self):
        self.setup_users()
        did = self.agreed_deal()
        eid = self.upload("farmer", did, "delivery_photo").get_json()["evidence"]["id"]
        self.assertEqual(self.call("farmer", "post", f"/api/ai/evidence/{eid}/analyse").status_code, 422)

    def test_missing_key_gives_clear_error(self):
        self.setup_users()
        did = self.agreed_deal()
        self.app.config["GEMINI_API_KEY"] = ""
        self.assertEqual(self.call("farmer", "post", f"/api/ai/deals/{did}/summary").status_code, 503)


class AdminTests(Base):
    def test_admin_dashboard_and_disable_user(self):
        self.setup_users()
        self.agreed_deal()
        dash = self.call("admin", "get", "/api/dashboard").get_json()
        self.assertEqual(dash["system"]["deals_total"], 1)
        users = self.call("admin", "get", "/api/admin/users").get_json()["users"]
        farmer = [u for u in users if u["role"] == "farmer"][0]
        self.assertEqual(self.call("admin", "patch", f"/api/admin/users/{farmer['id']}", json={"is_active": False}).status_code, 200)
        self.assertEqual(self.call("farmer", "get", "/api/auth/me").status_code, 401)
        self.assertEqual(self.call("farmer", "get", "/api/admin/users").status_code, 401)


if __name__ == "__main__":
    unittest.main()
