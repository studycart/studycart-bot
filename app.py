import os
import razorpay
import asyncio
from flask import Flask, render_template, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
RENDER_URL = os.getenv('WEB_URL')
WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')
FILE_PATH = "file_to_send.pdf"

# Validate environment variables
if not all([TELEGRAM_TOKEN, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RENDER_URL, WEBHOOK_SECRET]):
    raise RuntimeError("Missing one or more required environment variables")

# --- FLASK & BOT INITIALIZATION ---
app = Flask(__name__)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Initialise the Telegram bot immediately (works in serverless)
loop = asyncio.get_event_loop()
if not loop.is_running():
    loop.run_until_complete(application.initialize())
    print("Telegram bot initialized")

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    web_app_url = f"{RENDER_URL}/buy_page?user_id={user_id}"

    keyboard = [[InlineKeyboardButton("Buy", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        "Join Our Official Channel For More - \n"
        "https://t.me/+ZLiGAAJIsZlhNTII\n\n"
        "Whatsapp Channel-\n"
        "https://whatsapp.com/channel/0029VamrQXx9WtCAV6CBul2m"
    )
    await update.message.reply_text(text=message_text, reply_markup=reply_markup)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Update {update} caused error {context.error}")

application.add_handler(CommandHandler("start", start))
application.add_error_handler(error_handler)

# --- FLASK ROUTES ---
@app.route('/buy_page')
def buy_page():
    return render_template('buy_page.html')

@app.route('/create_payment_razorpay', methods=['POST'])
def create_payment_razorpay():
    data = request.json or {}
    user_id = data.get('user_id')
    amount_rupees = int(data.get('amount', 10))  # default ₹10

    if not user_id:
        return jsonify({'error': 'User ID is missing'}), 400

    amount_paise = amount_rupees * 100  # Convert to paise

    order_payload = {
        'amount': amount_paise,
        'currency': 'INR',
        'receipt': f'receipt_user_{user_id}',
        'notes': {'telegram_user_id': str(user_id)}
    }

    try:
        order = razorpay_client.order.create(data=order_payload)
        return jsonify({
            'order_id': order['id'],
            'key_id': RAZORPAY_KEY_ID,
            'amount': order['amount']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/razorpay', methods=['POST'])
async def razorpay_webhook():
    webhook_body = request.data
    webhook_signature = request.headers.get('x-razorpay-signature')

    try:
        razorpay_client.utility.verify_webhook_signature(
            webhook_body, webhook_signature, WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        return "Invalid signature", 400

    webhook_data = request.json
    event = webhook_data.get('event')

    if event == 'payment.captured':
        payment_entity = webhook_data['payload']['payment']['entity']
        user_id = payment_entity['notes'].get('telegram_user_id')

        if user_id:
            bot = Bot(token=TELEGRAM_TOKEN)
            try:
                if not os.path.exists(FILE_PATH):
                    await bot.send_message(
                        chat_id=int(user_id),
                        text="Sorry, file is temporarily unavailable."
                    )
                else:
                    with open(FILE_PATH, 'rb') as document:
                        await bot.send_document(
                            chat_id=int(user_id),
                            document=document,
                            caption="Thank you for your purchase! Here is your file."
                        )
            except Exception as e:
                print(f"Failed to send file to user {user_id}: {e}")

    return "Webhook processed", 200

@app.route('/telegram', methods=['POST'])
async def telegram_webhook_handler():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK", 200

@app.route('/set_webhook', methods=['GET'])
async def setup_webhook():
    webhook_url = f"{RENDER_URL}/telegram"
    await application.bot.set_webhook(url=webhook_url)
    return "Telegram webhook setup OK", 200

@app.route('/')
def index():
    return "Bot is running (Mini-App Version)!", 200
