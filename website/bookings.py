from flask import Blueprint, render_template, url_for, redirect, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import func
from . import db
from .models import Booking, Event

bookings_bp = Blueprint("bookings", __name__)

def _status_for(event):
    if getattr(event, "cancelled", False):
        return "Cancelled"
    now = datetime.now()
    end_at = getattr(event, "end_at", None)
    if end_at and end_at < now:
        return "Inactive"
    capacity = getattr(event, "capacity", None)
    if capacity is not None:
        sold = db.session.query(Booking).filter_by(event_id=event.id).count()
        if sold >= capacity:
            return "Sold Out"
    return "Open"

@bookings_bp.route("/booking-history")
@login_required
def booking_history():
    rows = (
        db.session.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    def fmt(dt, s):
        try: return dt.strftime(s)
        except Exception: return str(dt) if dt else ""
    bookings = []
    for r in rows:
        e = r.event
        img = getattr(e, "image", None) or "founders-breakfast.jpg"
        start_at = getattr(e, "start_at", None)
        end_at = getattr(e, "end_at", None)
        bookings.append({
            "event_id": getattr(e, "id", None),
            "event_title": getattr(e, "title", "Event"),
            "image_url": url_for("static", filename=f"img/{img}"),
            "thumb_url": url_for("static", filename=f"img/{img}"),
            "image_alt": f"Cover image for {getattr(e, 'title', 'Event')}",
            "when_line": f"{fmt(start_at, '%a, %d %b %Y')} • {fmt(start_at, '%-I:%M')}–{fmt(end_at, '%-I:%M %p')}" if start_at and end_at else fmt(start_at, '%a, %d %b %Y'),
            "date_short": fmt(start_at, '%d %b %Y'),
            "location_short": getattr(e, "location_text", None) or getattr(e, "location", "") or "",
            "booking_id": getattr(r, "public_id", None) or str(getattr(r, "id", "")),
            "booked_on_line": fmt(getattr(r, "created_at", None), '%a, %d %b %Y • %-I:%M %p'),
            "booked_on_short": fmt(getattr(r, "created_at", None), '%d %b %Y • %-I:%M %p'),
            "tickets": getattr(r, "quantity", 1),
            "status": _status_for(e),
            "cancellable": _status_for(e) == "Open",
        })
    return render_template("history.html", active_page="bookinghistory", bookings=bookings)

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

@bookings_bp.post("/booking/<string:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    q = db.session.query(Booking).filter(Booking.user_id == current_user.id)
    if hasattr(Booking, "public_id"):
        q = q.filter(Booking.public_id == booking_id)
    else:
        try:
            q = q.filter(Booking.id == int(booking_id))
        except Exception:
            q = q.filter(Booking.id == -1)
    booking = q.first()
    if not booking:
        flash("Booking not found.", "warning")
        return redirect(url_for("bookings.booking_history"))

    event = booking.event
    if _status_for(event) != "Open":
        flash("Only upcoming bookings can be cancelled.", "warning")
        return redirect(url_for("bookings.booking_history"))

    if hasattr(booking, "status"):
        try:
            booking.status = "Cancelled"
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Could not cancel booking.", "danger")
            return redirect(url_for("bookings.booking_history"))
    else:
        try:
            db.session.delete(booking)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Could not cancel booking.", "danger")
            return redirect(url_for("bookings.booking_history"))

    flash("Your booking was cancelled.", "success")
    return redirect(url_for("bookings.booking_history"))