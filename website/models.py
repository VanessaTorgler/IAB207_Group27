from . import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Numeric



class User(db.Model, UserMixin):
    __tablename__ = 'users' # good practice to specify table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), index=True, unique=True, nullable=False)
    email = db.Column(db.String(254), index=True, nullable=False, unique=True)
    mobile = db.Column(db.String(32), index=True)
	# password should never stored in the DB, an encrypted password is stored
	# the storage should be at least 255 chars long, depending on your hashing algorithm
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    # relation to call user.comments and comment.created_by
    comments = db.relationship('Comment', backref='user')
    
    # string print method
    def __repr__(self):
        return f"Name: {self.name}"

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(160))
    description = db.Column(db.Text)
    event_type = db.Column(db.String(40))
    event_timezone = db.Column(db.String(64))
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    location_type = db.Column(db.String(16))
    location_text = db.Column(db.String(200))
    join_url = db.Column(db.String(255))
    join_url_release_at = db.Column(db.DateTime)
    capacity = db.Column(db.Integer)
    cancelled = db.Column(db.Boolean, default=False)
    # ... Create the Comments db.relationship
	# relation to call destination.comments and comment.destination
    comments = db.relationship('Comment', backref='destination')
	
    # string print method
    def __repr__(self):
        return f"Name: {self.title}"

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    body = db.Column(db.Text, nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.now())
    edited_at = db.Column(db.DateTime, onupdate=datetime.now())
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    moderated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    moderation_reason = db.Column(db.String(160))

    # string print method
    def __repr__(self):
        return f"Comment: {self.body}"
class TicketType(db.Model):
    __tablename__ = 'ticket_types'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    name = db.Column(db.String(80))
    is_free = db.Column(db.Boolean, default=False)
    price = db.Column(db.Numeric(10,2))
    currency= db.Column(db.CHAR(3))
    capacity = db.Column(db.Integer)
    sales_start_at = db.Column(db.DateTime)
    sales_end_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    
    # string print method
    def __repr__(self):
        return f"TicketType: {self.name} for Event: {self.event_id}"

class Booking(db.Model):
    __tablename__ = 'bookings'
    booking_id = db.Column(db.String(24), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ticket_type = db.Column(db.Integer, db.ForeignKey('ticket_types.id'))
    qty=db.Column(db.Integer)
    total_amount = db.Column(db.Numeric(10,2))
    status= db.Column(db.String(12))
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # string print method
    def __repr__(self):
        return f"Order: {self.booking_id}"

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'))
    provider= db.Column(db.String(20))
    method_brand= db.Column(db.String(20))
    method_last4= db.Column(db.String(4))
    amount = db.Column(db.Numeric(10,2))
    currency= db.Column(db.CHAR(3))
    status= db.Column(db.String(12))
    provider_charge_id= db.Column(db.String(80))
    authorised_at = db.Column(db.DateTime)
    captured_at = db.Column(db.DateTime)
    refunded_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    
    # string print method
    def __repr__(self):
        return f"Payment: {self.id}"
    
class event_images(db.Model):
    __tablename__ = 'event_images'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id')) #add the unique, or nah?
    url = db.Column(db.String(255))
    alt_text = db.Column(db.String(160))
    created_at = db.Column(db.DateTime, default=datetime.now())
    
    # string print method
    def __repr__(self):
        return f"Image: {self.url}"
    
class event_tags(db.Model):
    __tablename__ = 'event_tags'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'))
    
    # string print method
    def __repr__(self):
        return f"Tag: {self.tag_id}"
    
class tags(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True)
    slug = db.Column(db.String(60), unique=True)
    
    # string print method
    def __repr__(self):
        return f"Tag: {self.name}"
    
