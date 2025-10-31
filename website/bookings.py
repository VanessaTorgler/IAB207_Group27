from flask import Blueprint, render_template, url_for, redirect, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import func
from . import db
from .models import Booking, Event, TicketType
import secrets
from decimal import Decimal

bookings_bp = Blueprint("bookings", __name__)

def _status_for(event):
    if getattr(event, "cancelled", False):
        return "Cancelled"
    now = datetime.now()
    if getattr(event, "end_at", None) and event.end_at < now:
        return "Inactive"
    cap = getattr(event, "capacity", None)
    if cap is not None:
        sold = (
            db.session.query(func.coalesce(func.sum(Booking.qty), 0))
            .filter(Booking.event_id == event.id, Booking.status == "CONFIRMED")
            .scalar()
            or 0
        )
        if sold >= int(cap or 0):
            return "Sold Out"
    return "Open"

def _can_cancel_event(event) -> bool:
    if getattr(event, "cancelled", False):
        return False
    start = getattr(event, "start_at", None)
    now = datetime.now(start.tzinfo) if (start and start.tzinfo) else datetime.now()
    return (start is None) or (start > now)

@bookings_bp.route("/booking-history")
@login_required
def booking_history():
    rows = (
        db.session.query(Booking)
        .filter(Booking.user_id == current_user.id, Booking.status != "CANCELLED")
        .order_by(Booking.created_at.desc())
        .all()
    )
    def fmt(dt, s):
        try: return dt.strftime(s)
        except Exception: return str(dt) if dt else ""
    bookings = []
    for r in rows:
        e = r.event
        cover = None
        if e and getattr(e, "images", None):
            try:
                cover = e.images[0].url
            except Exception:
                cover = None
        if not cover:
            cover = url_for("static", filename="img/founders-breakfast.jpg")
        start_at = getattr(e, "start_at", None)
        end_at = getattr(e, "end_at", None)
        when_line = ""
        if start_at and end_at:
            when_line = f"{fmt(start_at, '%a, %d %b %Y')} • {fmt(start_at, '%I:%M %p')}–{fmt(end_at, '%I:%M %p')}"
        elif start_at:
            when_line = fmt(start_at, '%a, %d %b %Y')
        
        bookings.append({
            "event_id": getattr(e, "id", None),
            "event_title": getattr(e, "title", "Event"),
            "image_url": cover,
            "image_url": cover,
            "image_alt": f"Cover image for {getattr(e, 'title', 'Event')}",
            "when_line": when_line,
            "date_short": fmt(start_at, '%d %b %Y'),
            "location_short": getattr(e, "location_text", "") or "",
            "booking_id": getattr(r, "booking_id", ""),
            "booked_on_line": fmt(getattr(r, "created_at", None), '%a, %d %b %Y • %I:%M %p'),
            "booked_on_short": fmt(getattr(r, "created_at", None), '%d %b %Y • %I:%M %p'),
            "tickets": getattr(r, "qty", 1),
            "status": _status_for(e),
            "cancellable": (getattr(r, "status", "CONFIRMED") == "CONFIRMED") and _can_cancel_event(e),
        })
    return render_template("history.html", active_page="bookinghistory", bookings=bookings)

def checkStatus(event_id):
    e = db.session.get(Event, event_id)
    now_utc = datetime.now(timezone.utc)

    # Cancelled
    if getattr(e, "cancelled", False):
        return "Cancelled"

    # Sold Out
    sold = (
        db.session.query(func.coalesce(func.sum(Booking.qty), 0))
        .filter(Booking.event_id == event_id, Booking.status == "CONFIRMED")
        .scalar()
        or 0
    )
    if e.capacity is not None and int(e.capacity or 0) <= 0:
        return "Sold Out"
    if e.capacity is not None and sold >= int(e.capacity):
        return "Sold Out"

    start_at = getattr(e, "start_at", None)
    if start_at is not None:
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        if start_at <= now_utc:
            return "Inactive"

    return "Open"

@bookings_bp.post("/booking/<string:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    q = db.session.query(Booking).filter(Booking.user_id == current_user.id)
    if hasattr(Booking, "booking_id"):
        q = q.filter(Booking.booking_id == booking_id)
    elif hasattr(Booking, "public_id"):
        q = q.filter(Booking.public_id == booking_id)
    else:
        try:
            q = q.filter(Booking.id == int(booking_id))
        except Exception:
            flash("Invalid booking reference.", "warning")
            return redirect(url_for("bookings.booking_history"))
            
    booking = q.first()
    if not booking:
        flash("Booking not found.", "warning")
        return redirect(url_for("bookings.booking_history"))

    event = booking.event
    if not _can_cancel_event(event):
        flash("Only upcoming bookings can be cancelled.", "warning")
        return redirect(url_for("bookings.booking_history"))

    try:
        if hasattr(booking, "status"):
            booking.status = "CANCELLED"
            if hasattr(booking, "cancelled_at"):
                booking.cancelled_at = func.now()
        else:
            db.session.delete(booking)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Cancel failed:", repr(e))
        flash("Could not cancel booking.", "danger")
        return redirect(url_for("bookings.booking_history"))

    flash("Your booking was cancelled. No refunds will be issued and this exact booking cannot be reinstated.", "success",)
    return redirect(url_for("bookings.booking_history"))

@bookings_bp.post("/event/<int:event_id>/book")
@login_required
def book_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("main.index"))

    # cannot book if you're the host
    if current_user.id == event.host_user_id:
        flash("Hosts can’t book their own events.", "warning")
        return redirect(url_for("events.event", event_id=event_id))

    # must be Open
    if checkStatus(event_id) != "Open":
        flash("This event is not open for booking.", "warning")
        return redirect(url_for("events.event", event_id=event_id))

    # qty from form
    try:
        qty = int((request.form.get("qty") or "1").strip())
    except Exception:
        qty = 1
    if qty < 1:
        qty = 1
    if qty > 12:
        qty = 12

    # capacity check
    sold = db.session.query(func.coalesce(func.sum(Booking.qty), 0)).filter(Booking.event_id == event_id, Booking.status == "CONFIRMED").scalar() or 0
    remaining = (event.capacity or 0) - int(sold)
    if event.capacity is not None and qty > remaining:
        flash(f"Only {remaining} tickets remaining.", "warning")
        return redirect(url_for("events.event", event_id=event_id))

    tt = (
        db.session.query(TicketType)
        .filter(TicketType.event_id == event_id)
        .order_by(TicketType.price.asc())
        .first()
    )
    if not tt:
        flash("No tickets available for this event.", "danger")
        return redirect(url_for("events.event", event_id=event_id))

    unit_price = Decimal(str(tt.price or 0))
    total_amount = unit_price * qty

    # create booking
    booking_id = secrets.token_hex(12) 
    b = Booking(
        booking_id=booking_id,
        event_id=event_id,
        user_id=current_user.id,
        ticket_type_id=tt.id,
        qty=qty,
        unit_price=unit_price,
        total_amount=total_amount,
        status="CONFIRMED",
    )
    db.session.add(b)
    db.session.flush()

    from .models import Payment
    p = Payment(
        booking_id=b.booking_id,
        provider="SIMULATED",
        method_brand="VISA",
        method_last4="4242",
        amount=total_amount,
        currency=tt.currency or "AUD",
        status="CAPTURED",
        authorised_at=func.now(),
        captured_at=func.now(),
    )
    db.session.add(p)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not complete your booking.", "danger")
        return redirect(url_for("events.event", event_id=event_id))

    flash("Your purchase is complete. See it in Booking History.", "success")
    return redirect(url_for("bookings.booking_history"))
