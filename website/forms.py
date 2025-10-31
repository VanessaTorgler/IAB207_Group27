from flask_wtf import FlaskForm
from wtforms.fields import TextAreaField, SubmitField, StringField, PasswordField, DateField, TimeField, FileField, DecimalField, SelectField, DateTimeField, BooleanField
from datetime import datetime
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, InputRequired, ValidationError, AnyOf
from werkzeug.utils import secure_filename
from flask_wtf.file import FileAllowed
from wtforms import HiddenField
import os, time, uuid

# creates the login information
class LoginForm(FlaskForm):
    user_name=StringField("User Name", validators=[InputRequired('Enter user name')])
    password=PasswordField("Password", validators=[InputRequired('Enter user password')])
    submit = SubmitField("Login")

# comment form
class CommentForm(FlaskForm):
    comment=TextAreaField("Your Comment:", validators=[InputRequired(), Length(min=1, max=500)])
    submit = SubmitField("Post Comment")
    
 # this is the registration form
class RegisterForm(FlaskForm):
    user_name=StringField("User Name", validators=[InputRequired()])
    email = StringField("Email Address", validators=[DataRequired(), Email("Please enter a valid email")])
    # linking two fields - password should be equal to data entered in confirm
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=36)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    contact_number = StringField('Contact Number', validators=[DataRequired(), Length(max=32)])
    street_address = StringField('Street Address', validators=[DataRequired(), Length(max=160)])
    profile_pic = FileField('Profile Picture (optional)', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only')])

    # submit button
    submit = SubmitField("Register")
    
# logout form    
class LogoutForm(FlaskForm):
    pass

class CreateEventForm(FlaskForm):
    title=StringField("Title", validators=[InputRequired(), Length(min=3, max=160, message="Title must be between 3 and 160 characters long.")])
    description=TextAreaField("Description", validators=[InputRequired(), Length(min=3, message="Description must be at least 3 characters long.")])
    category=SelectField("Category", choices=[('', 'Choose...'),('Tech & AI', 'Tech & AI'), ('Marketing', 'Marketing'), ('Finance', 'Finance'), ('Health', 'Health'), ('Education', 'Education')], validators=[DataRequired(message="Please select a category.")])
    format=SelectField("Format", choices=[('', 'Choose...'),('In-person', 'In-person'), ('Virtual', 'Virtual'), ('Hybrid', 'Hybrid')], validators=[DataRequired(message="Please select a format.")])
    date=DateField("Date", validators=[InputRequired()], format='%Y-%m-%d') 
    start_time = TimeField("Start Time", format='%H:%M', validators=[InputRequired()])
    end_time = TimeField("End Time", format='%H:%M', validators=[InputRequired()])
    location=StringField("Location", validators=[InputRequired(), Length(min=3, max=200, message="Location must be between 3 and 200 characters long.")])
    capacity=StringField("Capacity", validators=[InputRequired(), Length(min=1, max=8, message="Capacity must be between 1 and 8 characters long.")])
    event_image=FileField("Image", validators=[InputRequired()])
    image_alt_text=StringField("Image Alt Text", validators=[Length(max=255, message="Alt Text cannot exceed 255 characters.")])
    ticket_price=DecimalField("Ticket Price", places=2, rounding=None)
    rsvp_closes=DateTimeField("RSVP Closing Date", format='%Y-%m-%dT%H:%M', validators=[InputRequired()])
    host_name=StringField("Host Name", validators=[InputRequired(), Length(min=3, max=120)])
    host_contact=StringField("Host Contact Email", validators=[InputRequired(), Email("Please enter a valid email")])
    #CSS Modal handles these

    #submit = SubmitField("Publish")
    #reset = SubmitField("Reset")
    def validate_end_time(self, field):
        if self.start_time.data and field.data:
            if field.data <= self.start_time.data:
                raise ValidationError("End Time must be after Start Time.")

    def validate_rsvp_closes(self, field):
        if self.date.data and field.data and self.start_time.data:
            event_datetime = datetime.combine(self.date.data, self.start_time.data)
            if field.data >= event_datetime:
                raise ValidationError("RSVP Closing Date must be before the event start date and time.")

    def validate_date(self, field):
        if field.data:
            if field.data < datetime.today().date():
                raise ValidationError("Event date must be in the future.")
            
def check_upload_file(form):
    # get file data from form
    fp = form.event_image.data
    filename = secure_filename(fp.filename or "")
    if not filename:
        return None

    # allow-list by extension
    ALLOWED = {'.jpg', '.jpeg', '.png', '.webp'}
    root, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED:
        return None

    # unique filename to avoid collisions / caching issues
    unique_name = f"{root}_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    
    
    # get the current path of the module file… store image file relative to this path  
    BASE_PATH = os.path.dirname(__file__)
    # upload file location – directory of this file/static/img
    upload_dir = os.path.join(BASE_PATH, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    # store relative path in DB as image location in HTML is relative
    upload_path = os.path.join(upload_dir, unique_name)
    # save the file and return the db upload path  
    fp.save(upload_path)
    return f"/static/uploads/{unique_name}"


class ProfileForm(FlaskForm):
    # keep validations consistent with registration
    user_name = StringField('User Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=254)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name  = StringField('Last Name',  validators=[DataRequired(), Length(max=80)])
    contact_number = StringField('Contact Number', validators=[DataRequired(), Length(max=32)])
    street_address = StringField('Street Address', validators=[DataRequired(), Length(max=160)])

    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=8, max=36)])
    confirm_new_password = PasswordField('Confirm New Password',
                                         validators=[Optional(), EqualTo('new_password', message='Passwords must match')])

    # profile pic controls
    profile_pic = FileField('Replace Profile Picture',
                            validators=[Optional(), FileAllowed(['jpg','jpeg','png','gif'], 'Images only')])
    remove_profile_pic = BooleanField('Remove current picture')
    submit = SubmitField('Save changes')
    
class EventActionForm(FlaskForm):
    action = HiddenField(validators=[DataRequired(), AnyOf(['cancel', 'publish'])])
    
class BookingForm(FlaskForm):
    qty = StringField('Quantity', validators=[InputRequired(), Length(min=1, max=3)])
