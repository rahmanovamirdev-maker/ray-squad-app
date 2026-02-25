from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import io
import string
import random
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from pyngrok import ngrok

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

db = SQLAlchemy(app)

# Модель для хранения анкет
class Applicant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.String(50))
    english_level = db.Column(db.String(500))
    cpu_model = db.Column(db.String(200))
    gpu_model = db.Column(db.String(200))
    internet_speed = db.Column(db.String(100))
    work_experience = db.Column(db.String(500))
    interview_time = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False)
    telegram = db.Column(db.String(100))
    date_added = db.Column(db.DateTime, default=datetime.now)
    owner_username = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth,
            'english_level': self.english_level,
            'cpu_model': self.cpu_model,
            'gpu_model': self.gpu_model,
            'internet_speed': self.internet_speed,
            'work_experience': self.work_experience,
            'interview_time': self.interview_time,
            'phone': self.phone,
            'telegram': self.telegram,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M'),
            'owner_username': self.owner_username,
            'status': self.status
        }

# Модель пользователей
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(120))
    bio = db.Column(db.String(500))
    avatar_url = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, default=False)
    is_owner = db.Column(db.Boolean, default=False)  # Владелец - полный доступ
    is_guest = db.Column(db.Boolean, default=False)
    can_submit = db.Column(db.Boolean, default=True)  # Может ли отправлять ответы
    crypto_wallet = db.Column(db.String(200))  # Крипто кошелек
    earned_amount = db.Column(db.Float, default=0.0)  # Заработанная сумма
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login_at = db.Column(db.DateTime)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Модель для вопросов отбора
class SelectionQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(1000), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'question_text': self.question_text,
            'order': self.order
        }

# Модель для ответов гостей
class GuestAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    guest_name = db.Column(db.String(100), nullable=False)
    guest_tg = db.Column(db.String(100))
    guest_phone = db.Column(db.String(20))
    question_id = db.Column(db.Integer, db.ForeignKey('selection_question.id'), nullable=False)
    answer_text = db.Column(db.String(5000), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    approved = db.Column(db.Boolean, default=False)

    def to_dict(self):
        question = SelectionQuestion.query.get(self.question_id)
        return {
            'id': self.id,
            'user_id': self.user_id,
            'guest_name': self.guest_name,
            'guest_tg': self.guest_tg,
            'guest_phone': self.guest_phone,
            'question_id': self.question_id,
            'question_text': question.question_text if question else '',
            'answer_text': self.answer_text,
            'submitted_at': self.submitted_at.strftime('%d.%m.%Y %H:%M'),
            'approved': self.approved
        }

# Модель для сообщений в чате
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ID пользователя-гостя
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_name = db.Column(db.String(100))
    message_text = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    # Оставляем для совместимости со старыми данными
    answer_id = db.Column(db.Integer, db.ForeignKey('guest_answer.id'), nullable=True)

    def to_dict(self):
        sender = User.query.get(self.sender_id)
        return {
            'id': self.id,
            'guest_user_id': self.guest_user_id,
            'sender_id': self.sender_id,
            'sender_name': sender.username if sender else self.sender_name,
            'message_text': self.message_text,
            'created_at': self.created_at.strftime('%d.%m.%Y %H:%M:%S'),
            'is_admin': sender.is_admin if sender else False
        }

# Модель для слотов собеседований
class InterviewSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        start_str = self.start_time.strftime('%d.%m.%Y %H:%M')
        end_str = self.end_time.strftime('%d.%m.%Y %H:%M') if self.end_time else None
        return {
            'id': self.id,
            'start_time': start_str,
            'end_time': end_str,
            'is_open': self.is_open
        }

# Модель для истории синхронизации статусов с внешним API


# Создание таблиц
with app.app_context():
    db.create_all()
    # If owner_username column doesn't exist in the table (older DB), try to add it
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        if 'applicant' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applicant')]
            if 'owner_username' not in cols:
                # SQLite supports simple ALTER TABLE ADD COLUMN
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN owner_username VARCHAR(100)"))
                db.session.commit()
            if 'interview_time' not in cols:
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN interview_time VARCHAR(100)"))
                db.session.commit()
        if 'user' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('user')]
            if 'display_name' not in cols:
                print("[MIGRATION] Добавляю столбец display_name в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN display_name VARCHAR(120)"))
                db.session.commit()
                print("[MIGRATION] Столбец display_name добавлен успешно")
            if 'bio' not in cols:
                print("[MIGRATION] Добавляю столбец bio в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN bio VARCHAR(500)"))
                db.session.commit()
                print("[MIGRATION] Столбец bio добавлен успешно")
            if 'avatar_url' not in cols:
                print("[MIGRATION] Добавляю столбец avatar_url в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN avatar_url VARCHAR(500)"))
                db.session.commit()
                print("[MIGRATION] Столбец avatar_url добавлен успешно")
            if 'last_login_at' not in cols:
                print("[MIGRATION] Добавляю столбец last_login_at в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN last_login_at DATETIME"))
                db.session.commit()
                print("[MIGRATION] Столбец last_login_at добавлен успешно")
            if 'is_guest' not in cols:
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_guest BOOLEAN DEFAULT 0"))
                db.session.commit()
            if 'is_owner' not in cols:
                print("[MIGRATION] Добавляю столбец is_owner в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_owner BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[MIGRATION] Столбец is_owner добавлен успешно")
            if 'can_submit' not in cols:
                print("[MIGRATION] Добавляю столбец can_submit в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN can_submit BOOLEAN DEFAULT 1"))
                db.session.commit()
                print("[MIGRATION] Столбец can_submit добавлен успешно")
        if 'guest_answer' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('guest_answer')]
            if 'user_id' not in cols:
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN user_id INTEGER"))
                db.session.commit()
            if 'guest_tg' not in cols:
                print("[MIGRATION] Добавляю столбец guest_tg в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_tg VARCHAR(100)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_tg добавлен успешно")
            if 'guest_phone' not in cols:
                print("[MIGRATION] Добавляю столбец guest_phone в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_phone VARCHAR(20)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_phone добавлен успешно")
            if 'approved' not in cols:
                print("[MIGRATION] Добавляю столбец approved в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN approved BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[MIGRATION] Столбец approved добавлен успешно")
        if 'interview_slot' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('interview_slot')]
            if 'is_open' not in cols:
                print("[MIGRATION] Добавляю столбец is_open в таблицу interview_slot...")
                db.session.execute(text("ALTER TABLE interview_slot ADD COLUMN is_open BOOLEAN DEFAULT 1"))
                db.session.commit()
                print("[MIGRATION] Столбец is_open добавлен успешно")
        # Таблица Message должна быть создана автоматически через db.create_all()
        if 'message' not in insp.get_table_names():
            print("[INFO] Таблица Message будет создана при следующей миграции")
        else:
            # Проверяем и мигрируем структуру таблицы message
            message_cols = [c['name'] for c in insp.get_columns('message')]
            if 'guest_user_id' not in message_cols:
                print("[MIGRATION] Пересоздаю таблицу message с новой схемой...")
                # Сохраняем старые данные
                db.session.execute(text("""
                    CREATE TABLE message_backup AS SELECT * FROM message
                """))
                # Удаляем старую таблицу
                db.session.execute(text("DROP TABLE message"))
                # Создаём новую таблицу с правильной схемой
                db.session.execute(text("""
                    CREATE TABLE message (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        guest_user_id INTEGER NOT NULL,
                        sender_id INTEGER NOT NULL,
                        sender_name VARCHAR(100),
                        message_text VARCHAR(2000) NOT NULL,
                        created_at DATETIME,
                        answer_id INTEGER,
                        FOREIGN KEY(guest_user_id) REFERENCES user (id),
                        FOREIGN KEY(sender_id) REFERENCES user (id),
                        FOREIGN KEY(answer_id) REFERENCES guest_answer (id)
                    )
                """))
                # Копируем старые данные, получая guest_user_id из answer_id
                db.session.execute(text("""
                    INSERT INTO message (id, guest_user_id, sender_id, sender_name, message_text, created_at, answer_id)
                    SELECT m.id, 
                           COALESCE(ga.user_id, m.sender_id) as guest_user_id,
                           m.sender_id, 
                           m.sender_name, 
                           m.message_text, 
                           m.created_at, 
                           m.answer_id
                    FROM message_backup m
                    LEFT JOIN guest_answer ga ON m.answer_id = ga.id
                """))
                # Удаляем бэкап
                db.session.execute(text("DROP TABLE message_backup"))
                db.session.commit()
                print("[MIGRATION] Таблица message успешно обновлена")
    except Exception as e:
        # If anything fails, continue — application can still run, but admin should be informed
        print(f"[MIGRATION ERROR] {str(e)}")
        pass

    # Ensure admin user exists
    try:
        # users table is created by db.create_all()
        admin = User.query.filter_by(username='FLOWXZ').first()
        if not admin:
            admin = User(username='FLOWXZ', password_hash=generate_password_hash('qwertyuiopasd'), is_admin=True, is_owner=True)
            db.session.add(admin)
            db.session.commit()
            print("[INFO] Владелец FLOWXZ создан")
        elif not admin.is_owner:
            # Устанавливаем существующему админу статус владельца
            admin.is_owner = True
            admin.is_admin = True
            db.session.commit()
            print("[INFO] FLOWXZ установлен как Владелец")
    except Exception as e:
        print(f"[ADMIN USER ERROR] {str(e)}")
        pass

    # Ensure default questions exist
    try:
        question_count = SelectionQuestion.query.count()
        if question_count == 0:
            # Добавляем первый вопрос
            q1 = SelectionQuestion(question_text='Какие риски?', order=1)
            db.session.add(q1)
            db.session.commit()
    except Exception as e:
        print(f"[DEFAULT QUESTION ERROR] {str(e)}")
        pass

# Логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ==================== ФУНКЦИИ ДЛЯ СИНХРОНИЗАЦИИ СТАТУСОВ ====================



# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    page = request.args.get('page', 1, type=int)
    if user and user.is_admin:
        applicants = Applicant.query.order_by(Applicant.date_added.desc()).paginate(page=page, per_page=10)
    else:
        applicants = Applicant.query.filter_by(owner_username=user.username).order_by(Applicant.date_added.desc()).paginate(page=page, per_page=10)
    return render_template('index.html', applicants=applicants, current_user=user)

@app.route('/manual')
def manual():
    """Страница с мануалом"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('manual.html', current_user=user)

@app.route('/api/add-applicant', methods=['POST'])
def add_applicant():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        data = request.json

        slot_id = data.get('interview_slot_id')
        interview_time_value = (data.get('interview_time', '') or '').strip()

        open_slots_count = InterviewSlot.query.filter_by(is_open=True).count()
        if open_slots_count == 0:
            return jsonify({'success': False, 'message': 'Сейчас нет открытых слотов для собеседования'}), 400

        if not slot_id and not interview_time_value:
            return jsonify({'success': False, 'message': 'Укажите время собеседования'}), 400

        if interview_time_value and not slot_id:
            try:
                requested_dt = datetime.strptime(interview_time_value, '%d.%m.%Y %H:%M')
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Неверный формат времени. Используйте ДД.ММ.ГГГГ ЧЧ:ММ'
                }), 400

            open_slots = InterviewSlot.query.filter_by(is_open=True).all()
            slot_match = False
            for slot in open_slots:
                start = slot.start_time
                end = slot.end_time or slot.start_time
                if start <= requested_dt <= end:
                    slot_match = True
                    break

            if not slot_match:
                return jsonify({
                    'success': False,
                    'message': 'Нет свободных слотов на эту дату'
                }), 400

        if slot_id:
            slot = InterviewSlot.query.get(slot_id)
            if not slot or not slot.is_open:
                return jsonify({'success': False, 'message': 'Выбранный слот уже закрыт'}), 400
            start_str = slot.start_time.strftime('%d.%m.%Y %H:%M')
            if slot.end_time:
                end_str = slot.end_time.strftime('%d.%m.%Y %H:%M')
                interview_time_value = f"{start_str} - {end_str}"
            else:
                interview_time_value = start_str

        new_applicant = Applicant(
            full_name=data.get('full_name', ''),
            date_of_birth=data.get('date_of_birth', ''),
            english_level=data.get('english_level', ''),
            cpu_model=data.get('cpu_model', ''),
            gpu_model=data.get('gpu_model', ''),
            internet_speed=data.get('internet_speed', ''),
            work_experience=data.get('work_experience', ''),
            interview_time=interview_time_value,
            phone=data.get('phone', ''),
            telegram=data.get('telegram', ''),
            owner_username=user.username if user else None
        )
        
        db.session.add(new_applicant)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Анкета успешно добавлена'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/applicants')
def get_applicants():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if user.is_admin:
        applicants = Applicant.query.order_by(Applicant.date_added.desc()).all()
    else:
        applicants = Applicant.query.filter_by(owner_username=user.username).order_by(Applicant.date_added.desc()).all()
    return jsonify([a.to_dict() for a in applicants])


@app.route('/api/interview-slots')
def get_interview_slots():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    include_all = request.args.get('all') == '1'

    if include_all and user and user.is_admin:
        slots = InterviewSlot.query.order_by(InterviewSlot.start_time.asc()).all()
    else:
        slots = InterviewSlot.query.filter_by(is_open=True).order_by(InterviewSlot.start_time.asc()).all()

    return jsonify({'success': True, 'slots': [s.to_dict() for s in slots]}), 200


@app.route('/api/interview-slots', methods=['POST'])
def create_interview_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        data = request.json
        start_raw = data.get('start_time')
        end_raw = data.get('end_time')
        if not start_raw:
            return jsonify({'success': False, 'message': 'Укажите дату и время начала'}), 400

        start_time = datetime.fromisoformat(start_raw)
        end_time = datetime.fromisoformat(end_raw) if end_raw else None
        if end_time and end_time <= start_time:
            return jsonify({'success': False, 'message': 'Время окончания должно быть позже начала'}), 400

        slot = InterviewSlot(start_time=start_time, end_time=end_time, is_open=True)
        db.session.add(slot)
        db.session.commit()
        return jsonify({'success': True, 'slot': slot.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/interview-slots/<int:slot_id>/close', methods=['POST'])
def close_interview_slot(slot_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        slot = InterviewSlot.query.get_or_404(slot_id)
        slot.is_open = False
        db.session.commit()
        return jsonify({'success': True, 'slot': slot.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            user.last_login_at = datetime.now()
            db.session.commit()
            flash('Успешный вход', 'success')
            if user.is_admin:
                return redirect(url_for('admin_panel'))
            elif user.is_guest:
                return redirect(url_for('guest_selection'))
            return redirect(url_for('index'))
        else:
            flash('Неверные учётные данные', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/guest-register', methods=['POST'])
def guest_register():
    """Регистрация нового гостевого аккаунта"""
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        
        # Валидация
        if not username or not password:
            flash('Логин и пароль обязательны', 'error')
            return redirect(url_for('login'))
        
        if len(username) < 3:
            flash('Логин должен быть не менее 3 символов', 'error')
            return redirect(url_for('login'))
        
        if len(password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'error')
            return redirect(url_for('login'))
        
        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('login'))
        
        # Проверка существования пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('login'))
        
        # Создание нового гостевого аккаунта
        new_guest = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=False,
            is_guest=True
        )
        
        db.session.add(new_guest)
        db.session.commit()
        
        flash('✅ Аккаунт создан! Теперь вы можете войти и заполнить форму отбора.', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        print(f"[ERROR] Ошибка при регистрации гостя: {str(e)}")
        flash(f'Ошибка при создании аккаунта: {str(e)}', 'error')
        return redirect(url_for('login'))


@app.route('/guest-selection')
def guest_selection():
    """Страница отбора для гостей"""
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    questions = SelectionQuestion.query.order_by(SelectionQuestion.order).all()
    return render_template('guest_selection.html', questions=questions, current_user=user)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()
        crypto_wallet = request.form.get('crypto_wallet', '').strip()

        if display_name and len(display_name) > 120:
            flash('Имя слишком длинное (макс. 120 символов)', 'error')
            return redirect(url_for('profile'))
        if bio and len(bio) > 500:
            flash('Био слишком длинное (макс. 500 символов)', 'error')
            return redirect(url_for('profile'))
        if avatar_url:
            is_http = avatar_url.startswith('http://') or avatar_url.startswith('https://')
            is_static = avatar_url.startswith('/static/')
            if not is_http and not is_static:
                flash('Аватар: используйте ссылку http(s) или /static/', 'error')
                return redirect(url_for('profile'))

        user.display_name = display_name or None
        user.bio = bio or None
        user.avatar_url = avatar_url or None
        user.crypto_wallet = crypto_wallet or None
        db.session.commit()
        flash('Профиль обновлен', 'success')
        return redirect(url_for('profile'))

    # Статистика
    applicants_count = Applicant.query.filter_by(owner_username=user.username).count()
    approved_applicants = Applicant.query.filter_by(owner_username=user.username, status='approved').count()
    rejected_applicants = Applicant.query.filter_by(owner_username=user.username, status='rejected').count()
    guest_answers_count = GuestAnswer.query.filter_by(user_id=user.id).count()
    approved_answers_count = GuestAnswer.query.filter_by(user_id=user.id, approved=True).count()
    messages_sent_count = Message.query.filter_by(sender_id=user.id).count()
    messages_received_count = Message.query.filter_by(guest_user_id=user.id).count()
    last_message = Message.query.filter_by(sender_id=user.id).order_by(Message.created_at.desc()).first()

    stats = {
        'applicants_count': applicants_count,
        'approved_applicants': approved_applicants,
        'rejected_applicants': rejected_applicants,
        'guest_answers_count': guest_answers_count,
        'approved_answers_count': approved_answers_count,
        'messages_sent_count': messages_sent_count,
        'messages_received_count': messages_received_count,
        'last_message_at': last_message.created_at.strftime('%d.%m.%Y %H:%M') if last_message else None
    }

    return render_template('profile.html', current_user=user, stats=stats, is_admin_view=False)


@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
def admin_view_user_profile(user_id):
    """Просмотр профиля пользователя админом"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not admin or not admin.is_admin:
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    # Обработка POST запроса для обновления заработанной суммы
    if request.method == 'POST':
        earned_amount = request.form.get('earned_amount', '').strip()
        try:
            user.earned_amount = float(earned_amount) if earned_amount else 0.0
            db.session.commit()
            flash('Заработанная сумма обновлена', 'success')
        except ValueError:
            flash('Некорректная сумма', 'error')
        return redirect(url_for('admin_view_user_profile', user_id=user_id))
    
    # Получение статистики
    applicants_count = Applicant.query.filter_by(owner_username=user.username).count()
    approved_applicants = Applicant.query.filter_by(owner_username=user.username, status='approved').count()
    rejected_applicants = Applicant.query.filter_by(owner_username=user.username, status='rejected').count()
    guest_answers_count = GuestAnswer.query.filter_by(user_id=user.id).count()
    approved_answers_count = GuestAnswer.query.filter_by(user_id=user.id, approved=True).count()
    messages_sent_count = Message.query.filter_by(sender_id=user.id).count()
    messages_received_count = Message.query.filter_by(guest_user_id=user.id).count()
    last_message = Message.query.filter_by(sender_id=user.id).order_by(Message.created_at.desc()).first()

    stats = {
        'applicants_count': applicants_count,
        'approved_applicants': approved_applicants,
        'rejected_applicants': rejected_applicants,
        'guest_answers_count': guest_answers_count,
        'approved_answers_count': approved_answers_count,
        'messages_sent_count': messages_sent_count,
        'messages_received_count': messages_received_count,
        'last_message_at': last_message.created_at.strftime('%d.%m.%Y %H:%M') if last_message else None
    }

    return render_template('profile.html', current_user=user, stats=stats, is_admin_view=True, admin_user=admin)


@app.route('/api/submit-guest-answer', methods=['POST'])
def submit_guest_answer():
    """Сохранение ответа гостя"""
    try:
        print("=" * 60)
        print("[DEBUG] Получен POST запрос на /api/submit-guest-answer")
        data = request.json
        print(f"[DEBUG] Данные: {data}")
        
        # Проверка прав на отправку
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user and not user.can_submit:
                print("[ERROR] Пользователь не может отправлять ответы")
                return jsonify({'success': False, 'message': 'Вы уже отправили ответы. Обратитесь к администратору для повторной отправки'}), 403
        
        # Валидация
        if not data.get('guest_name'):
            print("[ERROR] guest_name не заполнено")
            return jsonify({'success': False, 'message': 'Введите имя'}), 400
        if not data.get('question_id') or not data.get('answer_text'):
            print(f"[ERROR] question_id={data.get('question_id')}, answer_text={data.get('answer_text')}")
            return jsonify({'success': False, 'message': 'Все поля обязательны'}), 400
        
        user_id = None
        if 'user_id' in session:
            user_id = session['user_id']
            print(f"[DEBUG] User ID из сессии: {user_id}")
        
        print(f"[DEBUG] Создаю GuestAnswer с данными:")
        print(f"  - user_id: {user_id}")
        print(f"  - guest_name: {data.get('guest_name')}")
        print(f"  - guest_tg: {data.get('guest_tg')}")
        print(f"  - guest_phone: {data.get('guest_phone')}")
        print(f"  - question_id: {data.get('question_id')}")
        print(f"  - answer_text: {data.get('answer_text')}")
        
        answer = GuestAnswer(
            user_id=user_id,
            guest_name=data.get('guest_name', ''),
            guest_tg=data.get('guest_tg', ''),
            guest_phone=data.get('guest_phone', ''),
            question_id=data.get('question_id'),
            answer_text=data.get('answer_text', '')
        )
        
        db.session.add(answer)
        db.session.commit()
        print(f"[SUCCESS] Ответ успешно сохранён с ID: {answer.id}")
        print("=" * 60)
        
        return jsonify({'success': True, 'message': 'Ответ отправлен', 'answer_id': answer.id}), 201
    except Exception as e:
        print(f"[EXCEPTION] {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('index'))
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin.html', users=users, current_user=user, current_tab='users')


@app.route('/admin/answers')
def admin_answers():
    """Просмотр ответов гостей"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('index'))
    answers = GuestAnswer.query.order_by(GuestAnswer.submitted_at.desc()).all()
    return render_template('admin.html', answers=answers, current_user=user, current_tab='answers')


@app.route('/admin/create-user', methods=['POST'])
def admin_create_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not admin or not admin.is_admin:
        return redirect(url_for('index'))
    username = request.form.get('username')
    password = request.form.get('password')
    is_worker = request.form.get('is_worker') == 'on'
    is_admin_role = request.form.get('is_admin') == 'on'
    
    # Если выбран рабочий аккаунт, то is_guest = False, иначе is_guest = True
    is_guest = not is_worker and not is_admin_role
    
    if not username or not password:
        flash('Введите логин и пароль', 'error')
        return redirect(url_for('admin_panel'))
    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким именем уже существует', 'error')
        return redirect(url_for('admin_panel'))
    
    new_user = User(username=username, password_hash=generate_password_hash(password), is_admin=is_admin_role, is_guest=is_guest)
    db.session.add(new_user)
    db.session.commit()
    
    if is_admin_role:
        user_type = 'администратор'
    elif is_worker:
        user_type = 'рабочий'
    else:
        user_type = 'гостевой'
    
    flash(f'{user_type.capitalize()} {username} создан. Пароль: {password}', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not admin or not admin.is_admin:
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    # Защита владельца - только владелец может удалить другого владельца
    if user.is_owner and not admin.is_owner:
        flash('Нельзя удалить владельца', 'error')
        return redirect(url_for('admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/api/reset-password/<int:user_id>', methods=['POST'])
def reset_user_password(user_id):
    """Сброс пароля пользователя и возврат нового пароля"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    admin = User.query.get(session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Защита владельца - только владелец может сбросить пароль другому владельцу
        if user.is_owner and not admin.is_owner:
            return jsonify({'success': False, 'message': 'Нельзя сбросить пароль владельца'}), 403
        
        # Генерируем новый пароль
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        print(f"[INFO] Сброс пароля для пользователя {user.username}")
        print(f"[INFO] Новый пароль: {new_password}")
        
        return jsonify({
            'success': True, 
            'message': 'Пароль сброшен',
            'new_password': new_password,
            'username': user.username
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/guest-answers')
def get_guest_answers():
    """Получение всех ответов гостей для админа"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        answers = GuestAnswer.query.order_by(GuestAnswer.submitted_at.desc()).all()
        return jsonify({'success': True, 'answers': [a.to_dict() for a in answers]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/approve-answer/<int:answer_id>', methods=['POST'])
def approve_answer(answer_id):
    """Одобрение ответа гостя"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        answer = GuestAnswer.query.get_or_404(answer_id)
        answer.approved = True
        db.session.commit()
        print(f"[INFO] Ответ {answer_id} одобрен")
        return jsonify({'success': True, 'message': 'Ответ одобрен'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/delete-answer/<int:answer_id>', methods=['DELETE'])
def delete_answer(answer_id):
    """Удаление ответа гостя"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        answer = GuestAnswer.query.get_or_404(answer_id)
        db.session.delete(answer)
        db.session.commit()
        print(f"[INFO] Ответ {answer_id} удален")
        return jsonify({'success': True, 'message': 'Ответ удален'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/lock-submissions', methods=['POST'])
def lock_submissions():
    """Блокировка возможности отправлять ответы"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(session['user_id'])
        if user:
            user.can_submit = False
            db.session.commit()
            print(f"[INFO] Пользователь {user.username} заблокирован для отправки ответов")
            return jsonify({'success': True, 'message': 'Отправка заблокирована'}), 200
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/toggle-submission/<int:user_id>', methods=['POST'])
def toggle_submission(user_id):
    """Переключение возможности отправлять ответы (только для админа)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    admin = User.query.get(session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        user.can_submit = not user.can_submit
        db.session.commit()
        status = 'разрешена' if user.can_submit else 'заблокирована'
        print(f"[INFO] Для пользователя {user.username} отправка {status}")
        return jsonify({'success': True, 'can_submit': user.can_submit, 'message': f'Отправка {status}'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/send-message', methods=['POST'])
def send_message():
    """Отправка сообщения в чат"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        guest_user_id = data.get('guest_user_id')  # ID пользователя-гостя
        message_text = data.get('message_text', '').strip()
        
        if not guest_user_id or not message_text:
            return jsonify({'success': False, 'message': 'Все поля обязательны'}), 400
        
        # Проверка: пользователь либо сам гость, либо админ
        user = User.query.get(session['user_id'])
        guest_user = User.query.get(guest_user_id)
        
        if not guest_user:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
        
        # Гость может писать только в свой чат, админ - в любой
        if not user.is_admin and user.id != guest_user_id:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        message = Message(
            guest_user_id=guest_user_id,
            sender_id=user.id,
            sender_name=user.username,
            message_text=message_text
        )
        
        db.session.add(message)
        db.session.commit()
        
        print(f"[INFO] Сообщение отправлено пользователем {user.username} для гостя {guest_user_id}")
        return jsonify({'success': True, 'message': message.to_dict()}), 201
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/messages/<int:guest_user_id>')
def get_messages(guest_user_id):
    """Получение последних сообщений для чата с гостем"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(session['user_id'])
        guest_user = User.query.get(guest_user_id)
        
        if not guest_user:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
        
        # Проверка: пользователь либо сам гость, либо админ
        if not user.is_admin and user.id != guest_user_id:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        # Получаем последние 50 сообщений для этого гостя
        messages = Message.query.filter_by(guest_user_id=guest_user_id).order_by(Message.created_at.desc()).limit(50).all()
        messages.reverse()  # Возвращаем в правильном порядке (старые → новые)
        
        return jsonify({
            'success': True, 
            'messages': [m.to_dict() for m in messages],
            'guest_username': guest_user.username
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/delete/<int:applicant_id>', methods=['DELETE'])
def delete_applicant(applicant_id):
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        applicant = Applicant.query.get_or_404(applicant_id)
        # allow admin or owner
        if not user.is_admin and applicant.owner_username != user.username:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        db.session.delete(applicant)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Запись удалена'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/applicant/<int:applicant_id>/status', methods=['POST'])
def update_applicant_status(applicant_id):
    """Изменение статуса анкеты (одобрить/отклонить)"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        applicant = Applicant.query.get_or_404(applicant_id)
        data = request.json
        status = data.get('status')
        
        if status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Некорректный статус'}), 400
        
        applicant.status = status
        db.session.commit()
        
        status_text = {'pending': 'Ожидает', 'approved': 'Одобрена', 'rejected': 'Отклонена'}
        return jsonify({'success': True, 'message': f'Статус изменен: {status_text[status]}', 'status': status}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/delete-all', methods=['DELETE'])
def delete_all_applicants():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        Applicant.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Все анкеты удалены'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/download-report')
def download_report():
    try:
        applicants = Applicant.query.order_by(Applicant.date_added.desc()).all()
        
        # Создание текстового отчета
        report_content = "=" * 80 + "\n"
        report_content += "ОТЧЕТ ПО КАНДИДАТАМ\n"
        report_content += f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report_content += f"Всего кандидатов: {len(applicants)}\n"
        report_content += "=" * 80 + "\n\n"
        
        for idx, applicant in enumerate(applicants, 1):
            report_content += f"Добавил: {applicant.owner_username}\n"
            report_content += f"КАНДИДАТ #{idx}\n"
            report_content += "-" * 80 + "\n"
            report_content += f"Имя: {applicant.full_name}\n"
            report_content += f"Возраст (Дата рождения): {applicant.date_of_birth}\n"
            report_content += f"Знание английского языка: {applicant.english_level}\n"
            report_content += f"Модель процессора: {applicant.cpu_model}\n"
            report_content += f"Модель видеокарты: {applicant.gpu_model}\n"
            report_content += f"Скорость Интернета: {applicant.internet_speed}\n"
            report_content += f"Где работал/ла: {applicant.work_experience}\n"
            report_content += f"Время собеседования: {applicant.interview_time}\n"
            report_content += f"Телефон: {applicant.phone}\n"
            report_content += f"Телега: {applicant.telegram}\n"
            report_content += f"Дата добавления: {applicant.date_added.strftime('%d.%m.%Y %H:%M')}\n"
            report_content += "\n"
        
        # Отправка файла
        file_stream = io.BytesIO(report_content.encode('utf-8'))
        return send_file(
            file_stream,
            mimetype='text/plain; charset=utf-8',
            as_attachment=True,
            download_name=f'report_{datetime.now().strftime("%d_%m_%Y_%H_%M")}.txt'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

if __name__ == '__main__':
    import os
    
    # Проверяем окружение
    env = os.environ.get('FLASK_ENV', 'development')
    debug_mode = env == 'development'
    
    if debug_mode:
        print("🚀 Запуск в режиме РАЗРАБОТКИ...")
        # Создание ngrok туннеля для удалённого доступа
        ngrok.set_auth_token("3A6zQHpsbYHKmKlLBDvJY3fKBXb_QrX2cmrP2Qufh6GmeRTY")
        print("🔧 Настройка ngrok...")
        try:
            # Убиваем все существующие туннели
            print("🔄 Останавливаю старые туннели...")
            ngrok.kill()
            import time
            time.sleep(2)
            
            # Создаём новый туннель с новым случайным доменом
            print("🌐 Создаю новый туннель...")
            public_url = ngrok.connect(5000, bind_tls=True)
            print(f"\n{'='*60}")
            print(f"✅ Ваш НОВЫЙ публичный URL:")
            print(f"🌐 {public_url}")
            print(f"{'='*60}")
            print(f"📱 Поделитесь этой ссылкой с другими людьми")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"⚠️ Ошибка ngrok: {e}")
            print("Запускаю приложение в режиме локальной сети...\n")
        
        # Запуск без auto-reloader чтобы избежать конфликтов с ngrok
        print("🏁 Запуск Flask сервера...")
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    else:
        print("🌍 Запуск в режиме PRODUCTION...")
        app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
