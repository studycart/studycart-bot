import os
import razorpay
import asyncio
import httpx
from flask import Flask, redirect, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURATION (Set these as Environment Variables on your server) ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
RENDER_URL = os.getenv('WEB_URL') 
WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')
# The file you want to send after successful payment
FILE_PATH = "file_to_send.pdf" 

# --- FLASK APP & BOT INITIALIZATION ---
app = Flask(__name__)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- TELEGRAM BOT HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and sends a payment link button."""
    user_id = update.effective_chat.id
    
    # This URL points to a route on our server that creates the payment and redirects
    payment_start_url = f"{RENDER_URL}/pay?user_id={user_id}"
    
    keyboard = [[InlineKeyboardButton("Buy", url=payment_start_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Join Our Official Channel For More - \n"
        "https://t.me/+ZliGAAJIsZlhNTII\n\n"
        "Whatsapp Channel - \n"
        "https://whatsapp.com/channel/0029VamrQXx9WtCAV6CBuI2m",
        reply_markup=reply_markup
    )

application.add_handler(CommandHandler("start", start))

# --- FLASK ROUTES ---
@app.route('/pay')
def pay_redirect():
    """Creates a Razorpay order and redirects the user to the payment page."""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return "Error: User ID is missing.", 400

    amount_in_paise = 100 # ₹1 = 100 paise
    order_payload = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'receipt_user_{user_id}',
        'notes': {'telegram_user_id': str(user_id)}
    }
    
    try:
        order = razorpay_client.order.create(data=order_payload)
        payment_link = order['short_url']
        return redirect(payment_link) # Immediately send the user to the payment page
    except Exception as e:
        print(f"Error creating Razorpay order: {e}")
        return "Error creating payment link. Please try again later.", 500

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
    if webhook_data.get('event') == 'payment.captured':
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
    await application.shutdown()
    return "Telegram webhook setup OK"
    
@app.route('/')
def index():
    return "Bot is running!", 200
    
