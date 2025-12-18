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
    
    # 创建诗歌表（添加weight字段）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS poems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            is_study TEXT NOT NULL DEFAULT '0',
            weight INTEGER NOT NULL DEFAULT 0,
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
        'SELECT id, title, is_study FROM poems ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    
    # 修改这里：返回包含标题和学习状态的字典列表
    return jsonify([{
        'title': poem['title'],
        'is_study': poem['is_study'] == '1'  # 转换为布尔值，便于前端使用
    } for poem in poems])

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


@app.route('/api/random', methods=['GET'])
def get_random_poems():
    """获取随机诗歌（只返回已学习的诗歌，权重低的诗歌有更高概率）"""
    count = request.args.get('count', 3, type=int)
    conn = get_db_connection()
    
    # 只获取已学习的诗歌（is_study = '1'）
    all_poems = conn.execute(
        "SELECT title, content, weight FROM poems WHERE is_study = '1'"
    ).fetchall()
    
    if not all_poems:
        conn.close()
        return jsonify([])
    
    # 限制数量不超过总诗歌数
    count = min(count, len(all_poems))
    
    # 计算选择概率：权重越低，概率越高
    # 使用公式：选择概率 = 1 / (weight + 1)
    # 这样权重为0的诗歌概率为1，权重为1的诗歌概率为1/2，以此类推
    poems_with_prob = []
    for poem in all_poems:
        weight = poem['weight']
        # 计算选择概率（权重越低，概率越高）
        probability = 1.0 / (weight + 1.0)
        poems_with_prob.append({
            'title': poem['title'],
            'content': poem['content'],
            'weight': weight,
            'probability': probability
        })
    
    # 计算总概率
    total_probability = sum(p['probability'] for p in poems_with_prob)
    
    # 如果总概率为0（不可能发生），则使用均匀分布
    if total_probability == 0:
        random_poems = random.sample([p for p in poems_with_prob], count)
    else:
        # 标准化概率
        normalized_probabilities = [p['probability'] / total_probability for p in poems_with_prob]
        
        # 使用加权随机选择
        random_poems = []
        available_poems = poems_with_prob.copy()
        available_probs = normalized_probabilities.copy()
        
        for _ in range(count):
            if not available_poems:
                break
                
            # 使用random.choices进行加权随机选择
            selected_idx = random.choices(range(len(available_poems)), weights=available_probs, k=1)[0]
            selected_poem = available_poems[selected_idx]
            random_poems.append(selected_poem)
            
            # 从可选列表中移除已选择的诗歌（避免重复）
            del available_poems[selected_idx]
            del available_probs[selected_idx]
            
            # 重新标准化剩余的概率
            if available_probs:
                total = sum(available_probs)
                if total > 0:
                    available_probs = [p / total for p in available_probs]
    
    # 更新被选中的诗歌的权重（weight+1）
    for poem in random_poems:
        conn.execute(
            "UPDATE poems SET weight = weight + 1 WHERE title = ?",
            (poem['title'],)
        )
    
    conn.commit()
    conn.close()
    
    # 转换为字典格式（只返回title和content）
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

@app.route('/api/poem/<title>/study', methods=['PUT'])
def mark_as_studied(title):
    """将诗歌标记为已学习（is_study=1）"""
    conn = get_db_connection()
    
    try:
        # 检查诗歌是否存在
        poem = conn.execute(
            'SELECT title FROM poems WHERE title = ?', 
            (title,)
        ).fetchone()
        
        if not poem:
            conn.close()
            return jsonify({"error": "诗歌未找到"}), 404
        
        # 更新is_study字段为1
        result = conn.execute(
            'UPDATE poems SET is_study = ? WHERE title = ?', 
            ("1", title)
        )
        conn.commit()
        conn.close()
        
        if result.rowcount > 0:
            return jsonify({"message": f"诗歌《{title}》已标记为已学习"})
        else:
            return jsonify({"error": "更新失败"}), 500
            
    except Exception as e:
        conn.close()
        return jsonify({"error": "服务器内部错误"}), 500



# 初始化数据库
if not os.path.exists('data'):
    os.makedirs('data')

init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)