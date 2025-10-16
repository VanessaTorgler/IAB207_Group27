from flask import Blueprint, render_template, session, request, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    session['event'] = None

    # read filters from query string
    q_text = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or '').strip()
    fmt = (request.args.get('format') or '').strip()
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    sort = (request.args.get('sort') or 'dateSoonest').strip()

    # subquery: MIN(ticket price) per event
    price_sq = (
        db.session.query(
            TicketType.event_id.label("event_id"),
            func.min(cast(TicketType.price, Float)).label("min_price"),
        )
        .group_by(TicketType.event_id)
        .subquery()
    )
    price_expr = func.coalesce(price_sq.c.min_price, 0.0)

    # base query
    qry = (
        db.session.query(
            Event,
            price_expr.label("min_price"),
            func.count(Booking.booking_id).label('popularity'),
        )
        .outerjoin(price_sq, price_sq.c.event_id == Event.id)
        .outerjoin(Booking, Booking.event_id == Event.id)
        .outerjoin(Event_Tag, Event_Tag.event_id == Event.id)
        .outerjoin(Tag, Tag.id == Event_Tag.tag_id)
        .group_by(Event.id)
    )

    # filters
    if q_text:
        ilike = f"%{q_text}%"
        qry = qry.filter(or_(Event.title.ilike(ilike), Event.description.ilike(ilike)))
    if category:
        qry = qry.filter(Tag.name == category)
    if fmt:
        qry = qry.filter(Event.event_type == fmt)
    if price_min is not None:
        qry = qry.filter(price_expr >= price_min)
    if price_max is not None:
        qry = qry.filter(price_expr <= price_max)

    # sorting
    if sort == 'dateSoonest':
        qry = qry.order_by(Event.start_at.asc().nulls_last())
    elif sort == 'priceLowHigh':
        qry = qry.order_by(price_expr.asc())
    elif sort == 'priceHighLow':
        qry = qry.order_by(price_expr.desc())
    elif sort == 'popularity':
        qry = qry.order_by(func.count(Booking.booking_id).desc(), Event.start_at.asc())
    else:
        qry = qry.order_by(Event.start_at.asc().nulls_last())

    rows = qry.all()
    results = [{"event": e, "min_price": float(mp or 0.0), "popularity": pop} for (e, mp, pop) in rows]

    return render_template(
        'index.html',
        active_page='home',
        results=results,
        q=q_text,
        category_selected=category,
        price_min=price_min,
        price_max=price_max,
        sort_selected=sort,
        fmt_selected=fmt,
    )


def check_upload_file(form):
    # get file data from form
    fp = form.event_image.data
    filename = secure_filename(fp.filename or "")
    if not filename:
        return None

    # allow-list by extension
    ALLOWED = {'.jpg', '.jpeg', '.png', '.webp'}
    root, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED:
        return None

    # unique filename to avoid collisions / caching issues
    unique_name = f"{root}_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    
    
    # get the current path of the module file… store image file relative to this path  
    BASE_PATH = os.path.dirname(__file__)
    # upload file location – directory of this file/static/img
    upload_dir = os.path.join(BASE_PATH, 'static', 'img')
    os.makedirs(upload_dir, exist_ok=True)
    # store relative path in DB as image location in HTML is relative
    upload_path = os.path.join(upload_dir, unique_name)
    # save the file and return the db upload path  
    fp.save(upload_path)
    return f"/static/img/{unique_name}"

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

@main_bp.route('/bookinghistory')
#@login_required
def bookingHistory():
    return render_template('history.html', active_page='bookinghistory')

def checkStatus(event_id):
    #if it's cancelled, return "Cancelled
    if db.session.execute(db.select(Event.cancelled).where(Event.id==event_id)).scalar_one():
        return "Cancelled"

    end_at = db.session.execute(db.select(Event.end_at).where(Event.id==event_id)).scalar_one()
    if end_at:
        now = datetime.now(timezone.utc)
        #if it's past, return "Inactive"
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        if end_at <= now:
            return "Inactive"

    #if num of tickets sold = capacity, return "Sold Out"
    sold = db.session.execute(
        db.select(func.count(Booking.booking_id)).where(Booking.event_id==event_id)
    ).scalar_one()
    cap = db.session.execute(db.select(Event.capacity).where(Event.id==event_id)).scalar_one()
    if cap is not None and cap <= sold:
        return "Sold Out"

    return "Open"

@main_bp.route('/create-update', methods=['GET', 'POST'])
#@login_required
def createUpdate():
    form = CreateEventForm()
    if form.validate_on_submit():
        db_file_path = check_upload_file(form)
        print("Form Submitted!")
        print(
            form.title.data, form.description.data, form.category.data, form.format.data,
            form.date.data, form.start_time.data, form.end_time.data, form.timezone.data,
            form.location.data, form.capacity.data, form.event_image.data, form.image_alt_text.data,
            form.ticket_price.data, form.rsvp_closes.data, form.host_name.data, form.host_contact.data
        )

        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt   = datetime.combine(form.date.data, form.end_time.data)

        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.format.data,
            event_timezone=form.timezone.data,
            start_at=start_dt,
            rsvp_closes=form.rsvp_closes.data,
            end_at=end_dt,
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

        tagfind = db.session.execute(
            db.select(Tag).where(Tag.name == form.category.data)
        ).scalar_one()

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
        flash(f"Successfully created event. You can <a href='{url_for('main.createUpdate')}' class='alert-link'>host another event</a> "
        f"or <a href='{url_for('main.event', event_id=event.id)}' class='alert-link'>visit it</a>.",
        "success")
        return redirect(url_for('main.index'))

    print(form.errors)
    return render_template('create-update.html', active_page='create-update', form=form)
