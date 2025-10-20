from . import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Numeric, func, CheckConstraint, Enum as SAEnum, Index, text, Boolean
import enum

# enums for Booking status, instead of storing them as strings
class BookingStatusEnum(str, enum.Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

# enums for Payment status, instead of storing them as strings
class PaymentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORISED = "AUTHORISED"
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"

BookingStatus = SAEnum(BookingStatusEnum, name='booking_status', native_enum=False, create_constraint=True, validate_strings=True)
PaymentStatus = SAEnum(PaymentStatusEnum, name='payment_status', native_enum=False, create_constraint=True, validate_strings=True)

class TimestampMixin(object):
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class User(TimestampMixin, db.Model, UserMixin):
    __tablename__ = 'users' # good practice to specify table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), index=True, unique=True, nullable=False)
    email = db.Column(db.String(254), index=True, nullable=False, unique=True)
    mobile = db.Column(db.String(32), index=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    street_address = db.Column(db.String(160))
    profile_pic_path = db.Column(db.String(255))
	# password should never stored in the DB, an encrypted password is stored
	# the storage should be at least 255 chars long, depending on your hashing algorithm
    password_hash = db.Column(db.String(255), nullable=False)
    # relation to call user.comments and comment.created_by
    comments = db.relationship('Comment', back_populates='user', foreign_keys='Comment.user_id')
    moderated_comments = db.relationship('Comment', back_populates='moderator', foreign_keys='Comment.moderated_by_user_id')
    
    # string print method
    def __repr__(self):
        return f"Name: {self.name}"

class Event(TimestampMixin, db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=False)
    title = db.Column(db.String(160), nullable=False, index=True)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(40))
    event_timezone = db.Column(db.String(64))
    start_at = db.Column(db.DateTime(timezone=True), index=True)
    end_at = db.Column(db.DateTime(timezone=True))
    rsvp_closes = db.Column(db.DateTime(timezone=True))
    deleted_at = db.Column(db.DateTime(timezone=True))
    #location_type = db.Column(db.String(16))
    location_text = db.Column(db.String(200))
    join_url = db.Column(db.String(255))
    join_url_release_at = db.Column(db.DateTime(timezone=True))
    capacity = db.Column(db.Integer)
    cancelled = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, server_default=text("1"))
    # ... Create the Comments db.relationship
	# relation to call destination.comments and comment.destination
    comments = db.relationship('Comment', back_populates='event', cascade='all, delete-orphan', passive_deletes=True)
    tags = db.relationship('Event_Tag', back_populates='event', cascade='all, delete-orphan', passive_deletes=True)
    images = db.relationship('Event_Image', back_populates='event', cascade='all, delete-orphan', passive_deletes=True)
    host = db.relationship('User', backref='hosted_events', foreign_keys=[host_user_id])
    
    __table_args__ = (
        CheckConstraint('(end_at IS NULL) OR (start_at IS NULL) OR (start_at <= end_at)', name='ck_event_time_order'), # stops an end date being before a start date
        CheckConstraint('(rsvp_closes IS NULL) OR (start_at IS NULL) OR (rsvp_closes <= start_at)', name='ck_rsvp_before_start'), # RSVP must close on/before the event start (never after it starts)
        CheckConstraint('capacity IS NULL OR capacity >= 0', name='ck_event_capacity_nonneg'), # Stops a capacity being set as a negative number - must be 0 or higher
    )
	
    # string print method
    def __repr__(self):
        return f"Name: {self.title}"

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)
    body = db.Column(db.Text, nullable=False)
    posted_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True))
    moderated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    moderation_reason = db.Column(db.String(160))
    
    event = db.relationship('Event', back_populates='comments')
    user = db.relationship('User', back_populates='comments', foreign_keys=[user_id])
    moderator = db.relationship('User', back_populates='moderated_comments', foreign_keys=[moderated_by_user_id])

    # string print method
    def __repr__(self):
        return f"Comment: {self.body}"
    
class TicketType(TimestampMixin, db.Model):
    __tablename__ = 'ticket_types'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    is_free = db.Column(db.Boolean, default=False, nullable=False)
    price = db.Column(db.Numeric(10,2), nullable=False)
    currency= db.Column(db.CHAR(3), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    sales_start_at = db.Column(db.DateTime(timezone=True))
    sales_end_at = db.Column(db.DateTime(timezone=True))
    
    __table_args__ = (
        CheckConstraint('capacity >= 0', name='ck_ticket_capacity_nonneg'), # can't have a negative capacity of tickets
        CheckConstraint('price >= 0', name='ck_ticket_price_nonneg'), # can't have a price that's a negative number
        CheckConstraint('is_free = FALSE OR price = 0', name='ck_ticket_free_means_zero'), # Ensure price is 0 if event is marked as free
        CheckConstraint(
            '(sales_start_at IS NULL) OR (sales_end_at IS NULL) OR (sales_start_at <= sales_end_at)',
            name='ck_ticket_sales_window'
        ), # can't have ticket sales end date be before the ticket sales start date
        CheckConstraint("length(currency) = 3", name='ck_currency_len_3'), # currency must be stored as 3 characters
    )
    
    # string print method
    def __repr__(self):
        return f"TicketType: {self.name} for Event: {self.event_id}"

class Booking(TimestampMixin, db.Model):
    __tablename__ = 'bookings'
    booking_id = db.Column(db.String(24), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    ticket_type_id = db.Column(db.Integer, db.ForeignKey('ticket_types.id', ondelete='RESTRICT'), index=True, nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_price   = db.Column(db.Numeric(10,2), nullable=False)
    total_amount = db.Column(db.Numeric(10,2), nullable=False)
    status = db.Column(BookingStatus, nullable=False, index=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        CheckConstraint('qty > 0', name='ck_booking_qty_positive'), # must have a positive number for the quantity
        CheckConstraint('unit_price >= 0', name='ck_booking_unit_price_nonneg'), # must have positive unit price
        CheckConstraint('total_amount >= 0', name='ck_booking_total_nonneg'),  # must have a positive total amount
    )
    
    user = db.relationship('User', backref='bookings')
    event = db.relationship('Event', backref='bookings')
    ticket_type = db.relationship('TicketType')
    
    # string print method
    def __repr__(self):
        return f"Order: {self.booking_id}"

class Payment(TimestampMixin, db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(24), db.ForeignKey('bookings.booking_id', ondelete='CASCADE'), index=True, nullable=False)
    provider= db.Column(db.String(20))
    method_brand= db.Column(db.String(20))
    method_last4= db.Column(db.String(4))
    amount = db.Column(db.Numeric(10,2), nullable=False)
    currency= db.Column(db.CHAR(3), nullable=False)
    status = db.Column(PaymentStatus, nullable=False, index=True)
    provider_charge_id= db.Column(db.String(80))
    authorised_at = db.Column(db.DateTime(timezone=True))
    captured_at = db.Column(db.DateTime(timezone=True))
    refunded_at = db.Column(db.DateTime(timezone=True))
    
    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_payment_amount_nonneg'), # must have a positive payment amount
        CheckConstraint("length(currency) = 3", name='ck_payment_currency_len_3'), # must have the currency in a 3-character format
    )
    
    # string print method
    def __repr__(self):
        return f"Payment: {self.id}"
    
class Event_Image(TimestampMixin, db.Model):
    __tablename__ = 'event_images'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), index=True, nullable=False)
    url = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(160))
    
    event = db.relationship('Event', back_populates='images')

    __table_args__ = (
        db.UniqueConstraint('event_id', 'url', name='uq_event_image_per_event'), # can't have duplicate event images in the same event
    )
    
    # string print method
    def __repr__(self):
        return f"Image: {self.url}"
    
class Event_Tag(db.Model):
    __tablename__ = 'event_tags'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False, index=True)
    
    event = db.relationship('Event', back_populates='tags')
    
    __table_args__ = (
        db.UniqueConstraint('event_id', 'tag_id', name='uq_event_tag'), # Can't have same tag applied twice to an event
    )
    
    # string print method
    def __repr__(self):
        return f"Tag: {self.tag_id}"
    
class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True)
    slug = db.Column(db.String(60), unique=True)
    
    # string print method
    def __repr__(self):
        return f"Tag: {self.name}"
    
    
#Indexing for improved performance

# Events list/sort/search
Index('ix_events_start_cancel', Event.start_at, Event.cancelled)
Index('ix_events_host_start', Event.host_user_id, Event.start_at)

# Bookings: user history & event sales
Index('ix_bookings_user_created', Booking.user_id, Booking.created_at.desc())
Index('ix_bookings_event_status', Booking.event_id, Booking.status)

# Payments: lookup by booking + status
Index('ix_payments_booking_status', Payment.booking_id, Payment.status)

# Tags: quick lookup by name/slug
Index('ix_tags_name', Tag.name)
Index('ix_tags_slug', Tag.slug)
