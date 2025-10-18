from flask import Blueprint, flash, render_template, request, url_for, redirect
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from .models import User
from .forms import LoginForm, RegisterForm
from . import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_name = form.user_name.data.strip()
        password = form.password.data
        user = db.session.scalar(db.select(User).where(User.name == user_name))
        if user is None:
            flash('Incorrect user name', 'danger')
        elif not check_password_hash(user.password_hash, password):
            flash('Incorrect password', 'danger')
        else:
            login_user(user)
            nextp = request.args.get('next')
            if not nextp or not nextp.startswith('/'):
                return redirect(url_for('main.index'))
            return redirect(nextp)
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        user_name = form.user_name.data.strip()
        email = form.email.data.strip().lower() if getattr(form, 'email', None) else None
        mobile = getattr(form, 'contact_number', None)
        mobile_val = mobile.data.strip() if mobile else None

        exists = db.session.scalar(db.select(User).where(User.name == user_name))
        if exists:
            flash('User name is already taken.', 'warning')
            return render_template('register.html', form=form)

        if email:
            mail_exists = db.session.scalar(db.select(User).where(User.email == email))
            if mail_exists:
                flash('An account with that email already exists.', 'warning')
                return render_template('register.html', form=form)

        user = User(name=user_name, email=email, password_hash=generate_password_hash(form.password.data))
        if hasattr(user, 'mobile') and mobile_val:
            user.mobile = mobile_val

        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registration successful. Welcome!', 'success')
        return redirect(url_for('main.index'))
    return render_template('register.html', form=form)

@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))