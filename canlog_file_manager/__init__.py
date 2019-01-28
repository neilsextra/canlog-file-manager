from flask import Flask, render_template
from flask_bower import Bower
from canlog_file_manager.processors.views import views

print('Creating', __name__)

app = Flask(__name__)    # Create an instance of the class for our use
        
Bower(app) 

app.register_blueprint(views)

wsgi_app = app.wsgi_app
