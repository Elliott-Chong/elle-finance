import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
import pytz
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
#pk_2c1125ad644841feb4723db4f9bbf7bc
# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    id = session['user_id']
    cash = db.execute('SELECT cash FROM users WHERE id=?', id)[0]['cash']
    stocks=db.execute("SELECT * FROM stocks WHERE user_id = ?", id)
    total=float(cash)
    for i in stocks:
        total+=i['amount'] * i['price']
    return render_template('index.html', stocks=stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method=='GET':
        return render_template('buy.html')
    else:
        id = session['user_id']
        max =  db.execute('SELECT cash FROM users WHERE id=?',id)
        symbol=request.form.get('symbol')
        result=lookup(symbol)
        if not result:
            return apology("Invalid Stock")
        name=result['name']
        price=result['price']
        symbol=result['symbol']
        amount=request.form.get('amount')
        cash=db.execute('SELECT cash FROM users WHERE id = ?', id)
        if int(price) * int(amount) > int( cash[0]['cash'] ):
            return apology("You Do Not Have Enough Cash To Purchase These Stocks")
        stock=db.execute('select amount from stocks where user_id=? and symbol like ?', id,symbol)
        if not stock:
            db.execute('INSERT INTO stocks (user_id, stock, symbol, price, amount) VALUES (?, ?, ?, ?, ?)', id, name, symbol, price, amount)
        else:
            db.execute('update stocks set amount = ? where user_id=? and symbol like ?', int(int(stock[0]['amount']) + int(amount)), id, symbol)
        db.execute('INSERT INTO history (user_id, symbol, shares, price, time_transacted) VALUES (?, ?, ?, ?, ?)', id, symbol, int(amount), price, datetime.now(tz=pytz.timezone('Asia/Singapore')).strftime("%Y-%m-%d %H:%M:%S"))
        updated_cash = float(cash[0]['cash']) - (float(price) * int(amount))
        db.execute('UPDATE users SET cash = ? WHERE id = ?', updated_cash, id)
        return redirect('/')



@app.route("/history")
@login_required
def history():
    id=session['user_id']
    history = db.execute('SELECT * FROM history where user_id = ?', id)
    return render_template('history.html', history = history)



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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        #return str(len(rows))
        # Ensure username exists anTd password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"],request.form.get("password")):
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
    if request.method=="POST":
        symbol=request.form.get('symbol')
        result=lookup(symbol)
        #app.logger.info(result)

        if not result:
            return apology("Invalid Stock")
        name=result['name']
        price=result['price']
        symbol=result['symbol']
        return render_template('displayquote.html', name=name, price=price,symbol=symbol)
    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method=='GET':
        return render_template('register.html')
    else:
        username=request.form.get('username')
        password=request.form.get('password')
        reconfirmpassword=request.form.get('reconfirmpassword')
        checkusername=db.execute('SELECT * FROM users WHERE username=?', username)
        if not username or not password or not reconfirmpassword:
            return apology("Please Fill Up All Required Fields")
        if len(checkusername)!=0:
            return apology("Username Already Exists")
        elif password != reconfirmpassword:
            return apology('Passwords Do Not Match')
        db.execute('INSERT INTO users (username, hash) VALUES (?, ?)', username, generate_password_hash(password))
        return redirect('/')
    #return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    id = session['user_id']
    if request.method=='GET':
        stocks=db.execute('SELECT * FROM stocks WHERE user_id=?', id)
        return render_template('sell.html', stocks=stocks)
    else:
        symbol=request.form.get('symbol')
        amount=request.form.get('amount')
        stocks=db.execute('SELECT * FROM stocks where user_id = ? and symbol=?', id, symbol)
        users=db.execute('SELECT * FROM users where id = ?', id)
        current_amount=stocks[0]['amount']
        price = stocks[0]['price']
        cash=users[0]['cash']

        if int(current_amount) - int(amount) >= 0:
            db.execute('UPDATE stocks SET amount=? WHERE user_id = ? and symbol=?', int(current_amount)-int(amount), id, symbol)
        if int(current_amount) - int(amount) == 0:
            db.execute('DELETE FROM stocks WHERE amount=0')
        elif int(current_amount) - int(amount) < 0:
            return apology('You Cannot Sell More Stocks Than You Own')
        db.execute('UPDATE users SET cash = ? WHERE id=?', float(cash) + float(price)*int(amount), id)
        db.execute('INSERT INTO history (user_id, symbol, shares, price, time_transacted) VALUES (?, ?, ?, ?, ?)', id, symbol, int(amount) * -1, price, datetime.now(tz=pytz.timezone('Asia/Singapore')).strftime("%Y-%m-%d %H:%M:%S"))
    return redirect('/')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == '__main__':
    app.run(debug=True)