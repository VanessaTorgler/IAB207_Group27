from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm, check_upload_file
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking, User
from .bookings import checkStatus
#from .views import check_upload_file
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid

events_bp = Blueprint('events', __name__)

@events_bp.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event(event_id):
    #if event_id is invalid, redirect to home
    if event_id not in [eid for (eid,) in db.session.execute(db.select(Event.id)).all()]:
        flash("Event not found.", "danger")
        return redirect(url_for('main.index'))
    session['event'] = event_id
    event = db.session.get(Event, event_id)
    form = CommentForm() 
    if form.validate_on_submit():
        event = db.session.get(Event, event_id)
        post_comment = Comment(body=form.comment.data, event = event, user = current_user)
        db.session.add(post_comment)
        db.session.commit()
        # confirmation message
        flash("Comment Posted!")
        return redirect(url_for('events.event', event_id = event_id))
    comments = db.session.execute(db.select(Comment).where(Comment.event_id==event_id)).scalars().all()
    title = db.session.execute(db.select(Event.title).where(Event.id==event_id)).scalar_one()
    description = db.session.execute(db.select(Event.description).where(Event.id==event_id)).scalar_one()
    capacity = db.session.execute(db.select(Event.capacity).where(Event.id==event_id)).scalar_one()
    hostID = db.session.execute(db.select(Event.host_user_id).where(Event.id==event_id)).scalar_one()
    hostName = db.session.execute(db.select(User.name).where(User.id==hostID)).scalar_one()
    hostEmail = db.session.execute(db.select(User.email).where(User.id==hostID)).scalar_one()
    imageAltText = db.session.execute(db.select(Event_Image.alt_text).where(Event_Image.event_id==event_id)).scalar_one_or_none()
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
    return render_template('event.html', event_id=event_id, host_email=hostEmail, comments=comments, form=form, event = event,
    title=title, status=status, price=price, description=description, category=tagName, format_type = formatType, capacity=capacity,
    host_name=hostName, start_at_date=startAtDate, start_at_time=startAtTime, end_at=endAt, image=image, active_page='event',
    image_alt_text=imageAltText)

# @events_bp.route("/events/<int:event_id>/comment", methods=['GET', 'POST'])
# @login_required
# def comment(event_id):
#     form = CommentForm()
#     # get event associated with comment
#     event = db.session.scalar(db.select(Event).where(Event.id == event_id))
#     if form.validate_on_submit():
#         post_comment = Comment(body=form.comment.data, event = event, user = current_user)
#         db.session.add(post_comment)
#         db.session.commit()
#         # confirmation message
#         flash("Comment Posted!")
#         return redirect(url_for('events.event', event_id = event_id))


@events_bp.route('/update/<int:event_id>', methods=['GET', 'POST'])
@login_required
def update(event_id):
    query = db.select(Event.id).where(Event.host_user_id==current_user.id)
    #check if event exists, without telling user if it doesnt
    if event_id not in [eid for (eid,) in db.session.execute(query).all()]:
        flash("You do not have permission to edit this event.", "danger")
        return redirect(url_for('main.index'))
    #check if current user is host of event
    if current_user.id != db.session.execute(db.select(Event.host_user_id).where(Event.id==event_id)).scalar_one():
        flash("You do not have permission to edit this event.", "danger")
        return redirect(url_for('main.index'))
    
    #get event details
    event = db.session.get(Event, event_id)
    #get event image details
    event_image= db.session.get(Event_Image, event_id)
    #get event tag details
    event_tag = db.session.get(Event_Tag, event_id)
    #get ticket type details
    ticket_type = db.session.get(TicketType, event_id)

    form = CreateEventForm(obj=event)
    form.event_image.validators = []
    #create form with existing event details manually, as obj=event does not populate fully
    form.description.data = event.description
    form.image_alt_text.data = event_image.alt_text
    tagfind = db.session.execute(
        db.select(Tag.name).where(Tag.id == event_tag.tag_id)).scalar_one()
    form.category.data = tagfind
    form.ticket_price.data = ticket_type.price
    form.format.data = event.event_type
    form.timezone.data = event.event_timezone
    form.date.data = event.start_at.date()
    form.start_time.data = event.start_at.time()
    form.end_time.data = event.end_at.time()
    form.host_name.data = db.session.execute(db.select(User.name).where(User.id==event.host_user_id)).scalar_one()
    form.host_contact.data = db.session.execute(db.select(User.email).where(User.id==event.host_user_id)).scalar_one()
    form.location.data = event.location_text
    #image not populated for security reasons


    if form.validate_on_submit():
        if form.event_image.data:
            #delete old image
            old_image_path = event_image.url
            if old_image_path:
                old_image_full_path = os.path.join(os.path.dirname(__file__), old_image_path.lstrip("/"))
                if os.path.exists(old_image_full_path):
                    os.remove(old_image_full_path)
            #upload new image
            db_file_path = check_upload_file(form)  
            event_image.url = db_file_path
        else:
            form.event_image.data = db.session.execute(db.select(Event_Image.url).where(Event_Image.event_id==event.id)).scalar_one()

        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt   = datetime.combine(form.date.data, form.end_time.data)
        #update event details
        event.title = form.title.data
        event.description =  form.description.data
        event.event_type = form.format.data
        event.event_timezone = form.timezone.data
        event.start_at = start_dt
        event.rsvp_closes = form.rsvp_closes.data
        event.end_at = end_dt
        event.location_text = form.location.data
        event.capacity = form.capacity.data
        event_image.alt_text = form.image_alt_text.data
        #update event tag details
        tagfind = db.session.execute(
            db.select(Tag).where(Tag.name == form.category.data)
        ).scalar_one()
        event_tag.tag_id = tagfind.id
        #update ticket type details
        ticket_type.is_free = (form.ticket_price.data == 0)
        ticket_type.price = form.ticket_price.data
        ticket_type.capacity = event.capacity
        ticket_type.sales_end_at = event.rsvp_closes
        
        db.session.add(event)
        db.session.add(event_image)
        db.session.add(event_tag)
        db.session.add(ticket_type)
        db.session.commit()
        flash(f"Successfully created event. You can <a href='{url_for('events.createUpdate')}' class='alert-link'>host another event</a> "
        f"or <a href='{url_for('events.event', event_id=event.id)}' class='alert-link'>visit it</a>.",
        "success")
        return redirect(url_for('main.index'))
    
    print(form.errors)
    return render_template('create-update.html', active_page='create-update', form=form, is_create=False)


@events_bp.route('/create', methods=['GET', 'POST'])
@login_required
def createUpdate():
    form = CreateEventForm()
    #clear form data (due to formdate=None filling entries with None)
    for field in form:
        if field.data is None:
            field.data = ""
   
    if form.validate_on_submit():
        #get and save image
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

        #create event entry
        event = Event(
            host_user_id=current_user.id,
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

        #create event image entry
        event_img = Event_Image(
            event_id=event.id,
            url=db_file_path,
            alt_text=form.image_alt_text.data
        )

        tagfind = db.session.execute(
            db.select(Tag).where(Tag.name == form.category.data)
        ).scalar_one()

        #create event tag entry
        event_tag = Event_Tag(
            event_id=event.id,
            tag_id=tagfind.id
        )
        #create ticket type entry
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
        #create an alert with links to create another event or view the created event
        flash(f"Successfully created event. You can <a href='{url_for('events.createUpdate')}' class='alert-link'>host another event</a> "
        f"or <a href='{url_for('events.event', event_id=event.id)}' class='alert-link'>visit it</a>.",
        "success")
        return redirect(url_for('main.index'))
    print(form.errors)
    return render_template('create-update.html', active_page='create-update', form=form, is_create=True)

@events_bp.route("/my-events")
@login_required
def my_events():
    # read query params
    view  = (request.args.get("view") or "grid").strip()
    when_ = (request.args.get("when") or "upcoming").strip()
    fmt   = (request.args.get("format") or "").strip()
    sort  = (request.args.get("sort") or "upcoming").strip()

    # filters (new)
    q_text            = (request.args.get("q") or "").strip()
    price_min         = request.args.get("price_min", type=float)
    price_max         = request.args.get("price_max", type=float)
    status_selected   = request.args.getlist("status")
    category_selected = request.args.getlist("category")

    # base query with metrics
    qry = (
        db.session.query(
            Event,
            func.min(cast(TicketType.price, Float)).label("min_price"),
            func.count(Booking.booking_id).label("sold_count"),
        )
        .outerjoin(TicketType, TicketType.event_id == Event.id)
        .outerjoin(Booking, Booking.event_id == Event.id)
        .filter(Event.host_user_id == current_user.id)
        .group_by(Event.id)
    )

    now_utc = datetime.now(timezone.utc)

    if when_ == "upcoming":
        qry = qry.filter((Event.start_at == None) | (Event.start_at >= now_utc))
    elif when_ == "past":
        qry = qry.filter((Event.end_at != None) & (Event.end_at < now_utc))

    if fmt:
        qry = qry.filter(Event.event_type == fmt)

    # sorting
    if sort == "upcoming":
        qry = qry.order_by((Event.start_at == None).asc(), Event.start_at.asc())
    elif sort == "created":
        qry = qry.order_by(Event.created_at.desc())
    elif sort == "title":
        qry = qry.order_by(func.lower(Event.title).asc())
    else:
        qry = qry.order_by((Event.start_at == None).asc(), Event.start_at.asc())

    rows = qry.all()

    # metrics/status for all rows
    metrics = {}
    for e, mp, sold in rows:
        status = "Open"
        if e.cancelled:
            status = "Cancelled"
        elif not getattr(e, "is_active", True):
            status = "Inactive"
        else:
            end_at = e.end_at
            if end_at is not None:
                if end_at.tzinfo is None:
                    end_at = end_at.replace(tzinfo=timezone.utc)
                if end_at <= now_utc:
                    status = "Inactive"
            if status == "Open" and e.capacity is not None and (sold or 0) >= e.capacity:
                status = "Sold Out"

        metrics[e.id] = {
            "min_price": float(mp or 0.0),
            "sold": int(sold or 0),
            "status": status,
        }

    # categories list
    all_categories = [name for (name,) in db.session.query(Tag.name).order_by(Tag.name).all()]

    # tags map
    tags_by_event_all: dict[int, list[str]] = {}
    if rows:
        all_event_ids = [e.id for (e, _, _) in rows]
        tag_rows = (
            db.session.query(Event_Tag.event_id, Tag.name)
            .join(Tag, Tag.id == Event_Tag.tag_id)
            .filter(Event_Tag.event_id.in_(all_event_ids))
            .all()
        )
        for eid, name in tag_rows:
            tags_by_event_all.setdefault(eid, []).append(name)

    # apply filters (search, status multi, category multi, price range)
    filtered_events = []
    status_allow_set = {s.lower().replace(" ", "") for s in status_selected} if status_selected else set()

    for e, _, _ in rows:
        m = metrics[e.id]

        # search
        if q_text and q_text.lower() not in (e.title or "").lower():
            continue

        # status (OR)
        if status_allow_set and m["status"].lower().replace(" ", "") not in status_allow_set:
            continue

        # categories (OR)
        if category_selected:
            ev_cats = set(tags_by_event_all.get(e.id, []))
            if not ev_cats.intersection(category_selected):
                continue

        # price range
        if price_min is not None and m["min_price"] < price_min:
            continue
        if price_max is not None and m["min_price"] > price_max:
            continue

        filtered_events.append(e)

    events = filtered_events

    # tags map for displayed events only
    tags_map: dict[int, list[str]] = {e.id: tags_by_event_all.get(e.id, []) for e in events}

    return render_template(
        "my-events.html",
        active_page="my-events",
        events=events,
        view=view,
        when_selected=when_,
        fmt_selected=fmt,
        sort_selected=sort,
        metrics=metrics,
        tags_map=tags_map,
        q_text=q_text,
        price_min=price_min,
        price_max=price_max,
        status_selected=status_selected,
        category_selected=category_selected,
        all_categories=all_categories,
    )

@events_bp.post("/event/<int:event_id>/action")
@login_required
def event_action(event_id):
    action = (request.form.get("action") or "").strip()
    e = db.session.get(Event, event_id)
    if not e or e.host_user_id != current_user.id:
        flash("Event not found.", "danger")
        return redirect(url_for("events.my_events", view=request.args.get("view", "table")))

    now_utc = datetime.now(timezone.utc)

    if action == "cancel":
        e.cancelled = True
        flash("Event has been cancelled.", "warning")
    elif action == "inactive":
        e.is_active = False
        flash("Event marked as inactive.", "info")
    else:
        flash("Unknown action.", "danger")
        return redirect(url_for("events.my_events", view=request.args.get("view", "table")))

    db.session.commit()
    # preserve current view if present
    return redirect(url_for("events.my_events", view=request.args.get("view", "table")))