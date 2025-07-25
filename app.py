from flask import Flask, render_template, request, redirect, url_for, g, flash, session, send_file
import logging
import re
import os
import io
import pandas as pd
import sqlite3

# --- 配置与全局变量 (中文注释) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

RESULTS_PASSWORD = "admin" # 您可以在这里修改密码

app = Flask(__name__)
app.secret_key = 'a-very-strong-secret-key-for-render-deployment' 

# --- 数据库路径处理 (为Render优化) ---
def get_db_path():
    """
    获取数据库文件的正确路径。
    在Render上，我们会使用一个叫做“持久化磁盘”的功能来永久保存数据。
    这个磁盘会被挂载到 /var/render/data 目录。
    """
    # RENDER_DATA_DIR 是Render平台会自动设置的环境变量
    data_dir = os.environ.get('RENDER_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(data_dir, 'vote.db')

# --- 数据库连接管理 (中文注释) ---
@app.before_request
def before_request():
    """在处理每个请求之前，获取数据库连接。"""
    g.db = sqlite3.connect(get_db_path())
    g.db.row_factory = sqlite3.Row

@app.teardown_appcontext
def teardown_appcontext(exception=None):
    """在请求处理结束后，关闭数据库连接。"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- 视图函数 (中文注释) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/nominate', methods=['POST'])
def nominate():
    # 使用 session 来跟踪每个用户的提交次数
    if 'submission_count' not in session:
        session['submission_count'] = 0

    if session['submission_count'] >= 5:
        flash('1セッションにつき5回まで推薦できます。', 'warning')
        return redirect(url_for('index'))
    
    nominee_name = request.form.get('nominee_name', '').strip()
    comment_text = request.form.get('comment_text', '').strip()

    if not re.match(r'^\S+ \S+$', nominee_name):
        flash('推薦される方の名前は「姓 名」の形式で、間に半角スペースを一つ入れて入力してください。', 'warning')
        return redirect(url_for('index'))

    if nominee_name and comment_text:
        try:
            cursor = g.db.cursor()
            cursor.execute("INSERT INTO votes (nominee_name, comment_text) VALUES (?, ?)", (nominee_name, comment_text))
            g.db.commit()
            
            session['submission_count'] += 1
            flash('推薦が成功しました！ご協力ありがとうございます。', 'success')
        except Exception as e:
            logging.error(f"Error adding nomination: {e}")
            flash('操作に失敗しました。しばらくしてからもう一度お試しください。', 'error')
        return redirect(url_for('index'))
    else:
        flash('推薦される方のお名前とコメント内容は必須です。', 'warning')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == RESULTS_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('results'))
        else:
            flash('パスワードが違います。', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('submission_count', None)
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))

@app.route('/results')
def results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT nominee_name, COUNT(id) as vote_count FROM votes GROUP BY nominee_name ORDER BY vote_count DESC")
        vote_counts = cursor.fetchall()
        labels = [row['nominee_name'] for row in vote_counts]
        data = [row['vote_count'] for row in vote_counts]
        
        cursor.execute("SELECT nominee_name, comment_text, timestamp FROM votes ORDER BY timestamp DESC")
        all_nominations = cursor.fetchall()

        return render_template('results.html', 
                               vote_counts=vote_counts, 
                               labels=labels, 
                               data=data,
                               all_nominations=all_nominations)
    except Exception as e:
        logging.error(f"Error fetching results: {e}")
        flash('結果リストを読み込めませんでした。', 'error')
        return render_template('results.html', vote_counts=[], labels=[], data=[], all_nominations=[])

@app.route('/export')
def export():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT nominee_name, comment_text, timestamp FROM votes ORDER BY timestamp DESC")
        all_nominations = cursor.fetchall()
        
        df = pd.DataFrame([dict(row) for row in all_nominations])
        if df.empty:
            flash('エクスポートするデータがありません。', 'warning')
            return redirect(url_for('results'))
            
        df.columns = ['推薦された方', '推薦理由', '推薦日時']
        
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name='推薦結果')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='推薦結果.xlsx'
        )
    except Exception as e:
        logging.error(f"Error exporting to Excel: {e}")
        flash('エクスポートに失敗しました。', 'error')
        return redirect(url_for('results'))

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nominee_name TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Database initialized.")

# --- 启动逻辑 ---
# 当在Render上运行时，Render会使用 "Start Command" 来启动应用，
# 而不会直接运行这个 if __name__ == '__main__': 部分。
# 这部分主要用于您在自己电脑上进行本地测试。
if __name__ == '__main__':
    init_db()
    # 监听所有网络接口
    app.run(host='0.0.0.0', port=5000, debug=True)
