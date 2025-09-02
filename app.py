import os
import json
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

# --- 配置 ---
app = Flask(__name__)
app.secret_key = 'your-super-secret-key-for-the-final-version-with-date'

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

FIXED_CATEGORIES = ["家具", "办公用品", "碗筷杯子", "电器", "娱乐", "户外", "其他"]


# --- 辅助函数 ---
def load_data(filename):
    if not os.path.exists(filename): return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)


# --- 页面路由 ---

# 路由 1: 网站主页 (无需改动)
@app.route('/')
def home():
    items = load_data('data.json')
    query = request.args.get('q', '').lower()
    category_filter = request.args.get('category', '')
    displayed_items = []
    for item in items:
        show = True
        if query and not (query in item['name'].lower() or query in item['description'].lower()): show = False
        if category_filter and category_filter != item['category']: show = False
        if show: displayed_items.append(item)
    contact_info = {'address': '新泽西州南布伦瑞克市 xxx 路 123 号', 'phone': '908-123-4567'}
    return render_template('index.html', items=displayed_items, contact=contact_info, categories=FIXED_CATEGORIES,
                           query=query, current_category=category_filter, logged_in=session.get('logged_in', False))


# 路由 2: 商品详情页
@app.route('/item/<int:item_id>')
def item_detail(item_id):
    items = load_data('data.json')
    item = next((item for item in items if item['id'] == item_id), None)
    if not item: return "Item not found", 404
    return render_template('item_detail.html', item=item, logged_in=session.get('logged_in', False))


# 路由 3: 处理预留请求 (已升级)
@app.route('/reserve/<int:item_id>', methods=['POST'])
def reserve(item_id):
    items = load_data('data.json')
    item_to_reserve = next((item for item in items if item['id'] == item_id), None)

    if item_to_reserve and item_to_reserve['quantity'] > 0:
        item_to_reserve['quantity'] -= 1
        save_data('data.json', items)

        reservations = load_data('reservations.json')
        new_reservation = {
            'id': reservations[-1]['id'] + 1 if reservations else 1,
            'item_id': item_id,
            'item_name': item_to_reserve['name'],
            'user_name': request.form.get('user_name'),
            'pickup_date': request.form.get('pickup_date'),  # *** 这是新增的地方 ***
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': '待处理'
        }
        reservations.append(new_reservation)
        save_data('reservations.json', reservations)
        flash('预留成功！我们会尽快与您联系。', 'success')
    else:
        flash('预留失败，商品可能已被预订。', 'error')

    return redirect(url_for('item_detail', item_id=item_id))


# --- 管理后台路由 (此部分代码无需修改) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True;
            flash('登录成功！', 'success');
            return redirect(url_for('admin'))
        else:
            flash('用户名或密码错误！', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None);
    flash('您已成功登出。', 'success');
    return redirect(url_for('home'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'): return redirect(url_for('login'))
    if request.method == 'POST':
        items = load_data('data.json')
        new_item = {
            'id': items[-1]['id'] + 1 if items else 1, 'name': request.form.get('name'),
            'description': request.form.get('description'), 'price': request.form.get('price'),
            'category': request.form.get('category'), 'quantity': int(request.form.get('quantity', 0)), 'image': ''
        }
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename);
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename));
                new_item['image'] = f'uploads/{filename}'
        items.append(new_item);
        save_data('data.json', items)
        flash(f"商品 '{new_item['name']}' 添加成功！", 'success')
        return redirect(url_for('admin'))
    all_items = load_data('data.json');
    all_reservations = load_data('reservations.json')
    return render_template('admin.html', items=all_items, reservations=all_reservations, categories=FIXED_CATEGORIES)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = load_data('data.json');
    item_to_delete = next((item for item in items if item['id'] == item_id), None)
    if item_to_delete: items.remove(item_to_delete); save_data('data.json', items); flash(
        f"商品 '{item_to_delete['name']}' 已删除。", 'success')
    return redirect(url_for('admin'))


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = load_data('data.json');
    item_to_edit = next((item for item in items if item['id'] == item_id), None)
    if not item_to_edit: flash("未找到商品", "error"); return redirect(url_for('admin'))
    if request.method == 'POST':
        item_to_edit.update({
            'name': request.form.get('name'), 'description': request.form.get('description'),
            'price': request.form.get('price'), 'category': request.form.get('category'),
            'quantity': int(request.form.get('quantity', 0))
        })
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename);
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename));
                item_to_edit['image'] = f'uploads/{filename}'
        save_data('data.json', items);
        flash(f"商品 '{item_to_edit['name']}' 更新成功！", 'success')
        return redirect(url_for('admin'))
    return render_template('edit.html', item=item_to_edit, categories=FIXED_CATEGORIES)


@app.route('/reservation/delete/<int:res_id>', methods=['POST'])
def delete_reservation(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    reservations = load_data('reservations.json');
    res_to_delete = next((r for r in reservations if r['id'] == res_id), None)
    if res_to_delete: reservations.remove(res_to_delete); save_data('reservations.json', reservations); flash(
        f"订单 (ID: {res_id}) 已删除。", 'success')
    return redirect(url_for('admin'))


@app.route('/reservation/edit/<int:res_id>', methods=['POST'])
def edit_reservation_status(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    reservations = load_data('reservations.json');
    res_to_edit = next((r for r in reservations if r['id'] == res_id), None)
    if res_to_edit: res_to_edit['status'] = request.form.get('status', '待处理'); save_data('reservations.json',
                                                                                            reservations); flash(
        f"订单 (ID: {res_id}) 状态已更新。", 'success')
    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run(debug=True)