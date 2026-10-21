from flask import Flask, render_template, request, redirect, session, url_for, send_file
import sqlite3
import qrcode
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'


def get_db_connection():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', fio=session['fio'], role=session['role'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM students WHERE login = ? AND password = ?', (login, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['fio'] = user['fio']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            return "Неверный логин или пароль <br><a href='/login'>Назад</a>"
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- АДМИНКА СТАРОСТЫ ---
@app.route('/admin')
def admin():
    if 'user_id' not in session or session['role'] != 'starosta':
        return "Доступ только для старосты <br><a href='/'>На главную</a>"

    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students WHERE role = 'student'").fetchall()

    today = datetime.now().strftime("%Y-%m-%d")
    stats = {}
    for s in students:
        marks = conn.execute("SELECT pair_number, status FROM attendance WHERE student_id = ? AND date = ?",
                             (s['id'], today)).fetchall()
        stats[s['id']] = {m['pair_number']: m['status'] for m in marks}

    conn.close()
    return render_template('admin.html', students=students, stats=stats)


# --- QR-КОД ---
@app.route('/qr/<int:pair_num>')
def qr_code(pair_num):
    # Используем IP-адрес компьютера, чтобы телефон мог достучаться
    host = request.host.split(':')[0]  # Берем IP без порта
    mark_url = f"http://{host}:5000/scan?pair_num={pair_num}"

    img = qrcode.make(mark_url)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    return send_file(buf, mimetype='image/png')


# --- СТРАНИЦА ПОДТВЕРЖДЕНИЯ (куда попадает телефон) ---
@app.route('/scan')
def scan():
    if 'user_id' not in session:
        # Если студент не залогинен, отправляем его на вход
        return redirect(url_for('login'))

    pair_num = request.args.get('pair_num', 1)
    return render_template('scan.html', pair_num=pair_num)


# --- ОТМЕТКА (POST-запрос от кнопки) ---
@app.route('/mark', methods=['POST'])
def mark():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    pair_num = int(request.form.get('pair_num', 1))
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO attendance (student_id, pair_name, pair_number, date, status) VALUES (?, ?, ?, date("now"), 1)',
            (session['user_id'], 'Предмет', pair_num))
        conn.commit()
        msg = "Вы успешно отметились!"
    except sqlite3.IntegrityError:
        msg = "Вы уже отметились на эту пару сегодня!"
    finally:
        conn.close()

    return f"{msg} <br><br><a href='/'>Вернуться на главную</a>"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)