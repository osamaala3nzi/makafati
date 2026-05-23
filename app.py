from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, date
import calendar
import base64
import database as db

app = Flask(__name__)
app.secret_key = 'makafati-secret-2024'


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def current_user():
    return db.get_user_by_id(session['user_id'])


def get_smart_data(user_id, month, year, total_spent, monthly_reward, reward_day=25):
    today = date.today()
    days_in_month = calendar.monthrange(year, month)[1]

    if today.month == month and today.year == year:
        days_passed = today.day
    else:
        days_passed = days_in_month

    days_remaining = max(days_in_month - days_passed, 0)
    daily_rate = total_spent / days_passed if days_passed > 0 else 0
    predicted_total = daily_rate * days_in_month
    remaining = monthly_reward - total_spent

    days_until_empty = int(remaining / daily_rate) if daily_rate > 0 else 999

    spent_pct = (total_spent / monthly_reward * 100) if monthly_reward > 0 else 0
    time_pct = (days_passed / days_in_month * 100)
    danger = spent_pct >= 60 and time_pct < 40

    # Days until next reward
    reward_day_clamped = min(reward_day, days_in_month)
    if today.month == month and today.year == year:
        if today.day < reward_day_clamped:
            days_until_reward = reward_day_clamped - today.day
        elif today.day == reward_day_clamped:
            days_until_reward = 0
        else:
            nm = month + 1 if month < 12 else 1
            ny = year if month < 12 else year + 1
            next_days = calendar.monthrange(ny, nm)[1]
            next_rd = min(reward_day, next_days)
            days_until_reward = (date(ny, nm, next_rd) - today).days
    else:
        days_until_reward = None

    return {
        'days_passed': days_passed,
        'days_remaining': days_remaining,
        'days_in_month': days_in_month,
        'daily_rate': round(daily_rate, 1),
        'predicted_total': round(predicted_total, 1),
        'days_until_empty': days_until_empty,
        'spent_pct': round(spent_pct, 1),
        'time_pct': round(time_pct, 1),
        'danger': danger,
        'remaining': round(remaining, 1),
        'days_until_reward': days_until_reward,
        'reward_day': reward_day_clamped,
    }


# ─── Landing ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        student_type = request.form.get('student_type', 'مع أهل')
        monthly_reward = float(request.form.get('monthly_reward', 990))

        if not all([username, email, password]):
            flash('يرجى ملء جميع الحقول', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('كلمتا المرور غير متطابقتين', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'error')
            return render_template('register.html')

        reward_day = int(request.form.get('reward_day', 25))
        reward_day = max(1, min(28, reward_day))
        success, msg = db.create_user(username, email, password, student_type, monthly_reward, reward_day)
        if success:
            user = db.get_user_by_email(email)
            session['user_id'] = user['id']
            flash('مرحباً بك في مكافأتي! 🎉', 'success')
            return redirect(url_for('dashboard'))
        flash(msg, 'error')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = db.get_user_by_email(email)
        if user and db.verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            flash(f'أهلاً {user["username"]}! 👋', 'success')
            return redirect(url_for('dashboard'))
        flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    now = date.today()
    month, year = now.month, now.year

    budget = db.get_or_create_budget(user['id'], month, year, user['monthly_reward'])
    budget_cats = db.get_budget_with_categories(budget['id'])
    transactions = db.get_transactions(user['id'], limit=10)
    total_spent = db.get_total_spent(user['id'], month, year)
    spending_by_cat = db.get_monthly_spending_by_category(user['id'], month, year)
    achievements = db.get_achievements(user['id'])

    smart = get_smart_data(user['id'], month, year, total_spent, user['monthly_reward'], user['reward_day'])

    db.check_and_grant_achievements(user['id'], month, year)

    month_name_ar = [
        '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
        'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
    ][month]

    return render_template('dashboard.html',
        user=user,
        budget=budget,
        budget_cats=budget_cats,
        transactions=transactions,
        total_spent=round(total_spent, 1),
        spending_by_cat=spending_by_cat,
        smart=smart,
        achievements=achievements,
        month_name=month_name_ar,
        year=year,
        remaining=smart['remaining'],
    )


# ─── Transactions ─────────────────────────────────────────────────────────────

@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    user = current_user()
    categories = db.get_all_categories()
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount', '').strip()
        note = request.form.get('note', '').strip()
        tx_date = request.form.get('transaction_date', str(date.today()))

        if not category_id or not amount:
            flash('يرجى ملء جميع الحقول المطلوبة', 'error')
            return render_template('add_transaction.html', categories=categories)
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            flash('المبلغ يجب أن يكون رقماً موجباً', 'error')
            return render_template('add_transaction.html', categories=categories)

        db.add_transaction(user['id'], int(category_id), amount, note, tx_date)
        db.check_and_grant_achievements(user['id'], date.today().month, date.today().year)
        flash('تم تسجيل المصروف بنجاح ✅', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_transaction.html', categories=categories)


@app.route('/api/delete_transaction/<int:tx_id>', methods=['DELETE'])
@login_required
def delete_transaction(tx_id):
    success = db.delete_transaction(tx_id, session['user_id'])
    return jsonify({'success': success})


# ─── Goals ────────────────────────────────────────────────────────────────────

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    user = current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title', '').strip()
            target = request.form.get('target_amount', '').strip()
            target_date = request.form.get('target_date', '')
            icon = request.form.get('icon', '🎯')
            if title and target:
                try:
                    db.add_goal(user['id'], title, float(target), target_date or None, icon)
                    flash('تم إضافة الهدف بنجاح 🎯', 'success')
                except ValueError:
                    flash('المبلغ غير صحيح', 'error')
        elif action == 'add_savings':
            goal_id = request.form.get('goal_id')
            amount = request.form.get('amount', '').strip()
            if goal_id and amount:
                try:
                    db.update_goal_savings(int(goal_id), user['id'], float(amount))
                    flash('تم تحديث مدخراتك ✅', 'success')
                except ValueError:
                    flash('المبلغ غير صحيح', 'error')
        elif action == 'delete':
            goal_id = request.form.get('goal_id')
            if goal_id:
                db.delete_goal(int(goal_id), user['id'])
                flash('تم حذف الهدف', 'success')
        return redirect(url_for('goals'))

    all_goals = db.get_goals(user['id'])
    goals_data = []
    for g in all_goals:
        pct = min(100, round(g['saved_amount'] / g['target_amount'] * 100, 1)) if g['target_amount'] > 0 else 0
        remaining = g['target_amount'] - g['saved_amount']
        months_needed = 0
        monthly_savings = user['monthly_reward'] * 0.1  # assume 10% monthly saving
        if remaining > 0 and monthly_savings > 0:
            months_needed = max(1, round(remaining / monthly_savings))
        goals_data.append({**dict(g), 'pct': pct, 'remaining': round(remaining, 1), 'months_needed': months_needed})

    return render_template('goals.html', user=user, goals=goals_data)


# ─── Profile ──────────────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            student_type = request.form.get('student_type', '')
            monthly_reward = request.form.get('monthly_reward', '')
            reward_day = request.form.get('reward_day', '')

            kwargs = {}
            if username and username != user['username']:
                kwargs['username'] = username
            if email and email != user['email']:
                kwargs['email'] = email
            if student_type:
                kwargs['student_type'] = student_type
            if monthly_reward:
                try:
                    kwargs['monthly_reward'] = float(monthly_reward)
                except ValueError:
                    pass
            if reward_day:
                try:
                    kwargs['reward_day'] = max(1, min(28, int(reward_day)))
                except ValueError:
                    pass

            if kwargs:
                ok, msg = db.update_user(user['id'], **kwargs)
                flash(msg, 'success' if ok else 'error')
            else:
                flash('لا توجد تغييرات', 'error')

        elif action == 'update_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not db.verify_password(current_pw, user['password_hash']):
                flash('كلمة المرور الحالية غير صحيحة', 'error')
            elif len(new_pw) < 6:
                flash('كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل', 'error')
            elif new_pw != confirm_pw:
                flash('كلمتا المرور الجديدتان غير متطابقتين', 'error')
            else:
                db.update_user(user['id'], password=new_pw)
                flash('تم تغيير كلمة المرور بنجاح ✅', 'success')

        elif action == 'update_avatar':
            file = request.files.get('avatar_file')
            if file and file.filename:
                allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in allowed:
                    flash('نوع الملف غير مدعوم. استخدم PNG أو JPG', 'error')
                else:
                    data = file.read()
                    if len(data) > 2 * 1024 * 1024:
                        flash('حجم الصورة كبير جداً (الحد 2MB)', 'error')
                    else:
                        b64 = base64.b64encode(data).decode('utf-8')
                        avatar_data = f"data:image/{ext};base64,{b64}"
                        db.update_user(user['id'], avatar=avatar_data)
                        flash('تم تحديث الصورة الشخصية ✅', 'success')
            else:
                flash('يرجى اختيار صورة', 'error')

        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


# ─── Emergency Mode ───────────────────────────────────────────────────────────

@app.route('/api/emergency_mode', methods=['POST'])
@login_required
def emergency_mode():
    user = current_user()
    now = date.today()
    budget = db.get_or_create_budget(user['id'], now.month, now.year, user['monthly_reward'])
    conn = db.get_db()
    # Cut entertainment, clothing by 50%
    non_essential = ['ترفيه', 'ملابس', 'أخرى']
    for name in non_essential:
        conn.execute("""
            UPDATE budget_categories
            SET allocated_amount = allocated_amount * 0.5
            WHERE budget_id = ? AND category_id = (
                SELECT id FROM categories WHERE name = ?
            )
        """, (budget['id'], name))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم تفعيل وضع الطوارئ! تم تخفيض ميزانيات الترفيه والملابس 50%'})


# ─── Social comparison (anonymous averages) ───────────────────────────────────

@app.route('/api/averages')
@login_required
def averages():
    conn = db.get_db()
    now = date.today()
    rows = conn.execute("""
        SELECT c.name, c.color, AVG(t.amount) as avg_amount, COUNT(t.id) as count
        FROM transactions t JOIN categories c ON t.category_id = c.id
        WHERE strftime('%m', t.transaction_date) = ? AND strftime('%Y', t.transaction_date) = ?
        GROUP BY c.id
    """, (f"{now.month:02d}", str(now.year))).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == '__main__':
    db.init_db()
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
else:
    # Called by gunicorn
    db.init_db()
