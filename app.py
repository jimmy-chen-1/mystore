import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

# --- 配置 ---
app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-final-version'

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# *** 新增：固定的分类列表 ***
FIXED_CATEGORIES = ["家具", "办公用品", "碗筷杯子", "电器", "娱乐", "户外", "其他"]


# --- 辅助函数 ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_items():
    if not os.path.exists('data.json'): return []
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_items(items):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=4, ensure_ascii=False)


# --- 页面路由 ---

# 路由 1: 网站主页
@app.route('/')
def home():
    items = load_items()
    query = request.args.get('q', '').lower()
    category_filter = request.args.get('category', '')  # 不需要lower()，因为要和中文匹配
    displayed_items = []
    for item in items:
        show = True
        if query and not (query in item['name'].lower() or query in item['description'].lower()): show = False
        if category_filter and category_filter != item['category']: show = False
        if show: displayed_items.append(item)

    # *** 修改：直接使用固定分类 ***
    categories = FIXED_CATEGORIES
    contact_info = {'address': '新泽西州南布伦瑞克市 xxx 路 123 号', 'phone': '908-123-4567'}
    return render_template('index.html', items=displayed_items, contact=contact_info, categories=categories,
                           query=query, current_category=category_filter, logged_in=session.get('logged_in', False))


# 路由 2: 登录页面 (无需改动)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('admin'))
        else:
            flash('用户名或密码错误！', 'error')
    return render_template('login.html')


# 路由 3: 登出功能 (无需改动)
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('您已成功登出。', 'success')
    return redirect(url_for('home'))


# 路由 4: 管理者页面
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        items = load_items()
        new_item = {
            'id': items[-1]['id'] + 1 if items else 1,
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'price': request.form.get('price'),
            'category': request.form.get('category'),  # 从下拉列表中获取
            'image': ''
        }
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_item['image'] = f'uploads/{filename}'

        items.append(new_item)
        save_items(items)
        flash(f"商品 '{new_item['name']}' 添加成功！", 'success')
        return redirect(url_for('admin'))

    all_items = load_items()
    # *** 修改：将固定分类传递给模板 ***
    return render_template('admin.html', items=all_items, categories=FIXED_CATEGORIES)


# 路由 5: 删除商品 (无需改动)
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = load_items()
    item_to_delete = next((item for item in items if item['id'] == item_id), None)
    if item_to_delete:
        items.remove(item_to_delete)
        save_items(items)
        flash(f"商品 '{item_to_delete['name']}' 已被删除。", 'success')
    else:
        flash("未找到要删除的商品。", "error")
    return redirect(url_for('admin'))


# 路由 6: 编辑商品
@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = load_items()
    item_to_edit = next((item for item in items if item['id'] == item_id), None)

    if not item_to_edit:
        flash("未找到要编辑的商品。", "error")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        item_to_edit['name'] = request.form.get('name')
        item_to_edit['description'] = request.form.get('description')
        item_to_edit['price'] = request.form.get('price')
        item_to_edit['category'] = request.form.get('category')  # 从下拉列表中获取

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                item_to_edit['image'] = f'uploads/{filename}'

        save_items(items)
        flash(f"商品 '{item_to_edit['name']}' 更新成功！", 'success')
        return redirect(url_for('admin'))

    # *** 修改：将固定分类传递给模板 ***
    return render_template('edit.html', item=item_to_edit, categories=FIXED_CATEGORIES)


if __name__ == '__main__':
    app.run(debug=True)