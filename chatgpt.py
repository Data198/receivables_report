import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote
import bcrypt
import time
import datetime
import os

# --- Session State Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "upload_trigger" not in st.session_state:
    st.session_state.upload_trigger = 0

# --- Database Connection ---
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

# --- Query Utility ---
@st.cache_data(ttl=600)
def run_query(query):
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# --- Login Page ---
def login_page():
    st.title("🔐 Login")
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
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")

# --- Main App ---
def main_app():
    st.sidebar.title(f"👤 Logged in as: {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    with st.sidebar:
     selected_tab = option_menu(
        menu_title="Navigation",
        options=["🏠 Home", "📤 Upload Billing", "📝 View and Update Collection", "📈 Reports"],
        icons=["house", "cloud-upload", "pencil-square", "bar-chart-line"],
        menu_icon="cast",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "5px", "background-color": "#f0f2f6"},
            "icon": {"color": "#3c3c3c", "font-size": "16px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "margin": "2px",
                "padding": "10px 10px",
                "--hover-color": "#e9f5ff",
            },
            "nav-link-selected": {"background-color": "#d0eaff", "font-weight": "bold"},
        }
    )


    if selected_tab == "🏠 Home":
        st.title("🏠 Home - Vehicle Visit Summary")
        selected_date = st.date_input("📅 Select Date", value=datetime.date.today())

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    COUNT(DISTINCT vin) AS vehicle_count,
                    SUM(COALESCE(cust_labor, 0) + COALESCE(ins_labor, 0)) AS labour_earned
                FROM fact_service_billing
                WHERE gst_invoice_date = :selected_date
            """), {"selected_date": selected_date}).fetchone()

            vehicles_count = result[0] if result else 0
            labour_earned = float(result[1] or 0.0)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"""
                <div style="background-color: #e0f2fe; padding: 20px; border-radius: 12px;
                            box-shadow: 2px 2px 10px rgba(0,0,0,0.1); text-align: center;">
                    <h3 style="color: #1e3a8a;">🚗 Vehicles Visited </h3>
                    <h1 style="font-size: 48px; margin-top: 0; color: #1e40af;">{vehicles_count}</h1>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div style="background-color: #e6fffa; padding: 20px; border-radius: 12px;
                            box-shadow: 2px 2px 10px rgba(0,0,0,0.1); text-align: center;">
                    <h3 style="color: #065f46;">🛠️ Labour Earned </h3>
                    <h1 style="font-size: 48px; margin-top: 0; color: #047857;">₹ {labour_earned:,.2f}</h1>
                </div>
            """, unsafe_allow_html=True)


    elif selected_tab == "📤 Upload Billing":
        st.title("📤 Upload Billing Data")
        uploaded_file = st.file_uploader("Choose Excel file", type=["xlsx"], key=f"uploader_{st.session_state.upload_trigger}")

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("📋 Preview of uploaded data:")
            st.dataframe(df)

            if 'gst_invoice_date' in df.columns:
                df['gst_invoice_date'] = pd.to_datetime(df['gst_invoice_date'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')
            if 'ro_date' in df.columns:
                df['ro_date'] = pd.to_datetime(df['ro_date'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')

            df['user_id'] = st.session_state.username

            if st.button("💾 Save to Database"):
                try:
                    df.to_sql('fact_service_billing', engine, if_exists='append', index=False)
                    st.success(f"✅ {len(df)} records saved to database.")
                    st.session_state.upload_trigger += 1
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error saving to database: {e}")

    elif selected_tab == "📝 View and Update Collection":
        st.title("📝 View & Update Collections")

        invoice_filter = st.text_input("🔍 GST Invoice No")
        vehicle_filter = st.text_input("🚗 Vehicle Reg. No")
        date_filter = st.date_input("📅 GST Invoice Date", value=None)

        where = []
        params = {}

        if invoice_filter:
            where.append("gst_invoice_no ILIKE :invoice_no")
            params['invoice_no'] = f"%{invoice_filter}%"
        if vehicle_filter:
            where.append("vehicle_reg_no ILIKE :vehicle_no")
            params['vehicle_no'] = f"%{vehicle_filter}%"
        if date_filter:
            where.append("gst_invoice_date = :invoice_date")
            params['invoice_date'] = date_filter

        filter_sql = " AND ".join(where)
        query = "SELECT * FROM fact_service_billing"
        if filter_sql:
            query += " WHERE " + filter_sql
        query += " ORDER BY gst_invoice_date DESC LIMIT 50"

        df = pd.read_sql(text(query), engine.connect(), params=params)

        if df.empty:
            st.info("No records found.")
        else:
            selected = st.selectbox("Select Record", df.index, format_func=lambda i: f"{df.loc[i, 'gst_invoice_no']} | {df.loc[i, 'dealer_code']}")
            record = df.loc[selected]

            st.markdown(f"### Invoice: `{record['gst_invoice_no']}` | Dealer: `{record['dealer_code']}`")
            st.write(f"**Customer:** {record['customer_name']} | **Vehicle:** {record['vehicle_reg_no']}")
            st.write(f"**Invoice Amt:** ₹{record['invoice_amt']} | **Total Collection:** ₹{record['total_collection']} | **Due:** ₹{record['due_amount']}")

            st.subheader("💰 Collection Details")
            col1, col2, col3 = st.columns(3)

            with col1:
                receipt_number_1 = st.text_input("Receipt Number (i)", value=record['receipt_number_1'] or "")
                receipt_date_1 = st.date_input("Receipt Date (i)", value=record['receipt_date_1'] if pd.notnull(record['receipt_date_1']) else None, key="rd1")
                source_of_receipt_1 = st.text_input("Source of Receipt (i)", value=record['source_of_receipt_1'] or "")
                receipt_amount_1 = st.number_input("Receipt Amount (i)", value=float(record['receipt_amount_1'] or 0), step=100.0)

            with col2:
                receipt_number_2 = st.text_input("Receipt Number (ii)", value=record['receipt_number_2'] or "")
                receipt_date_2 = st.date_input("Receipt Date (ii)", value=record['receipt_date_2'] if pd.notnull(record['receipt_date_2']) else None, key="rd2")
                source_of_receipt_2 = st.text_input("Source of Receipt (ii)", value=record['source_of_receipt_2'] or "")
                receipt_amount_2 = st.number_input("Receipt Amount (ii)", value=float(record['receipt_amount_2'] or 0), step=100.0)

            with col3:
                insurance_receipt_number = st.text_input("Insurance Receipt Number", value=record['insurance_receipt_number'] or "")
                insurance_receipt_date = st.date_input("Insurance Receipt Date", value=record['insurance_receipt_date'] if pd.notnull(record['insurance_receipt_date']) else None, key="ird")
                insurance_receipt_amount = st.number_input("Insurance Receipt Amount", value=float(record['insurance_receipt_amount'] or 0), step=100.0)
                advance_collected = st.number_input("Advance Collected", value=float(record['advance_collected'] or 0), step=100.0)
                discount_given = st.number_input("Discount Amount", value=float(record['discount_given'] or 0), step=100.0)

            st.subheader("📄 Other Details")
            col4, col5, col6 = st.columns(3)

            with col4:
                due_options = ["Pending", "Cleared", "Partially Paid"]
                type_of_due = st.selectbox("Type of Due", options=[""] + due_options, index=(due_options.index(record['type_of_due']) + 1) if record['type_of_due'] in due_options else 0)

            with col5:
                claim_number = st.text_input("Claim Number", value=record['claim_number'] or "")
                policy_number = st.text_input("Policy Number", value=record['policy_number'] or "")

            with col6:
                claim_remarks = st.text_area("Claim Remarks", value=record['claim_remarks'] or "")
                any_other_remarks = st.text_area("Any other remarks", value=record['any_other_remarks'] or "")

            if st.button("💾 Save All Updates"):
                total_input_collection = sum([
                    float(receipt_amount_1 or 0),
                    float(receipt_amount_2 or 0),
                    float(insurance_receipt_amount or 0),
                    float(advance_collected or 0),
                    float(discount_given or 0)
                ])

                if total_input_collection > float(record['invoice_amt'] or 0):
                    st.error("❌ Total collection + discount cannot exceed invoice amount.")
                    st.stop()

                with engine.begin() as conn:
                    fields_to_check = {
                        "receipt_amount_1": receipt_amount_1,
                        "receipt_amount_2": receipt_amount_2,
                        "insurance_receipt_amount": insurance_receipt_amount,
                        "advance_collected": advance_collected,
                        "discount_given": discount_given,
                        "receipt_number_1": receipt_number_1,
                        "receipt_date_1": str(receipt_date_1) if receipt_date_1 else "",
                        "source_of_receipt_1": source_of_receipt_1,
                        "receipt_number_2": receipt_number_2,
                        "receipt_date_2": str(receipt_date_2) if receipt_date_2 else "",
                        "source_of_receipt_2": source_of_receipt_2,
                        "insurance_receipt_number": insurance_receipt_number,
                        "insurance_receipt_date": str(insurance_receipt_date) if insurance_receipt_date else "",
                        "type_of_due": type_of_due,
                        "claim_number": claim_number,
                        "policy_number": policy_number,
                        "claim_remarks": claim_remarks,
                        "any_other_remarks": any_other_remarks
                    }

                    current_data = conn.execute(text(f"""
                        SELECT {", ".join(fields_to_check.keys())}
                        FROM fact_service_billing
                        WHERE dealer_code = :dealer_code AND gst_invoice_no = :gst_invoice_no
                    """), {
                        "dealer_code": record["dealer_code"],
                        "gst_invoice_no": record["gst_invoice_no"]
                    }).fetchone()

                    for i, field in enumerate(fields_to_check.keys()):
                        old_val = str(current_data[i]) if current_data[i] is not None else ""
                        new_val = str(fields_to_check[field]) if fields_to_check[field] is not None else ""
                        if old_val != new_val:
                            conn.execute(text("""
                                INSERT INTO service_billing_audit_log (
                                    username, gst_invoice_no, dealer_code, changed_field, old_value, new_value
                                ) VALUES (:user, :invoice, :dealer, :field, :old, :new)
                            """), {
                                "user": st.session_state.username,
                                "invoice": record["gst_invoice_no"],
                                "dealer": record["dealer_code"],
                                "field": field,
                                "old": old_val,
                                "new": new_val
                            })

                    update_q = text("""
                        UPDATE fact_service_billing
                        SET receipt_amount_1 = :ra1,
                            receipt_amount_2 = :ra2,
                            insurance_receipt_amount = :ira,
                            advance_collected = :adv,
                            discount_given = :disc,
                            receipt_number_1 = :rn1,
                            receipt_date_1 = :rd1,
                            source_of_receipt_1 = :sr1,
                            receipt_number_2 = :rn2,
                            receipt_date_2 = :rd2,
                            source_of_receipt_2 = :sr2,
                            insurance_receipt_number = :ins_no,
                            insurance_receipt_date = :ins_date,
                            type_of_due = :tod,
                            claim_number = :claim_no,
                            policy_number = :policy_no,
                            claim_remarks = :claim_r,
                            any_other_remarks = :any_r,
                            collection_timestamp = now()
                        WHERE dealer_code = :dealer_code AND gst_invoice_no = :gst_invoice_no
                    """)

                    conn.execute(update_q, {
                        "ra1": receipt_amount_1,
                        "ra2": receipt_amount_2,
                        "ira": insurance_receipt_amount,
                        "adv": advance_collected,
                        "disc": discount_given,
                        "rn1": receipt_number_1,
                        "rd1": receipt_date_1,
                        "sr1": source_of_receipt_1,
                        "rn2": receipt_number_2,
                        "rd2": receipt_date_2,
                        "sr2": source_of_receipt_2,
                        "ins_no": insurance_receipt_number,
                        "ins_date": insurance_receipt_date,
                        "tod": type_of_due,
                        "claim_no": claim_number,
                        "policy_no": policy_number,
                        "claim_r": claim_remarks,
                        "any_r": any_other_remarks,
                        "dealer_code": record["dealer_code"],
                        "gst_invoice_no": record["gst_invoice_no"]
                    })

                st.success("✅ Collection info updated and audit trail saved.")
                st.rerun()

    elif selected_tab == "📈 Reports":
        st.title("📈 REP-01 - Customer Outstanding Report")

        dealer_filter = st.text_input("🔍 Filter by Dealer Code")
        date_range = st.date_input("📅 Invoice Date Range", [])

        where = ["due_amount > 0"]
        params = {}

        if dealer_filter:
            where.append("dealer_code ILIKE :dealer_code")
            params["dealer_code"] = f"%{dealer_filter}%"
        
        if len(date_range) == 2:
            where.append("gst_invoice_date BETWEEN :start_date AND :end_date")
            params["start_date"] = date_range[0]
            params["end_date"] = date_range[1]

        filter_sql = " AND ".join(where)
        query = f"""
            SELECT 
                customer_name AS "Customer",
                gst_invoice_no AS "Invoice No",
                gst_invoice_date AS "Invoice Date",
                invoice_amt AS "Invoice Amount",
                total_collection AS "Total Collected",
                due_amount AS "Due Amount",
                type_of_due AS "Due Type",
                vehicle_reg_no AS "Vehicle No",
                dealer_code AS "Dealer"
            FROM fact_service_billing
            WHERE {filter_sql}
            ORDER BY gst_invoice_date DESC
        """

        df_outstanding = pd.read_sql(text(query), engine.connect(), params=params)

        if df_outstanding.empty:
            st.info("✅ No customer outstanding found for the selected filter.")
        else:
            st.dataframe(df_outstanding, use_container_width=True)
            csv = df_outstanding.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download as CSV", data=csv, file_name="customer_outstanding_report.csv", mime="text/csv")

# --- Entry Point ---
if __name__ == "__main__":
    if not st.session_state.logged_in:
        login_page()
    else:
        main_app()
