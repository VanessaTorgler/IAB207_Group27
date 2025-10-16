from flask import Blueprint, render_template, session, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from datetime import datetime
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking
from . import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
def index():
    # List all events with min ticket price + popularity
    qry = (
        db.session.query(
            Event,
            func.min(TicketType.price).label('min_price'),
            func.count(Booking.booking_id).label('popularity')
        )
        .outerjoin(TicketType, TicketType.event_id == Event.id)
        .outerjoin(Booking, Booking.event_id == Event.id)
        .group_by(Event.id)
        .order_by(Event.start_at.asc().nulls_last())
    )
    rows = qry.all()
    results = [{'event': e, 'min_price': mp, 'popularity': pop} for (e, mp, pop) in rows]

    return render_template(
        'index.html',
        active_page='home',
        results=results,
        q='', category_selected='',
        price_min=None, price_max=None,
        sort_selected='dateSoonest'
    )

@main_bp.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event_detail(event_id):
    session['event'] = event_id

    title = db.session.execute(db.select(Event.title).where(Event.id == event_id)).scalar_one()
    description = db.session.execute(db.select(Event.description).where(Event.id == event_id)).scalar_one()
    capacity = db.session.execute(db.select(Event.capacity).where(Event.id == event_id)).scalar_one()
    hostName = db.session.execute(db.select(Event.host_user_id).where(Event.id == event_id)).scalar_one()
    formatType = db.session.execute(db.select(Event.event_type).where(Event.id == event_id)).scalar_one()
    startAt = db.session.execute(db.select(Event.start_at).where(Event.id == event_id)).scalar_one()
    startAtDate = startAt.strftime("%a, %d %b %Y") if startAt else ""
    startAtTime = startAt.strftime("%I:%M %p").lstrip("0") if startAt else ""
    endAt = db.session.execute(db.select(Event.end_at).where(Event.id == event_id)).scalar_one()
    endAtStr = endAt.strftime("%I:%M %p").lstrip("0") if endAt else ""
    tagId = db.session.execute(db.select(Event_Tag.tag_id).where(Event_Tag.event_id == event_id)).scalar_one()
    tagName = db.session.execute(db.select(Tag.name).where(Tag.id == tagId)).scalar_one()
    price = db.session.execute(db.select(func.min(TicketType.price)).where(TicketType.event_id == event_id)).scalar()
    image = db.session.execute(db.select(Event_Image.url).where(Event_Image.event_id == event_id)).scalar_one_or_none()
    status = checkStatus(event_id)

    return render_template(
        'event.html',
        event_id=event_id,
        title=title,
        status=status,
        price=price,
        description=description,
        category=tagName,
        format_type=formatType,
        capacity=capacity,
        host_name=hostName,
        start_at_date=startAtDate,
        start_at_time=startAtTime,
        end_at=endAtStr,
        image=image,
        active_page='event'
    )

@main_bp.route('/bookinghistory')
@login_required
def bookingHistory():
    # Keep the original URL but serve the dynamic booking history from the new blueprint
    return redirect(url_for('bookings.booking_history'))

def checkStatus(event_id):
    # Cancelled?
    if db.session.execute(db.select(Event.cancelled).where(Event.id == event_id)).scalar_one():
        return "Cancelled"
    # Past?
    if db.session.execute(db.select(Event.end_at).where(Event.id == event_id)).scalar_one() < datetime.now():
        return "Inactive"
    # Sold out?
    sold = db.session.execute(db.select(func.count(Booking.booking_id)).where(Booking.event_id == event_id)).scalar_one()
    cap = db.session.execute(db.select(Event.capacity).where(Event.id == event_id)).scalar_one()
    if cap is not None and sold >= cap:
        return "Sold Out"
    return "Open"

@main_bp.route('/create-update', methods=['GET', 'POST'])
def createUpdate():
    form = CreateEventForm()
    if form.validate_on_submit():
        # Combine date + times
        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt = datetime.combine(form.date.data, form.end_time.data)

        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.format.data,
            event_timezone=form.timezone.data,
            start_at=start_dt,
            end_at=end_dt,
            rsvp_closes=form.rsvp_closes.data,
            location_text=form.location.data,
            capacity=int(form.capacity.data)
        )
        db.session.add(event)
        db.session.flush() 

        # Image
        event_img = Event_Image(
            event_id=event.id,
            url=form.event_image.data,
            alt_text=form.image_alt_text.data
        )
        db.session.add(event_img)

        # Tag link
        tag = db.session.execute(db.select(Tag).where(Tag.name == form.category.data)).scalar_one()
        event_tag = Event_Tag(event_id=event.id, tag_id=tag.id)
        db.session.add(event_tag)

        # Default ticket type
        ticket_type = TicketType(
            event_id=event.id,
            name="General Admission",
            is_free=(form.ticket_price.data or 0) == 0,
            price=form.ticket_price.data or 0,
            currency="AUD",
            capacity=event.capacity,
            sales_start_at=event.created_at,
            sales_end_at=event.rsvp_closes
        )
        db.session.add(ticket_type)

        db.session.commit()
        # clear form after success
        form = CreateEventForm(formdata=None)

    return render_template('create-update.html', active_page='create-update', form=form)

@main_bp.route('/search')
def search_events():
    """
    Supports:
      q           : text search (title/description)
      category    : Tag.name (e.g., 'Tech & AI', 'Marketing', ...)
      format      : Event.event_type ('In-person' | 'Virtual' | 'Hybrid')
      price_min   : minimum ticket price
      price_max   : maximum ticket price
      sort        : relevance | dateSoonest | priceLowHigh | priceHighLow | popularity
    """
    q_text     = (request.args.get('q') or '').strip()
    category   = (request.args.get('category') or '').strip()
    fmt        = (request.args.get('format') or '').strip()
    price_min  = request.args.get('price_min', type=float)
    price_max  = request.args.get('price_max', type=float)
    sort       = (request.args.get('sort') or 'relevance').strip()

    qry = (db.session.query(
                Event,
                func.min(TicketType.price).label('min_price'),
                func.count(Booking.booking_id).label('popularity')
           )
           .outerjoin(TicketType, TicketType.event_id == Event.id)
           .outerjoin(Booking, Booking.event_id == Event.id)
           # join tags so category can match Tag.name
           .outerjoin(Event_Tag, Event_Tag.event_id == Event.id)
           .outerjoin(Tag, Tag.id == Event_Tag.tag_id)
           .group_by(Event.id))

    if q_text:
        ilike = f"%{q_text}%"
        qry = qry.filter(or_(Event.title.ilike(ilike), Event.description.ilike(ilike)))

    # Category ->
    if category:
        qry = qry.filter(Tag.name == category)

    # Format 
    if fmt:
        qry = qry.filter(Event.event_type == fmt)

    if price_min is not None:
        qry = qry.having(func.coalesce(func.min(TicketType.price), 0) >= price_min)
    if price_max is not None:
        qry = qry.having(func.coalesce(func.min(TicketType.price), 1_000_000) <= price_max)

    if sort == 'dateSoonest':
        qry = qry.order_by(Event.start_at.asc().nulls_last())
    elif sort == 'priceLowHigh':
        qry = qry.order_by(func.coalesce(func.min(TicketType.price), 0).asc())
    elif sort == 'priceHighLow':
        qry = qry.order_by(func.coalesce(func.min(TicketType.price), 0).desc())
    elif sort == 'popularity':
        qry = qry.order_by(func.count(Booking.booking_id).desc(), Event.start_at.asc())
    else:  # relevance
        qry = qry.order_by(Event.start_at.asc().nulls_last())

    rows = qry.all()
    results = [{'event': e, 'min_price': mp, 'popularity': pop} for (e, mp, pop) in rows]

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