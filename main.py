import random
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from agents import Agent, ModelSettings, Runner, OpenAIChatCompletionsModel, RunConfig, function_tool
from dotenv import load_dotenv
import os
from twilio.rest import Client
from openai import AsyncOpenAI

load_dotenv()

# Environment variables
gemini_api_key = os.getenv("GEMINI_API_KEY")
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_WHATSAPP = "whatsapp:+14155238886" 
TO_WHATSAPP = "whatsapp:+923072502073"  

client = Client(ACCOUNT_SID, AUTH_TOKEN)


if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is not set.")

# OpenAI / Gemini client
external_client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=external_client,
)

config = RunConfig(
    model=model,
    model_provider=external_client,
    tracing_disabled=True,
)

# Product catalog & orders DB

products = {
    # Mobiles
    "iPhone 15 Pro": {"price": 1199.99, "category": "Mobiles", "stock": 20},
    "Samsung Galaxy S23": {"price": 999.99, "category": "Mobiles", "stock": 25},
    "OnePlus 11": {"price": 749.99, "category": "Mobiles", "stock": 30},

    # Laptops
    "MacBook Pro 16": {"price": 2399.99, "category": "Laptops", "stock": 15},
    "Dell XPS 15": {"price": 1899.99, "category": "Laptops", "stock": 20},
    "HP Spectre x360": {"price": 1599.99, "category": "Laptops", "stock": 18},

    # Shoes
    "Nike Air Max": {"price": 199.99, "category": "Shoes", "stock": 50},
    "Adidas Ultraboost": {"price": 179.99, "category": "Shoes", "stock": 40},
    "Puma Classic": {"price": 129.99, "category": "Shoes", "stock": 60},

    # Watches
    "Apple Watch Series 9": {"price": 399.99, "category": "Watches", "stock": 25},
    "Samsung Galaxy Watch 6": {"price": 349.99, "category": "Watches", "stock": 30},
    "Fitbit Versa 4": {"price": 229.99, "category": "Watches", "stock": 35},

    # Audio
    "Sony WH-1000XM5": {"price": 399.99, "category": "Audio", "stock": 40},
    "Bose QuietComfort 45": {"price": 329.99, "category": "Audio", "stock": 35},
    "AirPods Pro 2": {"price": 249.99, "category": "Audio", "stock": 50},

    # Gaming
    "PlayStation 5": {"price": 499.99, "category": "Gaming", "stock": 10},
    "Xbox Series X": {"price": 499.99, "category": "Gaming", "stock": 12},
    "Nintendo Switch OLED": {"price": 349.99, "category": "Gaming", "stock": 18},

    # TV & Displays
    "Samsung QLED 55": {"price": 1199.99, "category": "TV & Displays", "stock": 10},
    "LG OLED 65": {"price": 2299.99, "category": "TV & Displays", "stock": 8},
    "Sony Bravia 75": {"price": 2999.99, "category": "TV & Displays", "stock": 5},

    # Tablets
    "iPad Pro 12.9": {"price": 1299.99, "category": "Tablets", "stock": 20},
    "Samsung Galaxy Tab S9": {"price": 1099.99, "category": "Tablets", "stock": 22},
    "Xiaomi Pad 6": {"price": 499.99, "category": "Tablets", "stock": 30},

    # Cameras
    "Canon EOS R6": {"price": 2499.99, "category": "Cameras", "stock": 8},
    "Sony Alpha A7 IV": {"price": 2799.99, "category": "Cameras", "stock": 7},
    "Nikon Z6 II": {"price": 1999.99, "category": "Cameras", "stock": 9},
}


orders_db = {}

@function_tool
def show_catalog(category: str = None):
    """Show catalog items optionally filtered by category"""
    filtered = {name: info for name, info in products.items() if not category or info["category"].lower() == category.lower()}
    if not filtered:
        return {"message": "No products found in this category."}
    return "\n".join(f"{name} (${info['price']}, Stock: {info['stock']})" for name, info in filtered.items())

@function_tool
def special_offers():
    """Return special offers"""
    offers = [
        "🔥 10% off on Smartphone X today!",
        "💻 Buy Laptop Pro and get Wireless Mouse free!",
        "🎧 20% off on all audio products."
    ]
    return {"message": "Today's special offers:\n" + "\n".join(offers)}

@function_tool
def place_order(item: str, phone_number: str, address: str, quantity: int = 1):
    """Place a new order and send WhatsApp notification"""
    
    # Normalize product name
    item_normalized = " ".join(item.strip().split()).title()
    if item_normalized not in products:
        suggestions = [
            name for name in products 
            if any(word.lower() in name.lower() for word in item_normalized.split())
        ]
        if suggestions:
            return {"message": f"❓ '{item}' not found. Did you mean: {', '.join(suggestions)}?"}
        return {"message": f"❌ Product '{item}' not available."}

    # Calculate price and create order
    price = products[item_normalized]["price"] * quantity
    order_id = str(random.randint(1000, 9999))
    eta = random.randint(2, 7)  # delivery days
    orders_db[order_id] = {
        "item": item_normalized,
        "quantity": quantity,
        "phone_number": phone_number,
        "address": address,
        "price": price,
        "status": "Pending",
        "eta": eta
    }

    # WhatsApp message content
    message_body = (
        f"✅ Your order has been placed!\n\n"
        f"🛒 Product: {item_normalized}\n"
        f"📦 Quantity: {quantity}\n"
        f"💵 Total: ${price:.2f}\n"
        f"🆔 Order ID: {order_id}\n"
        f"🚚 Delivery in {eta} days."
    )

    # Send WhatsApp message via Twilio Sandbox
    try:
        client.messages.create(
            body=message_body,
            from_=FROM_WHATSAPP,              # Twilio Sandbox number
            to=f"whatsapp:+92{phone_number.lstrip('0')}"  # convert 03072502073 -> +923072502073
        )
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")

    return {
        "order_id": order_id,
        "message": f"✅ Order placed: {quantity} x {item_normalized} for ${price:.2f}. WhatsApp notification sent!",
        "item": item_normalized,
        "quantity": quantity,
        "phone_number": phone_number,
        "address": address,
        "price": price,
        "eta": eta
    }


@function_tool
def check_order_status(order_id: str):
    if order_id in orders_db:
        return orders_db[order_id]
    return f"❌ Order ID {order_id} not found."

@function_tool
def cancel_order(order_id: str):
    if order_id in orders_db:
        orders_db[order_id]["status"] = "Cancelled"
        return f"✅ Order {order_id} cancelled."
    return f"❌ Order ID {order_id} not found."

@function_tool
def update_order(order_id: str, item: str = None, quantity: int = None):
    if order_id not in orders_db:
        return {"message": f"❌ Order ID {order_id} not found."}

    order = orders_db[order_id]

    if item:
        item_normalized = " ".join(item.strip().split()).title()
        if item_normalized not in products:
            return {"message": f"❌ Product '{item}' not available."}
        order["item"] = item_normalized

    if quantity:
        order["quantity"] = quantity

    order["price"] = products[order["item"]]["price"] * order["quantity"]
    order["eta"] = random.randint(2, 7)

    # Notify owner
    owner_message = (
        f"📦 Updated Order (ID: {order_id}):\n"
        f"Item: {order['item']} x {order['quantity']}\n"
        f"Price: ${order['price']:.2f}\n"
        f"Phone: {order['phone_number']}\n"
        f"Address: {order['address']}\n"
        f"ETA: {order['eta']} days"
    )

@function_tool
def show_categories():
        """Return all unique categories"""
        unique_categories = list({info["category"] for info in products.values()})
        return {"categories": unique_categories}

place_order_agent = Agent(
    name="place_order",
    instructions="Collect info and place e-commerce orders.",
    tools=[place_order, show_catalog, special_offers, update_order],
    model_settings=ModelSettings(tool_choice="required")
)

update_order_agent = Agent(
    name="update_order",
    instructions="Update an existing order.",
    tools=[update_order],
    model_settings=ModelSettings(tool_choice="required")
)

cancel_order_agent = Agent(
    name="cancel_order",
    instructions="Cancel an existing order.",
    tools=[cancel_order],
    model_settings=ModelSettings(tool_choice="required")
)

check_order_status_agent = Agent(
    name="check_order_status",
    instructions="Check the status of an order.",
    tools=[check_order_status],
    model_settings=ModelSettings(tool_choice="required")
)

show_catalog_agent = Agent(
    name="show_catalog",
    instructions="Show products catalog.",
    tools=[show_catalog],
)

special_offers_agent = Agent(
    name="special_offers",
    instructions="Show today's offers",
    tools=[special_offers]
)

# Main agent
ecommerce_agent = Agent(
    name="ecommerce_assistant",
    instructions="Handle e-commerce shopping tasks. Use specialized agents for placing, updating, cancelling orders, checking status, showing catalog or offers.",
    tools=[show_catalog, show_categories, special_offers, check_order_status, update_order],
    handoffs=[place_order_agent, update_order_agent, cancel_order_agent]
)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kharedo-omega.vercel.app/"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


conversation_history = {}

@app.get("/")
def home():
    return {"message": "Welcome to E-Commerce Agent Backend!"}

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]



@app.get("/categories")
def get_categories():
    unique_categories = list({info["category"] for info in products.values()})
    return {"categories": unique_categories}

@app.post("/order")
def place_order(product_name: str, quantity: int, price: float):
    order_id = "5210"  # normally yeh database me generate hota hai
    total_price = quantity * price
    
    # WhatsApp message bhejna
    message_body = f"✅ Your order has been placed!\n\n🛒 Product: {product_name}\n📦 Quantity: {quantity}\n💵 Total: ${total_price}\n🆔 Order ID: {order_id}\n🚚 Delivery in 5 days."
    
    client.messages.create(
        body=message_body,
        from_=FROM_WHATSAPP,
        to=TO_WHATSAPP
    )
    
    return {
        "status": "success",
        "order_id": order_id,
        "message": "Order placed and WhatsApp notification sent!"
    }

@app.post("/chat/start")
async def start_chat(req: ChatRequest):
    session_id = "default_user"
    if session_id not in conversation_history:
        conversation_history[session_id] = []

    # Save incoming messages
    for msg in req.messages:
        conversation_history[session_id].append({"role": msg.role, "content": msg.content})

    # Format correctly for Runner
    formatted_history = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation_history[session_id]
    ]

    # Run agent
    response = await Runner.run(ecommerce_agent, formatted_history, run_config=config)

    # Save assistant reply
    conversation_history[session_id].append(
        {"role": "assistant", "content": response.final_output.strip()}
    )

    return {"response": response.final_output.strip()}


if __name__ == "__main__":
    import uvicorn  
    uvicorn.run(app, host="0.0.0.0", port=8080)
