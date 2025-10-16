from flask import Blueprint, render_template, url_for, redirect, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from . import db
from .models import Booking, Event

bookings_bp = Blueprint("bookings", __name__)

def _status_for(event: Event) -> str:
    # Compute status without touching other code/columns
    if getattr(event, "cancelled", False):
        return "Cancelled"
    now = datetime.now()
    end_at = getattr(event, "end_at", None)
    if end_at and end_at < now:
        return "Inactive"
    # capacity vs sold (best-effort, optional)
    capacity = getattr(event, "capacity", None)
    if capacity is not None:
        sold = db.session.query(Booking).filter_by(event_id=event.id).count()
        if sold >= capacity:
            return "Sold Out"
    return "Open"

@bookings_bp.route("/booking-history")
@login_required
def booking_history():
    # Fetch current user's bookings newest first
    rows = (
        db.session.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.booked_on.desc())
        .all()
    )
    bookings = []
    for r in rows:
        e = r.event  # expects relationship Booking.event -> Event
        # best-effort access with fallbacks to avoid KeyErrors
        img = getattr(e, "image", None) or "founders-breakfast.jpg"
        start_at = getattr(e, "start_at", None)
        end_at = getattr(e, "end_at", None)
        when_line = ""
        date_short = ""
        booked_on_line = ""
        booked_on_short = ""
        if start_at and end_at:
            try:
                when_line = f"{start_at.strftime('%a, %d %b %Y')} • {start_at.strftime('%-I:%M')}–{end_at.strftime('%-I:%M %p')}"
            except Exception:
                when_line = str(start_at)
        if start_at:
            try:
                date_short = start_at.strftime('%d %b %Y')
            except Exception:
                date_short = str(start_at)
        if getattr(r, "booked_on", None):
            try:
                booked_on_line = r.booked_on.strftime('%a, %d %b %Y • %-I:%M %p')
                booked_on_short = r.booked_on.strftime('%d %b %Y • %-I:%M %p')
            except Exception:
                booked_on_line = booked_on_short = str(r.booked_on)

        b = {
            "event_id": getattr(e, "id", None),
            "event_title": getattr(e, "title", "Event"),
            "image_url": url_for("static", filename=f"img/{img}"),
            "thumb_url": url_for("static", filename=f"img/{img}"),
            "image_alt": f"Cover image for {getattr(e, 'title', 'Event')}",
            "when_line": when_line,
            "date_short": date_short,
            "location_short": getattr(e, "location_text", None) or getattr(e, "location", "") or "",
            "booking_id": getattr(r, "public_id", None) or str(getattr(r, "id", "")),
            "booked_on_line": booked_on_line,
            "booked_on_short": booked_on_short,
            "tickets": getattr(r, "quantity", 1),
            "status": _status_for(e),
            "cancellable": True if _status_for(e) == "Open" else False,
        }
        bookings.append(b)

    return render_template("history.html", active_page="bookinghistory", bookings=bookings)

@bookings_bp.post("/booking/<string:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    # Only cancel your own booking; soft-cancel if status field exists, else delete
    q = db.session.query(Booking).filter(Booking.user_id == current_user.id)
    if hasattr(Booking, "public_id"):
        q = q.filter(Booking.public_id == booking_id)
    else:
        # id may be int; accept string id
        try:
            bid = int(booking_id)
            q = q.filter(Booking.id == bid)
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

    # Soft cancel if model supports it
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