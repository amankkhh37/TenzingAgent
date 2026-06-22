"""
Tests for Tenzing Growth Agent components
"""
import unittest
import sqlite3
import os
from src.database import Database
from src.lead_scorer import LeadScorer

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db = f"test_tenzing_{self._testMethodName}.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        self.db = Database(self.test_db)
    
    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
    
    def test_save_post(self):
        post_data = {
            "post_url": "https://www.facebook.com/posts/123",
            "group_url": "https://www.facebook.com/groups/123",
            "author_name": "John Doe",
            "post_text": "Looking for travel advice",
            "timestamp": "2 hours ago"
        }
        
        post_id = self.db.save_post(post_data)
        self.assertGreater(post_id, 0)
    
    def test_save_lead(self):
        # First save a post
        post_data = {
            "post_url": "https://www.facebook.com/posts/123",
            "group_url": "https://www.facebook.com/groups/123",
            "author_name": "John Doe",
            "post_text": "Looking for travel advice",
            "timestamp": "2 hours ago"
        }
        post_id = self.db.save_post(post_data)
        
        # Then save a lead
        lead_data = {
            "post_id": post_id,
            "intent": "booking",
            "destination": "Maldives",
            "lead_score": 85,
            "reason": "High intent",
            "suggested_reply": "Great question!"
        }
        self.db.save_lead(lead_data)
        
        # Verify lead was saved
        leads = self.db.get_pending_leads()
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]['lead_score'], 85)
    
    def test_update_lead_status(self):
        # Save post and lead
        post_data = {
            "post_url": "https://www.facebook.com/posts/123",
            "group_url": "https://www.facebook.com/groups/123",
            "author_name": "John Doe",
            "post_text": "Looking for travel advice",
            "timestamp": "2 hours ago"
        }
        post_id = self.db.save_post(post_data)
        
        lead_data = {
            "post_id": post_id,
            "intent": "booking",
            "destination": "Maldives",
            "lead_score": 85,
            "reason": "High intent",
            "suggested_reply": "Great question!"
        }
        self.db.save_lead(lead_data)
        
        # Update status
        lead = self.db.get_pending_leads()[0]
        self.db.update_lead_status(lead['id'], 'approved')
        
        # Verify status changed
        with sqlite3.connect(self.test_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM leads WHERE id = ?', (lead['id'],))
            status = cursor.fetchone()['status']
            self.assertEqual(status, 'approved')

    def test_delete_lead(self):
        # Save post and lead
        post_data = {
            "post_url": "https://www.facebook.com/posts/delete_test",
            "group_url": "https://www.facebook.com/groups/delete_test",
            "author_name": "Delete Tester",
            "post_text": "To be deleted",
            "timestamp": "now"
        }
        post_id = self.db.save_post(post_data)
        
        lead_data = {
            "post_id": post_id,
            "intent": "delete",
            "destination": "Nowhere",
            "lead_score": 50,
            "reason": "Test delete",
            "suggested_reply": "Delete me"
        }
        self.db.save_lead(lead_data)
        
        # Verify lead exists
        leads = self.db.get_pending_leads()
        self.assertEqual(len(leads), 1)
        lead_id = leads[0]['id']
        
        # Delete lead
        self.db.delete_lead(lead_id)
        
        # Verify lead is deleted
        leads_after = self.db.get_pending_leads()
        self.assertEqual(len(leads_after), 0)

if __name__ == '__main__':
    unittest.main()
