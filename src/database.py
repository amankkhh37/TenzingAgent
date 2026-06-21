import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "tenzing_growth.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Posts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_url TEXT UNIQUE,
                    group_url TEXT,
                    author_name TEXT,
                    post_text TEXT,
                    timestamp TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Leads table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER,
                    intent TEXT,
                    destination TEXT,
                    lead_score INTEGER,
                    reason TEXT,
                    suggested_reply TEXT,
                    status TEXT DEFAULT 'pending', -- pending, approved, rejected, posted
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                )
            ''')
            
            # Comments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER,
                    comment_text TEXT,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                )
            ''')
            conn.commit()

    def save_post(self, post_data: Dict) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO posts (post_url, group_url, author_name, post_text, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    post_data['post_url'],
                    post_data['group_url'],
                    post_data['author_name'],
                    post_data['post_text'],
                    post_data['timestamp']
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving post: {e}")
            return -1

    def save_lead(self, lead_data: Dict):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO leads (post_id, intent, destination, lead_score, reason, suggested_reply)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    lead_data['post_id'],
                    lead_data['intent'],
                    lead_data['destination'],
                    lead_data['lead_score'],
                    lead_data['reason'],
                    lead_data['suggested_reply']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving lead: {e}")

    def update_lead_status(self, lead_id: int, status: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE leads SET status = ? WHERE id = ?', (status, lead_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating lead status: {e}")

    def save_comment(self, post_id: int, comment_text: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO comments (post_id, comment_text) VALUES (?, ?)', (post_id, comment_text))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving comment: {e}")

    def get_pending_leads(self) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT l.*, p.post_text, p.post_url, p.author_name 
                    FROM leads l
                    JOIN posts p ON l.post_id = p.id
                    WHERE l.status = 'pending'
                    ORDER BY l.lead_score DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching pending leads: {e}")
            return []
