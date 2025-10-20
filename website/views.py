from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking, User
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid
from urllib.parse import urlencode

main_bp = Blueprint('main', __name__)

def _has_started(start_at):
    """
    Return True if the event's start_at has been reached.
    """
    if start_at is None:
        return False

    if start_at.tzinfo is None:
        now_local = datetime.now()
        return start_at <= now_local
    else:
        now_utc_naive = datetime()
        start_utc_naive = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        return start_utc_naive <= now_utc_naive


@main_bp.route('/')
def _index():
    # redirect base url to /home
    return redirect(url_for('main.index'))

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

    status_filter = (request.args.get('status') or '').strip() 
    page      = max((request.args.get('page', 1, type=int) or 1), 1)
    per_page  = request.args.get('per_page', 9, type=int) 
    
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
    
    qry = qry.filter(Event.is_draft == False)

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

    now_utc = datetime.now(timezone.utc)

    def derive_status(e, sold_count):
        # Check if Draft first
        if getattr(e, 'is_draft', False):
            return 'Draft'

        # Check if Cancelled next
        if getattr(e, 'cancelled', False):
            return 'Cancelled'

        # Check if Sold Out next
        if e.capacity is not None and (sold_count or 0) >= e.capacity:
            return 'Sold Out'

        # Check if Inactive using has_started()
        if _has_started(e.start_at):
            return 'Inactive'

        # All other events that don't meet above criteria = Open
        return 'Open'

    enriched = []
    for (e, mp, sold) in rows:
        status = derive_status(e, sold)
        if status == 'Draft':
            continue
        enriched.append({
            "event": e,
            "min_price": float(mp or 0.0),
            "sold_count": int(sold or 0),
            "status": status
        })

    if status_filter:
        enriched = [r for r in enriched if r["status"] == status_filter]

    # paginate
    total = len(enriched)
    pages = max((total + per_page - 1) // per_page, 1)
    start = (page - 1) * per_page
    end   = start + per_page
    page_items = enriched[start:end]
    
    window = 2
    start_page = max(1, page - window)
    end_page   = min(pages, page + window)

    base_params = request.args.to_dict()
    base_params.pop('page', None)
    base_params.pop('per_page', None)
    
    base_params = {k: v for k, v in base_params.items() if v not in (None, '', [])}
    base_qs = urlencode(base_params)

    return render_template(
        'index.html',
        active_page='home',
        results=page_items,
        q=q_text,
        category_selected=category,
        price_min=price_min,
        price_max=price_max,
        sort_selected=sort,
        fmt_selected=fmt,
        status_selected=status_filter,

        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        has_prev=(page > 1),
        has_next=(page < pages),
        prev_page=(page - 1),
        next_page=(page + 1),
        base_params=base_params,
        base_qs=base_qs,
        start_page=start_page,
        end_page=end_page,
    )

# @main_bp.route('/bookinghistory')
# @login_required
# def bookingHistory():
#     # Keep the original URL but serve the dynamic booking history from the new blueprint
#     return redirect(url_for('bookings.booking_history'))

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
    
    qry = qry.filter(Event.is_draft == False)

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