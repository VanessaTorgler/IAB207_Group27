from flask import Blueprint, render_template
from .forms import CreateEventForm

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

@main_bp.route('/create-update', methods=['GET', 'POST'])
def createUpdate():
    form = CreateEventForm() 
    if form.validate_on_submit():
        print("Form Submitted!")
        print(form.title.data, form.description.data, form.category.data, form.format.data, form.date.data, form.start_time.data, form.end_time.data, form.timezone.data, form.location.data, form.capacity.data, form.event_image.data, form.image_alt_text.data, form.ticket_price.data, form.rsvp_closes.data, form.host_name.data, form.host_contact.data)
        pass
    print(form.errors)
    return render_template('create-update.html', active_page='create-update', form=form)