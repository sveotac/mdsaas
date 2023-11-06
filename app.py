import os
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from summarizer.summarizer import (
    generate_summary,
) 
from config.config import Config
from api.doc_api import (_getAllSummaries, _saveDocuments)
from models import db, Document, User
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from blueprints.auth import auth_bp
from blueprints.documents import document_bp
from flask_login import LoginManager, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField

class LoginForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    submit = SubmitField('Submit')



ALLOWED_EXTENSIONS = ('txt', 'pdf')
UPLOAD_FOLDER = 'upload'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.register_blueprint(auth_bp)
app.register_blueprint(document_bp)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id)) 
    if user:
        return user
    else:
        return None

def app_factory(config_name='test'):
    app.config.from_object(Config)

    with app.app_context():
        db.init_app(app)
        db.create_all()

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route("/")
    def homepage():
        return render_template("auth/login.html")
    
    @app.route("/login")
    def loginPage():
        return render_template("auth/login.html")
    
    @app.route("/register")
    def registerPage():
        return render_template("auth/register.html")
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("main/dashboard.html")


    @app.route('/submit-document', methods=["POST"])
    def submit_document():
        if 'files[]' not in request.files:
                return jsonify({"error": "No files uploaded"}), 400
        uploaded_files = request.files.getlist('files[]')
        document_ids = []

        user_id = session.get("user_id")
        user = current_user
        if not user.is_authenticated:
            return jsonify({"error": "User not authenticated" }), 401
        
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                if file.filename.endswith('.pdf'):
                    pdf_reader = PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()

                    document = Document(user_id=user_id, content=text)
                else:
                    document = Document(user_id=user_id, content=file.read().decode('utf-8'))

                db.session.add(document)
                db.session.commit()
                document_ids.append(document.document_id)

        if document_ids:
            return jsonify({"document_ids": document_ids, "message": "Documents uploaded successfully"})

        return jsonify({"error": "No valid documents uploaded"}), 400

    
    ## ---------------------------------------------------------------------------- ##
    ## Logic for retrieveing the summary
    ## ---------------------------------------------------------------------------- ##
    @app.route('/retrieve-summary', methods=['GET'])
    def retrieve_summary():
        document_ids = request.args.getlist('document_ids')
        summaries = _getAllSummaries(document_ids)

    ## ---------------------------------------------------------------------------- ##
    ## Summarization endpoint TODO: needs to take more @params (module of summarization)
    ## ---------------------------------------------------------------------------- ##
    @app.route("/summarize", methods=["POST"])
    def summarize_text():
        try:
            data = request.get_json()
            if "document_ids" in data:
                document_ids = data["document_ids"]
                documents = [Document.query.get(id).content for id in document_ids]

                # Concatenate all documents into a single text
                combined_text = "\n".join(documents)

                # Generate a summary based on the combined text
                summary = generate_summary(combined_text)

                return jsonify({"summary": summary})
            else:
                return jsonify({"error": "No document IDs provided"}), 400

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        


    @app.route("/getDocument", methods=["GET"])
    def getDocument():
        document = Document.query.get("6")
        if document:
            content = document.content
            return render_template("document.html", content=content)
        else:
            return jsonify({'error': 'Document not found'}), 404
        
    # @app.route('/login', methods=['GET', 'POST'])
    # def login():
    #     if current_user.is_authenticated:
    #         return redirect(url_for('index'))
    #     form = LoginForm()
    #     if form.validate_on_submit():
    #         user = User.query.filter_by(username=form.username.data).first()
    #         if user is None or not user.check_password(form.password.data):
    #             flash('Invalid username or password')
    #             return redirect(url_for('/auth/login'))
    #         login_user(user, remember=form.remember_me.data)
    #         return redirect(url_for('index'))
    #     return render_template('auth/login.html', title='Sign In', form=form)
        
    return app, db