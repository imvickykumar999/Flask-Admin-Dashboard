import os
from datetime import datetime, timezone
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    redirect, 
    url_for
)
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from markupsafe import Markup
from flask_wtf.file import FileAllowed
from flask_admin.form import FileUploadField

class ScreenshotView(ModelView):
    # Directory for file uploads
    form_overrides = {
        'filename': FileUploadField
    }
    form_args = {
        'filename': {
            'label': 'Upload File',
            'validators': [
                FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
            ],
            'base_path': os.path.join(os.getcwd(), 'media/screenshots'),
            'allow_overwrite': False,
        }
    }

    # Show columns in admin list view
    column_list = ('filename', 'upload_time')

    # Customize image preview in admin list view
    column_formatters = {
        'filename': lambda v, c, m, p: Markup(
            f'<img src="/media/screenshots/{m.filename}" style="width:100px; height:auto;" />'
        )
    }

    # Override on_model_delete to delete file from folder
    def on_model_delete(self, model):
        # Get the file path
        file_path = os.path.join(os.getcwd(), 'media/screenshots', model.filename)

        # Check if the file exists and delete it
        if os.path.exists(file_path):
            os.remove(file_path)

        # Call the parent method to proceed with model deletion
        super(ScreenshotView, self).on_model_delete(model)
        
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # Automatically generates a secure random key

# Configure Upload Folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'media/screenshots')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Configure Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///files.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define File Model
class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Screenshot {self.filename}>"

# Initialize Flask-Admin
admin = Admin(app, name='Admin Dashboard', template_mode='bootstrap3')

# Add the custom ScreenshotView to the admin interface
admin.add_view(ScreenshotView(Screenshot, db.session))

@app.route('/upload_screenshot', methods=['POST'])
def upload_screenshot():
    """Handle screenshot upload."""
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Save file details in the database
    new_file = Screenshot(filename=file.filename)
    db.session.add(new_file)
    db.session.commit()

    return jsonify({
        "message": "File uploaded successfully",
        "url": f"/media/screenshots/{file.filename}"
    })

@app.route('/list_screenshots', methods=['GET'])
def list_screenshots():
    search_query = request.args.get('search', '').lower()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 8))

    # List all image files
    all_files = [
        {
            'filename': f,
            'url': f"/media/screenshots/{f}",
            'last_modified': os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], f))
        }
        for f in os.listdir(app.config['UPLOAD_FOLDER'])
        if f.endswith(('jpg', 'jpeg', 'png'))
    ]

    # Sort files by last modified timestamp (newest first)
    all_files.sort(key=lambda x: x['last_modified'], reverse=True)

    # Search filter
    if search_query:
        all_files = [f for f in all_files if search_query in f['filename'].lower()]

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_files = all_files[start:end]

    return jsonify(paginated_files)

@app.route('/')
def home():
    """Render the main page with dynamic images."""
    screenshots = Screenshot.query.order_by(Screenshot.upload_time.desc()).all()
    return render_template('index.html', images=[
        {
            'filename': screenshot.filename,
            'url': f"/media/screenshots/{screenshot.filename}"
        }
        for screenshot in screenshots
    ])

@app.route('/media/screenshots/<filename>')
def serve_screenshot(filename):
    """Serve uploaded screenshot files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin/')
def admin_redirect():
    # Redirect to the home page
    return redirect(url_for('home'))

if __name__ == '__main__':
    # Ensure the database tables are created within the app context
    with app.app_context():
        db.create_all()
    app.run(debug=True)
