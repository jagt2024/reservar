import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import toml
import json
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

def cargar_configuracion():
    try:
        config = toml.load("./.streamlit/config.toml")
        return config["clave_google"]["clave_email"]
    except FileNotFoundError:
        st.error("Configuration file not found.")
        return None
    except KeyError:
        st.error("Key not found in configuration file.")
        return None

def load_credentials_from_toml():
    # Load credentials from secrets.toml file
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    # Establish connection with Google Sheets
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def get_all_data(client):
    """Get all data saved in the sheet"""
    try:
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('ordenes')
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        st.error(f"Error retrieving data: {str(e)}")
        return []

def update_google_sheet(client, email, status="Sent"):
    """Update status and shipping date in Google Sheet for the given email"""
    try:
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('ordenes')
        
        # Find the row with the matching email
        cell = worksheet.find(email)
        if cell:
            row = cell.row
            
            # Get column indices for Email Status and Shipping Date
            headers = worksheet.row_values(1)
            email_status_col = headers.index("Email Status") + 1 if "Email Status" in headers else None
            shipping_date_col = headers.index("Shipping Date") + 1 if "Shipping Date" in headers else None
            
            # Current date in the appropriate format
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Update the cells if columns exist
            if email_status_col:
                worksheet.update_cell(row, email_status_col, status)
            if shipping_date_col:
                worksheet.update_cell(row, shipping_date_col, current_date)
                
            return True
        else:
            st.warning(f"Email {email} not found in Google Sheets")
            return False
    except Exception as e:
        st.error(f"Error updating Google Sheets: {str(e)}")
        return False

def mostrar_correo_masivo():
    st.title("📧 Mass Email Sending System")

    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Load Data", "Configure Email", "Send"])

    # TAB 1: Load Data
    with tab1:
        st.header("Upload Excel file with recipients")
        
        st.info("The Excel file must contain the columns: First Name, Last Name, Email, Phone Number, Estate, Actions")
        
        # Widget to upload file
        uploaded_file = st.file_uploader("Select an Excel file", type=["xlsx", "xls"], key="email_file_uploader")
        
        if uploaded_file is not None:
            try:
                # Load data from Excel file
                df = pd.read_excel(uploaded_file)
                
                # Save a copy of the original file to update later
                if 'uploaded_file_name' not in st.session_state:
                    st.session_state['uploaded_file_name'] = uploaded_file.name
                
                # Save file content to update it later
                if 'original_file_content' not in st.session_state:
                    # Reset file pointer to read it again
                    uploaded_file.seek(0)
                    st.session_state['original_file_content'] = uploaded_file.read()
                
                # Verify required columns
                required_columns = ["First Name", "Last Name", "Email", "Phone Number", "Estate", "Actions"]
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                # Ensure necessary columns exist for updating
                if "Email Status" not in df.columns:
                    df["Email Status"] = ""
                
                if "Shipping Date" not in df.columns:
                    df["Shipping Date"] = None
                
                if missing_columns:
                    st.error(f"The file does not contain the following required columns: {', '.join(missing_columns)}")
                else:
                    # Show dataframe
                    st.success("File successfully loaded!")
                    st.write("Data preview:")
                    st.dataframe(df)
                    
                    # Save in session state
                    st.session_state['df'] = df
                    
                    # Show basic statistics
                    st.subheader("Summary of loaded data")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total recipients", len(df))
                    with col2:
                        st.metric("Unique states", len(df["Estate"].unique()))
                    with col3:
                        emails_sin_valor = df["Email"].isna().sum()
                        st.metric("Empty emails", emails_sin_valor)
            
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")

    # TAB 2: Email Configuration
    with tab2:
        st.header("Configure email")
        
        # Check if data is loaded
        if 'df' not in st.session_state:
            st.warning("You must first load an Excel file in the 'Load Data' tab")
        else:
            # Sender configuration
            st.subheader("Sender configuration")
            
            # Checkbox to choose between using secrets or entering credentials manually
            use_secrets = st.checkbox("Use credentials", value=True, key="email_use_secrets")
            
            if use_secrets:
                st.info("Credentials configured in the secrets.toml file will be used")
                try:
                    # Show user saved in secrets to confirm
                    smtp_user = st.secrets['emails']['smtp_user']
                    st.success(f"Configured user: {smtp_user}")
                    st.session_state['use_secrets'] = True
                except Exception as e:
                    st.error(f"Could not load credentials from secrets.toml: {str(e)}")
                    st.session_state['use_secrets'] = False
                    use_secrets = False
            
            if not use_secrets:
                col1, col2 = st.columns(2)
                with col1:
                    smtp_user = "" #st.secrets['emails']['smtp_user']
                    sender_email = smtp_user #st.text_input("Sender email")
                    st.session_state['sender_email'] = sender_email
                with col2:
                    clave_email = cargar_configuracion()

                    if clave_email is not None:
                        clave_email_codificada = clave_email
                    else:
                        # Handle case when key is None
                        st.error("Could not obtain email key for connection")

                    sender_password = clave_email_codificada
                    st.session_state['sender_password'] = sender_password
        
                    st.session_state['use_secrets'] = True #False
            
            # SMTP server configuration
            st.session_state['smtp_server'] = "smtp.gmail.com"
            st.session_state['smtp_port'] = 587
            
            # Note about secure credentials
            st.info("📌 For Gmail, you may need an app password instead of your regular password. [More information](https://support.google.com/accounts/answer/185833)")
            
            # Recipient filtering
            st.subheader("Filter recipients")
            
            # Verify that "Estate" column exists and is accessible
            if isinstance(st.session_state['df'], pd.DataFrame) and "Estate" in st.session_state['df'].columns:
                # Filter options
                filter_options = st.multiselect("Filter by state", options=st.session_state['df']["Estate"].unique(), key="email_filter_options")
                
                # Apply filters if selected
                filtered_df = st.session_state['df']
                if filter_options:
                    filtered_df = filtered_df[filtered_df["Estate"].isin(filter_options)]
                
                # Show filtered recipients
                st.write(f"Selected recipients: {len(filtered_df)}")
                st.dataframe(filtered_df[["First Name", "Last Name", "Email", "Estate"]])
                
                # Save in session state
                st.session_state['filtered_df'] = filtered_df
            else:
                st.error("The DataFrame does not have an 'Estate' column or is not a valid DataFrame")
            
            # Message configuration
            st.subheader("Message configuration")

            sub_remitente = st.text_input("Enter sender email", key="sub_remite")
            email_subject = st.text_input("Email subject", key="email_subject_input")
            
            st.markdown("**Message content:**")
            st.markdown("You can use the following variables to personalize the message:")
            st.markdown("- `{first_name}`: Recipient's first name")
            st.markdown("- `{last_name}`: Recipient's last name")
            st.markdown("- `{email}`: Recipient's email")
            st.markdown("- `{estate}`: Recipient's state/province")
            st.markdown("- `{phone}`: Recipient's phone number")
            
            email_content = st.text_area(f"Email content", height=200,
                                          value=f"App Sender: {sub_remitente}\n\n""Dear {first_name} {last_name},\n\nI hope this message finds you well.\n\n[Your message here]\n\nBest regards,\n[Your name]\n\n"f"{sub_remitente}",key="email_content_input"
                                          )
            
            # Email preview
            if st.button("Generate preview", key="email_preview_button"):
                if isinstance(st.session_state.get('filtered_df'), pd.DataFrame) and len(st.session_state['filtered_df']) > 0:
                    preview_row = st.session_state['filtered_df'].iloc[0]
                    try:
                        preview_content = email_content.format(
                            first_name=preview_row.get("First Name", ""),
                            last_name=preview_row.get("Last Name", ""),
                            email=preview_row.get("Email", ""),
                            estate=preview_row.get("Estate", ""),
                            phone=preview_row.get("Phone Number", "")
                        )
                        
                        st.subheader("Email preview")
                        st.markdown(f"**To:** {preview_row.get('Email', '')}")
                        st.markdown(f"**Subject:** {email_subject}")
                        st.markdown("**Content:**")
                        st.markdown(preview_content)
                        
                        # Save in session state
                        st.session_state['email_subject'] = email_subject
                        st.session_state['email_content'] = email_content
                    except Exception as e:
                        st.error(f"Error generating preview: {str(e)}")
                else:
                    st.warning("No recipients selected to generate a preview")

    # TAB 3: Sending emails
    with tab3:
        st.header("Send emails")
        
        # Check if there's data and email configuration
        if not isinstance(st.session_state.get('filtered_df'), pd.DataFrame):
            st.warning("You must first configure recipients in the 'Configure Email' tab")
        elif 'email_subject' not in st.session_state:
            st.warning("You must first configure the email content in the 'Configure Email' tab")
        else:
            # Show summary before sending
            st.subheader("Sending summary")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Total recipients:** {len(st.session_state['filtered_df'])}")
                st.markdown(f"**Subject:** {st.session_state['email_subject']}")
            with col2:
                if st.session_state.get('use_secrets', False):
                    st.markdown(f"**Sender Domain:** {st.secrets['emails']['smtp_user']}")
                    st.markdown(f"**Sender App:** {sub_remitente}")
                else:
                    st.markdown(f"**Sender Domain:** {st.session_state.get('sender_email', 'Not configured')}")
                    st.markdown(f"**Sender App:** {sub_remitente}")
                st.markdown(f"**SMTP Server:** {st.session_state.get('smtp_server', 'Not configured')}")
            
            # Function to send emails
            def send_emails(progress_bar, status_text):
                if not isinstance(st.session_state.get('filtered_df'), pd.DataFrame):
                    return 0, 0, [], []
                    
                df = st.session_state['filtered_df']
                total_emails = len(df)
                success_count = 0
                error_count = 0
                error_list = []
                success_list = []
                
                # List to store successfully sent emails to update Excel and Google Sheets later
                successful_sends = []
                
                try:
                    # Load credentials for Google Sheets
                    creds = load_credentials_from_toml()
                    if creds:
                        gs_client = get_google_sheets_connection(creds)
                    else:
                        gs_client = None
                        status_text.warning("Could not load credentials for Google Sheets")
                    
                    # Determine which credentials to use for SMTP
                    if st.session_state.get('use_secrets', False):
                        try:
                            # Use credentials from secrets.toml
                            smtp_user = st.secrets['emails']['smtp_user']
                            smtp_password = st.secrets['emails']['smtp_password']
                        except Exception as e:
                            return 0, total_emails, [f"Error obtaining credentials from secrets: {str(e)}"], []
                    else:
                        # Use manually entered credentials
                        smtp_user = st.session_state.get('sender_email')
                        smtp_password = st.session_state.get('sender_password')
                        
                        if not smtp_user or not smtp_password:
                            return 0, total_emails, ["Error: Email or password not configured"], []
                    
                    # Get server configuration
                    smtp_server = st.session_state.get('smtp_server', 'smtp.gmail.com')
                    smtp_port = int(st.session_state.get('smtp_port', 587))
                    
                    # Show debug information
                    status_text.text(f"Connecting to {smtp_server}:{smtp_port} with user {smtp_user}...")
                    
                    # Configure SMTP server
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.ehlo()  # Can help with connection
                    server.starttls()
                    server.ehlo()  # Necessary after STARTTLS
                    
                    # Try login
                    status_text.text("Attempting authentication...")
                    server.login(smtp_user, smtp_password)
                    status_text.text("Authentication successful. Starting email sending...")
                    
                    # Current date for Shipping Date field
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    
                    # Send emails one by one
                    for i, (index, row) in enumerate(df.iterrows()):
                        try:
                            # Verify that email is valid
                            if pd.isna(row['Email']) or not isinstance(row['Email'], str) or '@' not in row['Email']:
                                raise ValueError("Invalid email address")
                                
                            # Create personalized message
                            msg = MIMEMultipart()
                            msg['From'] = smtp_user
                            msg['To'] = row['Email']
                            msg['Subject'] = st.session_state['email_subject']
                            
                            # Personalize content with safe handling of missing values
                            try:
                                personalized_content = st.session_state['email_content'].format(
                                    first_name=row.get("First Name", ""),
                                    last_name=row.get("Last Name", ""),
                                    email=row.get("Email", ""),
                                    estate=row.get("Estate", ""),
                                    phone=row.get("Phone Number", "")
                                )
                            except Exception as format_error:
                                # If there's an error in the format, use generic content
                                personalized_content = f"Dear recipient,\n\n{st.session_state['email_content']}"
                            
                            msg.attach(MIMEText(personalized_content, 'plain'))
                            
                            # Send email
                            server.send_message(msg)
                            success_count += 1
                            
                            # Save the email and its index to update Excel and Google Sheets later
                            successful_sends.append({
                                'index': index,
                                'email': row['Email']
                            })
                            
                            # Update Google Sheet for this email
                            if gs_client:
                                update_status = update_google_sheet(gs_client, row['Email'])
                                if update_status:
                                    success_list.append(f"Email sent and Google Sheets updated: {row['Email']}")
                                else:
                                    success_list.append(f"Email sent but Google Sheets not updated: {row['Email']}")
                            else:
                                success_list.append(f"Email sent (without Google Sheets update): {row['Email']}")
                            
                            # Update progress bar
                            progress_bar.progress((i + 1) / total_emails)
                            status_text.text(f"Processing {i+1}/{total_emails}: Sent to {row['Email']}")
                            
                            # Small pause to avoid sending limitations
                            time.sleep(0.5)
                            
                        except Exception as e:
                            error_count += 1
                            error_list.append(f"{row.get('Email', 'Unknown email')}: {str(e)}")
                            status_text.text(f"Error sending to {row.get('Email', 'Unknown email')}: {str(e)}")
                            progress_bar.progress((i + 1) / total_emails)
                            time.sleep(0.5)
                    
                    # Close connection
                    server.quit()
                    
                    # Update original DataFrame with statuses
                    if 'df' in st.session_state and isinstance(st.session_state['df'], pd.DataFrame):
                        for send_info in successful_sends:
                            idx = send_info['index']
                            # Update status and sending date
                            st.session_state['df'].at[idx, 'Email Status'] = 'Sent'
                            st.session_state['df'].at[idx, 'Shipping Date'] = current_date
                        
                        # Save changes to original Excel if it exists
                        if 'original_file_content' in st.session_state and 'uploaded_file_name' in st.session_state:
                            # Create a temporary file with updated Excel
                            updated_excel = f"updated_{st.session_state['uploaded_file_name']}"
                            st.session_state['df'].to_excel(updated_excel, index=False)
                            
                            # Allow user to download updated file
                            with open(updated_excel, 'rb') as f:
                                st.session_state['updated_excel_data'] = f.read()
                                st.session_state['updated_excel_name'] = updated_excel
                    
                    return success_count, error_count, error_list, success_list
                    
                except Exception as e:
                    return 0, total_emails, [f"Connection error: {str(e)}"], []
            
            # Button to test SMTP connection
            if st.button("Test SMTP connection", key="email_test_connection"):
                with st.spinner("Testing connection to SMTP server..."):
                    try:
                        # Determine which credentials to use
                        if st.session_state.get('use_secrets', False):
                            smtp_user = st.secrets['emails']['smtp_user']
                            smtp_password = st.secrets['emails']['smtp_password']
                        else:
                            smtp_user = st.session_state.get('sender_email')
                            smtp_password = st.session_state.get('sender_password')
                        
                        # Get server configuration
                        smtp_server = st.session_state.get('smtp_server', 'smtp.gmail.com')
                        smtp_port = int(st.session_state.get('smtp_port', 587))
                        
                        # Try connection
                        server = smtplib.SMTP(smtp_server, smtp_port)
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(smtp_user, smtp_password)
                        server.quit()
                        
                        st.success(f"✅ Successful connection to {smtp_server} with user {smtp_user}")
                    except Exception as e:
                        st.error(f"❌ Connection error: {str(e)}")
                        st.warning("If you're using Gmail, make sure to use an 'App Password' instead of your regular password.")
            
            # Test connection to Google Sheets
            if st.button("Test Google Sheets connection", key="gs_test_connection"):
                with st.spinner("Testing connection to Google Sheets..."):
                    try:
                        creds = load_credentials_from_toml()
                        if creds:
                            client = get_google_sheets_connection(creds)
                            if client:
                                # Try to access the sheet
                                all_data = get_all_data(client)
                                if isinstance(all_data, list):
                                    st.success(f"✅ Successful connection to Google Sheets. {len(all_data)} records found.")
                                else:
                                    st.warning("Connection was successful but data could not be retrieved.")
                            else:
                                st.error("Error connecting to Google Sheets.")
                        else:
                            st.error("Could not load credentials for Google Sheets.")
                    except Exception as e:
                        st.error(f"❌ Google Sheets connection error: {str(e)}")
            
            # Button to start sending
            if st.button("Start sending emails", key="email_send_button"):
                if isinstance(st.session_state.get('filtered_df'), pd.DataFrame) and len(st.session_state['filtered_df']) > 0:
                    with st.spinner("Sending emails..."):
                        # Create progress elements
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Execute sending
                        success_count, error_count, error_list, success_list = send_emails(progress_bar, status_text)
                        
                        # Show results
                        if success_count > 0:
                            st.success(f"✅ {success_count} emails sent successfully")
                            
                            # Offer download of updated Excel
                            if 'updated_excel_data' in st.session_state and 'updated_excel_name' in st.session_state:
                                st.download_button(
                                    label="Download updated Excel",
                                    data=st.session_state['updated_excel_data'],
                                    file_name=st.session_state['updated_excel_name'],
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            
                            # Show success details
                            if success_list:
                                with st.expander("View successful send details"):
                                    for success in success_list:
                                        st.success(success)
                        
                        if error_count > 0:
                            st.error(f"❌ {error_count} emails could not be sent")
                            with st.expander("View error details"):
                                for error in error_list:
                                    st.error(error)
                else:
                    st.warning("No recipients selected to send emails")

#if __name__ == "__main__":
#    mostrar_correo_masivo()