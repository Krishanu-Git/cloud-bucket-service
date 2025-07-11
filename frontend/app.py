import streamlit as st
import requests

API_URL = "http://backend:8000"

if "token" not in st.session_state:
    st.session_state.token = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.title("Cloud Bucket Service")

def show_auth_page():
    auth_option = st.radio("Choose action", ["Signup", "Login"])
    if auth_option == "Signup":
        st.subheader("Create a new account")
        username = st.text_input("Username", key="signup_user")
        password = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            r = requests.post(f"{API_URL}/signup", json={"username": username, "password": password})
            st.success(r.json().get("message", "Signup complete"))
    else:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            r = requests.post(f"{API_URL}/login", data={"username": username, "password": password})
            if r.status_code == 200:
                st.session_state.token = r.json()["access_token"]
                st.session_state.logged_in = True
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Login failed")

def show_main_menu():
    menu = st.sidebar.selectbox("Menu", [
        "Create Bucket", "Upload File", "List Files", "Download File", "Delete Bucket", "Delete Files"
    ])
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

    if menu == "Create Bucket":
        bucket_name = st.text_input("Bucket name")
        if st.button("Create"):
            r = requests.post(f"{API_URL}/buckets", json={"bucket": bucket_name}, headers=headers)
            st.write(r.json())

    if menu == "Upload File":
        bucket = st.text_input("Bucket")
        uploaded_file = st.file_uploader("Choose a file")
        if st.button("Upload") and uploaded_file:
            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            r = requests.post(f"{API_URL}/upload", params={"bucket": bucket}, files=files, headers=headers)
            st.write(r.json())

    if menu == "List Files":
        bucket = st.text_input("Bucket")
        if st.button("List"):
            r = requests.get(f"{API_URL}/files", params={"bucket": bucket}, headers=headers)
            st.write(r.json())

    if menu == "Download File":
        bucket = st.text_input("Bucket")
        filename = st.text_input("Filename")
        if st.button("Download"):
            r = requests.get(f"{API_URL}/download", params={"bucket": bucket, "filename": filename}, headers=headers)
            if r.status_code == 200:
                st.download_button("Download", r.content, file_name=filename)
            else:
                st.error("File not found")

    if menu == "Delete Bucket":
        bucket = st.text_input("Bucket to delete")
        if st.button("Delete Bucket"):
            r = requests.delete(f"{API_URL}/delete_bucket", params={"bucket": bucket}, headers=headers)
            st.write(r.json())

    if menu == "Delete Files":
        bucket = st.text_input("Bucket")
        filename = st.text_input("Filenames to delete (separated by commas)")
        if st.button("Delete File"):
            r = requests.delete(f"{API_URL}/delete_files", json={"bucket": bucket, "filename": filename}, headers=headers)
            st.write(r.json())

if not st.session_state.logged_in or not st.session_state.token:
    show_auth_page()
else:
    show_main_menu()
