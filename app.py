import json
import requests
from flask import Flask, request, send_from_directory
import razorpay

app = Flask(__name__)

# 🔐 Secrets (replace with env vars in production)
RAZORPAY_KEY_ID = 'your_key_id'
RAZORPAY_KEY_SECRET = 'your_key_secret'
RAZORPAY_WEBHOOK_SECRET = 'your_webhook_secret'
TELEGRAM_BOT_TOKEN = 'your_telegram_bot_token'

# 📄 Public file URL (hosted on Vercel or CDN)
FILE_URL = 'https://yourdomain.com/file_to_send.pdf'

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@app.route('/')
def home():
    return send_from_directory('.', 'buy_page.html')

@app.route('/create_order', methods=['POST'])
def create_order_route():
    data = request.get_json()
    amount = int(data.get('amount', 1)) * 100  # INR to paise
    chat_id = str(data.get('chat_id'))

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "receipt": f"receipt_{chat_id}",
        "notes": {
            "telegram_chat_id": chat_id
        }
    })

    return {
        "order_id": order['id'],
        "amount": order['amount'],
        "currency": order['currency']
    }

@app.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    try:
        body = request.data.decode('utf-8')
        signature = request.headers.get('X-Razorpay-Signature')
        razorpay_client.utility.verify_webhook_signature(body, signature, RAZORPAY_WEBHOOK_SECRET)

        payload = json.loads(body)
        payment_id = payload['payload']['payment']['entity']['id']
        payment = razorpay_client.payment.fetch(payment_id)

        if payment['status'] == 'captured':
            chat_id = payment['notes'].get('telegram_chat_id')
            if chat_id:
                send_file_to_telegram(chat_id)
                return 'File sent', 200
            else:
                return 'Missing Telegram chat ID', 400

        return 'Payment not captured', 400

    except razorpay.errors.SignatureVerificationError:
        return 'Invalid signature', 400
    except Exception as e:
        print("Webhook error:", e)
        return 'Server error', 500

def send_file_to_telegram(chat_id):
    requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument',
        data={
            'chat_id': chat_id,
            'document': FILE_URL,
            'caption': '✅ Payment received! Here’s your file. Thank you!'
        }
    )
