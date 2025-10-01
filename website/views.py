from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    return render_template('index.html', active_page='home')  
@main_bp.route('/event')
def event():
    return render_template('event.html')

@main_bp.route('/bookinghistory')
def bookingHistory():
    return render_template('history.html', active_page='bookinghistory')

@main_bp.route('/create-update')
def createUpdate():
    return render_template('create-update.html', active_page='create-update')