import unittest
from flask import url_for
from grapple import create_app, db
from grapple.models import User, Member, MembershipPlan, Membership, ClassType
from datetime import datetime, timedelta

class RoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client(use_cookies=True)
        
        # Create test user
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            role='admin'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def login(self):
        return self.client.post(
            url_for('auth.login'),
            data={
                'username': 'testuser',
                'password': 'password'
            },
            follow_redirects=True
        )
    
    def test_login_and_logout(self):
        # Test login
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back', response.data)
        
        # Test logout
        response = self.client.get(url_for('auth.logout'), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'You have been logged out', response.data)
    
    def test_dashboard_access(self):
        # Test access without login
        response = self.client.get(url_for('dashboard.index'), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In', response.data)
        
        # Test access with login
        self.login()
        response = self.client.get(url_for('dashboard.index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
    
    def test_member_routes(self):
        self.login()
        
        # Test member list
        response = self.client.get(url_for('members.index'))
        self.assertEqual(response.status_code, 200)
        
        # Test member creation
        response = self.client.post(
            url_for('members.create'),
            data={
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
                'phone': '555-1234',
                'belt_rank': 'white',
                'stripes': '0',
                'join_date': datetime.utcnow().date().strftime('%Y-%m-%d'),
                'is_active': 'y'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'John Doe', response.data)
        
        # Test member view
        member = Member.query.filter_by(email='john@example.com').first()
        response = self.client.get(url_for('members.view', member_id=member.id))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'John Doe', response.data)
    
    def test_membership_plan_routes(self):
        self.login()
        
        # Test plan creation
        response = self.client.post(
            url_for('billing.create_plan'),
            data={
                'name': 'Basic Plan',
                'description': 'A basic membership plan',
                'price': '99.99',
                'billing_frequency': 'monthly',
                'is_active': 'y'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Basic Plan', response.data)
        
        # Test plan list
        response = self.client.get(url_for('billing.plans'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Basic Plan', response.data)
    
    def test_class_type_routes(self):
        self.login()
        
        # Test class type creation
        response = self.client.post(
            url_for('classes.create_type'),
            data={
                'name': 'Fundamentals',
                'description': 'Basic techniques',
                'level': 'beginner'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Fundamentals', response.data)
        
        # Test class type list
        response = self.client.get(url_for('classes.types'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Fundamentals', response.data)
    
    def test_add_membership_to_member(self):
        self.login()
        
        # Create a member
        member = Member(
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            join_date=datetime.utcnow().date()
        )
        db.session.add(member)
        
        # Create a membership plan
        plan = MembershipPlan(name='Premium', price=149.99, billing_frequency='monthly')
        db.session.add(plan)
        db.session.commit()
        
        # Test adding membership to member
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=30)
        
        response = self.client.post(
            url_for('members.add_membership', member_id=member.id),
            data={
                'plan_id': str(plan.id),
                'start_date': today.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'price_paid': '149.99',
                'payment_status': 'active'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Membership has been added', response.data)
        
        # Verify membership was created
        membership = Membership.query.filter_by(member_id=member.id).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.plan_id, plan.id)
        self.assertEqual(membership.price_paid, 149.99)

if __name__ == '__main__':
    unittest.main()