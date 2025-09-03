import os
import datetime
import io
import csv
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

# 加载环境变量 (主要用于本地开发)
load_dotenv()

# --- 配置 ---
app = Flask(__name__)
app.secret_key = 'your-super-secret-key-for-the-final-db-version' 

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 数据库配置 ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 固定分类，这里是唯一的改动点，用于页面显示
FIXED_CATEGORIES = ["家具", "办公用品", "碗筷杯子", "电器", "娱乐", "户外", "其他"]

# --- 数据库模型 (代替 JSON 结构) ---
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    category = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(300), nullable=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    user_name = db.Column(db.String(200), nullable=False)
    pickup_date = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(100), default='待处理')

# --- 页面路由 (已全部更新为数据库操作) ---
@app.route('/')
def home():
    query = request.args.get('q', '').lower()
    category_filter = request.args.get('category', '')
    
    items_query = Item.query
    if category_filter:
        items_query = items_query.filter(Item.category == category_filter)
    if query:
        items_query = items_query.filter(Item.name.ilike(f'%{query}%'))
        
    displayed_items = items_query.all()
    contact_info = {'address': '新泽西州南布伦瑞克市 xxx 路 123 号', 'phone': '908-123-4567'}
    
    # 唯一改动：将所有的分类传递给模板，包括一个“所有分类”的选项
    all_categories = ['所有分类'] + FIXED_CATEGORIES 
    
    return render_template('index.html', 
                           items=displayed_items, 
                           contact=contact_info, 
                           categories=all_categories, # 注意这里
                           query=query, 
                           current_category=category_filter, 
                           logged_in=session.get('logged_in', False))

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template('item_detail.html', item=item, logged_in=session.get('logged_in', False))

@app.route('/reserve/<int:item_id>', methods=['POST'])
def reserve(item_id):
    item_to_reserve = Item.query.get_or_404(item_id)
    if item_to_reserve and item_to_reserve.quantity > 0:
        item_to_reserve.quantity -= 1
        new_reservation = Reservation(
            item_id=item_id, item_name=item_to_reserve.name,
            user_name=request.form.get('user_name'),
            pickup_date=request.form.get('pickup_date')
        )
        db.session.add(new_reservation)
        db.session.commit()
        flash('预留成功！我们会尽快与您联系。', 'success')
    else:
        flash('预留失败，商品可能已被预订。', 'error')
    return redirect(url_for('item_detail', item_id=item_id))

# --- 管理后台路由 (已全部更新为数据库操作) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True; flash('登录成功！', 'success'); return redirect(url_for('admin'))
        else: flash('用户名或密码错误！', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None); flash('您已成功登出。', 'success'); return redirect(url_for('home'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'): return redirect(url_for('login'))
    if request.method == 'POST':
        new_item = Item(
            name=request.form.get('name'), description=request.form.get('description'),
            price=float(request.form.get('price')), category=request.form.get('category'),
            quantity=int(request.form.get('quantity', 0))
        )
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename); os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)); new_item.image = f'uploads/{filename}'
        db.session.add(new_item); db.session.commit()
        flash(f"商品 '{new_item.name}' 添加成功！", 'success')
        return redirect(url_for('admin', view='products'))

    view = request.args.get('view', 'products')
    
    items_query = Item.query
    product_query = request.args.get('q_prod', '').lower()
    if product_query: items_query = items_query.filter(Item.name.ilike(f'%{product_query}%'))
    
    reservations_query = Reservation.query
    reservation_query = request.args.get('q_res', '').lower()
    reservation_status = request.args.get('f_res_status', '')
    if reservation_query: reservations_query = reservations_query.filter(Reservation.user_name.ilike(f'%{reservation_query}%'))
    if reservation_status: reservations_query = reservations_query.filter(Reservation.status == reservation_status)

    return render_template('admin.html', items=items_query.all(), reservations=reservations_query.all(), categories=FIXED_CATEGORIES, view=view, product_query=product_query, reservation_query=reservation_query, reservation_status=reservation_status)

@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    item_to_delete = Item.query.get_or_404(item_id)
    db.session.delete(item_to_delete); db.session.commit()
    flash(f"商品 '{item_to_delete.name}' 已删除。", 'success')
    return redirect(url_for('admin', view='products'))

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    item_to_edit = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        item_to_edit.name = request.form.get('name'); item_to_edit.description = request.form.get('description')
        item_to_edit.price = float(request.form.get('price')); item_to_edit.category = request.form.get('category')
        item_to_edit.quantity = int(request.form.get('quantity', 0))
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename); os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)); item_to_edit.image = f'uploads/{filename}'
        db.session.commit()
        flash(f"商品 '{item_to_edit.name}' 更新成功！", 'success')
        return redirect(url_for('admin', view='products'))
    return render_template('edit.html', item=item_to_edit, categories=FIXED_CATEGORIES)

@app.route('/reservation/delete/<int:res_id>', methods=['POST'])
def delete_reservation(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    res_to_delete = Reservation.query.get_or_404(res_id)
    db.session.delete(res_to_delete); db.session.commit()
    flash(f"订单 (ID: {res_id}) 已删除。", 'success')
    return redirect(url_for('admin', view='reservations'))

@app.route('/reservation/edit/<int:res_id>', methods=['POST'])
def edit_reservation_status(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    res_to_edit = Reservation.query.get_or_404(res_id)
    res_to_edit.status = request.form.get('status', '待处理'); db.session.commit()
    flash(f"订单 (ID: {res_id}) 状态已更新。", 'success')
    return redirect(url_for('admin', view='reservations'))

# 数据导出路由 (现在从数据库导出)
@app.route('/export/products')
def export_products():
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = Item.query.all(); output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['ID', '名称', '描述', '价格', '数量', '分类', '图片路径'])
    for item in items: writer.writerow([item.id, item.name, item.description, item.price, item.quantity, item.category, item.image])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=products_export.csv"})

@app.route('/export/reservations')
def export_reservations():
    if not session.get('logged_in'): return redirect(url_for('login'))
    reservations = Reservation.query.all(); output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['订单ID', '商品ID', '商品名称', '预留人姓名', '取货日期', '预留时间', '状态'])
    for res in reservations: writer.writerow([res.id, res.item_id, res.item_name, res.user_name, res.pickup_date, res.timestamp, res.status])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=reservations_export.csv"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # 在本地运行时创建数据库表（如果不存在）
    app.run(debug=True)
