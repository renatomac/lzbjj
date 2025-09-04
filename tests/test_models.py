import unittest
from datetime import datetime, timedelta
from grapple import create_app, db
from grapple.models import User, Member, MembershipPlan, Membership, ClassType, ClassSession

class ModelsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_user_model(self):
        # Test user creation
        user = User(username='testuser', email='test@example.com', first_name='Test', last_name='User')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # Test user retrieval
        retrieved_user = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(retrieved_user)
        self.assertEqual(retrieved_user.email, 'test@example.com')
        self.assertEqual(retrieved_user.first_name, 'Test')
        self.assertEqual(retrieved_user.last_name, 'User')
        
        # Test password hashing
        self.assertTrue(retrieved_user.check_password('password'))
        self.assertFalse(retrieved_user.check_password('wrong_password'))
    
    def test_member_model(self):
        # Test member creation
        member = Member(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='555-1234',
            belt_rank='blue',
            stripes=2
        )
        db.session.add(member)
        db.session.commit()
        
        # Test member retrieval
        retrieved_member = Member.query.filter_by(email='john@example.com').first()
        self.assertIsNotNone(retrieved_member)
        self.assertEqual(retrieved_member.first_name, 'John')
        self.assertEqual(retrieved_member.last_name, 'Doe')
        self.assertEqual(retrieved_member.belt_rank, 'blue')
        self.assertEqual(retrieved_member.stripes, 2)
        
        # Test full_name method
        self.assertEqual(retrieved_member.full_name(), 'John Doe')
    
    def test_membership_model(self):
        # Create a member
        member = Member(first_name='Jane', last_name='Smith', email='jane@example.com')
        db.session.add(member)
        
        # Create a membership plan
        plan = MembershipPlan(name='Basic', price=99.99, billing_frequency='monthly')
        db.session.add(plan)
        db.session.commit()
        
        # Create a membership
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=30)
        membership = Membership(
            member_id=member.id,
            plan_id=plan.id,
            start_date=today,
            end_date=end_date,
            price_paid=99.99,
            payment_status='active'
        )
        db.session.add(membership)
        db.session.commit()
        
        # Test membership retrieval
        retrieved_membership = Membership.query.filter_by(member_id=member.id).first()
        self.assertIsNotNone(retrieved_membership)
        self.assertEqual(retrieved_membership.plan_id, plan.id)
        self.assertEqual(retrieved_membership.start_date, today)
        self.assertEqual(retrieved_membership.end_date, end_date)
        self.assertEqual(retrieved_membership.price_paid, 99.99)
        
        # Test current_membership method
        current = member.current_membership()
        self.assertIsNotNone(current)
        self.assertEqual(current.id, membership.id)
    
    def test_class_session_model(self):
        # Create a class type
        class_type = ClassType(name='Fundamentals', level='beginner')
        db.session.add(class_type)
        
        # Create an instructor
        instructor = User(username='instructor', email='instructor@example.com', role='instructor')
        instructor.set_password('password')
        db.session.add(instructor)
        db.session.commit()
        
        # Create a class session
        today = datetime.utcnow().date()
        start_time = datetime.utcnow().time()
        end_time = (datetime.utcnow() + timedelta(hours=1)).time()
        
        session = ClassSession(
            class_type_id=class_type.id,
            instructor_id=instructor.id,
            date=today,
            start_time=start_time,
            end_time=end_time,
            capacity=20
        )
        db.session.add(session)
        db.session.commit()
        
        # Test class session retrieval
        retrieved_session = ClassSession.query.filter_by(class_type_id=class_type.id).first()
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.instructor_id, instructor.id)
        self.assertEqual(retrieved_session.date, today)
        self.assertEqual(retrieved_session.capacity, 20)
        
        # Test relationships
        self.assertEqual(retrieved_session.class_type.name, 'Fundamentals')
        self.assertEqual(retrieved_session.instructor.username, 'instructor')

if __name__ == '__main__':
    unittest.main()