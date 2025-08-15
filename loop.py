import streamlit as st
import sqlite3
import qrcode
import os
from datetime import datetime
import json
import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import io
import pandas as pd
import random
import numpy as np
import string
# Initialize database connection
def init_db():
    conn = sqlite3.connect("pallets.db")
    return conn


# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = "home"


# Page navigation
def navigate_to(page):
    st.session_state.page = page


# Home Page
def home_page():
    st.title("🏭 Rough Casting Management System")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.button("📝 Register New Product", on_click=navigate_to, args=("register",))
    with col2:
        st.button("📷 Scan QR Code", on_click=navigate_to, args=("scan",))
    with col3:
        st.button("📊 View Reports", on_click=navigate_to, args=("reports",))

    st.markdown("---")

    # Show recent products
    conn = init_db()
    recent_products = pd.read_sql("""
    SELECT batch_id, product_name, company, level, status 
    FROM products 
    ORDER BY last_updated DESC 
    LIMIT 5
    """, conn)

    if not recent_products.empty:
        st.subheader("Recently Updated Products")
        st.dataframe(recent_products, hide_index=True)
    else:
        st.info("No products found. Register a new product to get started.")

    conn.close()


# Register Product Page
def register_page():
    st.title("📝 Register New Product")
    st.markdown("---")

    with st.form("product_form"):
        product_name = st.text_input("Product Name", max_chars=50)
        company = st.text_input("Company", max_chars=30)

        col1, col2 = st.columns(2)
        with col1:
            level = st.selectbox(
                "Production Level",
                ["Raw", "Processing", "Finished", "Shipped"]
            )
        with col2:
            deadline = st.date_input("Deadline")

        stock_percent = st.slider("Initial Stock %", 0, 100, 50)

        submitted = st.form_submit_button("Register Product")

        if submitted:
            if not product_name or not company:
                st.error("Product name and company are required!")
                return

            # Generate batch ID
            company_code = company[:3].upper()
            product_code = product_name[:3].upper()
            timestamp = datetime.now().strftime("%y%m%d")
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            batch_id = f"{company_code}-{product_code}-{timestamp}-{random_str}"

            try:
                conn = init_db()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                INSERT INTO products (
                    batch_id, product_name, company, level, 
                    deadline, stock_percent, status, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, product_name, company, level,
                    deadline.strftime("%Y-%m-%d"), stock_percent, "Pending", timestamp
                ))

                # Generate QR code
                qr_data = {
                    "batch_id": batch_id,
                    "product_name": product_name,
                    "company": company
                }

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(json.dumps(qr_data))
                qr.make(fit=True)
                img = qr.make_image(fill="black", back_color="white")

                # Save QR code to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                conn.commit()
                conn.close()

                st.success(f"Product registered successfully! Batch ID: {batch_id}")

                # Display QR code
                st.image(img_bytes, caption=f"QR Code for {batch_id}", width=200)

                # Download button for QR code
                st.download_button(
                    label="Download QR Code",
                    data=img_bytes,
                    file_name=f"{batch_id}_qrcode.png",
                    mime="image/png"
                )

            except Exception as e:
                st.error(f"Error registering product: {e}")


# QR Code Scanning Page
def scan_page():
    st.title("📷 Scan QR Code")
    st.markdown("---")

    uploaded_file = st.file_uploader("Upload QR Code Image", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        # Read image file
        file_bytes = uploaded_file.getvalue()
        img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)

        # Detect QR code
        detected_qrs = decode(img)

        if not detected_qrs:
            st.error("No QR code found in the image!")
            return

        try:
            qr_data = json.loads(detected_qrs[0].data.decode('utf-8'))
            batch_id = qr_data.get("batch_id")

            if not batch_id:
                st.error("Invalid QR code data: missing batch_id")
                return

            st.success(f"Successfully scanned QR code for batch: {batch_id}")

            # Show product details
            conn = init_db()
            product = pd.read_sql(f"""
            SELECT product_name, company, level, deadline, stock_percent, status 
            FROM products WHERE batch_id = '{batch_id}'
            """, conn)

            if product.empty:
                st.error("Batch ID not found in database!")
                return

            st.subheader("Product Details")
            st.dataframe(product, hide_index=True)

            # Transaction options
            st.subheader("Transaction Options")
            tab1, tab2, tab3 = st.tabs(["Update Stock", "Change Level", "Update Status"])

            with tab1:
                with st.form("stock_form"):
                    current_stock = product.iloc[0]['stock_percent']
                    change = st.number_input(
                        "Stock Change",
                        min_value=-100,
                        max_value=100,
                        value=0,
                        help=f"Current stock: {current_stock}%"
                    )

                    if st.form_submit_button("Update Stock"):
                        new_stock = current_stock + change
                        if not 0 <= new_stock <= 100:
                            st.error("Stock must be between 0% and 100%")
                        else:
                            try:
                                cursor = conn.cursor()
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                cursor.execute("""
                                UPDATE products 
                                SET stock_percent = ?, last_updated = ? 
                                WHERE batch_id = ?
                                """, (new_stock, timestamp, batch_id))

                                # Log transaction
                                cursor.execute("""
                                INSERT INTO transaction_logs (
                                    batch_id, operation, quantity_change, 
                                    previous_stock, new_stock, timestamp
                                ) VALUES (?, ?, ?, ?, ?, ?)
                                """, (
                                    batch_id, "Stock Update", change,
                                    current_stock, new_stock, timestamp
                                ))

                                conn.commit()
                                st.success(f"Stock updated to {new_stock}%")
                                st.experimental_rerun()

                            except Exception as e:
                                st.error(f"Error updating stock: {e}")
                                conn.rollback()

            with tab2:
                with st.form("level_form"):
                    current_level = product.iloc[0]['level']
                    new_level = st.selectbox(
                        "New Production Level",
                        ["Raw", "Processing", "Finished", "Shipped"],
                        index=["Raw", "Processing", "Finished", "Shipped"].index(current_level)
                    )

                    if st.form_submit_button("Update Level"):
                        try:
                            cursor = conn.cursor()
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            cursor.execute("""
                            UPDATE products 
                            SET level = ?, last_updated = ? 
                            WHERE batch_id = ?
                            """, (new_level, timestamp, batch_id))

                            conn.commit()
                            st.success(f"Level changed to {new_level}")
                            st.experimental_rerun()

                        except Exception as e:
                            st.error(f"Error updating level: {e}")
                            conn.rollback()

            with tab3:
                with st.form("status_form"):
                    current_status = product.iloc[0]['status']
                    new_status = st.selectbox(
                        "New Status",
                        ["Pending", "In Progress", "Completed", "Delayed"],
                        index=["Pending", "In Progress", "Completed", "Delayed"].index(current_status)
                    )

                    if st.form_submit_button("Update Status"):
                        try:
                            cursor = conn.cursor()
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            cursor.execute("""
                            UPDATE products 
                            SET status = ?, last_updated = ? 
                            WHERE batch_id = ?
                            """, (new_status, timestamp, batch_id))

                            conn.commit()
                            st.success(f"Status changed to {new_status}")
                            st.experimental_rerun()

                        except Exception as e:
                            st.error(f"Error updating status: {e}")
                            conn.rollback()

            conn.close()

        except Exception as e:
            st.error(f"Error processing QR code: {e}")


# Reports Page
def reports_page():
    st.title("📊 Product Reports")
    st.markdown("---")

    report_type = st.selectbox(
        "Select Report Type",
        [
            "All Products",
            "By Status",
            "By Level",
            "Critical Stock (<20%)",
            "Upcoming Deadlines"
        ]
    )

    conn = init_db()

    if report_type == "All Products":
        st.subheader("All Products")
        df = pd.read_sql("""
        SELECT batch_id, product_name, company, level, 
               deadline, stock_percent, status 
        FROM products 
        ORDER BY deadline
        """, conn)

    elif report_type == "By Status":
        status = st.selectbox(
            "Select Status",
            ["Pending", "In Progress", "Completed", "Delayed"]
        )
        st.subheader(f"Products with Status: {status}")
        df = pd.read_sql(f"""
        SELECT batch_id, product_name, company, level, 
               deadline, stock_percent, status 
        FROM products 
        WHERE status = '{status}'
        ORDER BY deadline
        """, conn)

    elif report_type == "By Level":
        level = st.selectbox(
            "Select Production Level",
            ["Raw", "Processing", "Finished", "Shipped"]
        )
        st.subheader(f"Products at Level: {level}")
        df = pd.read_sql(f"""
        SELECT batch_id, product_name, company, level, 
               deadline, stock_percent, status 
        FROM products 
        WHERE level = '{level}'
        ORDER BY deadline
        """, conn)

    elif report_type == "Critical Stock (<20%)":
        st.subheader("Products with Critical Stock (<20%)")
        df = pd.read_sql("""
        SELECT batch_id, product_name, company, level, 
               deadline, stock_percent, status 
        FROM products 
        WHERE stock_percent < 20
        ORDER BY stock_percent
        """, conn)

    elif report_type == "Upcoming Deadlines":
        st.subheader("Products with Upcoming Deadlines (Next 7 Days)")
        df = pd.read_sql("""
        SELECT batch_id, product_name, company, level, 
               deadline, stock_percent, status 
        FROM products 
        WHERE deadline <= date('now', '+7 days')
        ORDER BY deadline
        """, conn)

    if not df.empty:
        # Format the deadline column
        df['deadline'] = pd.to_datetime(df['deadline']).dt.strftime('%Y-%m-%d')

        # Display as interactive table
        st.dataframe(
            df,
            column_config={
                "stock_percent": st.column_config.ProgressColumn(
                    "Stock %",
                    format="%d%%",
                    min_value=0,
                    max_value=100,
                )
            },
            hide_index=True,
            use_container_width=True
        )

        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download as CSV",
            csv,
            f"{report_type.lower().replace(' ', '_')}_report.csv",
            "text/csv"
        )
    else:
        st.info("No products found matching the criteria.")

    conn.close()


# Main App
def main():
    st.set_page_config(
        page_title="Rough Casting Management",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS
    st.markdown("""
    <style>
        .stButton button {
            width: 100%;
        }
        .stSelectbox, .stTextInput, .stDateInput, .stSlider {
            margin-bottom: 1rem;
        }
        .stDataFrame {
            margin-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

    # Page routing
    if st.session_state.page == "home":
        home_page()
    elif st.session_state.page == "register":
        register_page()
    elif st.session_state.page == "scan":
        scan_page()
    elif st.session_state.page == "reports":
        reports_page()


if __name__ == "__main__":
    main()