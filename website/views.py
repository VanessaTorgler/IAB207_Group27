from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    return render_template('index.html', active_page='home')  
@main_bp.route('/event')
def event():
    return render_template('event.html', active_page='event')

@main_bp.route('/bookinghistory')
def bookinghistory():
    return render_template('history.html', active_page='bookinghistory')