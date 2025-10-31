from flask import Blueprint, flash, render_template, request, url_for, redirect, current_app, abort
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from .models import User
from werkzeug.utils import secure_filename
from .forms import LoginForm, RegisterForm, ProfileForm, LogoutForm
import os
from uuid import uuid4
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
            
        pic_rel_path = None
        file = form.profile_pic.data
        if file:
            uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'profiles')
            os.makedirs(uploads_dir, exist_ok=True)
            filename = secure_filename(f"{uuid4().hex}_{file.filename}")
            abs_path = os.path.join(uploads_dir, filename)
            file.save(abs_path)
            pic_rel_path = f"uploads/profiles/{filename}"

        user = User(name=user_name, email=email, password_hash=generate_password_hash(form.password.data), mobile=mobile_val or None, first_name=form.first_name.data.strip(),last_name=form.last_name.data.strip(), street_address=(form.street_address.data or '').strip() or None, profile_pic_path=pic_rel_path)
        if hasattr(user, 'mobile') and mobile_val:
            user.mobile = mobile_val

        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registration successful. Welcome!', 'success')
        return redirect(url_for('main.index'))
    return render_template('register.html', form=form)

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    form = LogoutForm()
    if not form.validate_on_submit():
        abort(400)
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()

    # prefill from current_user on GET
    if request.method == 'GET':
        form.user_name.data = current_user.name
        form.email.data = current_user.email or ''
        form.first_name.data = current_user.first_name or ''
        form.last_name.data = current_user.last_name or ''
        form.contact_number.data = current_user.mobile or ''
        form.street_address.data = current_user.street_address or ''

    if form.validate_on_submit():
        # Uniqueness checks
        new_name = form.user_name.data.strip()
        new_email = form.email.data.strip().lower()

        name_taken = db.session.scalar(
            db.select(User).where(User.name == new_name, User.id != current_user.id)
        )
        if name_taken:
            flash('User name is already taken.', 'warning')
            return render_template('profile.html', form=form, user=current_user)

        email_taken = db.session.scalar(
            db.select(User).where(User.email == new_email, User.id != current_user.id)
        )
        if email_taken:
            flash('An account with that email already exists.', 'warning')
            return render_template('profile.html', form=form, user=current_user)

        # Update basic fields
        current_user.name = new_name
        current_user.email = new_email
        current_user.first_name = form.first_name.data.strip()
        current_user.last_name  = form.last_name.data.strip()
        current_user.mobile = (form.contact_number.data or '').strip() or None
        current_user.street_address = (form.street_address.data or '').strip() or None

        # Password change
        wants_pw_change = any([
            form.current_password.data,
            form.new_password.data,
            form.confirm_new_password.data
        ])

        if wants_pw_change:
            # Require all fields
            if not (form.current_password.data and form.new_password.data and form.confirm_new_password.data):
                flash('To change your password, please fill current, new, and confirm fields.', 'warning')
                return render_template('profile.html', form=form, user=current_user)

            # Verify current password
            if not check_password_hash(current_user.password_hash, form.current_password.data):
                flash('Current password is incorrect.', 'danger')
                return render_template('profile.html', form=form, user=current_user)

            current_user.password_hash = generate_password_hash(form.new_password.data)

        # Profile picture logic
        file = form.profile_pic.data
        remove_requested = form.remove_profile_pic.data

        uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'profiles')
        os.makedirs(uploads_dir, exist_ok=True)

        def _delete_old():
            if current_user.profile_pic_path:
                try:
                    os.remove(os.path.join(current_app.static_folder, current_user.profile_pic_path))
                except Exception:
                    pass

        if file:
            # Replace
            filename = secure_filename(f"{uuid4().hex}_{file.filename}")
            abs_path = os.path.join(uploads_dir, filename)
            file.save(abs_path)
            _delete_old()
            current_user.profile_pic_path = f"uploads/profiles/{filename}"
        elif remove_requested:
            # Remove only if no new file supplied
            _delete_old()
            current_user.profile_pic_path = None

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('profile.html', form=form, user=current_user)