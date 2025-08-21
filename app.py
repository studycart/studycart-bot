import os
import json
import time
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from telegram import Bot
import razorpay
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
FILE_PATH = "file_to_send.pdf"

# ✅ Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ✅ Ensure order_map.json exists
if not os.path.exists("order_map.json"):
    with open("order_map.json", "w") as f:
        json.dump({}, f)

# ✅ Internal mapping helpers
def save_order_mapping(order_id, telegram_user_id):
    try:
        with open("order_map.json", "r+") as f:
            data = json.load(f)
            data[order_id] = telegram_user_id
            f.seek(0)
            json.dump(data, f)
            f.truncate()
    except Exception as e:
        logging.error(f"Error saving order mapping: {e}")

def get_telegram_user(order_id):
    try:
        with open("order_map.json", "r") as f:
            data = json.load(f)
            return data.get(order_id)
    except Exception as e:
        logging.error(f"Error retrieving user from mapping: {e}")
        return None

# ✅ Serve homepage
@app.route("/")
def home():
    return send_from_directory("static", "index.html")

# ✅ Serve Razorpay payment page
@app.route("/buy")
def buy_page():
    return render_template("buy_page.html")

# ✅ Serve static HTML pages (about, contact, etc.)
@app.route("/<page>")
def static_html(page):
    file_path = f"{page}.html"
    full_path = os.path.join(app.static_folder, file_path)
    if os.path.exists(full_path):
        return send_from_directory("static", file_path)
    return "Page not found", 404

# ✅ Razorpay order creation
@app.route("/create_payment_razorpay", methods=["POST"])
def create_payment_razorpay():
    data = request.json
    user_id = data.get("user_id")
    amount = data.get("amount", 10000)  # ₹100 in paise

    if not user_id:
        return jsonify({"error": "User ID is missing"}), 400

    order_payload = {
        "amount": amount,
        "currency": "INR",
        "receipt": f"receipt_{int(time.time())}",
        "notes": {
            "product": "Digital File Purchase"
        }
    }

    try:
        order = razorpay_client.order.create(data=order_payload)
        save_order_mapping(order["id"], user_id)

        return jsonify({
            "order_id": order["id"],
            "key_id": RAZORPAY_KEY_ID,
            "amount": order["amount"]
        })
    except Exception as e:
        logging.error(f"Order creation failed: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Razorpay webhook for Telegram delivery
@app.route("/webhook/razorpay", methods=["POST"])
async def razorpay_webhook():
    webhook_body = request.data.decode("utf-8")
    webhook_signature = request.headers.get("x-razorpay-signature")

    try:
        razorpay_client.utility.verify_webhook_signature(
            webhook_body, webhook_signature, WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        logging.warning("Invalid webhook signature")
        return "Invalid signature", 400

    webhook_data = request.json
    event = webhook_data.get("event")

    if event == "payment.captured":
        payment_entity = webhook_data["payload"]["payment"]["entity"]
        order_id = payment_entity["order_id"]
        user_id = get_telegram_user(order_id)

        if user_id and str(user_id).isdigit():
            bot = Bot(token=TELEGRAM_TOKEN)
            try:
                with open(FILE_PATH, "rb") as document:
                    await bot.send_document(
                        chat_id=int(user_id),
                        document=document,
                        caption="✅ Thank you for your purchase! Here is your file."
                    )
            except Exception as e:
                logging.error(f"❌ Failed to send file to user {user_id}: {e}")

    return "Webhook processed", 200
