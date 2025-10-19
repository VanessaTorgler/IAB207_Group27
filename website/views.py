from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_, cast, Float
from datetime import datetime, timezone
from .forms import CreateEventForm, CommentForm
from .models import Event, Event_Image, Event_Tag, Tag, Comment, TicketType, Booking, User
from . import db
from werkzeug.utils import secure_filename
import os, time, uuid

main_bp = Blueprint('main', __name__)

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