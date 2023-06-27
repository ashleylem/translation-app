import io
import os
import openai
import docx
import cv2
import config
from cv2 import imdecode
import subprocess
from io import BytesIO
from flask import Flask, request, send_file, send_from_directory, render_template,  url_for, flash, redirect, jsonify, session, make_response
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches
import pytesseract
from PIL import Image
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, current_user, set_access_cookies, get_jwt_identity
import calendar
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, db, Translations
from utils import *
import uuid
import numpy as np


# pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

app = Flask(__name__, static_folder='static', static_url_path='')

app.config['SECRET_KEY'] = 'secret246'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my_app.db'

app.config["JWT_TOKEN_LOCATION"] = [
    "headers", "cookies", "json", "query_string"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_SECRET_KEY"] = "translator-project"
jwt = JWTManager(app)

db.init_app(app)
migrate = Migrate(app, db)


# Replace with your OpenAI API key
openai.api_key = config.api_key


@app.context_processor
def inject_user_logged_in():
    user_logged_in = 'access_token' in session
    return dict(user_logged_in=user_logged_in)


@app.context_processor
def inject_user():
    user_name = session.get('user_name')
    return dict(user_name=user_name)


@app.context_processor
def inject_user_id():
    user_id = session.get('user_id')
    return dict(user_id=user_id)


@app.route("/")
def index():
    return render_template('index.html')


ALLOWED_EXTENSIONS = {"pdf", "jpeg", "jpg", "png"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        id = str(uuid.uuid4())
        user = User.query.filter_by(email=email).first()

        if user:
            flash("User already exists")
            return redirect(url_for('login'))

        user = User(username=username, email=email,
                    password=hashed_password, name=name, id=id)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            access_token = create_access_token(identity=user.id)
            session['access_token'] = access_token
            session['user_name'] = user.name
            session['user_id'] = user.id
            if request.is_json:  # Respond with JSON when the request is a JSON request
                return jsonify(access_token=access_token), 200
            else:  # Redirect to the index page when the request is not a JSON request
                flash('Login successful.', 'success')
                return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    return render_template('login.html')


@app.route('/is_logged_in', methods=['GET'])
@jwt_required()
def is_logged_in():
    user_id = get_jwt_identity()
    if user_id:
        return {'logged_in': True}, 200
    else:
        return {'logged_in': False}, 200


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route("/profile")
def profile():
    return render_template('translate.html')

@app.route('/preview', methods=['POST'])
def preview_image():
    if 'file' not in request.files:
        print("No file uploaded")
        return "No file uploaded", 400

    file = request.files['file']
    filename= file.filename


    preview_name = preprocess_image(file, filename)

    return render_template('translate.html', filename=preview_name)

@app.route('/temp/<path:filename>')
def serve_image(filename):
    return send_from_directory('temp', filename)

@app.route('/cancel')
def cancel():
    os.remove('temp/preview.jpg')
    return redirect(url_for('profile'))

@app.route('/translate', methods=['POST'])
def translate():

    file_path= 'temp/preview.jpg'
    target_language = request.form.get('target_lang')
    source_language = request.form.get('source_lang')
    translator_name = request.form.get('translator_name')
    filename = request.form.get('filename')
    file_ext='.jpg'


    output_stream = image_to_docx(file_path, target_language, source_language, translator_name)

    output_stream = BytesIO(output_stream.getvalue())

    response = send_file(output_stream, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                         as_attachment=True, download_name=f'translated_{filename}.docx')

    if response:
        folder_name = 'translations'
        image_folder_name = "original_images"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        if not os.path.exists(image_folder_name):
            os.makedirs(image_folder_name)
        output_file_path = os.path.join(
            folder_name, f'translated_{filename}.docx')
        with open(output_file_path, 'wb') as f:
            f.write(output_stream.getbuffer())

        image_file_path = os.path.join(
            image_folder_name, f'{filename}{file_ext}')
        shutil.move(file_path, image_file_path)

        document = Translations(id=str(uuid.uuid4()), user_id=session.get(
            'user_id'), language=source_language, filename=f'translated_{filename}.docx', original_image=filename)
        db.session.add(document)
        db.session.commit()

    return response


@app.route('/translations', methods=['GET'])
def translations():
    translations = Translations.query.all()
    translations = list(
        map(lambda index: index.serialize(), translations)
    )
    response_body = jsonify(translations)
    return response_body


@app.route('/translations/<user_id>', methods=['GET'])
def translations_user(user_id):
    translations = Translations.query.filter_by(user_id=user_id).all()
    return render_template('translations.html', translations=translations)

@app.route('/original_images/<filename>')
def get_image(filename):
    return send_from_directory('original_images', filename)
    



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
