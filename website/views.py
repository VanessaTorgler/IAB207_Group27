from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment
from . import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    session['event'] = None
    return render_template('index.html', active_page='home')  
@main_bp.route('/event') #/<int:event_id>', methods=['GET', 'POST']
def event(): #event_id
    #session['event'] = event_id
    #form = CommentForm() 
    #if form.validate_on_submit():
    #    comment = Comment(event_id, current_user.id, form.comment.data)
    return render_template('event.html', )#event_id=event_id

@main_bp.route('/bookinghistory')
#@login_required
def bookingHistory():
    return render_template('history.html', active_page='bookinghistory')

@main_bp.route('/create-update', methods=['GET', 'POST'])
#@login_required
def createUpdate():
    form = CreateEventForm() 
    if form.validate_on_submit():
        print("Form Submitted!")
        print(form.title.data, form.description.data, form.category.data, form.format.data, form.date.data, form.start_time.data, form.end_time.data, form.timezone.data, form.location.data, form.capacity.data, form.event_image.data, form.image_alt_text.data, form.ticket_price.data, form.rsvp_closes.data, form.host_name.data, form.host_contact.data)
        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.category.data,
            event_timezone=form.timezone.data,
            start_at=form.date.data,
            end_at=form.date.data,
            location_text=form.location.data,
            capacity=form.capacity.data
        )
        event_img = Event_Image(
            event_id=event.id,
            url=form.event_image.data,
            alt_text=form.image_alt_text.data
        )
        tagfind = db.session.execute(db.select(Tag).where(Tag.name==form.category.data)).scalar_one()
        event_tag = Event_Tag(
            event_id=event.id,
            tag_id=tagfind.id
        )
        db.session.add(event)
        db.session.add(event_img)
        db.session.add(event_tag)
        db.session.commit()
        print("Event created with ID:", event.id)
        print("EventImg created with ID:", event_img.id)
        form = CreateEventForm(formdata=None) 

    print(form.errors)
    return render_template('create-update.html', active_page='create-update', form=form)