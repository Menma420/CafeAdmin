from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session , flash
from pymongo import MongoClient
import hashlib
from bson import ObjectId
from flask_pymongo import PyMongo
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session handling

# MongoDB Atlas Connection
client = MongoClient("mongodb+srv://cafetrio606142:iiitcafe123@cluster0.k6mvr.mongodb.net/cafetrio?retryWrites=true&w=majority&appName=Cluster0")
db = client["cafetrio"] 
users_collection = db["admins"]  
menu_collection=db['menus']
order_collection=db['orders']
client_collection=db['users']

# Hashing function for passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


@app.route("/")
def home():
    if "logged_in" in session and session["logged_in"]:
        return render_template("dashboard.html", username=session["username"])
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        # Check if the username already exists
        if users_collection.find_one({"username": username}):
            return "Username already exists! <a href='/signup'>Try again</a>"

        # Store the hashed password in MongoDB
        hashed_password = hash_password(password)
        users_collection.insert_one({"username": username,"email": email,"password": hashed_password})

        return "Signup Successful! <a href='/login'>Login</a>"
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        
        user = users_collection.find_one({"username": username})
        if user and user["password"] == hash_password(password):
            session["logged_in"] = True
            session["username"] = username
            session["user_id"]=str(user['_id'])
            return redirect(url_for("home"))
            #return render_template("dashboard.html")
        return "Invalid credentials! <a href='/login'>Try again</a>"
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/menu", methods=["GET", "POST"])
def menu():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = float(request.form["price"])
        category = request.form["category"]
        image = request.form["image"]
        estimated_time = int(request.form["et"])
        availability = True if request.form.get("availability") == "on" else False

        # Insert menu item into MongoDB
        menu_collection.insert_one({
            "name": name,
            "description": description,
            "price": price,
            "category": category,
            "image": image,
            "et": estimated_time,
            "availability": availability
        })

    # Fetch all menu items
    menu_items = menu_collection.find()

    return render_template("menu.html", menu_items=menu_items)


@app.route("/update_availability/<item_id>")
def update_availability(item_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    item_id = ObjectId(item_id)
    item = menu_collection.find_one({"_id": item_id})
    
    if item:
        new_availability = not item["availability"]
        menu_collection.update_one({"_id": item_id}, {"$set": {"availability": new_availability}})
    
    return redirect(url_for("menu"))
    
@app.route("/delete_menu_item/<item_id>", methods=["POST"])
def delete_menu_item(item_id):
    if not session.get("logged_in"):
        flash("You need to be logged in to delete items.", "danger")
        return redirect(url_for("login"))
        

    user = users_collection.find_one({"_id": ObjectId(session["user_id"])})  # Get user from session
    if not user:
        flash("Invalid session. Please log in again.", "danger")
        return redirect(url_for("login"))

    password = request.form.get("password")
    
    
    if not (user["password"] == hash_password(password)):
        flash("Incorrect password. Deletion failed.", "danger")
        return redirect(url_for("menu"))

    try:
        
        result = menu_collection.delete_one({"_id": ObjectId(item_id)})

        if result.deleted_count > 0:
            flash("Item deleted successfully.", "success")
        else:
            flash("Item not found.", "danger")

    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for("menu"))

@app.route("/orders")
def all_orders():
    orders = order_collection.find()
    result = []

    for order in orders:
        

        # Fetch User details
        user = client_collection.find_one({"_id": order["customerId"]}, {"name": 1, "email": 1, "_id": 0})

        # Fetch Items (Menu) details
        items_list = []
        for item in order.get("items", []):  # items should be an array
            
            menu = menu_collection.find_one({"_id": ObjectId(item["menuId"])}, {"name": 1, "price": 1, "_id": 0})
            if menu:
                menu["quantity"] = item["quantity"]  # Add quantity from the order
                items_list.append(menu)
            else:
                print(f"WARNING: Menu ID {item['menuId']} not found!")

        # Order Data
        order_data = {
            "order_id": str(order["_id"]),  # Convert ObjectId to string
            "customer": user if user else {"name": "Unknown", "email": "Unknown"},
            "items": items_list,  # Expanded items array
            "totalAmount": order["totalAmount"],
            "status": order["status"],
            "timeToPrepare": order.get("timeToPrepare", 10),
            "transactionId": order.get("transactionId", "No Payment"),
            "createdAt": order["createdAt"],
            "updatedAt": order["updatedAt"]
        }
        result.append(order_data)
    return render_template("orders.html", orders=result)

@app.route("/update_order_status/<order_id>", methods=["POST"])
def update_order_status(order_id):
    new_status = request.form.get("status")

    if new_status not in ["Pending", "Preparing", "Completed", "Cancelled"]:
        flash("Invalid status selected!", "danger")
        return redirect(url_for("all_orders"))

    order_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": new_status, "updatedAt": datetime.utcnow()}}
    )

    flash("Order status updated successfully!", "success")
    return redirect(url_for("all_orders"))

@app.route("/profile")
def profile():
    if "logged_in" not in session:
        return redirect(url_for("login"))

    user = users_collection.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("home"))

    return render_template("profile.html", user=user)

@app.route("/change-password", methods=["POST"])
def change_password():
    if "logged_in" not in session:
        return redirect(url_for("login"))

    user = users_collection.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("profile"))

    old_password = request.form["old_password"]
    new_password = request.form["new_password"]

    
    if user["password"] != hash_password(old_password):
        flash("Old password is incorrect!", "danger")
        return redirect(url_for("profile"))

    
    hashed_password = hash_password(new_password)
    users_collection.update_one({"_id": user["_id"]}, {"$set": {"password": hashed_password}})

    flash("Password updated successfully!", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True)
