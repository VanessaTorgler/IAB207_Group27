from flask import Blueprint, render_template, session, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm, check_upload_file
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking, User
from .bookings import checkStatus
from .forms import EventActionForm
#from .views import check_upload_file
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid

events_bp = Blueprint('events', __name__)

def _has_started(start_at):
    """
    Return True if the event's start_at has been reached.
    """
    if start_at is None:
        return False

    if start_at.tzinfo is None:
        # Compare naive to naive: treat DB value as local time on the server
        now_local = datetime.now()
        return start_at <= now_local
    else:
        # Compare in UTC, then drop tzinfo so both sides are naive
        now_utc_naive = datetime.utcnow()
        start_utc_naive = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        return start_utc_naive <= now_utc_naive


@events_bp.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event(event_id):
    #if event_id is invalid, redirect to home
    if event_id not in [eid for (eid,) in db.session.execute(db.select(Event.id)).all()]:
        flash("Event not found.", "danger")
        return redirect(url_for('main.index'))
    session['event'] = event_id
    #form = CommentForm() 
    #if form.validate_on_submit():
    #    comment = Comment(event_id, current_user.id, form.comment.data)
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
    
    startAt = db.session.execute(db.select(Event.start_at).where(Event.id == event_id)).scalar_one()
    startAtDate = startAt.strftime("%a, %d %b %Y") if startAt else ""
    startAtTime = startAt.strftime("%I:%M %p").lstrip("0") if startAt else ""

    endAt_dt = db.session.execute(
        db.select(Event.end_at).where(Event.id == event_id)
    ).scalar_one()

    endAt = endAt_dt.strftime("%I:%M %p").lstrip("0") if endAt_dt else ""


    image = db.session.execute(
        db.select(Event_Image.url).where(Event_Image.event_id==event_id)
    ).scalar_one_or_none()
    status = checkStatus(event_id)
    
    is_host = False
    if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
        is_host = (current_user.id == hostID)
        
    # sold quantity (sum of bookings)
    sold_qty = db.session.query(func.coalesce(func.sum(Booking.qty), 0)).filter(Booking.event_id == event_id, Booking.status == "CONFIRMED").scalar() or 0
    remaining = None
    if capacity is not None:
        try:
            remaining = max(int(capacity) - int(sold_qty), 0)
        except Exception:
            remaining = None
    
    return render_template('event.html', event_id=event_id, host_email=hostEmail,
    title=title, status=status, price=price, description=description, category=tagName, format_type = formatType, capacity=capacity,
    host_name=hostName, start_at_date=startAtDate, start_at_time=startAtTime, end_at=endAt, image=image, active_page='event',
    image_alt_text=imageAltText, is_host=is_host, remaining=remaining, sold_qty=sold_qty,)

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
    event_image = db.session.query(Event_Image).filter_by(event_id=event_id).first()
    #get event tag details
    event_tag   = db.session.query(Event_Tag).filter_by(event_id=event_id).first()
    #get ticket type details
    ticket_type = db.session.query(TicketType).filter_by(event_id=event_id).first()

    form = CreateEventForm(obj=event)
    form.event_image.validators = []
    #create form with existing event details manually, as obj=event does not populate fully
    if request.method == "GET":
        form.description.data = event.description
        form.image_alt_text.data = (event_image.alt_text if event_image else "")
        tagfind = db.session.execute(db.select(Tag.name).where(Tag.id == event_tag.tag_id)).scalar_one() if event_tag else ""
        form.category.data = tagfind
        form.ticket_price.data = ticket_type.price if ticket_type else 0
        form.format.data = event.event_type

        # start_at -> date + time
        if event.start_at:
            form.date.data = event.start_at.replace(tzinfo=None).date()
            form.start_time.data = event.start_at.replace(tzinfo=None).time()

        # end_at -> time
        if event.end_at:
            form.end_time.data = event.end_at.replace(tzinfo=None).time()

        # rsvp_closes -> datetime-local
        if event.rsvp_closes:
            form.rsvp_closes.data = event.rsvp_closes.replace(tzinfo=None)

        form.host_name.data = db.session.execute(db.select(User.name).where(User.id == event.host_user_id)).scalar_one()
        form.host_contact.data = db.session.execute(db.select(User.email).where(User.id == event.host_user_id)).scalar_one()
        form.location.data = event.location_text or ""
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
        action = (request.form.get("action") or "").strip().lower()
        if action == "draft":
            event.is_draft = True
            event.is_active = False
            event.cancelled = False
            msg = "Event saved as Draft."
            cat = "info"
        elif action == "publish":
            event.is_draft = False
            event.is_active = True
            event.cancelled = False
            msg = "Event published."
            cat = "success"
        elif action == "schedule":
            event.is_draft = True
            event.is_active = False
            event.cancelled = False
            msg = "Event scheduled (saved as Draft for now)."
            cat = "info"
        else:
            msg = "Event updated."
            cat = "success"

        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt   = datetime.combine(form.date.data, form.end_time.data)

        rc = form.rsvp_closes.data
        rsvp_dt = rc.replace(tzinfo=None) if rc else None

        #update event details
        event.title = form.title.data
        event.description =  form.description.data
        event.event_type = form.format.data
        event.start_at = start_dt
        event.rsvp_closes = rsvp_dt
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
        flash(msg, cat)
        return redirect(url_for('events.my_events'))
    
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
        action = (request.form.get("action") or "publish").strip().lower()
        #get and save image
        db_file_path = check_upload_file(form)
        print("Form Submitted!")
        print(
            form.title.data, form.description.data, form.category.data, form.format.data, form.date.data, form.start_time.data, 
            form.end_time.data, form.location.data, form.capacity.data, form.event_image.data, form.image_alt_text.data,
            form.ticket_price.data, form.rsvp_closes.data, form.host_name.data, form.host_contact.data
        )
        
        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt   = datetime.combine(form.date.data, form.end_time.data)

        rc = form.rsvp_closes.data
        rsvp_dt = rc.replace(tzinfo=None) if rc else None

        #create event entry
        event = Event(
            host_user_id=current_user.id,
            title=form.title.data,
            description=form.description.data,
            event_type=form.format.data,
            start_at=start_dt,
            rsvp_closes=rsvp_dt,
            end_at=end_dt,
            location_text=form.location.data,
            capacity=form.capacity.data
        )

        if action == "draft":
            event.is_draft = True
            event.is_active = False
            event.cancelled = False
        elif action == "publish":
            event.is_draft = False
            event.is_active = True
            event.cancelled = False
        
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
        
        if action == "draft":
            flash("Event saved as Draft.", "info")
        elif action == "publish":
            flash("Event published.", "success")
        else:
            flash("Event scheduled (saved as Draft for now).", "info")

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
            func.coalesce(func.sum(Booking.qty), 0).label("sold_count"),
        )
        .outerjoin(TicketType, TicketType.event_id == Event.id)
        .outerjoin(Booking, Booking.event_id == Event.id)
        .filter(Event.host_user_id == current_user.id)
        .group_by(Event.id)
    )
    
    filters_cleared = not (q_text or status_selected or category_selected or (price_min is not None) or (price_max is not None))
    if ("when" not in request.args) and filters_cleared:
        when_ = "all"

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
        sold = int(sold or 0)
        if getattr(e, "is_draft", False):
            status = "Draft"
        elif e.cancelled:
            status = "Cancelled"
        else:
            status = "Open"

            # Sold Out
            if e.capacity is not None and (sold or 0) >= e.capacity:
                status = "Sold Out"

            # Inactive only when start time has been reached
            if status == "Open" and _has_started(e.start_at):
                status = "Inactive"
                
        metrics[e.id] = {
            "min_price": float(mp or 0.0),
            "sold": sold,
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
    form = EventActionForm()
    if not form.validate_on_submit():  # CSRF + valid action
        abort(400)
        
    action = (request.form.get("action") or "").strip()
    e = db.session.get(Event, event_id)
    if not e or e.host_user_id != current_user.id:
        flash("Event not found.", "danger")
        return redirect(url_for("events.my_events", view=request.args.get("view", "table")))

    if action == "cancel":
        e.cancelled = True
        e.is_active = False
        e.is_draft  = False
        flash("Event has been cancelled.", "warning")

    elif action == "draft":
        e.is_draft  = True
        e.is_active = False
        e.cancelled = False
        flash("Event saved as draft.", "info")

    elif action == "publish":
        e.is_active = True
        e.is_draft  = False
        e.cancelled = False
        flash("Event published.", "success")

    else:
        flash("Unknown action.", "danger")
        return redirect(url_for("events.my_events", view=request.args.get("view", "table")))

    db.session.commit()
    return redirect(url_for("events.my_events", view=request.args.get("view", "table")))