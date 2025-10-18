from flask import Blueprint, render_template, session, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking
from .views import checkStatus
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid

events_bp = Blueprint('events', __name__)

@events_bp.route('/event/<int:event_id>', methods=['GET', 'POST'])
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
    price = db.session.execute(
        db.select(func.min(TicketType.price)).where(TicketType.event_id==event_id)
    ).scalar()
    startAtDate = startAt.strftime("%a, %d %b %Y") 
    startAtTime = startAt.strftime("%I:%M %p").lstrip("0")
    endAt = db.session.execute(db.select(Event.end_at).where(Event.id==event_id)).scalar_one()
    endAt = endAt.strftime("%I:%M %p").lstrip("0")
    image = db.session.execute(
        db.select(Event_Image.url).where(Event_Image.event_id==event_id)
    ).scalar_one_or_none()
    status = checkStatus(event_id)
    return render_template('event.html', event_id=event_id, title=title, status=status, price=price, description=description, category=tagName, format_type = formatType, capacity=capacity, host_name=hostName, start_at_date=startAtDate, start_at_time=startAtTime, end_at=endAt, image=image, active_page='event')