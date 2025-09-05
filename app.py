import os
import datetime
import io
import csv
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import math

# --- 配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = 'a-truly-random-and-secret-key-final-with-cloudinary' 

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

# --- MongoDB 配置 ---
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in the environment variables.")
client = MongoClient(MONGO_URI)
db = client.my_store

# --- Cloudinary 配置 ---
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    raise RuntimeError("Cloudinary credentials (CLOUD_NAME, API_KEY, API_SECRET) are not fully set in environment variables.")

cloudinary.config(
  cloud_name = CLOUDINARY_CLOUD_NAME, 
  api_key = CLOUDINARY_API_KEY, 
  api_secret = CLOUDINARY_API_SECRET,
  secure = True
)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
FIXED_CATEGORIES = ["家具", "办公用品", "碗筷杯子", "电器", "娱乐", "户外", "其他"]
ITEMS_PER_PAGE = 9 # 设置每页显示的商品数量

# --- 前台页面路由 ---
@app.route('/')
def home():
    # 获取当前页码，默认为第一页
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '')
    category_filter = request.args.get('category', '')
    
    search_filter = {}
    if category_filter:
        search_filter['category'] = category_filter
    if query:
        search_filter['$or'] = [{'name': {'$regex': query, '$options': 'i'}}, {'description': {'$regex': query, '$options': 'i'}}]
    
    # 获取符合条件的总商品数
    total_items = db.items.count_documents(search_filter)
    # 计算总页数
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

    # 使用 skip 和 limit 从数据库中只获取当前页的商品
    displayed_items = list(db.items.find(search_filter).skip((page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE))
    
    contact_info = {'address': '新泽西州南布伦瑞克市 xxx 路 123 号', 'phone': '908-123-4567'}
    all_categories = ['所有分类'] + FIXED_CATEGORIES
    
    return render_template('index.html', 
                           items=displayed_items, 
                           contact=contact_info, 
                           categories=all_categories, 
                           query=query, 
                           current_category=category_filter, 
                           logged_in=session.get('logged_in', False),
                           page=page,
                           total_pages=total_pages)

@app.route('/item/<item_id>')
def item_detail(item_id):
    item = db.items.find_one({'_id': ObjectId(item_id)})
    if item is None: abort(404)
    return render_template('item_detail.html', item=item, logged_in=session.get('logged_in', False))

@app.route('/reserve/<item_id>', methods=['POST'])
def reserve(item_id):
    quantity_to_reserve = int(request.form.get('quantity_to_reserve', 0))
    if quantity_to_reserve <= 0:
        flash('预留数量必须大于0。', 'error')
        return redirect(url_for('item_detail', item_id=item_id))
    result = db.items.find_one_and_update(
        {'_id': ObjectId(item_id), 'quantity': {'$gte': quantity_to_reserve}},
        {'$inc': {'quantity': -quantity_to_reserve}}
    )
    if result:
        new_reservation = {
            'item_id': item_id, 'item_name': result['name'], 'user_name': request.form.get('user_name'),
            'pickup_date': request.form.get('pickup_date'), 'quantity_reserved': quantity_to_reserve,
            'contact_info': request.form.get('contact_info', ''),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'status': '待处理'
        }
        db.reservations.insert_one(new_reservation)
        flash('预留成功！我们会尽快与您联系。', 'success')
    else:
        flash('预留失败，商品库存不足或已被预订。', 'error')
    return redirect(url_for('item_detail', item_id=item_id))

# --- 管理后台路由 ---
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
        image_url = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                try:
                    upload_result = cloudinary.uploader.upload(file)
                    image_url = upload_result.get('secure_url')
                except Exception as e:
                    flash(f"图片上传失败: {e}", "error")
        
        new_item = {
            'name': request.form.get('name'), 'description': request.form.get('description'),
            'price': float(request.form.get('price', 0)), 'category': request.form.get('category'),
            'quantity': int(request.form.get('quantity', 0)), 'image': image_url
        }
        db.items.insert_one(new_item)
        flash(f"商品 '{new_item['name']}' 添加成功！", 'success')
        return redirect(url_for('admin', view='products'))

    view = request.args.get('view', 'products'); product_query = request.args.get('q_prod', ''); reservation_query = request.args.get('q_res', ''); reservation_status = request.args.get('f_res_status', '')
    item_filter = {}; 
    if product_query: item_filter['name'] = {'$regex': product_query, '$options': 'i'}
    reservation_filter = {}; 
    if reservation_query: reservation_filter['user_name'] = {'$regex': reservation_query, '$options': 'i'}
    if reservation_status: reservation_filter['status'] = reservation_status
    all_items = list(db.items.find(item_filter)); all_reservations = list(db.reservations.find(reservation_filter))
    return render_template('admin.html', items=all_items, reservations=all_reservations, categories=FIXED_CATEGORIES, view=view, product_query=product_query, reservation_query=reservation_query, reservation_status=reservation_status)

@app.route('/edit/<item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    item_to_edit = db.items.find_one({'_id': ObjectId(item_id)})
    if item_to_edit is None:
        flash("未找到要编辑的商品。", "error"); return redirect(url_for('admin', view='products'))
        
    if request.method == 'POST':
        update_data = {
            'name': request.form.get('name'), 'description': request.form.get('description'),
            'price': float(request.form.get('price', item_to_edit.get('price', 0))),
            'category': request.form.get('category'),
            'quantity': int(request.form.get('quantity', item_to_edit.get('quantity', 0)))
        }
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                try:
                    upload_result = cloudinary.uploader.upload(file)
                    update_data['image'] = upload_result.get('secure_url')
                except Exception as e:
                    flash(f"图片上传失败: {e}", "error")
        
        db.items.update_one({'_id': ObjectId(item_id)}, {'$set': update_data})
        flash(f"商品 '{update_data['name']}' 更新成功！", 'success')
        return redirect(url_for('admin', view='products'))
        
    return render_template('edit.html', item=item_to_edit, categories=FIXED_CATEGORIES)

@app.route('/delete/<item_id>', methods=['POST'])
def delete_item(item_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    result = db.items.find_one_and_delete({'_id': ObjectId(item_id)})
    if result: flash(f"商品 '{result['name']}' 已删除。", 'success')
    return redirect(url_for('admin', view='products'))

@app.route('/reservation/delete/<res_id>', methods=['POST'])
def delete_reservation(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    reservation = db.reservations.find_one({'_id': ObjectId(res_id)})
    if reservation:
        db.items.update_one({'_id': ObjectId(reservation['item_id'])}, {'$inc': {'quantity': reservation.get('quantity_reserved', 1)}})
    db.reservations.delete_one({'_id': ObjectId(res_id)})
    flash(f"订单 (ID: {res_id}) 已删除，商品库存已恢复。", 'success')
    return redirect(url_for('admin', view='reservations'))

@app.route('/reservation/edit/<res_id>', methods=['POST'])
def edit_reservation_status(res_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    new_status = request.form.get('status', '待处理')
    db.reservations.update_one({'_id': ObjectId(res_id)}, {'$set': {'status': new_status}})
    flash(f"订单 (ID: {res_id}) 状态已更新。", 'success')
    return redirect(url_for('admin', view='reservations'))

@app.route('/export/products')
def export_products():
    if not session.get('logged_in'): return redirect(url_for('login'))
    items = list(db.items.find({})); output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['ID', '名称', '描述', '价格', '数量', '分类', '图片路径'])
    for item in items: writer.writerow([str(item['_id']), item.get('name'), item.get('description'), item.get('price'), item.get('quantity'), item.get('category'), item.get('image')])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=products_export.csv"})

@app.route('/export/reservations')
def export_reservations():
    if not session.get('logged_in'): return redirect(url_for('login'))
    reservations = list(db.reservations.find({})); output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['订单ID', '商品ID', '商品名称', '预留人姓名', '预留数量', '联系方式', '取货日期', '预留时间', '状态'])
    for res in reservations: 
        writer.writerow([str(res['_id']), res.get('item_id'), res.get('item_name'), res.get('user_name'), res.get('quantity_reserved'), res.get('contact_info', '未提供'), res.get('pickup_date'), res.get('timestamp'), res.get('status')])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=reservations_export.csv"})

if __name__ == '__main__':
    app.run(debug=True)
