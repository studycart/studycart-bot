import os
import razorpay
from flask import Flask, render_template, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackContext

# --- CONFIGURATION ---
# Load your secret keys from environment variables on Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
RENDER_URL = os.getenv('WEB_URL') 
# This is a secret you create yourself in the Razorpay webhook settings
WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET') 

# The file you want to send after successful payment
FILE_PATH = "file_to_send.pdf"

# --- FLASK APP & BOT INITIALIZATION ---
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# --- TELEGRAM BOT HANDLERS ---
def start(update: Update, context: CallbackContext):
    """Handles the /start command."""
    user_id = update.effective_chat.id
    web_app_url = f"{RENDER_URL}/buy_page?user_id={user_id}"
    
    keyboard = [[InlineKeyboardButton("Buy Now (₹1)", web_app={"url": web_app_url})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "Welcome! Click the button below to purchase your exclusive file for just ₹1.",
        reply_markup=reply_markup
    )

# --- FLASK ROUTES ---
@app.route('/buy_page')
def buy_page():
    """Renders the payment page."""
    return render_template('buy_page.html')

@app.route('/create_payment_razorpay', methods=['POST'])
def create_payment_razorpay():
    """Endpoint called by the frontend to create a Razorpay order."""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User ID is missing'}), 400

    # Razorpay requires amount in the smallest currency unit (100 paise = 1 INR)
    amount_in_paise = 100 
    
    order_payload = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'receipt_user_{user_id}',
        'notes': {
            'telegram_user_id': str(user_id) # Store user ID in notes to retrieve later
        }
    }
    
    try:
        order = razorpay_client.order.create(data=order_payload)
        response_data = {
            'order_id': order['id'],
            'key_id': RAZORPAY_KEY_ID,
            'amount': order['amount']
        }
        return jsonify(response_data)
    except Exception as e:
        print(f"Error creating Razorpay order: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    """Handles webhook notifications from Razorpay for automated verification."""
    webhook_body = request.data
    webhook_signature = request.headers.get('x-razorpay-signature')
    
    try:
        # --- IMPORTANT: Verify the webhook authenticity ---
        razorpay_client.utility.verify_webhook_signature(
            webhook_body, webhook_signature, WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError as e:
        print(f"Webhook security check failed: {e}")
        return "Invalid signature", 400

    # --- Process the payment event ---
    webhook_data = request.json
    event = webhook_data.get('event')

    if event == 'payment.captured':
        payment_entity = webhook_data['payload']['payment']['entity']
        user_id = payment_entity['notes'].get('telegram_user_id')

        if user_id:
            try:
                # Send the file to the user who paid
                with open(FILE_PATH, 'rb') as document:
                    bot.send_document(
                        chat_id=int(user_id),
                        document=document,
                        caption="Thank you for your purchase! Here is your file."
                    )
                print(f"Successfully sent file to user {user_id}")
            except Exception as e:
                print(f"Failed to send file to user {user_id}: {e}")
                
    return "Webhook processed", 200

# --- SETUP ROUTES FOR TELEGRAM AND SERVER ---
@app.route('/set_webhook', methods=['GET'])
def setup_webhook():
    """A one-time setup endpoint to register the bot's webhook with Telegram."""
    webhook_url = f"{RENDER_URL}/telegram"
    if bot.set_webhook(url=webhook_url):
        return "Telegram webhook setup OK"
    else:
        return "Telegram webhook setup failed"

@app.route('/telegram', methods=['POST'])
def telegram_webhook_handler():
    """Handles incoming updates from Telegram."""
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.process_update(update)
    return "OK", 200
    
@app.route('/')
def index():
    """A simple route to check if the bot is running."""
    return "Bot is running with Razorpay!", 200
