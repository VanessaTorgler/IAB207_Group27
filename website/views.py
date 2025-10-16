from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from . import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    session['event'] = None
    return render_template('index.html', active_page='home')  

def check_upload_file(form):
  # get file data from form  
  fp = form.event_image.data
  filename = fp.filename
  # get the current path of the module file… store image file relative to this path  
  BASE_PATH = os.path.dirname(__file__)
  # upload file location – directory of this file/static/img
  upload_path = os.path.join(BASE_PATH, 'static/img', secure_filename(filename))
  # store relative path in DB as image location in HTML is relative
  db_upload_path = '/static/img/' + secure_filename(filename)
  # save the file and return the db upload path  
  fp.save(upload_path)
  return db_upload_path

@main_bp.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event(event_id):
    session['event'] = event_id
    #form = CommentForm() 
    #if form.validate_on_submit():
    #    comment = Comment(event_id, current_user.id, form.comment.data)
    title = db.session.execute(db.select(Event.title).where(Event.id==event_id)).scalar_one()
    description = db.session.execute(db.select(Event.description).where(Event.id==event_id)).scalar_one()
    capacity = db.session.execute(db.select(Event.capacity).where(Event.id==event_id)).scalar_one()
    hostName = db.session.execute(db.select(Event.host_user_id).where(Event.id==event_id)).scalar_one()
    formatType = db.session.execute(db.select(Event.event_type).where(Event.id==event_id)).scalar_one()
    startAt = db.session.execute(db.select(Event.start_at).where(Event.id==event_id)).scalar_one()
    tagId = db.session.execute(db.select(Event_Tag.tag_id).where(Event_Tag.event_id==event_id)).scalar_one()
    tagName = db.session.execute(db.select(Tag.name).where(Tag.id==tagId)).scalar_one()
    price= db.session.execute(db.select(TicketType.price).where(TicketType.event_id==event_id)).scalar_one()
    startAtDate = startAt.strftime("%a, %d %b %Y") 
    startAtTime = startAt.strftime("%I:%M %p").lstrip("0")
    endAt = db.session.execute(db.select(Event.end_at).where(Event.id==event_id)).scalar_one()
    endAt = endAt.strftime("%I:%M %p").lstrip("0")
    image = db.session.execute(db.select(Event_Image.url).where(Event_Image.event_id==event_id)).scalar_one()
    status = checkStatus(event_id)
    return render_template('event.html', event_id=event_id, title=title, status=status, price=price, description=description, category=tagName, format_type = formatType, capacity=capacity, host_name=hostName, start_at_date=startAtDate, start_at_time=startAtTime, end_at=endAt, image=image, active_page='event')

@main_bp.route('/bookinghistory')
#@login_required
def bookingHistory():
    return render_template('history.html', active_page='bookinghistory')

def checkStatus(event_id):
    #if it's cancelled, return "Cancelled
    if db.session.execute(db.select(Event.cancelled).where(Event.id==event_id)).scalar_one() == True:
        return "Cancelled"
    #if it's past, return "Inactive"
    elif db.session.execute(db.select(Event.end_at).where(Event.id==event_id)).scalar_one() < datetime.now():
        return "Inactive"
    #if num of tickets sold = capacity, return "Sold Out"
    elif db.session.execute(db.select(Event.capacity).where(Event.id==event_id)).scalar_one() <= db.session.execute(db.select(db.func.count(Booking.booking_id)).where(Booking.event_id==event_id)).scalar_one():
        return "Sold Out"
    else:
        return "Open"


@main_bp.route('/create-update', methods=['GET', 'POST'])
#@login_required
def createUpdate():
    form = CreateEventForm() 
    if form.validate_on_submit():
        db_file_path = check_upload_file(form)
        print("Form Submitted!")
        print(form.title.data, form.description.data, form.category.data, form.format.data, form.date.data, form.start_time.data, form.end_time.data, form.timezone.data, form.location.data, form.capacity.data, form.event_image.data, form.image_alt_text.data, form.ticket_price.data, form.rsvp_closes.data, form.host_name.data, form.host_contact.data)
        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.format.data,
            event_timezone=form.timezone.data,
            start_at=form.date.data,
            rsvp_closes=form.rsvp_closes.data,
            end_at=form.date.data,
            location_text=form.location.data,
            capacity=form.capacity.data
        )
        db.session.add(event)
        db.session.flush()
        event_img = Event_Image(
            event_id=event.id,
            url=db_file_path,
            alt_text=form.image_alt_text.data
        )
        tagfind = db.session.execute(db.select(Tag).where(Tag.name==form.category.data)).scalar_one()
        event_tag = Event_Tag(
            event_id=event.id,
            tag_id=tagfind.id
        )
        ticket_type = TicketType(
            event_id=event.id,
            name="General Admission",
            is_free=(form.ticket_price.data == 0),
            price=form.ticket_price.data,
            capacity=event.capacity,
            currency="AUD",
            sales_start_at=event.created_at,
            sales_end_at=event.rsvp_closes
        )
        db.session.add(event_img)
        db.session.add(event_tag)
        db.session.add(ticket_type)
        db.session.commit()
        print("Event created with ID:", event.id)
        print("EventImg created with ID:", event_img.id)
        form = CreateEventForm(formdata=None) 

    print(form.errors)
    return render_template('index.html', active_page='home', form=form, created_event=True)