from flask import Flask, render_template, request, redirect, session, jsonify, make_response
import pymysql
from datetime import datetime, date, timedelta
from io import BytesIO
from captcha.image import ImageCaptcha
import random
import string

app = Flask(__name__)
app.secret_key = 'worktime_secret_2025'

# ---------------- 数据库配置 ---------------- #
from config import DB_CONFIG
def get_conn():
    return pymysql.connect(**DB_CONFIG)

# ---------------- 验证码生成 ---------------- #
def gen_captcha_text():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

@app.route('/captcha')
def captcha():
    text = gen_captcha_text()
    session['captcha'] = text
    image = ImageCaptcha().generate_image(text)
    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    response = make_response(buf.read())
    response.content_type = 'image/png'
    return response

# ---------------- 登录/注册/登出 ---------------- #
@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        captcha_in = data.get('captcha', '').upper()
        captcha_real = session.get('captcha', '').upper()

        if captcha_in != captcha_real:
            return jsonify({'success': False, 'message': '验证码错误'})

        conn = get_conn()
        with conn.cursor() as c:
            c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['display_name'] = user['display_name']
            session['role'] = user['role']
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '账号或密码错误'})
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        display = data.get('displayName')
        user = data.get('username')
        pwd = data.get('password')

        conn = get_conn()
        with conn.cursor() as c:
            c.execute("SELECT id FROM users WHERE username=%s", (user,))
            if c.fetchone():
                return jsonify({'success': False, 'message': '账号已存在'})
            c.execute("INSERT INTO users (display_name, username, password) VALUES (%s, %s, %s)",
                      (display, user, pwd))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- 忘记密码 ---------------- #
# 1. 返回页面
@app.route('/reset_pwd')
def reset_pwd():
    return render_template('reset_pwd.html')

# 2. 真正改密码
@app.route('/api/reset_pwd', methods=['POST'])
def api_reset_pwd():
    data = request.get_json()
    username = data.get('username', '').strip()
    new_pwd = data.get('new_password', '').strip()
    captcha_in = data.get('captcha', '').upper()
    captcha_real = session.get('captcha', '').upper()

    if not username or not new_pwd:
        return jsonify({'success': False, 'message': '账号/新密码不能为空'})
    if captcha_in != captcha_real:
        return jsonify({'success': False, 'message': '验证码错误'})

    conn = get_conn()
    try:
        with conn.cursor() as c:
            # 先拿角色
            c.execute('SELECT id, role FROM users WHERE username=%s', (username,))
            user = c.fetchone()
            if not user:
                return jsonify({'success': False, 'message': '账号不存在'})
            if user['role'] == 'admin':
                return jsonify({'success': False, 'message': '管理员账号不支持自助重置'})
            # 执行重置
            c.execute('UPDATE users SET password=%s WHERE id=%s', (new_pwd, user['id']))
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

# ---------------- 主界面 ---------------- #
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    # 管理员直接进 admin 面板
    if session.get('role') == 'admin':
        return redirect('/admin')
    # 传今天、本周一给模板
    today = datetime.today()
    monday = today - timedelta(days=today.weekday())
    return render_template('dashboard.html',
                           user=session,
                           today=today.strftime('%Y-%m-%d'),
                           monday=monday.strftime('%Y-%m-%d'))

# ---------------- 管理员专用：用户列表 ----------------
@app.route('/api/users')
def api_users():
    if session.get('role') != 'admin':
        return jsonify([]), 403
    conn = get_conn()
    with conn.cursor() as c:
        # 只列出普通用户，管理员不显示
        c.execute('SELECT id, display_name FROM users WHERE role=%s ORDER BY id', ('user',))
        rows = c.fetchall()
    conn.close()
    return jsonify([{'id': r['id'], 'name': r['display_name']} for r in rows])

# ---------------- 管理员专用：主页面 ----------------
@app.route('/admin')
def admin_page():
    if session.get('role') != 'admin':
        return redirect('/dashboard')          # 普通用户直接赶回普通面板
    return render_template('admin.html', user=session)

# ---------------- 管理员个人中心页面 ----------------
@app.route('/profile_admin')
# 管理员专用：个人中心页面
@app.route('/admin/profile')
def admin_profile():
    if session.get('role') != 'admin':
        return redirect('/dashboard')          # 普通用户赶走
    return render_template('profile_admin.html', user=session)


# 返回用户在指定区间内的出勤天数
@app.route('/api/days')
def api_days():
    uid = request.args.get('user_id', type=int)
    start = request.args.get('start')
    end = request.args.get('end')
    if not uid or not start or not end:
        return jsonify(0)
    conn = get_conn()
    with conn.cursor() as c:
        c.execute("""SELECT COUNT(*) AS days
                     FROM records
                     WHERE user_id=%s AND date>=%s AND date<=%s AND work_hours IS NOT NULL""",
                  (uid, start, end))
        r = c.fetchone()
    conn.close()
    return jsonify(r['days'] or 0)

# ---------------- 管理员用户管理页面 ----------------
@app.route('/admin/users')
def admin_users():
    """管理员专用：用户管理页面"""
    if session.get('role') != 'admin':
        return redirect('/dashboard')
    return render_template('admin_users.html', user=session)


@app.route('/api/all_users')
def api_all_users():
    """返回全部用户（含管理员）"""
    if session.get('role') != 'admin':
        return jsonify([]), 403
    conn = get_conn()
    with conn.cursor() as c:
        c.execute('SELECT id, display_name, username, role FROM users ORDER BY id')
        rows = c.fetchall()
    conn.close()
    return jsonify(rows)


@app.route('/api/user/delete/<int:user_id>', methods=['POST'])
def api_user_delete(user_id):
    """级联删除用户及其工时记录"""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    conn = get_conn()
    try:
        with conn.cursor() as c:
            # 检查是否为管理员用户
            c.execute('SELECT role FROM users WHERE id=%s', (user_id,))
            user_role = c.fetchone()
            if user_role and user_role['role'] == 'admin':
                return jsonify({'success': False, 'message': '管理员用户不可删除'})

            # 先删工时记录
            c.execute('DELETE FROM records WHERE user_id=%s', (user_id,))
            # 再删用户
            c.execute('DELETE FROM users WHERE id=%s', (user_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


# ---------------- 个人中心页面 ----------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')
    # 直接把 session 透传给模板，用来显示顶部欢迎语
    return render_template('profile.html', user=session)

# ---------------- 个人中心：回显当前用户信息 ----------------
@app.route('/api/user/info')
def user_info():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    conn = get_conn()
    with conn.cursor() as c:
        # 把 role 也查出来
        c.execute('SELECT display_name, username, role FROM users WHERE id=%s', (session['user_id'],))
        row = c.fetchone()
    conn.close()
    # 一起返回
    return jsonify({
        'success':      True,
        'display_name': row['display_name'],
        'username':     row['username'],
        'role':         row['role']          # 新增
    })

# ---------------- 更新用户名 ----------------
@app.route('/api/user/update_name', methods=['POST'])
def update_name():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    new_name = request.json.get('display_name', '').strip()
    if not new_name:
        return jsonify({'success': False, 'message': '用户名不能为空'})
    conn = get_conn()
    with conn.cursor() as c:
        c.execute('UPDATE users SET display_name=%s WHERE id=%s', (new_name, session['user_id']))
    conn.commit()
    conn.close()
    session['display_name'] = new_name          # 实时刷新顶部欢迎语
    return jsonify({'success': True})

# ---------------- 独立修改密码页 ----------------
@app.route('/change_pwd')
def change_pwd():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('change_pwd.html')

# ---------------- 独立修改密码 ----------------
@app.route('/api/user/update_pwd', methods=['POST'])
def update_pwd():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.json
    old_pwd = data.get('old_password')
    new_pwd = data.get('new_password')
    if not old_pwd or not new_pwd:
        return jsonify({'success': False, 'message': '请完整填写密码'})
    conn = get_conn()
    with conn.cursor() as c:
        # 先校验旧密码
        c.execute('SELECT password FROM users WHERE id=%s', (session['user_id'],))
        real_pwd = c.fetchone()['password']
        if real_pwd != old_pwd:
            return jsonify({'success': False, 'message': '原密码错误'})
        # 再更新
        c.execute('UPDATE users SET password=%s WHERE id=%s', (new_pwd, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------- 自定义打卡 ---------------- #
@app.route('/custom_clock', methods=['POST'])
def custom_clock():
    user_id = session['user_id']
    data = request.get_json()
    date = data.get('date')
    clock_in = data.get('clock_in') or None
    clock_out = data.get('clock_out') or None

    conn = get_conn()
    with conn.cursor() as c:
        c.execute("SELECT id, clock_in FROM records WHERE user_id=%s AND date=%s", (user_id, date))
        rec = c.fetchone()

        work_hours = None
        if clock_in and clock_out:
            t_in = datetime.strptime(clock_in, '%H:%M')
            t_out = datetime.strptime(clock_out, '%H:%M')
            # 使用 total_seconds() 并保留 4 位小数，避免过早四舍五入
            work_hours = round((t_out - t_in).total_seconds() / 3600, 4)

        if rec:
            c.execute("UPDATE records SET clock_in=%s, clock_out=%s, work_hours=%s WHERE id=%s",
                      (clock_in, clock_out, work_hours, rec['id']))
        else:
            c.execute("INSERT INTO records (user_id, date, clock_in, clock_out, work_hours) VALUES (%s,%s,%s,%s,%s)",
                      (user_id, date, clock_in, clock_out, work_hours))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ---------------- 一周汇总（自动取本周） ---------------- #
@app.route('/week_summary')
def week_summary():
    user_id = session['user_id']
    today = datetime.today().date()
    monday = today - timedelta(days=today.weekday())          # 本周一
    # 如果只想看本周已发生天数，把 sunday 换成 today 即可
    sunday = monday + timedelta(days=6)

    conn = get_conn()
    with conn.cursor() as c:
        sql = """
            SELECT date, clock_in, clock_out, work_hours
            FROM records
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date
        """
        c.execute(sql, (user_id, monday, sunday))
        rows = c.fetchall()
    conn.close()

    # ---- 工具：timedelta → HH:MM ----
    def td2hm(td):
        if td is None:
            return '-'
        total_seconds = int(td.total_seconds())
        h, r = divmod(total_seconds, 3600)
        m, _ = divmod(r, 60)
        return f'{h:02d}:{m:02d}'

    # ---- 工具：float 小时 → X小时Y分钟（ZZZ分钟） ----
    def fmt_hm(hours: float) -> str:
        if hours is None or hours == 0:
            return '-'
        total_min = int(round(hours * 60))
        h, m = divmod(total_min, 60)
        return f'{h}小时{m}分钟（{total_min}分钟）'

    # ---- 补全 7 天结构 ----
    days_map = {}
    for i in range(7):
        day = monday + timedelta(days=i)
        days_map[str(day)] = {
            'date': str(day),
            'weekday': ['一','二','三','四','五','六','日'][i],
            'clock_in': '-',
            'clock_out': '-',
            'work_hours': 0.0,      # 数值：参与累计
            'display_time': '-'     # 字符串：给前端看
        }

    # ---- 填充真实数据 ----
    for r in rows:
        # 规范化显示字段
        ci = td2hm(r['clock_in'])
        co = td2hm(r['clock_out'])

        # 优先用打卡时间差计算当日工时（分钟），再转为小时小数（保持高精度）
        day_min = 0
        if ci != '-' and co != '-':
            try:
                ih, im = map(int, ci.split(':'))
                oh, om = map(int, co.split(':'))
                day_min = (oh * 60 + om) - (ih * 60 + im)
                if day_min < 0:
                    day_min = 0
            except Exception:
                day_min = 0
        else:
            # 回退到数据库中的 work_hours（可能是 timedelta 或 float）
            wh_val = r['work_hours']
            if isinstance(wh_val, timedelta):
                day_min = int(wh_val.total_seconds() / 60)
            elif wh_val is None:
                day_min = 0
            else:
                day_min = int(float(wh_val) * 60)

        wh_hours = round(day_min / 60, 4)
        days_map[str(r['date'])].update({
            'clock_in': ci,
            'clock_out': co,
            'work_hours': wh_hours,
            'display_time': fmt_hm(wh_hours)
        })

    # ---- 只累计到今天为止的日时长（以打卡差为准，小时数由上面计算的 work_hours 得出） ----
    days_list = [days_map[str(monday + timedelta(days=i))] for i in range(today.weekday() + 1)]
    week_total = round(sum(float(d['work_hours']) for d in days_list), 4)

    return jsonify({'days': list(days_map.values()), 'week_total': week_total})

# ---------------- 原打卡接口（保留兼容） ---------------- #
@app.route('/clock_in', methods=['POST'])
def clock_in():
    user_id = session['user_id']
    date = datetime.now().strftime('%Y-%m-%d')
    clock_in = datetime.now().strftime('%H:%M:%S')

    conn = get_conn()
    with conn.cursor() as c:
        c.execute("SELECT id FROM records WHERE user_id=%s AND date=%s", (user_id, date))
        rec = c.fetchone()
        if rec:
            c.execute("UPDATE records SET clock_in=%s WHERE id=%s", (clock_in, rec['id']))
        else:
            c.execute("INSERT INTO records (user_id, date, clock_in) VALUES (%s, %s, %s)",
                      (user_id, date, clock_in))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/clock_out', methods=['POST'])
def clock_out():
    user_id = session['user_id']
    date = datetime.now().strftime('%Y-%m-%d')
    clock_out = datetime.now().strftime('%H:%M:%S')

    conn = get_conn()
    with conn.cursor() as c:
        c.execute("SELECT id, clock_in FROM records WHERE user_id=%s AND date=%s", (user_id, date))
        rec = c.fetchone()
        if rec:
            work_hours = None
            if rec['clock_in']:
                # 处理可能的存储格式（含秒或不含秒）
                try:
                    t_in = datetime.strptime(rec['clock_in'], '%H:%M:%S')
                except:
                    t_in = datetime.strptime(rec['clock_in'], '%H:%M')
                t_out = datetime.strptime(clock_out, '%H:%M:%S')
                work_hours = round((t_out - t_in).total_seconds() / 3600, 4)
            c.execute("UPDATE records SET clock_out=%s, work_hours=%s WHERE id=%s",
                      (clock_out, work_hours, rec['id']))
        else:
            c.execute("INSERT INTO records (user_id, date, clock_out) VALUES (%s, %s, %s)",
                      (user_id, date, clock_out))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# -------------- 工时统计（默认本周） --------------
@app.route('/records')
def records():
    user_id = session['user_id']
    role    = session.get('role', 'user')
    start   = request.args.get('start')
    end     = request.args.get('end')

    # 默认本周
    if not start or not end:
        today  = datetime.today().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        start  = monday.strftime('%Y-%m-%d')
        end    = sunday.strftime('%Y-%m-%d')

    # ★ 关键：管理员可选用户，普通用户只能看自己
    target_user = request.args.get('user_id')
    if role == 'admin' and target_user:
        params = [int(target_user), start, end]
        user_filter = 'r.user_id = %s'
    else:
        params = [user_id, start, end]
        user_filter = 'r.user_id = %s'

    conn = get_conn()
    with conn.cursor() as c:
        sql = f"""
            SELECT u.display_name, r.date, r.clock_in, r.clock_out, r.work_hours
            FROM records r
            JOIN users u ON u.id = r.user_id
            WHERE {user_filter}
              AND r.date BETWEEN %s AND %s
            ORDER BY r.date
        """
        c.execute(sql, params)
        rows = c.fetchall()
    conn.close()

    # 后续把 TIME/timedelta 统一转可序列化格式 …
    for r in rows:
        # 规范化 clock 字段显示格式（保留到分）
        if isinstance(r['clock_in'], timedelta):
            r['clock_in'] = (datetime.min + r['clock_in']).strftime('%H:%M')
        if isinstance(r['clock_out'], timedelta):
            r['clock_out'] = (datetime.min + r['clock_out']).strftime('%H:%M')

        # 关键：如果有打卡时间则优先按时间差实时计算 work_hours（秒级），避免使用数据库里被四舍五入的值
        if r.get('clock_in') and r.get('clock_out'):
            try:
                # 兼容 HH:MM 或 HH:MM:SS
                try:
                    t_in = datetime.strptime(r['clock_in'], '%H:%M:%S')
                except:
                    t_in = datetime.strptime(r['clock_in'], '%H:%M')
                try:
                    t_out = datetime.strptime(r['clock_out'], '%H:%M:%S')
                except:
                    t_out = datetime.strptime(r['clock_out'], '%H:%M')
                # 若 parse 成功，使用 total_seconds() 计算小时，保留 4 位小数
                wh = round((t_out - t_in).total_seconds() / 3600, 4)
                if wh < 0:
                    wh = 0.0
                r['work_hours'] = float(wh)
            except Exception:
                # 解析失败则退回数据库值
                r['work_hours'] = float(r['work_hours']) if r['work_hours'] else 0.0
        else:
            r['work_hours'] = float(r['work_hours']) if r['work_hours'] else 0.0
    return jsonify(rows)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, debug=True)