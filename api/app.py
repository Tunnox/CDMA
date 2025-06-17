from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import psycopg2

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your secret key

# Configure your PostgreSQL database connection here
connection = psycopg2.connect(dbname='AGT', user='postgres', password='pgsqtk116chuk95', host='chukspace.ctiuisa62ks5.eu-north-1.rds.amazonaws.com', port='5432')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keyword = request.form['keyword']
    cursor = connection.cursor()
    
    # SQL query to search for data in DATA_RECORDS table
    sql_query = f"""
        SELECT * FROM "public"."AGT_CHILDREN_DATA_RECORDS" 
        WHERE "first_name" ILIKE %s 
           OR "last_name" ILIKE %s 
           OR "age"::TEXT ILIKE %s 
           OR "gender" ILIKE %s
           OR "contact_number"::TEXT ILIKE %s
           OR "age_group" ILIKE %s
           OR "consent" ILIKE %s
           OR "birthday" ILIKE %s
    """
    
    # Execute the query with wildcard search
    cursor.execute(sql_query, [f'%{keyword}%'] * 8)
    
    results = cursor.fetchall()
    
    # Close cursor after fetching results
    cursor.close()
    
    return render_template('index.html', results=results)

@app.route('/update', methods=['POST'])
def update():
    data = request.form
    cursor = connection.cursor()
    
    # SQL query to update the record
    sql_update = """
        UPDATE "public"."AGT_CHILDREN_DATA_RECORDS"
        SET "first_name" = %s, "last_name" = %s, "age" = %s, "gender" = %s, 
            "contact_number" = %s, "age_group" = %s, "consent" = %s, "birthday" = %s
        WHERE "first_name" = %s
    """
    
    # Execute the update query
    cursor.execute(sql_update, (
        data['first_name'], data['last_name'], data['age'], data['gender'],
        data['contact_number'], data['age_group'], data['consent'], data['birthday'],
        data['first_name']
    ))
    
    connection.commit()  # Commit the changes
    cursor.close()
    flash('Record updated successfully!')
    return redirect(url_for('index'))

@app.route('/insert', methods=['GET','POST'])
def insert():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        age = request.form['age']
        gender = request.form['gender']
        contact_number = request.form['contact_number']
        age_group = request.form['age_group']
        consent = request.form['consent']
        birthday = request.form['birthday']

        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO "public"."AGT_CHILDREN_DATA_RECORDS" ("first_name", "last_name", "age", "gender", "contact_number", "age_group", "consent", "birthday")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (first_name, last_name, age, gender, contact_number, age_group, consent, birthday))
        connection.commit()  # Don't forget to commit the transaction!
        cursor.close()
    
    flash('Record inserted successfully!')
    return redirect(url_for('index'))

@app.route('/insert_attendance', methods=['GET', 'POST'])
def insert_attendance():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        date = request.form['date']

        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO "public"."attendance_manager" ("first_name", "last_name", "date")
            VALUES (%s, %s, %s);
        """, (first_name, last_name, date))
        connection.commit()  # Don't forget to commit the transaction!
        cursor.close()
    
    flash('Attendance record inserted successfully!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
