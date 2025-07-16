import streamlit as st
import requests
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

API_URL = "http://backend:8000"

if "token" not in st.session_state:
    st.session_state.token = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.title("Cloud Bucket Service")

def show_auth_page():
    auth_option = st.radio("Choose action", ["Signup", "Login"])
    logger.debug(f"Auth page loaded, option selected: {auth_option}")
    if auth_option == "Signup":
        st.subheader("Create a new account")
        username = st.text_input("Username", key="signup_user")
        password = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            logger.info(f"Attempting signup for user: {username}")
            r = requests.post(f"{API_URL}/signup", json={"username": username, "password": password})
            logger.debug(f"Signup response: {r.status_code} {r.text}")
            if r.status_code == 200:
                st.session_state.username = username
            st.success(r.json().get("message", "Signup complete"))
    else:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            logger.info(f"Attempting login for user: {username}")
            r = requests.post(f"{API_URL}/login", data={"username": username, "password": password})
            if r.status_code == 200:
                st.session_state.token = r.json()["access_token"]
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Logged in!")
                logger.info(f"User {username} logged in successfully")
                st.rerun()
                logger.info(f"User {username} logged in successfully")
                st.rerun()
            else:
                logger.info(f"Login failed for user: {username}")
                st.error("Login failed")

def show_main_menu():
    menu = st.sidebar.selectbox("Menu", [
        "Create Bucket", "Upload File", "List Files",
        "Download File", "Delete Bucket", "Delete Files",
        "Share File", "Files Shared With Me"
    ])
    logger.debug(f"Main menu selected: {menu}")
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

    if menu == "Create Bucket":
        bucket_name = st.text_input("Bucket name")
        if st.button("Create"):
            logger.info(f"Creating bucket: {bucket_name}")
            r = requests.post(f"{API_URL}/buckets", json={"bucket": bucket_name}, headers=headers)
            logger.debug(f"Create bucket response: {r.status_code} {r.text}")
            st.write(r.json())

    if menu == "Upload File":
        bucket = st.text_input("Bucket")
        uploaded_file = st.file_uploader("Choose a file")
        if st.button("Upload") and uploaded_file:
            logger.info(f"Uploading file: {uploaded_file.name} to bucket: {bucket}")
            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            r = requests.post(f"{API_URL}/upload", params={"bucket": bucket}, files=files, headers=headers)
            logger.debug(f"Upload file response: {r.status_code} {r.text}")
            st.write(r.json())

    if menu == "List Files":
        bucket = st.text_input("Bucket")
        if st.button("List"):
            logger.info(f"Listing files in bucket: {bucket}")
            r = requests.get(f"{API_URL}/files", params={"bucket": bucket}, headers=headers)
            logger.debug(f"List files response: {r.status_code} {r.text}")
            st.write(r.json())

    if menu == "Download File":
        bucket = st.text_input("Bucket")
        filename = st.text_input("Filename")
        if st.button("Download"):
            logger.info(f"Downloading file: {filename} from bucket: {bucket}")
            r = requests.get(f"{API_URL}/download", params={"bucket": bucket, "filename": filename}, headers=headers)
            logger.debug(f"Download file response: {r.status_code}")
            if r.status_code == 200:
                st.download_button("Download", r.content, file_name=filename)
            else:
                logger.info(f"File not found: {filename} in bucket: {bucket}")
                st.error("File not found")

    if menu == "Delete Bucket":
        bucket = st.text_input("Bucket to delete")
        if st.button("Delete Bucket"):
            logger.info(f"Deleting bucket: {bucket}")
            r = requests.delete(f"{API_URL}/delete_bucket", params={"bucket": bucket}, headers=headers)
            logger.debug(f"Delete bucket response: {r.status_code} {r.text}")
            st.write(r.json())

    if menu == "Delete Files":
        bucket = st.text_input("Bucket")
        filename = st.text_input("Filenames to delete (separated by commas)")
        if st.button("Delete File"):
            logger.info(f"Deleting files: {filename} from bucket: {bucket}")
            r = requests.delete(f"{API_URL}/delete_files", json={"bucket": bucket, "filename": filename}, headers=headers)
            logger.debug(f"Delete files response: {r.status_code} {r.text}")
            st.write(r.json())

    if menu == "Share File":
        bucket = st.text_input("Bucket")
        filename = st.text_input("Filename")
        shared_with_username = st.text_input("Username to share with")
        if st.button("Share"):
            logger.info(f"Sharing file: {filename} from bucket: {bucket} with user: {shared_with_username}")
            r = requests.post(f"{API_URL}/share", json={
                "bucket": bucket,
                "filename": filename,
                "shared_with_username": shared_with_username
            }, headers=headers)
            logger.debug(f"Share file response: {r.status_code} {r.text}")
            if r.status_code == 200:
                st.success(r.json().get("message", "File shared successfully"))
            else:
                st.error(r.json().get("detail", "Failed to share file"))

    if menu == "Files Shared With Me":
        logger.info("Fetching files shared with current user")
        r = requests.get(f"{API_URL}/shared_with_me", headers=headers)
        logger.debug(f"Files shared with me response: {r.status_code} {r.text}")
        if r.status_code == 200:
            shared_files = r.json()
            if shared_files:
                for f in shared_files:
                    st.write(f"Bucket: {f['bucket']}, Filename: {f['filename']}")
                    dr = requests.get(
                        f"{API_URL}/download_shared",
                        params={"bucket": f["bucket"], "filename": f["filename"]},
                        headers=headers
                    )
                    logger.debug(f"Download shared file response: {dr.status_code} for {f['filename']}")
                    if dr.status_code == 200:
                        st.download_button(
                            label=f"Download {f['filename']}",
                            data=dr.content,
                            file_name=f['filename'],
                            mime="application/octet-stream",
                            key=f"download_{f['bucket']}_{f['filename']}"
                        )
                    else:
                        st.error(dr.json().get("detail", "Download failed"))
            else:
                st.info("No files shared with you.")
        else:
            st.error("Failed to fetch shared files.")

    if st.sidebar.button("Logout"):
        logger.info("User logged out")
        st.session_state.token = None
        st.session_state.logged_in = False
        st.success("Logged out successfully")
        st.rerun()
    
    if st.session_state.logged_in and st.session_state.token:
        logger.debug(f"User session: logged_in={st.session_state.username}")
        st.sidebar.markdown(f"**Logged in as:** `{st.session_state.username}`")

if not st.session_state.logged_in or not st.session_state.token:
    logger.debug("User not logged in, showing auth page")
    show_auth_page()
else:
    logger.debug("User logged in, showing main menu")
    show_main_menu()
