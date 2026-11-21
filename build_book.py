"""Builds the AmataShield Master Project Book PDF.   python documentation/tools/build_book.py <output.pdf>"""
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer)
from reportlab.platypus.tableofcontents import TableOfContents

from book_lib import *  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else "AmataShield_Master_Project_Book.pdf"
TEST_SUMMARY = open("/tmp/test_result.txt").read().strip() if os.path.exists("/tmp/test_result.txt") else ""
story = []
H1 = lambda t: story.extend([PageBreak(), P(x(t), "h1")])
H2 = lambda t: story.append(P(x(t), "h2"))
H3 = lambda t: story.append(P(x(t), "h3"))
B = lambda t: story.append(P(t))
L = lambda items: story.extend(bullets(items))
SP = lambda n=4: story.append(Spacer(1, n * mm))
D = lambda d: story.extend([d.flow(), Spacer(1, 3 * mm)])


# ---------------------------------------------------------------- page decoration
def draw_shield(c, cx, cy, s):
    p = c.beginPath()
    p.moveTo(cx, cy + 0.5 * s); p.lineTo(cx + 0.45 * s, cy + 0.35 * s); p.lineTo(cx + 0.45 * s, cy - 0.05 * s)
    p.curveTo(cx + 0.45 * s, cy - 0.3 * s, cx + 0.2 * s, cy - 0.45 * s, cx, cy - 0.5 * s)
    p.curveTo(cx - 0.2 * s, cy - 0.45 * s, cx - 0.45 * s, cy - 0.3 * s, cx - 0.45 * s, cy - 0.05 * s)
    p.lineTo(cx - 0.45 * s, cy + 0.35 * s); p.close()
    c.setFillColor(DEEP); c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(colors.white); c.circle(cx, cy - 0.02 * s, 0.22 * s, fill=1, stroke=0)
    c.setStrokeColor(GOLD); c.setLineWidth(0.035 * s); c.setLineCap(1); c.setLineJoin(1)
    q = c.beginPath(); q.moveTo(cx - 0.11 * s, cy - 0.03 * s); q.lineTo(cx - 0.03 * s, cy - 0.11 * s); q.lineTo(cx + 0.13 * s, cy + 0.08 * s)
    c.drawPath(q, fill=0, stroke=1)


def cover(c, doc):
    w, h = A4
    c.setFillColor(DEEP); c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0E7A4B")); c.rect(0, 0, w, 70 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD); c.rect(0, 70 * mm, w, 2.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.circle(w / 2, h - 75 * mm, 34 * mm, fill=1, stroke=0)
    draw_shield(c, w / 2, h - 75 * mm, 55 * mm)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 38); c.drawCentredString(w / 2, h - 140 * mm, "AmataShield")
    c.setFont("Helvetica", 14); c.drawCentredString(w / 2, h - 150 * mm, "Digital trust and evidence records for Rwanda's dairy value chain")
    c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 12); c.drawCentredString(w / 2, h - 170 * mm, "MASTER PROJECT BOOK")
    c.setFillColor(colors.white); c.setFont("Helvetica", 10)
    for i, t in enumerate(["A. Project presentation   B. Technical report   C. Complete source code",
                           "D. Team learning guide   E. Future development"]):
        c.drawCentredString(w / 2, h - (180 + 6 * i) * mm, t)
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, 40 * mm, "Project initiator: Donatien - Electronics and Telecommunication Engineering, University of Rwanda (UR-CST)")
    c.drawCentredString(w / 2, 33 * mm, "Version: MVP stage 1 - November 2026 - prepared with AI assistance (Claude)")
    c.drawCentredString(w / 2, 26 * mm, "Status: working prototype with fictional demo data. Not yet field-tested with real users.")


def footer(c, doc):
    c.saveState()
    c.setStrokeColor(LINE); c.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#5d6f64"))
    c.drawString(18 * mm, 9.5 * mm, "AmataShield Master Project Book")
    c.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"Page {doc.page}")
    c.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm, topMargin=17 * mm, bottomMargin=19 * mm,
                         title="AmataShield Master Project Book", author="AmataShield team")
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [Frame(0, 0, 1, 1)], onPage=cover), PageTemplate("main", [fr], onPage=footer)])

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name in ("h1", "h2"):
            lvl = 0 if fl.style.name == "h1" else 1
            key = f"k{self.seq.nextf('toc')}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (lvl, fl.getPlainText(), self.page, key))


def diagram_arch():
    d = Diagram(172, 78)
    d.box(2, 28, 40, 26, "Phone browser\n(Android Chrome)\nHTML + CSS + JavaScript\ncamera via getUserMedia", fill=colors.HexColor("#FFF3C4"), stroke=GOLD)
    d.box(62, 14, 48, 54, "Flask application (Python)\nroutes.py: business rules\nauth.py: sessions, roles\nschemas.py: validation\nai/gemini.py: AI client", fill=PALE)
    d.box(130, 50, 40, 20, "SQLite database\n(users, deals, evidence,\npayments, disputes, audit)", fill=colors.HexColor("#DCE8FF"), stroke=NAVY)
    d.box(130, 26, 40, 18, "Evidence file store\n(original photos/PDFs,\nSHA-256 recorded)", fill=colors.HexColor("#DCE8FF"), stroke=NAVY)
    d.box(130, 2, 40, 18, "Google Gemini API\n(external; key kept on\nthe server only)", fill=colors.HexColor("#E8DFF7"), stroke=colors.HexColor("#6B3FA0"))
    d.arrow(42, 41, 62, 41, label="HTTPS + JSON"); d.arrow(62, 36, 42, 36)
    d.arrow(110, 60, 130, 60); d.arrow(110, 35, 130, 35); d.arrow(110, 22, 130, 11, label="image + prompt")
    d.text(86, 72, "Server (one small machine for the pilot)", size=7, color=NAVY, bold=True)
    return d


def diagram_states():
    d = Diagram(172, 62)
    row1 = [("Open", 2), ("Pending\nacceptance", 26), ("Agreed", 50), ("In transit", 74), ("Delivered", 98), ("Received", 122), ("Completed", 146)]
    for i, (t, x0) in enumerate(row1):
        d.box(x0, 38, 22, 14, t, fill=colors.HexColor("#D6F5DC") if t == "Completed" else PALE, size=6.8)
        if i:
            d.arrow(row1[i - 1][1] + 22, 45, x0, 45)
    d.text(13, 56, "post", size=6); d.text(37, 56, "other side accepts", size=6); d.text(61, 56, "creator confirms", size=6)
    d.text(85, 56, "pickup + evidence", size=6); d.text(109, 56, "arrival", size=6); d.text(133, 56, "buyer accepts", size=6); d.text(157, 56, "payment confirmed", size=6)
    d.box(26, 6, 24, 14, "Cancelled", fill=colors.HexColor("#FDE1DE"), stroke=colors.HexColor("#C0392B"), size=6.8)
    d.box(98, 6, 30, 14, "Disputed\n(back to previous state\nwhen resolved)", fill=colors.HexColor("#FDE1DE"), stroke=colors.HexColor("#C0392B"), size=6.2)
    d.arrow(37, 38, 37, 20, dash=True); d.arrow(61, 38, 45, 20, dash=True)
    d.arrow(85, 38, 105, 20, dash=True); d.arrow(133, 38, 120, 20, dash=True)
    d.text(150, 14, "Payment record runs in parallel:", size=6.5, bold=True, anchor="middle")
    d.text(150, 8, "unconfirmed > reported > confirmed", size=6.2); d.text(150, 3, "(or disputed)", size=6.2)
    return d


def diagram_erd():
    d = Diagram(172, 100)
    def t(x0, y0, name, cols, w=44):
        h = 6 + 4.4 * len(cols)
        d.box(x0, y0, w, h, name, fill=colors.white, stroke=DEEP, size=6.3, bold=True)
        d.text(x0 + w / 2, y0 + h - 5.2, name, size=7, bold=True, color=DEEP)
        for i, c in enumerate(cols):
            d.text(x0 + 2, y0 + h - 10 - i * 4.4, c, size=5.8, anchor="start")
        return h
    t(2, 62, "users", ["id PK", "role, full_name", "phone UNIQUE", "password_hash", "district, organisation"])
    t(64, 52, "deals", ["id PK, public_id", "creator/seller/buyer/driver_id FK", "litres, price, total", "status, payment_status", "seller/buyer_accepted_at", "terms_hash"], w=50)
    t(126, 70, "evidence", ["id PK, deal_id FK", "submitted_by FK", "category, sha256", "stored_name, measurement"], w=44)
    t(126, 42, "payments", ["id PK, deal_id FK", "reported_by, amount", "method, reference", "status"], w=44)
    t(126, 14, "ai_analyses", ["id PK, deal_id FK", "evidence_id FK, kind", "output_json (draft)", "confirmed_json (human)"], w=44)
    t(64, 14, "disputes", ["id PK, deal_id FK", "opened_by, reason", "status, final_outcome"], w=50)
    t(2, 20, "dispute_events", ["id PK, dispute_id FK", "user_id, kind", "body, ref_event_id"])
    t(2, 2, "audit_log", ["deal_id, user_id", "action, detail, time"], w=44)
    t(64, 78, "driver_applications", ["deal_id FK, driver_id FK", "proposed_fee, status"], w=50)
    d.arrow(46, 70, 64, 66, head=False); d.arrow(114, 66, 126, 78, head=False); d.arrow(114, 62, 126, 52, head=False)
    d.arrow(100, 52, 100, 38, head=False); d.arrow(114, 56, 126, 26, head=False); d.arrow(64, 28, 46, 28, head=False)
    d.arrow(90, 78, 90, 70, head=False)
    return d


def diagram_ai():
    d = Diagram(172, 52)
    steps = [("1. Photo or\nreceipt saved\n(original kept)", 2), ("2. Server sends\nimage + safety\nrules to Gemini", 36), ("3. Gemini returns\nJSON draft\n(null if unclear)", 70),
             ("4. Draft stored as\n'pending review'", 104), ("5. A person checks,\ncorrects, confirms\nor rejects", 138)]
    for i, (t, x0) in enumerate(steps):
        d.box(x0, 18, 32, 24, t, fill=PALE if i != 4 else colors.HexColor("#FFF3C4"), stroke=DEEP if i != 4 else GOLD, size=6.6)
        if i:
            d.arrow(steps[i - 1][1] + 32, 30, x0, 30)
    d.box(2, 1, 168, 11, "AI never: certifies milk or lab results | confirms a payment | changes payment or deal status | decides who is right in a dispute", fill=colors.HexColor("#FDE7E4"), stroke=colors.HexColor("#C0392B"), size=6.5)
    return d


def diagram_journey():
    d = Diagram(172, 92)
    seq = [("Farmer posts milk\n(litres, price)", 2, 70), ("Buyer accepts\nthe terms", 46, 70), ("Farmer confirms\n= agreed", 90, 70), ("Driver applies\n(fee)", 134, 70),
           ("Party approves\ndriver", 134, 46), ("Lactometer photo\n+ reading", 90, 46), ("Pickup\nrecorded", 46, 46), ("Arrival at\nbuyer", 2, 46),
           ("Buyer checks\nmilk, accepts", 2, 22), ("Buyer reports\npayment", 46, 22), ("Seller confirms\nreceipt", 90, 22), ("Completed", 134, 22)]
    for i, (t, x0, y0) in enumerate(seq):
        d.box(x0, y0, 36, 15, t, fill=colors.HexColor("#D6F5DC") if t == "Completed" else PALE, size=6.6)
    arrows = [(38, 77, 46, 77), (82, 77, 90, 77), (126, 77, 134, 77), (152, 70, 152, 61), (134, 53, 126, 53), (90, 53, 82, 53), (46, 53, 38, 53),
              (20, 46, 20, 37), (38, 29, 46, 29), (82, 29, 90, 29), (126, 29, 134, 29)]
    for a in arrows:
        d.arrow(*a)
    d.box(40, 2, 92, 11, "Any step can go to DISPUTE: both sides add evidence, propose, agree. Mediator can record outcome.", fill=colors.HexColor("#FDE7E4"), stroke=colors.HexColor("#C0392B"), size=6.3)
    return d


def diagram_usecase():
    d = Diagram(172, 100)
    actors = [("Farmer", 8, 82), ("Buyer", 8, 60), ("Driver", 8, 38), ("Coop admin", 8, 16), ("System admin", 8, -6 + 12)]
    cases = [("Register / sign in", 70, 94), ("Post or accept a deal", 70, 82), ("Confirm agreement", 70, 70), ("Apply / approve driver", 70, 58), ("Submit evidence", 70, 46),
             ("Record pickup / arrival", 70, 34), ("Report / confirm payment", 70, 22), ("Open / resolve dispute", 120, 82), ("Request AI draft and review it", 120, 62),
             ("View dashboard", 120, 42), ("Mediate in district", 120, 24), ("Manage users", 120, 8)]
    for name, cx, cy in cases:
        d.oval(cx, cy, 24, 5.2, name, size=6.2)
    for name, ax, ay in actors:
        d.box(ax - 8, ay - 4, 22, 8, name, fill=colors.HexColor("#FFF3C4"), stroke=GOLD, size=6.5)
    links = {"Farmer": [0, 1, 2, 4, 5, 6, 7, 8, 9], "Buyer": [0, 1, 2, 3, 4, 6, 7, 8, 9], "Driver": [0, 3, 4, 5, 9],
             "Coop admin": [0, 7, 9, 10], "System admin": [0, 9, 10, 11]}
    for name, ax, ay in actors:
        for i in links[name]:
            cx, cy = cases[i][1], cases[i][2]
            d.arrow(ax + 14, ay, cx - 24, cy, head=False, color=colors.HexColor("#9fb5a7"))
    return d


def diagram_dfd():
    d = Diagram(172, 70)
    d.box(2, 26, 30, 18, "Users\n(farmer, buyer,\ndriver, admin)", fill=colors.HexColor("#FFF3C4"), stroke=GOLD, round_=False)
    d.oval(86, 35, 24, 17, "1.0\nAmataShield\nAPI and rules", fill=PALE, size=7)
    d.box(130, 50, 40, 16, "D1 Database", fill=colors.HexColor("#DCE8FF"), stroke=NAVY, round_=False)
    d.box(130, 26, 40, 16, "D2 Evidence files", fill=colors.HexColor("#DCE8FF"), stroke=NAVY, round_=False)
    d.box(130, 2, 40, 16, "Gemini API (external)", fill=colors.HexColor("#E8DFF7"), stroke=colors.HexColor("#6B3FA0"), round_=False)
    d.arrow(32, 38, 62, 38, label="requests, photos"); d.arrow(62, 32, 32, 32, label="records, drafts")
    d.arrow(106, 44, 130, 56, label="deals, users"); d.arrow(106, 36, 130, 34, label="files"); d.arrow(106, 28, 130, 12, label="image+rules")
    d.arrow(130, 8, 106, 26, dash=True)
    return d


def phone_mock(title, rows, x0=0):
    d = Diagram(62, 108)
    d.box(2, 2, 58, 104, "", fill=colors.HexColor("#1a1a1a"), stroke=colors.black)
    d.box(4.5, 6, 53, 96, "", fill=colors.HexColor("#F4F8F5"), stroke=colors.HexColor("#F4F8F5"), round_=False)
    d.box(4.5, 94, 53, 8, "", fill=DEEP, stroke=DEEP, round_=False)
    d.text(31, 96.5, title, size=7, color=colors.white, bold=True)
    y = 88
    for kind, txt in rows:
        if kind == "stat":
            d.box(7, y - 8, 22, 9, txt, fill=colors.white, size=5.6); y_next = y
            d.box(32, y - 8, 22, 9, "", fill=colors.white, size=5.6)
        elif kind == "btn":
            d.box(7, y - 7, 47, 7, txt, fill=GOLD, stroke=GOLD, size=6.2, bold=True); y -= 9; continue
        else:
            d.box(7, y - 12, 47, 12, txt, fill=colors.white, size=5.6)
            y -= 14; continue
        y -= 11
    d.box(4.5, 6, 53, 8, "Home   Market   Post   Deals   Me", fill=colors.white, stroke=LINE, size=5.2, round_=False)
    return d


# ================================================================= COVER + TOC
story.extend([NextPageTemplate("main"), PageBreak()])
story.append(P("Contents", "h1"))
toc = TableOfContents()
toc.levelStyles = [S["toc1"], S["toc2"]]
story.append(toc)
story.append(Spacer(1, 6 * mm))
story.append(callout("<b>How to read this book.</b> Part A is the pitch. Part B is the engineering report. Part C contains every source file "
                     "exactly as it is in the ZIP. Part D teaches the team how it works. Part E is the roadmap. "
                     "<b>Honesty rule:</b> anything not verified is labelled <i>user-provided</i>, <i>assumption</i> or <i>proposed</i>. "
                     "No statistics, interviews, partners or test results have been invented.", "ok"))

# ================================================================= PART A
H1("PART A - PROJECT PRESENTATION")
B("This part is written as a pitch narrative: one idea per heading, ready to become slides. A PowerPoint file is the next deliverable in the staged plan.")
H2("A1. AmataShield: project identity")
B("<b>AmataShield</b> (amata = milk in Kinyarwanda) is a mobile-first web platform that gives farmers, buyers and drivers one shared, time-stamped "
  "record of a milk deal: what was agreed, what was delivered, what quality evidence exists, what payment was reported and confirmed, and what happened if there was a disagreement.")
callout_text = ("<b>Tagline (proposal):</b> One record. Both sides. Every litre.<br/><b>Not claimed:</b> AmataShield does not guarantee quality, does not guarantee payment and does not hold money.")
story.append(callout(callout_text))
H2("A2. The problem (user-provided preliminary research - to be verified)")
L(["Farmers find it hard to reach reliable buyers; buyers find it hard to aggregate enough milk.",
   "Milk spoils quickly; cold-chain transport is difficult for small producers.",
   "Quality rejection disputes: a buyer says the milk failed, the farmer cannot prove otherwise.",
   "Minimum delivery quantities exclude small farmers; payments can be delayed; verbal deals leave no evidence.",
   "Communication and digital-literacy barriers make app-heavy solutions hard to adopt."])
H2("A3. Who experiences it")
story.append(table([["Group", "Pain (from user research, unverified)", "What AmataShield gives them"],
    ["Small-scale farmer", "No proof of quality or delivery; late payment; hard to find buyers", "Posted offers, evidence record, payment confirmation trail"],
    ["Buyer / processor", "Unreliable supply, rejected-milk arguments, aggregation effort", "Searchable offers, agreed terms, evidence before pickup"],
    ["Driver / transporter", "Unclear job terms and fee; blamed for spoilage", "Job list, fee agreed in app, photos at pickup and arrival"],
    ["Cooperative / collection centre", "Mediating disputes without records", "District oversight view, dispute history, mediation tool"]], [38, 72, 62]))
H2("A4. Why existing approaches leave gaps")
B("Informal phone calls, WhatsApp messages and handwritten notes do work for relationships, but they create scattered, editable and hard-to-trace evidence. "
  "<b>Assumption to test:</b> no tool used by small dairy farmers today combines agreement, quality evidence, delivery steps and payment confirmation in one record. "
  "A survey of existing Rwandan platforms has <b>not yet been done</b> and is listed as a task in Part E.")
H2("A5. The proposed solution")
L(["A <b>marketplace</b> of posted offers (sell milk / want milk) with filters, as sketched in the founder's notebook.",
   "A <b>two-party agreement</b>: both sides accept the same terms; a fingerprint of the terms is stored.",
   "<b>Evidence-first delivery</b>: a lactometer photo or measurement is required before pickup can be recorded.",
   "<b>Payment records, not payment processing</b>: the buyer reports, the seller confirms - like a peer-to-peer marketplace that only hosts decisions.",
   "<b>Structured disputes</b> with evidence from both sides, proposals, agreement and a mediator option.",
   "<b>Gemini AI drafts</b> that a person must check - never an authority."])
H2("A6. How AmataShield works")
D(diagram_journey())
story.append(P("Figure A1 - The deal journey from the founder's notebook sketches, as implemented.", "small"))
H2("A7. Farmer experience")
L(["Register with phone number and role. Post litres, price, location and quality needs.", "Confirm the buyer who accepts. Approve a driver. Add a lactometer photo at pickup.",
   "Confirm payment only when the money has really arrived. Open a dispute if something is wrong."])
H2("A8. Buyer experience")
L(["Browse offers, filter by district, litres and price. Accept an offer's exact terms.", "Optionally hire a driver. Check the milk on arrival and accept or dispute.",
   "Report the payment with method and reference; wait for the seller's confirmation."])
H2("A9. Gemini AI integration")
B("Gemini is called only from the server. It can read a payment-receipt photo, read a lactometer photo, summarise a deal, compare the agreement with evidence "
  "and explain a dispute in plain language, including an experimental Kinyarwanda option. Every output is stored as a <b>draft</b>; a person must confirm or correct it.")
H2("A10. Evidence and trust architecture")
L(["Original files are stored unchanged; a SHA-256 fingerprint is saved so later edits would be detectable.", "Server time is recorded for every action; the phone's claimed time is shown separately and not trusted.",
   "Every state change writes to an audit history visible to the parties.", "Evidence cannot be deleted by users. Both parties see the same record."])
H2("A11. System architecture")
D(diagram_arch())
story.append(P("Figure A2 - Architecture of the implemented MVP.", "small"))
H2("A12. Demonstration of the application")
B("The app runs locally with fictional demo data (python -m backend.seed). <b>Honest status:</b> the interface was implemented and syntax-checked, "
  "and the API workflow is covered by automated tests, but the screens have <b>not yet been tested on physical Android phones</b>. The mock-ups below are drawings of the implemented screens, not screenshots.")
story.append(Table([[phone_mock("Home", [("stat", "4\nActive"), ("stat", "2\nPending"), ("card", "Milk for sale 200 L\nAgreed - payment reported"), ("card", "Buyer wants 300 L\nOpen"), ("btn", "Post deal")]).flow(),
                     phone_mock("Deal AS-2026...", [("card", "200 L x 350 RWF\nTotal 70,000 RWF"), ("btn", "Add evidence"), ("card", "Lactometer photo\nBy driver - SHA-256 ab12.."), ("btn", "Record pickup")]).flow()]],
                   colWidths=[85 * mm, 85 * mm]))
story.append(P("Figure A3 - Illustrative mock-ups (drawn, not photographed).", "small"))
H2("A13. Market opportunity")
B("<b>No market-size numbers are claimed.</b> The opportunity is to serve the actors who already trade milk: farmers, cooperatives, collection centres, transporters, buyers and processors. "
  "Sizing requires official counts (for example national statistics and agriculture agencies) - listed as a verification task. A reasonable first target is <b>one cooperative and its regular buyers in one district</b>.")
H2("A14. Business and sustainability model (hypotheses, untested)")
story.append(table([["Option", "Idea", "Risk"], ["Cooperative / buyer subscription", "Monthly fee for records, reports and oversight tools", "Willingness to pay unknown"],
    ["Per-transaction service fee", "Small fee on completed deals", "Parties may avoid the app to skip fees"], ["Grant-funded pilot", "Development partners fund a district pilot", "Time-limited; needs impact evidence"],
    ["Premium analytics", "Historical price and volume insights for cooperatives and processors", "Needs months of real data first"]], [42, 80, 50]))
H2("A15. Competitive differentiation (to be confirmed by market survey)")
L(["Evidence-first and neutral: serves both sides instead of only buyers or only farmers.", "Does not require holding money, so it can launch without a payment licence.",
   "Built for low-resource use: mobile web, no app-store install, SMS/USSD planned.", "Open, documented code that a small student team can maintain."])
H2("A16. Implementation roadmap")
story.append(table([["Stage", "Focus", "Exit test"], ["1 (done)", "Working MVP with tests", "Demo with fictional data"], ["2", "Phone testing, Kinyarwanda UI, HTTPS pilot server, SMS/WhatsApp notices", "5-10 real users complete a deal"],
    ["3", "Cooperative integration, analytics, anomaly flags", "One cooperative uses it weekly"], ["4", "USSD, voice, routes, authorised mobile-money integration", "Legal and partner agreements in place"]], [20, 100, 52]))
H2("A17. Risks and mitigation")
story.append(table([["Risk", "Mitigation"], ["Users do not adopt a digital process", "Start with cooperative staff as helpers; SMS/USSD later; simple screens"],
    ["Fake or edited evidence", "Hashes, server timestamps, two-sided review, human mediation; AI is never the judge"], ["Legal exposure (payments, data)", "No money handling; legal advice before any payment feature; data-protection review"],
    ["Poor connectivity", "Small pages now; offline queue planned"], ["AI misreads photos", "Draft-only, mandatory human confirmation, accuracy testing with real photos"]], [60, 112]))
H2("A18. Team and required partnerships")
B("<b>Team:</b> project initiator (engineering student) and student collaborators. <b>No partnerships are claimed.</b> Needed: a pilot cooperative or collection centre, an agronomy/dairy adviser, "
  "a legal adviser, and later a licensed payment provider.")
H2("A19. Expected impact (hypotheses to measure)")
L(["Fewer unresolved quality and payment disputes.", "Faster payment confirmation after delivery.", "More small farmers able to document deals and access buyers.",
   "Measure with a baseline before the pilot: dispute count, days-to-payment, volumes recorded."])
H2("A20. Closing pitch and call to action")
B("AmataShield turns informal milk deals into a shared record both sides can trust. We ask for: a pilot cooperative, field feedback, a dairy-technical mentor, and support to test with real farmers.")

# ================================================================= PART B
H1("PART B - TECHNICAL REPORT")
H2("B1. Executive summary")
B("AmataShield is a Flask (Python) and plain-JavaScript web application with a SQLite database that records milk transactions between farmers and buyers, with drivers, cooperative administrators and system administrators. "
  "It implements user accounts and roles, a marketplace, two-party acceptance, driver assignment, evidence upload with hashing, delivery steps, payment status records, disputes, dashboards, an audit history, "
  "and server-side Gemini integration with mandatory human review. <b>22 automated tests pass</b>. Not yet tested: real Gemini calls, physical phones, the browser camera on a device, load, and security review.")
H2("B2. Background of the Rwandan dairy sector")
B("This section is intentionally limited. The project documents the founder's <i>preliminary field observations</i> but <b>has not yet verified national dairy statistics</b>. "
  "Before external submission, add sourced figures (production, number of cooperatives and collection centres, cold-chain capacity) from official sources and cite them in the references list.")
H2("B3. Problem statement")
B("Milk transactions between small producers and buyers often rely on verbal agreements. When quality is questioned, payment is delayed or quantities differ, there is no shared, timestamped record, so disputes are hard to resolve fairly.")
H2("B4. Research findings (status labels)")
story.append(table([["Finding", "Source", "Status"],
    ["Hard to connect farmers with reliable buyers", "Founder's preliminary research", "User-provided, unverified"], ["Spoilage and cold-chain difficulty", "Founder", "User-provided, unverified"],
    ["Quality-rejection disputes", "Founder", "User-provided, unverified"], ["Minimum delivery quantities", "Founder", "User-provided, unverified"],
    ["Delayed payment, fraud, transaction disagreements", "Founder", "User-provided, unverified"], ["Weak documentation; digital-literacy barriers", "Founder", "User-provided, unverified"],
    ["Peer-to-peer hosting model: platform records decisions, no payments", "Founder's notebook design", "Design decision (implemented)"],
    ["Driver role and in-app/phone/SMS/WhatsApp hiring", "Founder's notebook", "Driver role implemented; SMS/WhatsApp/chat proposed"],
    ["Browser can open the phone camera", "Web platform capability", "Implemented; not device-tested here"]], [78, 48, 46]))
H2("B5. Project justification and objectives")
L(["Create a shared, traceable record for each milk transaction.", "Reduce disputes by requiring evidence before pickup and by giving both parties the same view.",
   "Keep the system affordable: one small server, open-source tools, pay-per-use AI.", "Prepare for SMS/USSD, mobile-money and cooperative integration without redesigning the core."])
H2("B6. Scope and limitations")
B("In scope: web MVP, roles, deals, evidence, payment records, disputes, dashboards, AI drafts, documentation, tests. "
  "Out of scope now: money movement, escrow, SMS/USSD, offline mode, GPS routing, voice, regulatory approval. AmataShield does not certify milk quality.")
H2("B7. Existing approaches and relevant platforms")
B("Informal channels (calls, WhatsApp, notebooks) and cooperative collection records are the baseline. General peer-to-peer marketplaces (the founder's example is a crypto P2P exchange) show a model where the platform hosts the "
  "agreement and evidence while payment happens outside. A systematic review of Rwandan agri-marketplaces and dairy-sector digital tools is <b>not yet done</b>.")
H2("B8. System requirements")
H3("Functional requirements")
story.append(table([["ID", "Requirement", "Status"], ["F1", "Register, sign in/out, hashed passwords, profiles", "Implemented, tested"], ["F2", "Roles: farmer, buyer, driver, cooperative admin, system admin", "Implemented, tested"],
    ["F3", "Post and browse deals with filters", "Implemented, tested (API)"], ["F4", "Two-party acceptance with timestamps and terms fingerprint", "Implemented, tested"],
    ["F5", "Driver applications and approval", "Implemented, tested"], ["F6", "Evidence upload with categories, hash, history", "Implemented, tested"],
    ["F7", "Pickup requires quality evidence; arrival; buyer receipt", "Implemented, tested"], ["F8", "Payment states: unconfirmed, reported, confirmed, disputed", "Implemented, tested"],
    ["F9", "Disputes: open, comment, evidence, proposal, agree, mediator outcome", "Implemented, tested"], ["F10", "AI drafts with human review (receipt, lactometer, summary, consistency, dispute help)", "Implemented; tested with a fake AI only"],
    ["F11", "Role dashboards", "Implemented, API tested"], ["F12", "SMS/USSD, chat, GPS distance, 1-minute booking window", "Proposed, not built"]], [12, 112, 48]))
H3("Non-functional requirements")
story.append(table([["Area", "Requirement", "Status"], ["Usability", "Mobile-first, large touch targets, plain language", "Implemented; needs user testing"], ["Security", "Hashed passwords, server-side checks, upload checks, CSRF header, access control per deal", "Implemented; no external audit"],
    ["Privacy", "Phone numbers shown only to parties; minimal data sent to AI", "Implemented"], ["Performance", "Pilot scale on one small server", "Not load-tested"], ["Reliability", "Daily backups of database and uploads", "Procedure only (Section B16)"],
    ["Maintainability", "Plain SQL, one routes file, tests, docs", "Implemented"], ["Accessibility", "Labels, focus outlines, contrast", "Basic; not audited"]], [30, 100, 42]))
H2("B9. System architecture")
D(diagram_arch())
B("The browser loads one HTML page and JavaScript. All data moves as JSON over HTTPS to Flask. Flask checks who the user is, what role they have and what part they play in the deal before touching the database or files. "
  "Only the server talks to Gemini, so the API key is never exposed.")
H2("B10. Database architecture")
D(diagram_erd())
story.append(P("Figure B2 - Entity relationships (simplified). The exact SQL is in database/schema.sql (Part C).", "small"))
B("Design choices: SQLite for zero-cost pilots; timestamps as UTC text; evidence rows are insert-only; <i>output_json</i> keeps the raw AI draft unchanged while <i>confirmed_json</i> stores what a person verified; <i>terms_hash</i> fixes the agreed terms.")
H2("B11. Use-case diagram")
D(diagram_usecase())
H2("B12. Data-flow diagram (level 0) and process flowchart")
D(diagram_dfd())
D(diagram_states())
story.append(P("Figure B4 - Transaction lifecycle. Disputes can be opened from any live state and return the deal to its previous state when resolved.", "small"))
H2("B13. AI integration architecture")
D(diagram_ai())
B("Prompts (backend/ai/prompts.py) tell Gemini to report only what is visible, return null when unclear, never judge safety and never confirm payments, and to answer in one JSON object. "
  "Text analyses send only structured facts (no phone numbers). A missing or failing AI service returns a clear error and never blocks the normal workflow. <b>Real-API behaviour is untested here</b> because no key or network was available in the build environment.")
H2("B14. User-interface design")
B("Visual identity: deep green (trust, agriculture), fresh green (growth), white (cleanliness), warm gold (primary actions), dark navy (technical sections). "
  "Single-page layout with bottom navigation for thumb reach, big buttons, status badges, and a server-provided list of allowed actions so each user only sees valid buttons.")
H2("B15. Security and privacy")
story.append(table([["Threat", "Control in the code"], ["Stolen passwords from database", "Salted hash (Werkzeug); never stored or logged in plain text"], ["Guessing passwords", "5 failed attempts per phone lock login for 5 minutes (in memory)"],
    ["Cross-site request forgery", "Mutating requests require X-Requested-With header; SameSite=Lax cookie"], ["Accessing another person's deal or file", "Every route checks the user's role in that deal"],
    ["Malicious upload", "Magic-byte check (JPG/PNG/WEBP/PDF only), random file names, 8 MB limit"], ["Script injection in the page", "All user text is escaped before display"],
    ["AI key leakage", "Key only in server environment (.env, git-ignored)"], ["Tampered evidence", "SHA-256 stored; server timestamps; insert-only evidence"]], [60, 112]))
callout_priv = callout("<b>Not yet done:</b> HTTPS deployment, formal penetration test, data-retention policy, consent text for photos, and a legal review under Rwanda's personal-data protection rules (verify the current law with a lawyer). "
                       "Do not collect real farmer data in a pilot before these are addressed.", "warn")
story.append(callout_priv)
H2("B16. Implementation methodology, deployment and backups")
B("Iterative: notebook sketches -> data model -> API with tests -> frontend -> documentation. Tests were written with the API so rules are protected as the code grows.")
H3("Deployment steps (small pilot)")
L(["Rent a small Linux server or use a free-tier host; install Python 3.11+.", "Copy the project, create a virtual environment, pip install -r requirements.txt.",
   "Create .env with a long random SECRET_KEY, SESSION_COOKIE_SECURE=1 and the Gemini key.", "Run with a production server (for example: pip install gunicorn; gunicorn -w 2 'backend.app:create_app()'), behind HTTPS (Caddy or nginx + Let's Encrypt).",
   "Back up database/amatashield.db and uploads/ daily to another location; test a restore."])
H2("B17. Testing strategy and actual results")
B("Automated tests (tests/test_api.py, Python unittest) run the real Flask app against a temporary database. The Gemini network call is replaced with a fake.")
story.append(callout("<b>Actual result recorded during this build:</b> <font face='Courier'>" + x(TEST_SUMMARY.replace("\n", " ")) + "</font> (22 tests).", "ok"))
story.append(table([["Area", "What the tests prove", "Result"], ["Accounts", "Register, login, logout, hash stored, validation, duplicates, lockout, CSRF header, admin-only account creation", "Passed"],
    ["Deals", "Role limits, two-party acceptance, terms hash, decline, privacy of phones, buy requests, full happy path with driver and payment, cancel rules", "Passed"],
    ["Evidence", "File-type check, access control, insert-only listing, no evidence before agreement, driver receipt block", "Passed"],
    ["Payments and disputes", "Seller rejection opens dispute, proposal and agreement resolve it, mediator outcome, state restoration", "Passed"],
    ["AI (fake)", "Drafts need review, human correction kept, raw draft preserved, no phones sent, errors handled, no change to payment status", "Passed with fake AI"],
    ["Admin", "Statistics, disabling a user ends their session", "Passed"]], [30, 112, 30]))
H3("Checks performed outside the unit tests")
L(["Server started; /api/health, index page, CSS, JS and logo returned HTTP 200; a login POST without the security header returned 403.", "JavaScript passed a syntax check (node --check).", "Demo seed script ran successfully."])
H3("Not tested (and exact steps to test them)")
story.append(table([["Not tested", "How to test"], ["Real Gemini calls", "Add GEMINI_API_KEY, upload a clear receipt photo, press 'Read with AI', compare each value with the photo"],
    ["Browser camera on a phone", "Open the site over HTTPS on an Android phone, Add evidence > Take photo, allow camera, capture, save"], ["Mobile responsiveness", "Open on 3 Android phones; use Chrome DevTools device mode; check every screen for horizontal scrolling"],
    ["Automated UI flow", "Add Playwright tests (Stage 2)"], ["Load and concurrency", "Use a tool such as Locust against a staging server"], ["Security review", "Run OWASP ZAP and ask a security mentor to review"]], [50, 122]))
H2("B18. Project costs and resource requirements")
B("Exact costs depend on quotes, so <b>no amounts are invented</b>. A budget spreadsheet (XLSX) is a later deliverable. Cost categories: development laptops (existing), small cloud server or free tier, domain name, "
  "Gemini API usage (pay per request; check current Google pricing), SMS gateway fees (Stage 2), field-testing transport and airtime, legal consultation, and optional phones for testing.")
H2("B19. Risks, sustainability and scalability")
B("Risks are in Part A17. Sustainability depends on a revenue model validated in the pilot. Scaling path: move SQLite to PostgreSQL, store files in object storage, add background jobs for notifications, "
  "add caching and monitoring, and separate the AI service. The single-routes design is deliberately simple; split it when the team grows.")
H2("B20. Conclusion")
B("The MVP demonstrates a complete, tested workflow on the server side and a mobile-first interface. The next evidence the project needs is not more code but real use: testing on phones and with a cooperative.")
H2("B21. References and appendices")
L(["Google, Gemini API documentation: https://ai.google.dev/gemini-api/docs (check current model names and pricing).", "Pallets, Flask documentation: https://flask.palletsprojects.com/",
   "OWASP Application Security Verification Standard and Cheat Sheet Series: https://owasp.org/", "SQLite documentation: https://www.sqlite.org/docs.html",
   "<b>To add after field verification:</b> official Rwandan dairy statistics, regulations on payment services and personal-data protection, and literature on dairy cold chains."])

# ================================================================= PART C
H1("PART C - COMPLETE SOURCE CODE")
B("Every file below is shown exactly as in the ZIP (long lines are wrapped; wrapped lines are indented). Colours: purple keywords, orange strings, grey comments, blue names.")
FILES = [
    ("README.md", "Project overview, install, run, test, limitations."), ("requirements.txt", "Python dependencies (only Flask)."), (".env.example", "Template for secrets; copy to .env."),
    (".gitignore", "Keeps secrets, databases and uploads out of git."), ("run.py", "Starts the development server."),
    ("backend/config.py", "Reads environment variables and .env."), ("backend/database.py", "SQLite connection and small query helpers."),
    ("backend/schemas.py", "Validation of every input field."), ("backend/auth.py", "Password check, session user, role decorator, login throttling."),
    ("backend/routes.py", "All API endpoints and business rules."), ("backend/app.py", "Application factory, CSRF guard, security headers."),
    ("backend/seed.py", "Fictional demo data loader."), ("backend/ai/prompts.py", "Prompts and safety rules for Gemini."), ("backend/ai/gemini.py", "Server-side Gemini REST client."),
    ("database/schema.sql", "Complete database schema."), ("database/sample_data.sql", "Demo rows (fictional)."),
    ("frontend/index.html", "Page shell."), ("frontend/css/style.css", "Mobile-first styling and brand colours."), ("frontend/js/app.js", "Single-page app: API calls, camera, views, router."),
    ("frontend/assets/logo.svg", "Logo."), ("tests/test_api.py", "22 automated tests."),
    ("documentation/API.md", "API reference."), ("documentation/TEAM_TASKS.md", "Starter task allocation."), ("documentation/ROADMAP.md", "Roadmap summary."),
]
for path, note in FILES:
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as fh:
        text = fh.read()
    story.append(P(x(path), "h2"))
    story.append(file_header(path, note + f"  ({len(text.splitlines())} lines)"))
    story.append(Spacer(1, 1.5 * mm))
    story.append(code_flowable(path, text))
    story.append(Spacer(1, 4 * mm))

# ================================================================= PART D
H1("PART D - TEAM LEARNING GUIDE")
B("Each concept follows the same pattern: <b>what it is, why AmataShield needs it, how it works, where it is in the code, how to change it, how to test it</b>.")
def concept(title, what, why, how, where, change, test):
    H2(title)
    story.append(table([["What", what], ["Why we need it", why], ["How it works", how], ["Where in code", where], ["How to modify", change], ["How to test", test]], [28, 144], header=False))
concept("D1. Frontend and backend talking (JSON API)",
       "The phone shows pages (frontend). The server holds rules and data (backend). They exchange small JSON messages.",
       "Keeps secrets (AI key, database) off the phone and lets many users share one record.",
       "app.js calls fetch('/api/deals/5/confirm', POST). Flask routes.py receives it, checks the user, changes the database, returns JSON. The page redraws.",
       "frontend/js/app.js function api(); backend/routes.py (@bp.get / @bp.post).",
       "Add an endpoint in routes.py, then call it with api() in app.js.", "Run the app, open browser DevTools > Network and watch requests; or add a test in tests/test_api.py.")
concept("D2. How the database stores information",
       "SQLite stores tables of rows in one file (database/amatashield.db).",
       "A deal, its evidence, payments and disputes must stay linked and survive restarts.",
       "schema.sql defines tables. deals.seller_id points to users.id (foreign key). Evidence rows are only ever inserted, never changed. Example: a 200 L deal for 350 RWF stores total_value 70000.",
       "database/schema.sql; backend/database.py (query, one, execute).", "Edit schema.sql, delete the .db file in development, restart.", "sqlite3 database/amatashield.db  then: select id,status from deals;")
concept("D3. Accounts, sessions and roles",
       "A session is a signed cookie that remembers who is signed in. A role (farmer, buyer...) limits what they can do.",
       "A farmer must not confirm a payment for another farmer; a buyer must not read another buyer's evidence.",
       "Login checks the password hash, then stores the user id in the cookie. @login_required('buyer') blocks other roles. role_in_deal() decides whether you are the seller, buyer or driver of one deal.",
       "backend/auth.py, backend/routes.py (role_in_deal, allowed_actions).", "Change allowed_actions() to alter which buttons/actions appear.", "tests: DealFlowTests.test_outsider_cannot_see_agreed_deal_or_phones")
concept("D4. How a transaction is accepted by both sides",
       "Both parties explicitly accept the same terms; each acceptance has a timestamp.",
       "Prevents 'I never agreed to that price' arguments.",
       "Example: Mukamana posts 200 L at 350 RWF (her acceptance is recorded). Buyer taps Accept (buyer time recorded; status pending_acceptance). Mukamana taps Confirm (status agreed). A SHA-256 fingerprint of the terms is saved.",
       "routes.py: create_deal, join_deal, confirm_deal, terms_fingerprint.", "Add fields to the fingerprint list in terms_fingerprint if new terms are added.", "tests: DealFlowTests.test_two_party_acceptance_and_totals")
concept("D5. How evidence is stored",
       "Photos, PDFs and typed measurements attached to a deal.",
       "Disputes need proof that both sides can see and that is hard to edit afterwards.",
       "The server checks the first bytes of the file (magic bytes), saves it under a random name, stores the original name, size, SHA-256 hash, server time and the phone's claimed time. Rows cannot be deleted from the app.",
       "routes.py: add_evidence, _file_kind, evidence_file; table evidence.", "Add a category: schema.sql CHECK list, schemas.py EVIDENCE_CATEGORIES, LABELS in app.js.", "tests: EvidenceTests")
concept("D6. How the browser camera works",
       "Browsers can ask permission to use the camera with navigator.mediaDevices.getUserMedia.",
       "Farmers can capture the lactometer at the moment of pickup without extra apps.",
       "app.js opens the rear camera into a video element, draws one frame to a canvas, converts it to a JPEG file and uploads it like any other file. Camera works only on HTTPS or localhost. The 'Choose file' button is a fallback that opens the phone's camera app.",
       "frontend/js/app.js: captureFromCamera, evidenceDialog.", "Change quality in canvas.toBlob(..., 0.9).", "Phone test over HTTPS (see Part B17).")
concept("D7. How Gemini receives and analyses images",
       "A Google AI model that can read images and text.",
       "Saves typing: it drafts the amount on a receipt or the reading on a lactometer photo for a person to check.",
       "routes.py reads the saved file, gemini.py base64-encodes it and sends it with prompts.py rules to the Gemini REST API using the server's key. The reply (JSON) is saved as a draft. The user opens 'Check and confirm', corrects values and confirms; only then is confirmed_json saved.",
       "backend/ai/gemini.py, backend/ai/prompts.py, routes.py (ai_evidence, review_ai), app.js (aiReview).", "Edit prompts.py to change wording or fields. Change the model with GEMINI_MODEL in .env.", "Unit test uses a fake; real test: add the key and try a clear photo.")
H2("D8. Running and testing the project")
L(["python -m venv .venv, activate it, pip install -r requirements.txt.", "cp .env.example .env and edit it.", "python -m backend.seed then python run.py, open http://localhost:5000.",
   "python -m unittest discover -s tests -v (takes about 20 seconds because password hashing is deliberately slow)."])
H2("D9. Common errors and fixes")
story.append(table([["Error", "Cause", "Fix"], ["ModuleNotFoundError: flask", "Virtual environment not active", "Activate .venv; pip install -r requirements.txt"], ["Address already in use", "Another program uses port 5000", "Change the port in run.py"],
    ["403 'Missing security header'", "A fetch call lacks X-Requested-With", "Use the api() helper in app.js"], ["Camera not available", "Page is not HTTPS", "Use localhost, HTTPS, or 'Choose file'"],
    ["AI is not configured", "GEMINI_API_KEY missing", "Add it to .env and restart"], ["no such table", "Old database file", "Delete database/amatashield.db in development"],
    ["429 Too many attempts", "5 wrong passwords", "Wait 5 minutes (or restart in development)"], ["413 File too large", "Over 8 MB", "Take a smaller photo or raise MAX_UPLOAD_MB"]], [48, 52, 72]))
H2("D10. How team members can contribute")
L(["Pick a task in documentation/TEAM_TASKS.md; create a git branch; change one thing; add or update a test; run all tests; open a pull request.", "Non-coders: field interviews (with consent), photo collection for AI accuracy, translation to Kinyarwanda, documentation review.",
   "Rules: never commit .env, never test with real farmers' private data, never claim a feature works without testing it."])

# ================================================================= PART E
H1("PART E - FUTURE DEVELOPMENT")
H2("E1. Remaining work (honest list)")
L(["Test on real Android phones; fix layout issues.", "Verify sector facts and survey existing platforms.", "Add HTTPS deployment, backups and monitoring.", "Kinyarwanda interface; larger-text mode.",
   "Notifications (SMS/WhatsApp) and the notebook's 1-minute booking window.", "In-app chat; GPS distance filter; persistent rate limiting.", "Legal review of data protection; consent text."])
H2("E2. Roadmap of advanced features (all proposed, none implemented unless stated)")
feats = [
 ["1. AI evidence interpretation", "Disputes over lactometer/receipts", "Labelled photos, readings", "Gemini now; later a small vision model", "Medium", "Stage 1-3 (draft reader exists)", "Misreads; must stay advisory"],
 ["2. Farmer aggregation", "Small volumes miss buyer minimums", "Offers by district and time", "Grouping by location/time window", "Medium", "Stage 3", "Needs trusted cooperative; split payments"],
 ["3. Route optimisation", "Costly collection trips", "GPS points, road network", "Vehicle-routing heuristics, OpenStreetMap", "Hard", "Stage 4", "Poor map data; GPS cost"],
 ["4. Kinyarwanda voice", "Literacy barriers", "Kinyarwanda speech/text samples", "Speech-to-text and text-to-speech services", "Hard", "Stage 4", "Accuracy for dialects, data scarcity"],
 ["5. SMS and USSD", "Feature phones, low data", "Short code, aggregator account", "SMS gateway; USSD menus mapped to API", "Medium", "Stage 2-3", "Operator agreements and fees"],
 ["6. Anomaly detection", "Fraud or odd prices/volumes", "Months of real transaction history", "Rules first, then statistics", "Medium", "Stage 3", "False alarms; needs data"],
 ["7. Historical analytics", "Prices and reliability unclear", "Completed deals", "SQL reports, charts", "Easy", "Stage 2-3", "Privacy aggregation"],
 ["8. Cooperative integration", "Records held in notebooks", "Member lists, collection logs", "CSV import, API", "Medium", "Stage 3", "Partner buy-in"],
 ["9. Mobile-money integration", "Payment status stays manual", "Licensed provider API access", "Provider API + webhooks; reconcile with records", "Hard", "Stage 4", "Licensing, fees, fraud liability"],
 ["10. Market intelligence", "Farmers lack price visibility", "Prices over time, regions", "Aggregated dashboards", "Medium", "Stage 4", "Needs enough volume"]]
story.append(table([["Feature", "Problem", "Data", "Technology", "Difficulty", "Stage", "Risks"]] + feats, [26, 24, 24, 30, 14, 20, 34]))
H2("E3. Hardware opportunities")
B("Low-cost digital lactometer or temperature probe with Bluetooth (electronics-engineering opportunity); battery-powered cooling-monitor tags for transport; QR-labelled milk cans. "
  "These are <b>proposals</b>: they need field requirements, cost study and prototype testing before any claim.")
H2("E4. Escrow: legal and technical requirements (overview, not legal advice)")
L(["Holding or moving customer money is typically a regulated payment activity in Rwanda; expect to need authorisation or to partner with an already-licensed provider. Confirm with the National Bank of Rwanda and a lawyer.",
   "Technical: provider API, webhooks, double-entry ledger, reconciliation, refunds, fraud controls, audit logs, secure key storage, uptime monitoring.",
   "Business: clear terms of service, dispute and refund rules, customer identification checks required by the provider.",
   "Until then, AmataShield records statuses only and says so on screen."])
H2("E5. Deployment and scaling roadmap")
story.append(table([["Step", "Change"], ["Pilot", "One small server, SQLite, daily backups, HTTPS"], ["Growth", "PostgreSQL, object storage for photos, background worker, monitoring"],
    ["Scale", "Separate AI service, queue, read replicas, mobile apps if needed"]], [30, 142]))
SP(6)
story.append(callout("<b>Delivery status of this build:</b> Stage 1 complete - source ZIP and this book. Still to produce in later stages: editable Word report, PowerPoint pitch, budget XLSX, standalone API/installation/roadmap PDFs, "
                     "task-allocation PDF, test report PDF, real screenshots from a running browser, and verified sector research.", "warn"))

Doc(OUT).multiBuild(story)
print("built", OUT)
