
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from algoritmo import detect_all_biases
import os

app = Flask(__name__)
app.secret_key = os.environ.get("MINDTRADE_SECRET", "dev-secret")

# SQLite database config
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'mindtrade.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -------------------
# Database Models
# -------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    trades = db.relationship("Trade", backref="user", lazy=True)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    asset_name = db.Column(db.String(50))
    asset_type = db.Column(db.String(20))
    fraction_invested = db.Column(db.Float)
    pnl = db.Column(db.Float)
    sold_early = db.Column(db.Boolean, default=False)
    held_too_long = db.Column(db.Boolean, default=False)
    direction = db.Column(db.String(10))
    trade_reason = db.Column(db.String(50))
    notes = db.Column(db.Text)
    size = db.Column(db.Float)
    entry_time = db.Column(db.String(50))
    exit_time = db.Column(db.String(50))

# -------------------
# Routes
# -------------------
@app.route("/")
def root():
    return redirect(url_for("intro"))

@app.route("/intro")
def intro():
    return render_template("intro.html")

@app.route("/home")
def home():
    return render_template("intro.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form.get("email", "").strip()
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already exists.")
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        print(f"✅ New user added: {username}")
        db.session.commit()
        session["user"] = username
        return redirect(url_for("trade_input"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if not user or user.password != password:
            return render_template("login.html", error="Invalid credentials.")
        session["user"] = username
        return redirect(url_for("trade_input"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("intro"))

@app.route("/trade_input", methods=["GET", "POST"])
def trade_input():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        form = request.form
        try:
            account_size = float(form.get("account_size", 0) or 0)
            fraction_invested = float(form.get("fraction_invested", 0) or 0)
            entry_price = float(form.get("entry_price", 0) or 0)
            exit_price = float(form.get("exit_price", 0) or 0)
        except ValueError:
            return render_template("trade_input.html", error="Please enter valid numeric values.")

        entry_time = form.get("entry_timestamp")
        exit_time = form.get("exit_timestamp")

        position_size = account_size * fraction_invested
        shares = position_size / entry_price if entry_price != 0 else 0.0
        pnl_value = shares * (exit_price - entry_price)

        new_trade = Trade(
            user_id=user.id,
            asset_name=form.get("asset_name", ""),
            asset_type=form.get("asset_type", "").lower(),
            fraction_invested=fraction_invested,
            pnl=pnl_value,
            sold_early=False,
            held_too_long=False,
            direction=form.get("direction", "").lower(),
            trade_reason=form.get("trade_reason", "").lower(),
            notes=form.get("notes", ""),
            size=position_size,
            entry_time=entry_time,
            exit_time=exit_time
        )

        db.session.add(new_trade)
        print(f"✅ New trade added for user {username}: {form.get('asset_name', '')}, PNL={pnl_value}")
        db.session.commit()

        trades_data = [
            {
                "asset_type": t.asset_type,
                "fraction_invested": t.fraction_invested,
                "pnl": t.pnl,
                "sold_early": t.sold_early,
                "held_too_long": t.held_too_long,
                "direction": t.direction,
                "trade_reason": t.trade_reason,
                "notes": t.notes,
                "size": t.size,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time
            }
            for t in user.trades
        ]

        bias_results = detect_all_biases(trades_data)
        return render_template("results.html", bias_results=bias_results, total_trades=len(trades_data))

    return render_template("trade_input.html")

@app.route("/view_notifications")
def view_notifications():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()
    trades = user.trades if user else []
    return render_template("view_notifications.html", trades=trades, total_trades=len(trades))

@app.route("/api/bias_analysis")
def api_bias_analysis():
    username = session.get("user")
    if not username:
        return jsonify({"error": "not authenticated"}), 401

    user = User.query.filter_by(username=username).first()
    trades_data = [
        {
            "asset_type": t.asset_type,
            "fraction_invested": t.fraction_invested,
            "pnl": t.pnl,
            "sold_early": t.sold_early,
            "held_too_long": t.held_too_long,
            "direction": t.direction,
            "trade_reason": t.trade_reason,
            "notes": t.notes,
            "size": t.size,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time
        }
        for t in user.trades
    ]
    bias_results = detect_all_biases(trades_data)
    return jsonify(bias_results)

# Always ensure database tables exist at startup
with app.app_context():
    db.create_all()
    print("✅ Database tables ensured.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
