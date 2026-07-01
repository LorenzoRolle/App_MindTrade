from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from algoritmo import detect_all_biases
import os

app = Flask(__name__)
app.secret_key = os.environ.get("MINDTRADE_SECRET", "dev-secret")


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or f"sqlite:///{os.path.join(BASE_DIR, 'mindtrade.db')}"
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
    direction = db.Column(db.String(10))
    trade_reason = db.Column(db.String(50))
    notes = db.Column(db.Text)
    size = db.Column(db.Float)
    entry_time = db.Column(db.String(50))
    exit_time = db.Column(db.String(50))
    # NOTE: sold_early / held_too_long columns removed.
    # detect_loss_aversion() now derives this signal itself from
    # entry_time/exit_time + pnl instead of relying on flags nobody ever set.
    # If your existing DB still has those columns, that's fine — SQLAlchemy
    # just won't touch them; drop them later with a migration if you want.

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
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()
    trades = user.trades if user else []
    return render_template("home.html", trades=trades, total_trades=len(trades))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        action = request.form.get("action")  # which button was clicked
        username = request.form["username"].strip()
        email = request.form.get("email", "").strip()
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already used.")
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="Email already used.")
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
        action = request.form.get("action")  # which button was clicked
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if not user or user.password != password:
            return render_template("login.html", error="Invalid credentials.")
        session["user"] = username
        return redirect(url_for("home"))
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
        action = request.form.get("action")  # which button was clicked
        form = request.form
        try:
            entry_prices = form.getlist("entry_price[]")
            exit_prices = form.getlist("exit_price[]")
            account_sizes = form.getlist("account_size[]")
            fractions_invested = form.getlist("fraction_invested[]")
        except ValueError:
            return render_template("trade_input.html", error="Please enter valid numeric values.")

        entry_times = form.getlist("entry_timestamp[]")
        exit_times = form.getlist("exit_timestamp[]")
        asset_name = form.getlist("asset_name[]")
        asset_types = form.getlist("asset_type[]")
        directions = form.getlist("direction[]")
        reasons = form.getlist("trade_reason[]")
        notes = form.getlist("notes[]")

        # Sanity check: if this comes back empty, your trade_input.html form
        # fields are not named with "[]" (e.g. name="asset_name" instead of
        # name="asset_name[]"), and nothing below will ever run.
        if not asset_name:
            return render_template(
                "trade_input.html",
                error="No trade data received — check that form field names end in '[]'."
            )

        for i in range(len(asset_name)):
            entry_price = float(entry_prices[i])
            exit_price = float(exit_prices[i])
            account_size = float(account_sizes[i])
            fraction_invested = float(fractions_invested[i])

            position_size = account_size * fraction_invested
            shares = position_size / entry_price if entry_price != 0 else 0.0

            direction_i = (directions[i] or "").lower()
            if direction_i == "short":
                pnl_value = shares * (entry_price - exit_price)
            else:  # "long" or default
                pnl_value = shares * (exit_price - entry_price)

            new_trade = Trade(
                user_id=user.id,
                asset_name=asset_name[i],
                asset_type=(asset_types[i] or "").lower(),
                fraction_invested=fraction_invested,
                pnl=pnl_value,
                direction=direction_i,
                trade_reason=(reasons[i] or "").lower(),
                notes=notes[i],
                size=position_size,
                entry_time=entry_times[i],
                exit_time=exit_times[i]
            )
            db.session.add(new_trade)
            print(f"✅ New trade queued for user {username}: {asset_name[i]}, PNL={pnl_value}")

        # Single commit after the loop, not once per trade — avoids partial
        # writes if one row in a multi-row submit fails halfway through.
        db.session.commit()

        # Refresh the user object so user.trades reflects everything just committed.
        user = User.query.filter_by(id=user.id).first()

        trades_data = [
            {
                "asset_type": t.asset_type,
                "fraction_invested": t.fraction_invested,
                "pnl": t.pnl,
                "direction": t.direction,
                "trade_reason": t.trade_reason,
                "notes": t.notes,
                "size": t.size,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time
            }
            for t in user.trades
        ]

        if len(trades_data) < 2:
            return render_template(
                "results.html",
                message="You need at least 2 trades to analyze your patterns.",
                total_trades=len(trades_data)
            )

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

@app.route("/results")
def results():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()
    trades = user.trades if user else []

    if len(trades) < 2:
        return render_template("results.html", message="You need at least 2 trades to analyze your patterns.", total_trades=len(trades))

    trades_data = [
        {
            "asset_type": t.asset_type,
            "fraction_invested": t.fraction_invested,
            "pnl": t.pnl,
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

# Always ensure database tables exist at startup
with app.app_context():
    db.create_all()
    print("✅ Database tables ensured.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
