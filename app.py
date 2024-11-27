import openai
import datetime
import os
from flask import (
    Flask, 
    render_template, 
    request,
    session,
    abort,
    flash,
    redirect,
    url_for,
)    

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import bcrypt

from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # DB_PATH = "blog_app.db"

    def get_db_connection():        
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
        )

    # Insert a new blog entry into the database
    def insert_entry(title, content, email):        
        try:            
            connection = get_db_connection()
            cursor = connection.cursor()            
            
            # Create a table in Postgresql
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    date TIMESTAMP DEFAULT NOW(),
                    email TEXT
                )
                """)            
            
            # SQL query to insert data for Postgresql
            sql_insert_query = """
            INSERT INTO entries (title, content, email)
            VALUES (%s, %s, %s)
            """        
            entry_data = (title, content, email)

            # Execute the query
            cursor.execute(sql_insert_query, entry_data)
            connection.commit()
            print("Entry inserted successfully.")
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)

        finally:
            connection.close()
            print("Postgresql connection is closed")
        
    # Fetch all blog entries from the database
    def fetch_entries():
        entries = []        
        try:            
            connection = get_db_connection()
            cursor = connection.cursor()        

            # Define the query to retrieve data
            query = "SELECT title, content, email, date, id FROM entries ORDER BY date DESC"
            cursor.execute(query)
            
            # Fetch all rows from the result
            entries = cursor.fetchall()
            return entries
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)
            return []

        finally:
            connection.close()
            print("Postgresql connection is closed")        

    # Insert a new user into the users table
    def insert_user(email, password):        
        try:            
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            connection = get_db_connection()
            cursor = connection.cursor()            
            
            # Create table in Postgresql
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL
                )
            """)

            # SQL query to insert data
            sql_insert_query = """
            INSERT INTO users (email, password)
            VALUES (%s, %s)
            """
            user_data = (email, hashed_password.decode('utf-8'))

            # Execute the query
            cursor.execute(sql_insert_query, user_data)
            connection.commit()
            print("User inserted successfully.")
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)

        finally:
            connection.close()
            print("Postgresql connection is closed")

    # Check if an email is already registered
    def is_email_registered(email):        
        try:            
            connection = get_db_connection()
            cursor = connection.cursor()
                        
            # Query to check if the email exists in the users table
            query = "SELECT COUNT(*) FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            
            # Fetch the result
            result = cursor.fetchone()
            return result[0] > 0  # True if email exists, False otherwise
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)
            return False

        finally:
            # Close the cursor and connection if they exist
            connection.close()
                
    # Validate user login credential
    def validate_user(email, password):        
        try:            
            connection = get_db_connection()
            cursor = connection.cursor()       
                        
            # Query to check if the email and password match
            query = "SELECT password FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            
            # Fetch the stored password if the email exists
            result = cursor.fetchone()
            if result:
                stored_hashed_password = result[0]
                return bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8'))
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)
            return False

        finally:
            connection.close()

    # Display a detailed post
    def get_post_by_id(post_id):        
        try:            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Define the query to fetch the post by ID
            query = "SELECT title, content, email, date FROM entries WHERE id = %s"
            cursor.execute(query, (post_id,))
            
            # Fetch the result
            post = cursor.fetchone()
            return post
                
        except Exception as e:
            print("Error while interacting with PostgreSQL:", e)
            return None

        finally:
            connection.close()
                
    def generate_content_with_openai(title):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a technical blog writer."},
                    {"role": "user", "content": f"Write a 200 word blog post based on the title: '{title}'"}
                ],
                max_tokens=800  # Adjust max tokens as needed
            )
            content = response.choices[0].message['content']
            return content
        except Exception as e:
            print(f"Error generating content: {e}")
            return "Error generating content. Please try again."

    # Sign-up route
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")    
            
            if is_email_registered(email):
                flash("Email is already registered. Please log in.", "warning")
                return redirect(url_for("login"))
                
            # Proceed with registration if email is not registered
            
            # Insert user into Postgresql
            insert_user(email, password)
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("signup.html")

    # Login route
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            
            if validate_user(email,password):
                session["email"] = email
                flash("Login successfull", "success")
                return redirect(url_for("home"))
            else:
                flash("Invalid email or password", "danger")
                return redirect(url_for("login"))
            
        return render_template("login.html")

    # Home route
    @app.route("/", methods=["GET", "POST"])
    def home():
        if "email" not in session:
            return redirect(url_for("signup"))
        
        user_email = session["email"]
        title = ""
        content = ""
        
        if request.method == "POST":    
            # Check if the generate content button was pressed       
            if request.form.get("generate_content") == "true":
                    title = request.form.get("title")
                    content = generate_content_with_openai(title)
                    entries = fetch_entries()
                    return render_template("index.html", entries=entries, user_email=user_email, content=content, title=title)        
            else:
                # Otherwise, treat it as a submission
                title = request.form.get("title")
                content = request.form.get("content")
                # Insert entry into Postgresql
                insert_entry(title, content, user_email)
                flash("BLog entry submitted successfully", "success")
                
        # Fetch all entries for display
        entries = fetch_entries()
        return render_template("index.html", entries=entries, user_email=user_email)        

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("email", None)
        flash("You have been logged out", "info")
        return redirect(url_for("login"))

    @app.route("/post/<int:post_id>")
    def post(post_id):
        if "email" not in session:
            return redirect(url_for("signup"))

        user_email = session["email"]
        
        # Fetch the detailed post using the post ID    
        post = get_post_by_id(post_id)
        
        if post:
            # Render the post details in a template
            return render_template("post_detail.html", title=post[0], content=post[1], email=post[2], date=post[3], user_email=user_email)
        else:
            flash("Post not found.", "warning")
            return redirect(url_for("home"))

    if __name__ == "__main__":    
        app.run(debug=True)
    
    return app

    