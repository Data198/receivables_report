import streamlit as st
import bcrypt
import psycopg2
from urllib.parse import quote

# Connect to database
conn = psycopg2.connect(**st.secrets["postgres"])
cursor = conn.cursor()

# New password
new_password = "newpassword123"
hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

# Update password_hash for accountant1
cursor.execute("UPDATE users SET password_hash = %s WHERE username = %s", (hashed.decode(), "accountant1"))
conn.commit()

# Close connection
cursor.close()
conn.close()