import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "GET":
        stock_prices = {}

        userid = session.get("user_id")

        user_info = db.execute(
            "SELECT stock, SUM(shares) AS shares FROM transactions WHERE user_id=? GROUP BY stock",
            userid,
        )
        cash = db.execute("SELECT cash FROM users WHERE id=?", userid)

        total = cash[0]["cash"]

        for line in user_info:
            symbol = line["stock"]
            stock_prices[line["stock"]] = lookup(symbol)
            totalshares = line["shares"]
            price = lookup(symbol)["price"]
            total += price * totalshares

        return render_template(
            "index.html",
            user_info=user_info,
            cash=cash,
            stock_prices=stock_prices,
            total=total,
        )

    elif request.method == "POST":
        user = session.get("user_id")
        deposit = request.form.get("deposit")

        if not deposit or not deposit.isnumeric() or int(deposit) <= 0:
            return apology("Proper amount required!", 400)

        cash = db.execute("SELECT cash FROM users WHERE id=?", user)
        balance = cash[0]["cash"] + int(deposit)

        db.execute("UPDATE users SET cash=? WHERE id=?", balance, user)

        return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock_info = lookup(symbol)
        user = session.get("user_id")
        user_info = db.execute("SELECT * FROM users WHERE id=?", user)
        if not symbol or not lookup(symbol):
            return apology("Not valid stock!", 400)
        if not shares or not shares.isnumeric() or int(shares) <= 0:
            return apology("Not valid shares!", 400)
        if (int(shares) * stock_info["price"]) > user_info[0]["cash"]:
            return apology("Insufficient balance!", 403)

        balance = user_info[0]["cash"] - int(shares) * stock_info["price"]

        db.execute("UPDATE users SET cash=? WHERE id=?", balance, user)

        db.execute(
            "INSERT INTO transactions (user_id, username, cash, stock, stock_price, shares, activity, activity_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            user,
            user_info[0]["username"],
            user_info[0]["cash"],
            symbol,
            stock_info["price"],
            shares,
            "BUY",
            date.today(),
        )

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user = session.get("user_id")

    user_data = {}

    data_history = db.execute(
        "SELECT activity, stock, stock_price, shares, activity_date FROM transactions WHERE user_id=?",
        user,
    )

    # for data in data:
    # user_data["activity"] = data["activity"]
    # user_data["symbol"] = data["stock"]
    # user_data["price"] = data["stock_price"]
    # user_data["shares"] = data["shares"]
    # user_data["date"] = data["activity_date"]

    return render_template("history.html", data_history=data_history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol or not lookup(symbol):
            return apology("Stock does not exist!", 400)

        return render_template("quoted.html", symbol=lookup(symbol))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    user_data = db.execute("SELECT * FROM users")

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Username is required!", 400)
        elif not request.form.get("password"):
            return apology("Password is required!", 400)
        elif not request.form.get("confirmation"):
            return apology("Password must be confirmed!", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password does not match!", 400)

        for row in user_data:
            if row["username"] == request.form.get("username"):
                return apology("Username already exists!", 400)

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("password")),
        )

        return render_template("login.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    SHARES = []
    stocks = {}

    user = session.get("user_id")
    user_info = db.execute(
        "SELECT stock, SUM(shares) AS shares FROM transactions WHERE user_id=? GROUP BY stock",
        user,
    )

    if request.method == "GET":
        for line in user_info:
            SHARES.append(line["stock"])

        return render_template("sell.html", symbols=SHARES)

    elif request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock_info = lookup(symbol)
        cash = db.execute("SELECT * FROM users WHERE id=?", user)
        if not symbol:
            return apology("Not valid stock!", 403)
        if not shares or not shares.isnumeric() or int(shares) <= 0:
            return apology("Not valid shares!", 400)
        for symbol in user_info:
            stocks[symbol["stock"]] = symbol["shares"]

        stock_shares = stocks[request.form.get("symbol")]

        if int(shares) > stock_shares:
            return apology("Not valid shares quantity!", 400)

        balance = cash[0]["cash"] + int(shares) * stock_info["price"]
        shares = (-1) * int(shares)
        db.execute("UPDATE users SET cash=? WHERE id=?", balance, user)
        db.execute(
            "INSERT INTO transactions (user_id, username, cash, stock, stock_price, shares, activity, activity_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            user,
            cash[0]["username"],
            cash[0]["cash"],
            request.form.get("symbol"),
            stock_info["price"],
            shares,
            "SELL",
            date.today(),
        )

        return redirect("/")
