import sqlite3
import json
from datetime import datetime
import qrcode
import os
import time


# ---------- 1. DATABASE SETUP ----------
def init_db():
    """Initialize database with both pallets and logs tables"""
    with sqlite3.connect("pallets.db") as conn:
        cursor = conn.cursor()

        # Create pallets table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pallets (
            pallet_id TEXT PRIMARY KEY,
            item_name TEXT,
            quantity INTEGER,
            last_updated TEXT
        )
        """)

        # Create logs table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pallet_id TEXT,
            operation TEXT,
            quantity_change INTEGER,
            previous_quantity INTEGER,
            new_quantity INTEGER,
            timestamp TEXT,
            FOREIGN KEY(pallet_id) REFERENCES pallets(pallet_id)
        )
        """)
        conn.commit()


# ---------- 2. QR GENERATION ----------
def generate_qr(pallet_id, item_name, quantity):
    """Generate QR code for a pallet"""
    data = {
        "pallet_id": pallet_id,
        "item_name": item_name,
        "quantity": quantity
    }
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    img.save(f"{pallet_id}.png")
    print(f"QR code generated for pallet {pallet_id}")


# ---------- 3. LOGGING FUNCTION ----------
def log_operation(conn, pallet_id, operation, qty_change, prev_qty, new_qty):
    """Log the operation details"""
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO logs (pallet_id, operation, quantity_change, previous_quantity, new_quantity, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (pallet_id, operation, qty_change, prev_qty, new_qty, timestamp))
    conn.commit()


# ---------- 4. PROCESS SCANNED QR ----------
def process_scan(qr_data):
    """Process scanned QR code with entry/exit selection"""
    pallet_info = json.loads(qr_data)
    pallet_id = pallet_info["pallet_id"]

    print(f"\nScanned Pallet: {pallet_id}")
    print(f"Item: {pallet_info['item_name']}")

    while True:
        operation = input("Enter operation (entry/exit): ").strip().lower()
        if operation in ("entry", "exit"):
            break
        print("Invalid operation. Please enter 'entry' or 'exit'")

    with sqlite3.connect("pallets.db") as conn:
        cursor = conn.cursor()

        # Get current quantity
        cursor.execute("SELECT quantity FROM pallets WHERE pallet_id = ?", (pallet_id,))
        row = cursor.fetchone()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row:  # Existing pallet
            current_qty = row[0]
            qty_change = pallet_info["quantity"]

            if operation == "entry":
                new_qty = current_qty + qty_change
                print(f"Adding {qty_change} items to pallet {pallet_id}")
            else:  # exit
                if current_qty < qty_change:
                    print(f"Warning: Not enough items (Current: {current_qty}, Trying to remove: {qty_change})")
                    return
                new_qty = current_qty - qty_change
                print(f"Removing {qty_change} items from pallet {pallet_id}")

            # Update pallet
            cursor.execute("""
                UPDATE pallets 
                SET quantity = ?, last_updated = ? 
                WHERE pallet_id = ?
            """, (new_qty, timestamp, pallet_id))

            # Log operation
            log_operation(conn, pallet_id, operation, qty_change, current_qty, new_qty)

            print(f"Updated quantity: {new_qty}")
            print(f"Previous quantity: {current_qty}")

        else:  # New pallet
            if operation == "exit":
                print("Cannot exit - pallet doesn't exist in system!")
                return

            new_qty = pallet_info["quantity"]
            cursor.execute("""
                INSERT INTO pallets (pallet_id, item_name, quantity, last_updated)
                VALUES (?, ?, ?, ?)
            """, (pallet_id, pallet_info["item_name"], new_qty, timestamp))

            # Log operation
            log_operation(conn, pallet_id, "initial entry", new_qty, 0, new_qty)

            print(f"New pallet registered with quantity: {new_qty}")

        conn.commit()


# ---------- 5. VIEW LOGS ----------
def view_logs():
    """Display transaction logs"""
    with sqlite3.connect("pallets.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT log_id, pallet_id, operation, quantity_change, 
               previous_quantity, new_quantity, timestamp 
        FROM logs 
        ORDER BY timestamp DESC
        LIMIT 20
        """)
        logs = cursor.fetchall()

        print("\n=== RECENT TRANSACTIONS ===")
        print(f"{'ID':<5} {'Pallet':<10} {'Operation':<10} {'Change':<8} {'Previous':<8} {'New':<8} {'Timestamp':<20}")
        for log in logs:
            print(f"{log[0]:<5} {log[1]:<10} {log[2]:<10} {log[3]:<8} {log[4]:<8} {log[5]:<8} {log[6]:<20}")


# ---------- 6. MAIN MENU ----------
def main_menu():
    """Display main menu and handle user input"""
    init_db()

    while True:
        print("\n===== PALETTE MANAGEMENT SYSTEM =====")
        print("1. Generate QR Code")
        print("2. Scan QR Code")
        print("3. View Transaction Logs")
        print("4. Exit")

        choice = input("Enter your choice (1-4): ")

        if choice == "1":
            pallet_id = input("Enter pallet ID: ")
            item_name = input("Enter item name: ")
            quantity = int(input("Enter initial quantity: "))
            generate_qr(pallet_id, item_name, quantity)

        elif choice == "2":
            # Simulated QR scan - in real use, you'd get this from a QR scanner
            pallet_id = input("Enter pallet ID (or scan QR): ")
            item_name = input("Enter item name: ")
            quantity = int(input("Enter quantity: "))

            qr_content = json.dumps({
                "pallet_id": pallet_id,
                "item_name": item_name,
                "quantity": quantity
            })

            process_scan(qr_content)

        elif choice == "3":
            view_logs()

        elif choice == "4":
            print("Exiting system...")
            break

        else:
            print("Invalid choice. Please try again.")


# ---------- 7. RUN APPLICATION ----------
if __name__ == "__main__":
    main_menu()