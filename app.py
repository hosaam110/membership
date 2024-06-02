from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import logging
import tempfile

app = Flask(__name__, static_url_path='', static_folder='root/pages')
CORS(app)  # Enable CORS for all routes

# Path to your JSON file
json_file_path = os.path.join(os.path.dirname(__file__), 'sunlit-realm-311015-2cbfedf98184.json')

# Define the scope
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Authenticate and initialize the gspread client
creds = Credentials.from_service_account_file(json_file_path, scopes=scope)
client = gspread.authorize(creds)

# Authenticate and initialize the Google Drive client
drive_service = build('drive', 'v3', credentials=creds)

# Use the spreadsheet ID to open the spreadsheet
spreadsheet_id = '1vigUVv4xMWdahTLh86GmBgswsXaPK_-3QdfCDfrBMvI'
sheet = client.open_by_key(spreadsheet_id).sheet1

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')

# Folder ID for "Identities" folder in Google Drive
folder_id = '1JmGVCBMAOEiYP9wyeeCaYkS-UULBplA2'

def upload_to_drive(file_path, filename, folder_id):
    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='application/pdf')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def setup_worksheet(sheet):
    headers = [
        'رقم العضوية المؤقت',
        'رقم الهوية',
        'هل انت طالب في إسطنبول',
        'الاسم الرباعي باللغة العربية',
        'الاسم الرباعي بالغة الإنجليزية',
        'تاريخ الميلاد',
        'الجنس',
        'رقم الهاتف التركي',
        'رقم الواتس اب',
        'موقع السكن',
        'البريد الالكتروني',
        'اسم الجامعة او المعهد (باللغة الإنجليزية)',
        'التخصص الجامعي باللغة الإنجليزية (اذا كنت طالب تحضيري الرجاء كتابة في خانة الجواب تحضيري)',
        'المرحلة الجامعية',
        'ارفاق الاورنجي بلقسي بصيغة PDF او صورة واضحة',
        'ارفاق الهوية بصيغة PDF او صورة واضحة (بالجهة الامامية)',
        'ارفاق الهوية بصيغة PDF او صورة واضحة (بالجهة الخلفية)',
        'هل تقر بأن البيانات أعلاه صحيحة'
    ]
    if not sheet.get_all_values():
        sheet.append_row(headers)

@app.route('/check_id', methods=['GET'])
def check_id():
    try:
        national_id = request.args.get('nationalId')
        records = sheet.col_values(2)  # Get all values in column B (رقم الهوية)
        if national_id in records:
            return jsonify({"message": "Membership exists"})
        return jsonify({"message": "Not found"})
    except Exception as e:
        logging.error(f"Error during ID check: {e}")
        return jsonify({"message": "Error during ID check"}), 500

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form.to_dict()
        files = request.files
        logging.debug(f"Received data: {data}")

        # Set up the worksheet with headers if empty
        setup_worksheet(sheet)

        national_id = data.get('nationalId')

        # Generate temporary membership number
        temp_membership_number = f"TMP-{national_id}"

        # Upload files to Google Drive with national ID and type as the filename
        uploaded_files = {}
        for key in files:
            file = files[key]
            filename = f"{national_id}_{key}.pdf"
            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                file.save(temp_file.name)
                temp_file_path = temp_file.name

            file_id = upload_to_drive(temp_file_path, filename, folder_id)
            uploaded_files[key] = filename
            os.remove(temp_file_path)  # Delete the temporary file after upload

        new_row = [
            temp_membership_number,
            national_id,
            data.get('isStudent'),
            data.get('fullNameAr'),
            data.get('fullNameEn'),
            data.get('birthDate'),
            data.get('gender'),
            data.get('phoneNumber'),
            data.get('whatsappNumber'),
            data.get('residenceLocation'),
            data.get('email'),
            data.get('universityName'),
            data.get('universityMajor'),
            data.get('universityLevel'),
            uploaded_files.get('orangeSlip'),
            uploaded_files.get('frontId'),
            uploaded_files.get('backId'),
            data.get('declaration')
        ]
        logging.debug(f"Appending row: {new_row}")
        sheet.append_row(new_row)

        return jsonify({"message": "Success", "temp_membership_number": temp_membership_number})
    except Exception as e:
        logging.error(f"Error during registration: {e}", exc_info=True)
        return jsonify({"message": "Error during registration"}), 500

@app.route('/<path:path>')
def serve_page(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(debug=True)
