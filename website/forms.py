from flask_wtf import FlaskForm
from wtforms.fields import TextAreaField, SubmitField, StringField, PasswordField, DateField, TimeField, FileField, DecimalField, SelectField, DateTimeField
from wtforms.validators import InputRequired, Length, Email, EqualTo, DataRequired

# creates the login information
class LoginForm(FlaskForm):
    user_name=StringField("User Name", validators=[InputRequired('Enter user name')])
    password=PasswordField("Password", validators=[InputRequired('Enter user password')])
    submit = SubmitField("Login")

 # this is the registration form
class RegisterForm(FlaskForm):
    user_name=StringField("User Name", validators=[InputRequired()])
    email = StringField("Email Address", validators=[Email("Please enter a valid email")])
    # linking two fields - password should be equal to data entered in confirm
    password=PasswordField("Password", validators=[InputRequired(),
                  EqualTo('confirm', message="Passwords should match")])
    confirm = PasswordField("Confirm Password")

    # submit button
    submit = SubmitField("Register")

class CreateEventForm(FlaskForm):
    title=StringField("Title", validators=[InputRequired(), Length(min=3, max=160)])
    description=TextAreaField("Description", validators=[InputRequired(), Length(min=3)])
    category=SelectField("Category", choices=[('', 'Choose...'),('Tech & AI', 'Tech & AI'), ('Marketing', 'Marketing'), ('Finance', 'Finance'), ('Health', 'Health'), ('Education', 'Education')], validators=[DataRequired(message="Please select a category.")])
    format=SelectField("Format", choices=[('', 'Choose...'),('In-person', 'In-person'), ('Virtual', 'Virtual'), ('Hybrid', 'Hybrid')], validators=[DataRequired(message="Please select a format.")])
    date=DateField("Date", validators=[InputRequired()], format='%Y-%m-%d') 
    start_time = TimeField("Start Time", format='%H:%M', validators=[InputRequired()]) #getting rid of the 12-hour format because its a struggle to use
    end_time = TimeField("End Time", format='%H:%M', validators=[InputRequired()])
    timezone = SelectField('Timezone', choices=[
        ("(GMT +8:00) Perth", "(GMT +8:00) Perth"),
        ("(GMT +9:30) Adelaide", "(GMT +9:30) Adelaide"),
        ("(GMT +10:00) Sydney (AEST/AEDT)", "(GMT +10:00) Sydney (AEST/AEDT)"),
        ("(GMT +10:00) Brisbane (AEST)", "(GMT +10:00) Brisbane (AEST)"),
        ("(GMT -12:00) Eniwetok, Kwajalein", "(GMT -12:00) Eniwetok, Kwajalein"),
        ("(GMT -11:00) Midway Island, Samoa", "(GMT -11:00) Midway Island, Samoa"),
        ("(GMT -10:00) Hawaii", "(GMT -10:00) Hawaii"),
        ("(GMT -9:30) Taiohae", "(GMT -9:30) Taiohae"),
        ("(GMT -9:00) Alaska", "(GMT -9:00) Alaska"),
        ("(GMT -8:00) Pacific Time (US & Canada)", "(GMT -8:00) Pacific Time (US & Canada)"),
        ("(GMT -7:00) Mountain Time (US & Canada)", "(GMT -7:00) Mountain Time (US & Canada)"),
        ("(GMT -6:00) Central Time (US & Canada), Mexico City", "(GMT -6:00) Central Time (US & Canada), Mexico City"),
        ("(GMT -5:00) Eastern Time (US & Canada), Bogota, Lima", "(GMT -5:00) Eastern Time (US & Canada), Bogota, Lima"),
        ("(GMT -4:30) Caracas", "(GMT -4:30) Caracas"),
        ("(GMT -4:00) Atlantic Time (Canada), La Paz", "(GMT -4:00) Atlantic Time (Canada), La Paz"),
        ("(GMT -3:30) Newfoundland", "(GMT -3:30) Newfoundland"),
        ("(GMT -3:00) Brazil, Buenos Aires, Georgetown", "(GMT -3:00) Brazil, Buenos Aires, Georgetown"),
        ("(GMT -2:00) Mid-Atlantic", "(GMT -2:00) Mid-Atlantic"),
        ("(GMT -1:00) Azores, Cape Verde Islands", "(GMT -1:00) Azores, Cape Verde Islands"),
        ("(GMT) Western Europe Time, London, Lisbon, Casablanca", "(GMT) Western Europe Time, London, Lisbon, Casablanca"),
        ("(GMT +1:00) Brussels, Copenhagen, Madrid, Paris", "(GMT +1:00) Brussels, Copenhagen, Madrid, Paris"),
        ("(GMT +2:00) Kaliningrad, South Africa", "(GMT +2:00) Kaliningrad, South Africa"),
        ("(GMT +3:00) Baghdad, Riyadh, Moscow, St. Petersburg", "(GMT +3:00) Baghdad, Riyadh, Moscow, St. Petersburg"),
        ("(GMT +3:30) Tehran", "(GMT +3:30) Tehran"),
        ("(GMT +4:00) Abu Dhabi, Muscat, Baku, Tbilisi", "(GMT +4:00) Abu Dhabi, Muscat, Baku, Tbilisi"),
        ("(GMT +4:30) Kabul", "(GMT +4:30) Kabul"),
        ("(GMT +5:00) Ekaterinburg, Islamabad, Karachi, Tashkent", "(GMT +5:00) Ekaterinburg, Islamabad, Karachi, Tashkent"),
        ("(GMT +5:30) Bombay, Calcutta, Madras, New Delhi", "(GMT +5:30) Bombay, Calcutta, Madras, New Delhi"),
        ("(GMT +5:45) Kathmandu, Pokhara", "(GMT +5:45) Kathmandu, Pokhara"),
        ("(GMT +6:00) Almaty, Dhaka, Colombo", "(GMT +6:00) Almaty, Dhaka, Colombo"),
        ("(GMT +6:30) Yangon, Mandalay", "(GMT +6:30) Yangon, Mandalay"),
        ("(GMT +7:00) Bangkok, Hanoi, Jakarta", "(GMT +7:00) Bangkok, Hanoi, Jakarta"),
        ("(GMT +8:45) Eucla", "(GMT +8:45) Eucla"),
        ("(GMT +9:00) Tokyo, Seoul, Osaka, Sapporo, Yakutsk", "(GMT +9:00) Tokyo, Seoul, Osaka, Sapporo, Yakutsk"),
        ("(GMT +10:30) Lord Howe Island", "(GMT +10:30) Lord Howe Island"),
        ("(GMT +11:00) Magadan, Solomon Islands, New Caledonia", "(GMT +11:00) Magadan, Solomon Islands, New Caledonia"),
        ("(GMT +11:30) Norfolk Island", "(GMT +11:30) Norfolk Island"),
        ("(GMT +12:00) Auckland, Wellington, Fiji, Kamchatka", "(GMT +12:00) Auckland, Wellington, Fiji, Kamchatka"),
        ("(GMT +12:45) Chatham Islands", "(GMT +12:45) Chatham Islands"),
        ("(GMT +13:00) Apia, Nukualofa", "(GMT +13:00) Apia, Nukualofa"),
        ("(GMT +14:00) Line Islands, Tokelau", "(GMT +14:00) Line Islands, Tokelau"),
    ], default="(GMT +10:00) Brisbane (AEST)")
    location=StringField("Location", validators=[InputRequired(), Length(min=3, max=200)])
    capacity=StringField("Capacity", validators=[InputRequired(), Length(min=1, max=8)])
    event_image=FileField("Image", validators=[InputRequired()])
    image_alt_text=StringField("Image Alt Text", validators=[Length(max=255)])
    ticket_price=DecimalField("Ticket Price", places=2, rounding=None)
    rsvp_closes=DateTimeField("RSVP Closing Date", format='%Y-%m-%dT%H:%M', validators=[InputRequired()])
    host_name=StringField("Host Name", validators=[InputRequired(), Length(min=3, max=120)])
    host_contact=StringField("Host Contact Email", validators=[InputRequired(), Email("Please enter a valid email")])
    #CSS Modal handles these

    #submit = SubmitField("Publish")
    #draft = SubmitField("Save as Draft")
    #schedule = SubmitField("Schedule")
    #reset = SubmitField("Reset")