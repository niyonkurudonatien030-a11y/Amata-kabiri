"""Load DEMO data:  python -m backend.seed
All people, phone numbers and deals below are fictional test data, not real records.
Every demo account uses the password  Demo1234"""
from backend.app import create_app
from backend import database as db
from backend.auth import hash_password

USERS = [
    ("admin", "System Admin", "+250788000001", "Kigali", "AmataShield"),
    ("coop_admin", "Kayonza Coop Admin", "+250788000002", "Kayonza", "Demo Dairy Cooperative"),
    ("farmer", "Demo Farmer Mukamana", "+250788100001", "Kayonza", "Demo Dairy Cooperative"),
    ("farmer", "Demo Farmer Habimana", "+250788100002", "Nyagatare", None),
    ("buyer", "Demo Buyer Dairy Ltd", "+250788200001", "Kigali", "Demo Dairy Ltd"),
    ("driver", "Demo Driver Jean", "+250788300001", "Kayonza", None),
]


def run():
    app = create_app()
    with app.app_context():
        if db.one("SELECT 1 FROM users LIMIT 1"):
            print("Database already has users; seed skipped.")
            return
        ids = {}
        for role, name, phone, district, org in USERS:
            ids[phone] = db.execute(
                "INSERT INTO users (role,full_name,phone,password_hash,district,organisation,created_at) VALUES (?,?,?,?,?,?,?)",
                (role, name, phone, hash_password("Demo1234"), district, org, db.now()))
        f1, f2, b1 = ids["+250788100001"], ids["+250788100002"], ids["+250788200001"]
        ts = db.now()
        for pid, creator, seller, litres, price, loc, dist in [
            ("AS-DEMO-0001", f1, f1, 200, 350, "Kayonza collection centre", "Kayonza"),
            ("AS-DEMO-0002", f2, f2, 500, 330, "Nyagatare market road", "Nyagatare")]:
            db.execute("INSERT INTO deals (public_id,deal_type,creator_id,seller_id,litres,price_per_litre,total_value,location,district,"
                       "quality_requirements,status,seller_accepted_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, "sell", creator, seller, litres, price, litres * price, loc, dist,
                        "Same-day milk, lactometer photo at pickup", "open", ts, ts, ts))
        db.execute("INSERT INTO deals (public_id,deal_type,creator_id,buyer_id,litres,price_per_litre,total_value,location,district,status,buyer_accepted_at,created_at,updated_at) "
                   "VALUES ('AS-DEMO-0003','buy',?,?,300,340,102000,'Kigali processing site','Kigali','open',?,?,?)", (b1, b1, ts, ts, ts))
        print("Demo data loaded. Sign in with phone 0788100001 (farmer), 0788200001 (buyer), 0788300001 (driver),")
        print("0788000002 (coop admin) or 0788000001 (admin). Password: Demo1234")


if __name__ == "__main__":
    run()
