from flask import Flask, render_template, request, jsonify, send_file
import os
from collections import defaultdict
from datetime import datetime
import json
import pandas as pd
from werkzeug.utils import secure_filename
import chardet
import folium
import geopy
from geopy.geocoders import Nominatim
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

app = Flask(__name__)
geolocator = Nominatim(user_agent="bounding_box_app")
#Excel Reporting
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def run_excel_qa(file_path):
    report_lines = []
    
    # File info
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_path)[1]
    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    last_modified = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')

    report_lines.append(f"File Name: {file_name}")
    report_lines.append(f"File Extension: {file_ext}")
    report_lines.append(f"File Size: {file_size_mb} MB")
    report_lines.append(f"Last Modified: {last_modified}\n")

    wb = load_workbook(file_path, data_only=True)

    for sheet in wb.worksheets:
        sheet_name = sheet.title
        is_hidden = sheet.sheet_state != 'visible'
        display_name = f"{sheet_name} (hidden)" if is_hidden else sheet_name
        report_lines.append(f"Sheet: {display_name}")

        df = pd.DataFrame(sheet.values)
        num_rows, num_cols = df.shape
        report_lines.append(f"  - Total Rows: {num_rows}")
        report_lines.append(f"  - Total Columns: {num_cols}")

        # Empty cells
        empty_cells = []
        for r in range(1, num_rows + 1):
            for c in range(1, num_cols + 1):
                value = sheet.cell(row=r, column=c).value
                if value in [None, "", " "]:
                    cell_name = f"{get_column_letter(c)}{r}"
                    empty_cells.append(cell_name)
        report_lines.append(f"  - Empty Cells: {', '.join(empty_cells) if empty_cells else 'None'}")

        # Hidden columns
        hidden_columns = []
        for col_cells in sheet.iter_cols():
            col_letter = get_column_letter(col_cells[0].column)
            if sheet.column_dimensions[col_letter].hidden:
                hidden_columns.append(col_letter)
        report_lines.append(f"  - Hidden Columns: {', '.join(hidden_columns) if hidden_columns else 'None'}")

        # Data quality
        quality_issues = []
        for col in df.columns:
            col_series = df[col].dropna()
            if col_series.empty:
                quality_issues.append(f"    - Column {get_column_letter(col + 1)} is completely empty")
            elif col_series.nunique() == 1 and col_series.iloc[0] in [None, "", " "]:
                quality_issues.append(f"    - Column {get_column_letter(col + 1)} has uniform missing value")
            elif col_series.apply(type).nunique() > 1:
                quality_issues.append(f"    - Column {get_column_letter(col + 1)} has mixed data types")
        if quality_issues:
            report_lines.append("  - Data Quality Issues:")
            report_lines.extend(quality_issues)
        else:
            report_lines.append("  - Data Quality Issues: None")
        report_lines.append("")

    return "\n".join(report_lines)

#Functions list
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
        "Hidden_Folders": {"Count": len(hidden_folders), "Names": hidden_folders},
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

#Function to add a geographic bounding box  
def create_bounding_box(lat, lon, delta=0.1):
    """Create a bounding box around a point."""
    return {
        "west": lon - delta,
        "east": lon + delta,
        "south": lat - delta,
        "north": lat + delta
    }

def generate_bounding_box(points):
    """Create a bounding box around multiple points."""
    lats = [point[0] for point in points]
    lons = [point[1] for point in points]
    return {
        "west": min(lons),
        "east": max(lons),
        "south": min(lats),
        "north": max(lats)
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    report = {}
    if request.method == 'POST':
        folder_path = request.form['folder_path']
        report = generate_folder_report(folder_path)
    return render_template('index.html', folder_report=report)

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

@app.route('/geobox', methods=['GET', 'POST'])
def geobox():
    bounding_box = None
    map_html = None

    if request.method == 'POST':
        location_input = request.form['coordinates']
        location = geolocator.geocode(location_input)

        if location:
            lat, lon = location.latitude, location.longitude
            bounding_box = create_bounding_box(lat, lon)

            # Create a map with the bounding box
            m = folium.Map(location=[lat, lon], zoom_start=10)
            folium.Rectangle(
                bounds=[[bounding_box['south'], bounding_box['west']],
                        [bounding_box['north'], bounding_box['east']]],
                color='blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)

            map_html = m._repr_html_()

    return render_template('index.html', bounding_box=bounding_box, map_html=map_html)

@app.route('/geobox_multiple', methods=['GET', 'POST'])
def geobox_multiple():
    bounding_box_multiple = None
    map_html_multiple = None

    if request.method == 'POST':
        coordinates_input = request.form['coordinates']  # Expecting a comma-separated list of lat,lon
        coordinates_list = [tuple(map(float, coord.split(','))) for coord in coordinates_input.split(';')]

        if coordinates_list:
            bounding_box_multiple = generate_bounding_box(coordinates_list)

            # Create a map with the bounding box
            m = folium.Map(location=[(bounding_box_multiple['north'] + bounding_box_multiple['south']) / 2, 
                                      (bounding_box_multiple['east'] + bounding_box_multiple['west']) / 2], zoom_start=10)
            folium.Rectangle(
                bounds=[[bounding_box_multiple['south'], bounding_box_multiple['west']],
                        [bounding_box_multiple['north'], bounding_box_multiple['east']]],
                color='blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)

            map_html_multiple = m._repr_html_()

    return render_template('index.html', bounding_box_multiple=bounding_box_multiple, map_html_multiple=map_html_multiple)

@app.route("/Excel_reporting", methods=["GET", "POST"])
def Excel_reporter():
    report = None
    if request.method == "POST":
        uploaded_file = request.files["excel_file"]
        if uploaded_file and uploaded_file.filename.endswith((".xlsx", ".xls")):
            filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(file_path)
            report = run_excel_qa(file_path)
    return render_template("index.html", excel_report=report)

app = Flask(__name__)

@app.route('/leave_balance', methods=['GET', 'POST'])
def leave_balance():
    result = None
    if request.method == 'POST':
        try:
            total_hours = float(request.form['total_hours'])
            daily_hours = float(request.form['daily_hours'])
            days_left = total_hours / daily_hours
            result = round(days_left, 2)
        except (ValueError, ZeroDivisionError):
            result = "Invalid input. Please enter valid numbers."

    return render_template('index.html', leave=result)

if __name__ == '__main__':
    app.run(debug=True)
