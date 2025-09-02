
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from algoritmo import detect_all_biases
import os

app = Flask(__name__)
app.secret_key = os.environ.get("MINDTRADE_SECRET", "dev-secret")

# SQLite database config
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Use DATABASE_URL env var if available (Render will provide it), else fallback to SQLite
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    # Render uses old postgres:// scheme, SQLAlchemy needs postgresql://
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
        
        for i in range(len(asset_name)):
            entry_price = float(entry_prices[i])
            exit_price = float(exit_prices[i])
            account_size = float(account_sizes[i])
            fraction_invested = float(fractions_invested[i])
            
            position_size = account_size * fraction_invested
            shares = position_size / entry_price if entry_price != 0 else 0.0
            pnl_value = shares * (exit_price - entry_price)

            new_trade = Trade(
                user_id=user.id,
                asset_name=asset_name[i],
                asset_type=(asset_types[i] or "").lower(),
                fraction_invested=fraction_invested,
                pnl=pnl_value,
                sold_early=False,
                held_too_long=False,
                direction=(directions[i] or "").lower(),
                trade_reason=(reasons[i] or "").lower(),
                notes=notes[i],
                size=position_size,
                entry_time=entry_times[i],
                exit_time=exit_times[i]
            )

            db.session.add(new_trade)
            print(f"✅ New trade added for user {username}: {form.get('asset_name', '')}, PNL={pnl_value}")

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
        db.session.commit()
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

# Always ensure database tables exist at startup
with app.app_context():
    db.create_all()
    print("✅ Database tables ensured.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
