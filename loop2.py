import sqlite3
import json
from datetime import datetime
import qrcode
import os
import time
from PIL import Image
import webbrowser
import cv2
from pyzbar.pyzbar import decode
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


# ---------- 2. QR GENERATION & DISPLAY ----------
def generate_and_show_qr(pallet_id, item_name, quantity):
    """Generate and display QR code for a pallet"""
    data = {
        "pallet_id": pallet_id,
        "item_name": item_name,
        "quantity": quantity
    }
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    filename = f"{pallet_id}.png"
    img.save(filename)

    # Show the QR code image
    print(f"\nQR code generated for pallet {pallet_id}")
    print(f"Item: {item_name}")
    print(f"Quantity: {quantity}")

    # Open the image
    img = Image.open(filename)
    img.show()

    return filename


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
    """Process scanned QR code with confirmation"""
    try:
        pallet_info = json.loads(qr_data)
    except json.JSONDecodeError:
        print("Invalid QR code data!")
        return

    pallet_id = pallet_info["pallet_id"]

    print("\n=== QR CODE DETAILS ===")
    print(f"Pallet ID: {pallet_id}")
    print(f"Item: {pallet_info['item_name']}")
    print(f"Quantity: {pallet_info['quantity']}")

    # Ask for confirmation
    confirm = input("\nDo you want to proceed with this transaction? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Transaction cancelled.")
        return

    # Only proceed if user confirms
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
                print(f"\nAdding {qty_change} items to pallet {pallet_id}")
            else:  # exit
                if current_qty < qty_change:
                    print(f"\nError: Not enough items (Current: {current_qty}, Trying to remove: {qty_change})")
                    return
                new_qty = current_qty - qty_change
                print(f"\nRemoving {qty_change} items from pallet {pallet_id}")

            # Update pallet
            cursor.execute("""
                UPDATE pallets 
                SET quantity = ?, last_updated = ? 
                WHERE pallet_id = ?
            """, (new_qty, timestamp, pallet_id))

            # Log operation
            log_operation(conn, pallet_id, operation, qty_change, current_qty, new_qty)

            print(f"Previous quantity: {current_qty}")
            print(f"New quantity: {new_qty}")
            print("Transaction completed successfully!")

        else:  # New pallet
            if operation == "exit":
                print("\nCannot exit - pallet doesn't exist in system!")
                return

            new_qty = pallet_info["quantity"]
            cursor.execute("""
                INSERT INTO pallets (pallet_id, item_name, quantity, last_updated)
                VALUES (?, ?, ?, ?)
            """, (pallet_id, pallet_info["item_name"], new_qty, timestamp))

            # Log operation
            log_operation(conn, pallet_id, "initial entry", new_qty, 0, new_qty)

            print(f"\nNew pallet registered with quantity: {new_qty}")
            print("Transaction completed successfully!")

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


# ---------- 6. SCAN QR CODE ----------
def scan_qr_code():
    """Handle QR code scanning with proper file validation"""
    print("\n=== SCAN QR CODE ===")
    print("1. Enter QR code data manually")
    print("2. Scan QR code from image file")
    print("3. Back to main menu")

    choice = input("Enter your choice (1-3): ")

    if choice == "1":
        # Manual entry
        pallet_id = input("Enter pallet ID: ")
        item_name = input("Enter item name: ")
        quantity = int(input("Enter quantity: "))

        qr_content = json.dumps({
            "pallet_id": pallet_id,
            "item_name": item_name,
            "quantity": quantity
        })
        process_scan(qr_content)

    elif choice == "2":
        # QR code file scanning
        while True:
            filepath = input("Enter QR code image file path (or 'cancel' to abort): ").strip()

            if filepath.lower() == 'cancel':
                print("Scanning cancelled.")
                return

            if not os.path.exists(filepath):
                print(f"Error: File not found at {filepath}")
                print("Please try again or type 'cancel'")
                continue

            try:
                # Read the QR code using OpenCV
                img = cv2.imread(filepath)
                detected_qrs = decode(img)

                if not detected_qrs:
                    print("No QR code found in the image. Try another file.")
                    continue

                # Get the first detected QR code
                qr_data = detected_qrs[0].data.decode('utf-8')
                print(f"\nQR code scanned successfully!")
                process_scan(qr_data)
                break

            except Exception as e:
                print(f"Error scanning QR code: {e}")
                print("Please try another file or type 'cancel'")

    elif choice == "3":
        return

    else:
        print("Invalid choice!")

# ---------- 7. MAIN MENU ----------
def main_menu():
    """Display main menu and handle user input"""
    init_db()

    while True:
        print("\n===== PALLET MANAGEMENT SYSTEM =====")
        print("1. Generate QR Code")
        print("2. Scan QR Code")
        print("3. View Transaction Logs")
        print("4. Exit")

        choice = input("Enter your choice (1-4): ")

        if choice == "1":
            pallet_id = input("Enter pallet ID: ")
            item_name = input("Enter item name: ")
            quantity = int(input("Enter initial quantity: "))
            generate_and_show_qr(pallet_id, item_name, quantity)

        elif choice == "2":
            scan_qr_code()

        elif choice == "3":
            view_logs()

        elif choice == "4":
            print("Exiting system...")
            break

        else:
            print("Invalid choice. Please try again.")


# ---------- 8. RUN APPLICATION ----------
if __name__ == "__main__":
    main_menu()