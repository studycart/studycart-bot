from flask import Flask, render_template, request, jsonify, redirect
import razorpay, os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET")))

user_balances = {}
leaderboard = []

@app.route("/")
def index():
    tg_data = request.args.get("tgWebAppData")
    if not tg_data:
        return redirect("https://t.me/UPWinBot?startapp")  # Replace with your bot username
    return render_template("index.html")

@app.route("/verify_session", methods=["POST"])
def verify_session():
    data = request.get_json()
    init_data = data.get("initData")
    # Optional: verify Telegram initData here
    return jsonify({"status": "ok"})

@app.route("/deposit")
def deposit():
    return render_template("deposit.html")

@app.route("/create_order", methods=["POST"])
def create_order():
    amount = int(request.form["amount"]) * 100
    telegram_id = request.form.get("telegram_id", "anon")
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "notes": { "telegram_id": telegram_id }
    })
    return jsonify(order)

@app.route("/razorpay_webhook", methods=["POST"])
def razorpay_webhook():
    payload = request.json
    try:
        payment = payload["payload"]["payment"]["entity"]
        telegram_id = payment["notes"]["telegram_id"]
        amount = int(payment["amount"]) // 100
        user_balances[telegram_id] = user_balances.get(telegram_id, 0) + amount
        print(f"Credited ₹{amount} to {telegram_id}")
    except Exception as e:
        print("Webhook error:", e)
    return "OK"

@app.route("/session")
def session():
    telegram_id = request.args.get("id", "anon")
    balance = user_balances.get(telegram_id, 0)
    return jsonify({ "balance": balance })

@app.route("/chicken")
def chicken():
    return render_template("chicken.html")

@app.route("/aviator")
def aviator():
    return render_template("aviator.html")

@app.route("/submit_score", methods=["POST"])
def submit_score():
    data = request.json
    leaderboard.append(data)
    return "OK"

@app.route("/leaderboard")
def show_leaderboard():
    top = sorted(leaderboard, key=lambda x: float(x["score"]), reverse=True)[:10]
    return render_template("leaderboard.html", board=top)

@app.route("/loot_drop")
def loot_drop():
    return render_template("loot_drop.html")
