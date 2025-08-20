import os
import razorpay
import asyncio
import httpx
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

# --- FLASK APP & BOT INITIALIZATION ---
app = Flask(__name__)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- TELEGRAM BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
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
    
    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup
    )

application.add_handler(CommandHandler("start", start))

# --- FLASK ROUTES ---
@app.route('/buy_page')
def buy_page():
    return render_template('buy_page.html')

@app.route('/create_payment_razorpay', methods=['POST'])
def create_payment_razorpay():
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount', 100)
    
    if not user_id:
        return jsonify({'error': 'User ID is missing'}), 400

    order_payload = {
        'amount': amount,
        'currency': 'INR',
        'receipt': f'receipt_user_{user_id}',
        'notes': {'telegram_user_id': str(user_id)}
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
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    webhook_body = request.data
    webhook_signature = request.headers.get('x-razorpay-signature')
    
    try:
        razorpay_client.utility.verify_webhook_signature(
            webhook_body, webhook_signature, WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError as e:
        return "Invalid signature", 400

    webhook_data = request.json
    event = webhook_data.get('event')

    if event == 'payment.captured':
        payment_entity = webhook_data['payload']['payment']['entity']
        user_id = payment_entity['notes'].get('telegram_user_id')

        if user_id:
            async def send_file():
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    with open(FILE_PATH, 'rb') as document:
                        await bot.send_document(
                            chat_id=int(user_id),
                            document=document,
                            caption="Thank you for your purchase! Here is your file."
                        )
                except Exception as e:
                    print(f"Failed to send file to user {user_id}: {e}")
            
            asyncio.run(send_file())
                
    return "Webhook processed", 200

@app.route('/telegram', methods=['POST'])
async def telegram_webhook_handler():
    await application.initialize()
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    await application.shutdown()
    return "OK", 200

@app.route('/set_webhook', methods=['GET'])
async def setup_webhook():
    await application.initialize()
    webhook_url = f"{RENDER_URL}/telegram"
    await application.bot.set_webhook(url=webhook_url)
    return "Telegram webhook setup OK"
    
@app.route('/')
def index():
    return "Bot is running (Mini-App Version)!", 200
