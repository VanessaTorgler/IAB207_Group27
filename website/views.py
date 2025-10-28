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
        now_utc_naive = datetime.utcnow()
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

    sold_sq = (
        db.session.query(
            Booking.event_id.label("event_id"),
            func.coalesce(func.sum(Booking.qty), 0).label("sold_qty"),
        )
        .filter(Booking.status == "CONFIRMED")
        .group_by(Booking.event_id)
        .subquery()
    )

    sold_qty_col = func.coalesce(sold_sq.c.sold_qty, 0).label("sold_qty")
    
    # base query
    qry = (
        db.session.query(
            Event,
            price_expr.label("min_price"),
            sold_qty_col,
        )
        .outerjoin(price_sq, price_sq.c.event_id == Event.id)
        .outerjoin(sold_sq, sold_sq.c.event_id == Event.id)
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
        qry = qry.order_by(sold_qty_col.desc(), Event.start_at.asc())
    else:
        qry = qry.order_by(Event.start_at.asc().nulls_last())

    rows = qry.all()

    now_utc = datetime.now(timezone.utc)

    def derive_status(e, sold_count):
        if getattr(e, 'cancelled', False):
            return 'Cancelled'

        cap = e.capacity
        if cap is not None and int(cap) <= 0:
            return 'Sold Out'
        if cap is not None and (sold_count or 0) >= cap:
            return 'Sold Out'

        if _has_started(e.start_at):
            return 'Inactive'

        return 'Open'


    enriched = []
    for (e, mp, sold_qty) in rows:
        s = derive_status(e, int(sold_qty or 0))
        enriched.append({
            "event": e,
            "min_price": float(mp or 0.0),
            "sold_count": int(sold_qty or 0),
            "status": s
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
        start_page=start_page,
        end_page=end_page,
    )

# Legacy redirect: keep old links working
@main_bp.route('/bookinghistory')
def bookingHistory():
    return redirect(url_for('bookings.booking_history'))

@main_bp.route('/search')
def search_events():
    q_text     = (request.args.get('q') or '').strip()
    category   = (request.args.get('category') or '').strip()
    fmt        = (request.args.get('format') or '').strip()
    price_min  = request.args.get('price_min', type=float)
    price_max  = request.args.get('price_max', type=float)
    sort       = (request.args.get('sort') or 'relevance').strip()

    # define min price subquery/expr in THIS function
    price_sq = (
        db.session.query(
            TicketType.event_id.label("event_id"),
            func.min(cast(TicketType.price, Float)).label("min_price"),
        )
        .group_by(TicketType.event_id)
        .subquery()
    )
    price_expr = func.coalesce(price_sq.c.min_price, 0.0)

    sold_sq = (
        db.session.query(
            Booking.event_id.label("event_id"),
            func.coalesce(func.sum(Booking.qty), 0).label("sold_qty"),
        )
        .filter(Booking.status == "CONFIRMED")
        .group_by(Booking.event_id)
        .subquery()
    )
    
    qry = (
        db.session.query(
            Event,
            price_expr.label("min_price"),
            func.coalesce(sold_sq.c.sold_qty, 0).label("sold_qty"),
        )
        .outerjoin(price_sq, price_sq.c.event_id == Event.id)
        .outerjoin(Booking, Booking.event_id == Event.id)
        .outerjoin(Event_Tag, Event_Tag.event_id == Event.id)
        .outerjoin(Tag, Tag.id == Event_Tag.tag_id)
        .group_by(Event.id, price_sq.c.min_price, sold_sq.c.sold_qty)
    )

    if q_text:
        ilike = f"%{q_text}%"
        qry = qry.filter(or_(Event.title.ilike(ilike), Event.description.ilike(ilike)))
    if category:
        qry = qry.filter(Tag.name == category)
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
        qry = qry.order_by(func.coalesce(sold_sq.c.sold_qty, 0).desc(), Event.start_at.asc())
    else:
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