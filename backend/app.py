from flask import Flask, render_template, request, jsonify
import requests, qrcode, io, os, random, string, json
from datetime import datetime
import yagmail

# Create Flask app
app = Flask(__name__, template_folder='.')  # use root folder for index.html

# ---------------------- CONFIG ----------------------
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")       # Gmail address
APP_PASSWORD = os.getenv("APP_PASSWORD")       # Gmail app password
TICKETS_DIR = os.getenv("TICKETS_DIR", "tickets")  # default folder if not set
# ----------------------------------------------------

# Ensure tickets directory exists
if not os.path.exists(TICKETS_DIR):
    os.makedirs(TICKETS_DIR)

SALES_FILE = os.path.join(TICKETS_DIR, "sales.json")

# ---------- UTILITY FUNCTIONS ----------
def generate_ticket_id():
    """Generate a unique 10-character ticket ID."""
    return "TKT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_qr_code(ticket_id, save_path):
    """Create and save a QR code image for a ticket."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(ticket_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(save_path)

def send_ticket_email(receiver_email, name, tickets):
    """Send email with ticket details and QR attachments."""
    subject = f"🎟️ Your Ticket(s) for the Event"
    body = f"""
Hi {name},

Your payment has been confirmed! 🎉
Below are your ticket details:

{"".join([f"- Ticket ID: {t['ticket_id']}\n" for t in tickets])}

Each ticket has its own QR code attached to this email.
Please present it at the event gate for entry.

Thank you for your purchase!

-- Event Team
"""
    yag = yagmail.SMTP(SENDER_EMAIL, APP_PASSWORD)
    attachments = [t["qr_code"] for t in tickets]
    yag.send(to=receiver_email, subject=subject, contents=body, attachments=attachments)
    print(f"📧 Email sent to {receiver_email}")

def save_sale(name, email, quantity, payment_reference):
    """Save a sale record to JSON file (without phone number)."""
    sale = {
        "name": name,
        "email": email,
        "quantity": quantity,
        "payment_reference": payment_reference,
        "time": datetime.now().isoformat()
    }

    # Load existing data
    if os.path.exists(SALES_FILE):
        with open(SALES_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    # Append new sale and save
    data.append(sale)
    with open(SALES_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------- FLASK ROUTES ----------
@app.route("/")
def home():
   return jsonify({"message": "Ticket backend running!"})

@app.route("/verify", methods=["POST"])
def verify_payment():
    data = request.get_json()
    reference = data.get("reference")
    name = data.get("name")
    email = data.get("email")
    quantity = int(data.get("quantity", 1))

    # Verify payment with Paystack
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    response = requests.get(url, headers=headers)
    result = response.json()

    if result.get("data", {}).get("status") == "success":
        tickets = []

        # Generate tickets
        for _ in range(quantity):
            ticket_id = generate_ticket_id()
            qr_filename = f"{TICKETS_DIR}/{ticket_id}.png"
            create_qr_code(ticket_id, qr_filename)
            tickets.append({"ticket_id": ticket_id, "qr_code": qr_filename})

        # Save sale to JSON
        save_sale(name, email, quantity, reference)

        # Send tickets via email
        send_ticket_email(email, name, tickets)

        return jsonify({
            "status": "success",
            "message": f"Payment verified and tickets sent to {email}.",
            "tickets": tickets
        })
    else:
        return jsonify({
            "status": "failed",
            "message": "Payment verification failed."
        })

# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
