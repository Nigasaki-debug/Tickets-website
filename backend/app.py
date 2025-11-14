from flask import Flask, request, jsonify
import requests, qrcode, os, random, string, json
from datetime import datetime
import yagmail

# ---------------------- CONFIG ----------------------
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

# Always save inside backend/tickets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TICKETS_DIR = os.path.join(BASE_DIR, "tickets")
os.makedirs(TICKETS_DIR, exist_ok=True)

SALES_FILE = os.path.join(TICKETS_DIR, "sales.json")

# ----------------------------------------------------

app = Flask(__name__)

# ---------- UTILITY FUNCTIONS ----------
def generate_ticket_id():
    return "TKT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_qr_code(ticket_id):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(ticket_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    qr_filename = os.path.join(TICKETS_DIR, f"{ticket_id}.png")
    img.save(qr_filename)

    print("QR CREATED:", qr_filename)
    return qr_filename

def save_sale(name, email, quantity, payment_reference):
    sale = {
        "name": name,
        "email": email,
        "quantity": quantity,
        "payment_reference": payment_reference,
        "time": datetime.now().isoformat()
    }

    if os.path.exists(SALES_FILE):
        try:
            with open(SALES_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []
    else:
        data = []

    data.append(sale)

    with open(SALES_FILE, "w") as f:
        json.dump(data, f, indent=4)

    print("SALE SAVED:", sale)

def send_ticket_email(receiver_email, name, tickets):
    subject = "🎟️ Your Ticket(s)"
    body = f"Hi {name},\nYour tickets are attached.\n"

    yag = yagmail.SMTP(SENDER_EMAIL, APP_PASSWORD)
    attachments = [t["qr_code"] for t in tickets]

    yag.send(
        to=receiver_email,
        subject=subject,
        contents=body,
        attachments=attachments
    )

    print("EMAIL SENT TO:", receiver_email)

# ---------------------------------------------------------

@app.route("/")
def home():
    return jsonify({"message": "Ticket backend running!"})

@app.route("/verify", methods=["POST"])
def verify_payment():
    try:
        data = request.get_json()
        reference = data.get("reference")
        name = data.get("name")
        email = data.get("email")
        quantity = int(data.get("quantity", 1))

        print("PAYMENT VERIFY REQUEST:", data)

        headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        response = requests.get(url, headers=headers)
        result = response.json()

        print("PAYSTACK RESPONSE:", result)

        if result.get("data", {}).get("status") == "success":
            tickets = []

            for _ in range(quantity):
                ticket_id = generate_ticket_id()
                qr_path = create_qr_code(ticket_id)
                tickets.append({"ticket_id": ticket_id, "qr_code": qr_path})

                print("TICKET CREATED:", ticket_id)

            save_sale(name, email, quantity, reference)
            send_ticket_email(email, name, tickets)

            return jsonify({
                "status": "success",
                "message": "Tickets generated and emailed!",
                "tickets": [t["ticket_id"] for t in tickets]
            })
        else:
            return jsonify({"status": "failed", "message": "Payment not verified."})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error", "message": str(e)})

# ---------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
