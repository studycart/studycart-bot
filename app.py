import os
import requests
import hashlib
import json
from flask import Flask, render_template, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackContext

# --- CONFIGURATION ---
# Load your secret keys from environment variables on Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
EASEBUZZ_KEY = os.getenv('EASEBUZZ_API_KEY')
EASEBUZZ_SALT = os.getenv('EASEBUZZ_SALT')
RENDER_URL = os.getenv('WEB_URL') # Your Render URL e.g., "https://studycart-store.onrender.com"

# The file you want to send after successful payment
FILE_PATH = "file_to_send.pdf"

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# A simple in-memory "database" to map transaction IDs to user IDs
# In a real app, you would use a proper database like Redis or PostgreSQL
txnid_to_userid_map = {}

# --- TELEGRAM BOT HANDLERS ---
def start(update: Update, context: CallbackContext):
    """Handles the /start command."""
    user_id = update.effective_chat.id

    # URL for the Web App button, passing the user's ID
    web_app_url = f"{RENDER_URL}/buy_page?user_id={user_id}"

    keyboard = [
        [InlineKeyboardButton("Buy Now (₹1)", web_app={"url": web_app_url})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Welcome! Click the button below to purchase your exclusive file for just ₹1.",
        reply_markup=reply_markup
    )

# --- EASEBUZZ HELPER FUNCTION ---
def create_easebuzz_payment(amount, txnid, firstname, email, phone, productinfo, user_id):
    """Creates a payment request with Easebuzz and returns the payment URL."""
    hash_string = f"{EASEBUZZ_KEY}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|||||||||||{EASEBUZZ_SALT}"
    payment_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()

    payload = {
        'key': EASEBUZZ_KEY,
        'txnid': txnid,
        'amount': amount,
        'productinfo': productinfo,
        'firstname': firstname,
        'email': email,
        'phone': phone,
        'surl': f'{RENDER_URL}/webhook/easebuzz', # Success URL
        'furl': f'{RENDER_URL}/webhook/easebuzz', # Failure URL
        'hash': payment_hash
    }

    # Use Easebuzz production or test URL accordingly
    response = requests.post("https://pay.easebuzz.in/payment/initiateLink", data=payload)

    if response.status_code == 200:
        response_data = response.json()
        if response_data['status'] == 1:
            txnid_to_userid_map[txnid] = user_id # Store the mapping
            return response_data['data'] # This is the payment URL
    return None

# --- FLASK ROUTES ---
@app.route('/buy_page')
def buy_page():
    """Renders the payment page."""
    user_id = request.args.get('user_id')
    return render_template('buy_page.html', user_id=user_id)

@app.route('/create_payment', methods=['POST'])
def create_payment_endpoint():
    """Endpoint called by the frontend to initiate payment."""
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID is missing'}), 400

    # Create a unique transaction ID
    import time
    txnid = f"studycart-{user_id}-{int(time.time())}"

    # Dummy data, you can collect this from the user if needed
    payment_url = create_easebuzz_payment(
        amount="1.0",
        txnid=txnid,
        firstname="Customer",
        email="customer@example.com",
        phone="9999999999",
        productinfo="Digital File Purchase",
        user_id=user_id
    )

    if payment_url:
        return jsonify({'payment_url': payment_url})
    else:
        return jsonify({'error': 'Failed to create payment link'}), 500

@app.route('/webhook/easebuzz', methods=['POST'])
def easebuzz_webhook():
    """Handles webhook notifications from Easebuzz."""
    response_data = request.form
    txnid = response_data.get('txnid')
    status = response_data.get('status')

    # --- IMPORTANT: Verify the webhook authenticity ---
    reverse_hash_string = f"{EASEBUZZ_SALT}|{status}|||||||||||{response_data.get('email')}|{response_data.get('firstname')}|{response_data.get('productinfo')}|{response_data.get('amount')}|{txnid}|{EASEBUZZ_KEY}"
    calculated_hash = hashlib.sha512(reverse_hash_string.encode('utf-8')).hexdigest()

    if calculated_hash != response_data.get('hash'):
        print("Webhook security check failed: Hash mismatch")
        return "Hash mismatch", 400 # Or just ignore

    # --- Process the payment ---
    if status == 'success' and txnid in txnid_to_userid_map:
        user_id = txnid_to_userid_map.pop(txnid) # Retrieve and remove

        try:
            # Send the file to the user
            with open(FILE_PATH, 'rb') as document:
                bot.send_document(
                    chat_id=user_id,
                    document=document,
                    caption="Thank you for your purchase! Here is your file."
                )
            print(f"Successfully sent file to user {user_id}")
        except Exception as e:
            print(f"Failed to send file to user {user_id}: {e}")

    return "Webhook received", 200

# --- SETUP ROUTES FOR TELEGRAM AND SERVER ---
@app.route('/set_webhook', methods=['GET'])
def setup_webhook():
    """A one-time setup endpoint to register the webhook with Telegram."""
    webhook_url = f"{RENDER_URL}/telegram"
    if bot.set_webhook(url=webhook_url):
        return "Telegram webhook setup OK"
    else:
        return "Telegram webhook setup failed"

@app.route('/telegram', methods=['POST'])
def telegram_webhook_handler():
    """Handles incoming updates from Telegram."""
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.add_handler(CommandHandler("start
