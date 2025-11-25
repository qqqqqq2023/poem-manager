from flask import Flask, request, jsonify, send_from_directory
import os
import random
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)

# 数据库文件路径
DATABASE = 'data/db.sqlite'

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # 使返回的行像字典一样访问
    return conn

def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    
    # 创建诗歌表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS poems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建设置表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # 插入默认设置
    conn.execute('''
        INSERT OR IGNORE INTO settings (key, value) 
        VALUES ('random_count', '3')
    ''')
    
    # 插入示例诗歌数据（如果表为空）
    cursor = conn.execute('SELECT COUNT(*) as count FROM poems')
    count = cursor.fetchone()['count']
    
    if count == 0:
        sample_poems = [
            ("静夜思", "床前明月光，\n疑是地上霜。\n举头望明月，\n低头思故乡。"),
            ("春晓", "春眠不觉晓，\n处处闻啼鸟。\n夜来风雨声，\n花落知多少。"),
            ("相思", "红豆生南国，\n春来发几枝。\n愿君多采撷，\n此物最相思。")
        ]
        
        for title, content in sample_poems:
            conn.execute(
                'INSERT INTO poems (title, content) VALUES (?, ?)',
                (title, content)
            )
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

@app.route('/api/poems', methods=['GET'])
def get_poems():
    """获取所有诗歌列表"""
    conn = get_db_connection()
    poems = conn.execute(
        'SELECT id, title FROM poems ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    
    return jsonify([poem['title'] for poem in poems])

@app.route('/api/poem/<title>', methods=['GET'])
def get_poem(title):
    """获取特定诗歌内容"""
    conn = get_db_connection()
    poem = conn.execute(
        'SELECT title, content FROM poems WHERE title = ?', 
        (title,)
    ).fetchone()
    conn.close()
    
    if poem:
        return jsonify({
            'title': poem['title'],
            'content': poem['content']
        })
    else:
        return jsonify({"error": "诗歌未找到"}), 404

@app.route('/api/poem', methods=['POST'])
def add_poem():
    """添加新诗歌"""
    data = request.json
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    
    if not title or not content:
        return jsonify({"error": "标题和内容不能为空"}), 400
    
    conn = get_db_connection()
    
    try:
        conn.execute(
            'INSERT INTO poems (title, content) VALUES (?, ?)',
            (title, content)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "诗歌添加成功"})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "标题已存在"}), 400
    except Exception as e:
        conn.close()
        return jsonify({"error": "添加失败"}), 500

@app.route('/api/poem/<title>', methods=['DELETE'])
def delete_poem(title):
    """删除诗歌"""
    conn = get_db_connection()
    result = conn.execute(
        'DELETE FROM poems WHERE title = ?', 
        (title,)
    )
    conn.commit()
    conn.close()
    
    if result.rowcount > 0:
        return jsonify({"message": "诗歌删除成功"})
    else:
        return jsonify({"error": "诗歌未找到"}), 404

@app.route('/api/random', methods=['GET'])
def get_random_poems():
    """获取随机诗歌"""
    count = request.args.get('count', 3, type=int)
    conn = get_db_connection()
    
    # 获取所有诗歌
    all_poems = conn.execute(
        'SELECT title, content FROM poems'
    ).fetchall()
    conn.close()
    
    if not all_poems:
        return jsonify([])
    
    # 随机选择指定数量的诗歌
    count = min(count, len(all_poems))
    random_poems = random.sample(all_poems, count)
    
    # 转换为字典格式
    poems_list = [
        {
            'title': poem['title'],
            'content': poem['content']
        }
        for poem in random_poems
    ]
    
    return jsonify(poems_list)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取设置"""
    conn = get_db_connection()
    settings_rows = conn.execute(
        'SELECT key, value FROM settings'
    ).fetchall()
    conn.close()
    
    settings = {}
    for row in settings_rows:
        settings[row['key']] = row['value']
    
    # 确保有默认值
    if 'random_count' not in settings:
        settings['random_count'] = '3'
    
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """更新设置"""
    data = request.json
    
    conn = get_db_connection()
    
    try:
        for key, value in data.items():
            conn.execute(
                'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                (key, str(value))
            )
        conn.commit()
        conn.close()
        return jsonify({"message": "设置更新成功"})
    except Exception as e:
        conn.close()
        return jsonify({"error": "更新失败"}), 500

# 初始化数据库
if not os.path.exists('data'):
    os.makedirs('data')

init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)