import streamlit as st
from sqlalchemy import create_engine, text
from urllib.parse import quote
import datetime

# Setup connection
@st.cache_resource
def init_connection():
    password = quote(st.secrets['postgres']['password'])
    conn_str = (
        f"postgresql+psycopg2://{st.secrets['postgres']['user']}:{password}@"
        f"{st.secrets['postgres']['host']}:{st.secrets['postgres']['port']}/"
        f"{st.secrets['postgres']['database']}"
    )
    return create_engine(conn_str)

engine = init_connection()

st.title("🔧 DEBUG: DB Update Test")

# Inputs
invoice_no = st.text_input("GST Invoice No")
dealer_code = st.text_input("Dealer Code")
new_amt = st.number_input("New Receipt Amount 1", step=100.0)

if st.button("Force Update & Audit"):
    try:
        with engine.begin() as conn:
            # Fetch current value
            current = conn.execute(text("""
                SELECT receipt_amount_1 FROM fact_service_billing
                WHERE gst_invoice_no = :gst AND dealer_code = :dealer
            """), {"gst": invoice_no, "dealer": dealer_code}).fetchone()

            if not current:
                st.error("❌ Record not found.")
            else:
                old_amt = current[0]
                st.write(f"Old receipt_amount_1: {old_amt}")

                # Update DB
                conn.execute(text("""
                    UPDATE fact_service_billing
                    SET receipt_amount_1 = :amt, collection_timestamp = now()
                    WHERE gst_invoice_no = :gst AND dealer_code = :dealer
                """), {
                    "amt": new_amt, "gst": invoice_no, "dealer": dealer_code
                })

                # Audit log
                conn.execute(text("""
                    INSERT INTO service_billing_audit_log (
                        username, gst_invoice_no, dealer_code, changed_field, old_value, new_value
                    ) VALUES (
                        :user, :gst, :dealer, 'receipt_amount_1', :old, :new
                    )
                """), {
                    "user": "debug_user",  # Replace with session user if needed
                    "gst": invoice_no,
                    "dealer": dealer_code,
                    "old": str(old_amt),
                    "new": str(new_amt)
                })

                st.success("✅ Updated and logged!")

    except Exception as e:
        st.error(f"❌ Error occurred: {e}")
