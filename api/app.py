from flask import Flask, render_template, request, jsonify, send_file
import os
from collections import defaultdict
import datetime
import json
import pandas as pd
from werkzeug.utils import secure_filename
import chardet

app = Flask(__name__)


def generate_folder_report(folder_path):
    file_count = 0
    total_size = 0
    file_types = defaultdict(list)
    empty_folders = []
    corrupt_files = []
    hidden_folders = []
    
    # Get folder name and path
    folder_name = os.path.basename(folder_path)
    folder_creation_time = os.path.getctime(folder_path)
    folder_last_modified_time = os.path.getmtime(folder_path)
    
    for dirpath, dirnames, filenames in os.walk(folder_path):
        # Check for hidden folders
        for dirname in dirnames:
            if dirname.startswith('.'):
                hidden_folders.append(dirname)
        
        if not filenames and not dirnames:
            empty_folders.append(dirpath)
        
        for filename in filenames:
            file_count += 1
            _, ext = os.path.splitext(filename)
            file_types[ext].append(f"{filename} ({dirpath})")  # Updated to include folder path
            
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
            
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
            except Exception:
                corrupt_files.append(file_path)
    
    # Convert sizes
    size_kb = total_size / 1024
    size_mb = size_kb / 1024
    size_gb = size_mb / 1024
    
    report = {
        "Folder Name": folder_name,
        "Hidden Folders": {"Count": len(hidden_folders), "Names": hidden_folders},
        "Creation Date": datetime.datetime.fromtimestamp(folder_creation_time).strftime('%Y-%m-%d %H:%M:%S'),
        "Last Modified Date": datetime.datetime.fromtimestamp(folder_last_modified_time).strftime('%Y-%m-%d %H:%M:%S'),
        "Total Files": file_count,
        "Total Size (bytes)": total_size,
        "Total Size (KB)": size_kb,
        "Total Size (MB)": size_mb,
        "Total Size (GB)": size_gb,
        "File Types": {ext: files for ext, files in file_types.items()},
        "Empty Folders": empty_folders,
        "Corrupt Files": corrupt_files,
        "Folder Structure Issues": []
    }
    
    if empty_folders or corrupt_files:
        report["Folder Structure Issues"].append("Issues found:")
        if empty_folders:
            report["Folder Structure Issues"].append(f"Empty folders: {len(empty_folders)}")
        if corrupt_files:
            report["Folder Structure Issues"].append(f"Corrupt files: {len(corrupt_files)}")
    
    return report

# Function to convert JSON to CSV
def json_to_csv(json_file):
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    df = pd.json_normalize(data)
    csv_file_path = os.path.splitext(json_file)[0] + '.csv'
    df.to_csv(csv_file_path, index=False)
    return f"CSV file saved at: {csv_file_path}"

# Function to detect file encoding
def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']
        return encoding, confidence

@app.route('/', methods=['GET', 'POST'])
def index():
    report = {}
    if request.method == 'POST':
        folder_path = request.form['folder_path']
        report = generate_folder_report(folder_path)
    return render_template('index.html', report=report)

@app.route('/count', methods=['POST'])
def count():
    text = request.form.get('text', '')
    word_count = len(text.split()) if text else 0
    char_count = len(text)
    return jsonify({'words': word_count, 'characters': char_count})

@app.route('/convert', methods=['GET', 'POST'])
def convert():
    if request.method == 'POST':
        json_file_path = request.form['file_path']
        if 'convert' in request.form:
            message = json_to_csv(json_file_path)
            return render_template('index.html', message=message)
        elif 'decode' in request.form:
            encoding, confidence = detect_encoding(json_file_path)
            return render_template('index.html', encoding=encoding, confidence=confidence)
    return render_template('index.html')


def paths_generator(folder_path):
    folder_path = request.form['folder_path']
    data = []
    # Check if the folder exists
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        for root, dirs, files in os.walk(folder_path):
            for dir_name in dirs:
                folder_name = dir_name
                folder_full_path = os.path.join(root, dir_name)
                data.append({
                    'Folder_Name': folder_name,
                    'File_Name': '',
                    'Folder_Path': folder_full_path,
                    'File_Path': '',
                    'File_Extension': ''
                })
            for file_name in files:
                file_full_path = os.path.join(root, file_name)
                file_extension = os.path.splitext(file_name)[1]
                data.append({
                    'Folder_Name': '',
                    'File_Name': file_name,
                    'Folder_Path': root,
                    'File_Path': file_full_path,
                    'File_Extension': file_extension
                })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Save DataFrame to Excel
        excel_path = os.path.join(folder_path, "Paths_Generated.xlsx")  # Corrected file name
        df.to_excel(excel_path, index=False)  # Save DataFrame to Excel
        return f"Excel file saved to {excel_path}"
    


    return "Invalid folder path!"

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        folder_path = request.form['folder_path']
        if 'generate' in request.form:
            alart_message = paths_generator(folder_path)
            return render_template('index.html', alart_message=alart_message)

if __name__ == '__main__':
    app.run(debug=True)
