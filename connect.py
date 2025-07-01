import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote
import bcrypt
import time

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "upload_trigger" not in st.session_state:
    st.session_state.upload_trigger = 0

# DB connection
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

# Query wrapper
@st.cache_data(ttl=600)
def run_query(query):
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# Login page
def login_page():
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            with engine.connect() as conn:
                query = text("SELECT password_hash FROM users WHERE username = :username")
                result = conn.execute(query, {"username": username}).fetchone()

                if result and bcrypt.checkpw(password.encode(), result[0].encode()):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid credentials")

# Main app
def main_app():
    tab1, tab2 = st.tabs(["Home", "Billing details"])

    with tab1:
        st.write("Welcome to the dashboard!")
        st.subheader("Upload Bills")
        uploaded_file = st.file_uploader("Choose import template file", type=["xlsx"], key=f"uploader_{st.session_state.upload_trigger}")

        if uploaded_file is not None:
            st.write("File uploaded successfully!")
            df = pd.read_excel(uploaded_file)
            st.write("Preview of uploaded data:", df)

            if 'gst_invoice_date' in df.columns:
                df['gst_invoice_date'] = pd.to_datetime(df['gst_invoice_date'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')
            if 'ro_date' in df.columns:
                df['ro_date'] = pd.to_datetime(df['ro_date'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')

            if st.session_state.username:
                df['user_id'] = st.session_state.username
            else:
                st.error("No user logged in. Please log in again.")
                return

            if st.button("Save to Database"):
                try:
                    df.to_sql('fact_service_billing', engine, if_exists='append', index=False)
                    st.success(f"{len(df)} records saved to the database successfully!")
                    st.session_state.upload_trigger += 1
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving to database: {str(e)}")

    with tab2:
        st.subheader("Collection Details")

        query_dealer_invoice = """
            SELECT DISTINCT TRIM(UPPER(dealer_code)) AS dealer_code, gst_invoice_no 
            FROM fact_service_billing
        """
        dropdown_data = run_query(query_dealer_invoice)
        dealer_options = sorted(set(dropdown_data['dealer_code'].dropna().unique()))
        invoice_options = sorted(set(dropdown_data['gst_invoice_no'].dropna().unique()))

        with st.form(key="collection_form"):
            dealer_code = st.selectbox("Dealer Code", options=dealer_options, key="dealer_code_select")
            gst_invoice_no = st.selectbox("GST Invoice No", options=invoice_options, key="gst_invoice_no_select")
            receipt_number = st.text_input("Receipt Number", key="receipt_number_input")
            receipt_amount = st.number_input("Receipt Amount", min_value=0.0, step=0.01, key="receipt_amount_input")
            source_of_receipt = st.selectbox("Source of Receipt", ["Cash", "Card", "Bank Transfer", "Insurance"], key="source_of_receipt_select")
            type_of_due = st.selectbox("Type of Due", ["Pending", "Overdue", "Cleared"], key="type_of_due_select")
            discount_amount = st.number_input("Discount Amount", min_value=0.0, step=0.01, key="discount_amount_input")
            claim_number = st.text_input("Claim Number", key="claim_number_input")
            policy_number = st.text_input("Policy Number", key="policy_number_input")
            claim_remarks = st.text_input("Claim Remarks", key="claim_remarks_input")
            any_other_remarks = st.text_input("Any other remarks", key="any_other_remarks_input")

            if st.form_submit_button("Save Collection"):
                try:
                    with engine.begin() as conn:
                        insert_query = text("""
                            INSERT INTO fact_collections (
                                dealer_code, gst_invoice_no, receipt_number, receipt_amount,
                                source_of_receipt, type_of_due, discount_amount,
                                claim_number, policy_number, claim_remarks, any_other_remarks
                            ) VALUES (
                                :dealer_code, :gst_invoice_no, :receipt_number, :receipt_amount,
                                :source_of_receipt, :type_of_due, :discount_amount,
                                :claim_number, :policy_number, :claim_remarks, :any_other_remarks
                            )
                        """)
                        conn.execute(insert_query, {
                            "dealer_code": dealer_code,
                            "gst_invoice_no": gst_invoice_no,
                            "receipt_number": receipt_number,
                            "receipt_amount": receipt_amount,
                            "source_of_receipt": source_of_receipt,
                            "type_of_due": type_of_due,
                            "discount_amount": discount_amount,
                            "claim_number": claim_number,
                            "policy_number": policy_number,
                            "claim_remarks": claim_remarks,
                            "any_other_remarks": any_other_remarks
                        })

                    st.success("Collection details saved successfully!")

                    # Clear form values
                    st.session_state["dealer_code_select"] = dealer_options[0] if dealer_options else ""
                    st.session_state["gst_invoice_no_select"] = invoice_options[0] if invoice_options else ""
                    st.session_state["receipt_number_input"] = ""
                    st.session_state["receipt_amount_input"] = 0.0
                    st.session_state["source_of_receipt_select"] = "Cash"
                    st.session_state["type_of_due_select"] = "Pending"
                    st.session_state["discount_amount_input"] = 0.0
                    st.session_state["claim_number_input"] = ""
                    st.session_state["policy_number_input"] = ""
                    st.session_state["claim_remarks_input"] = ""
                    st.session_state["any_other_remarks_input"] = ""

                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving collection: {str(e)}")

# Run app
if not st.session_state.logged_in:
    login_page()
else:
    main_app()
