import sqlite3
import logging

DATABASE = 'vote.db'

def get_db():
    """
    获取数据库连接。
    (中文注释：此函数无变化)
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise

def init_db():
    """
    初始化数据库，创建 'votes' 表。
    (中文注释：此函数无变化)
    """
    try:
        conn = get_db()
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
        logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

def add_nomination(nominee_name, comment_text):
    """
    向数据库中添加一条新的提名记录。
    (中文注释：此函数无变化)
    """
    sql = "INSERT INTO votes (nominee_name, comment_text) VALUES (?, ?)"
    try:
        from flask import g
        db = g.db
        cursor = db.cursor()
        cursor.execute(sql, (nominee_name, comment_text))
        db.commit()
        logging.info(f"Added nomination for: {nominee_name}")
    except sqlite3.Error as e:
        logging.error(f"Failed to add nomination: {e}")
        db.rollback()
        raise

def get_all_nominations():
    """
    从数据库中获取所有提名记录，按时间倒序排列。
    (中文注释：此函数无变化，但新版结果页不再使用它)
    """
    sql = "SELECT nominee_name, comment_text, timestamp FROM votes ORDER BY timestamp DESC"
    try:
        from flask import g
        db = g.db
        cursor = db.cursor()
        cursor.execute(sql)
        nominations = cursor.fetchall()
        return nominations
    except sqlite3.Error as e:
        logging.error(f"Failed to fetch nominations: {e}")
        raise

# --- 新增函数：获取投票统计结果 (中文注释) ---
def get_vote_counts():
    """
    统计每个被提名人的得票数，并按票数从高到低排序。
    这是生成图表的核心数据。
    """
    # SQL解释：
    # SELECT nominee_name, COUNT(id) as vote_count: 选择被提名人姓名，并计算每个人的记录数（即票数），命名为 vote_count
    # FROM votes: 从 votes 表
    # GROUP BY nominee_name: 按姓名进行分组统计
    # ORDER BY vote_count DESC: 按计算出的票数（vote_count）降序排列
    sql = """
        SELECT nominee_name, COUNT(id) as vote_count
        FROM votes
        GROUP BY nominee_name
        ORDER BY vote_count DESC
    """
    try:
        from flask import g
        db = g.db
        cursor = db.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        logging.info("Fetched vote counts successfully.")
        return results
    except sqlite3.Error as e:
        logging.error(f"Failed to fetch vote counts: {e}")
        raise