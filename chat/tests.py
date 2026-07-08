from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage, RoomLastRead

User = get_user_model()

class ChatAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', email='alice@example.com', password='password123')
        self.user2 = User.objects.create_user(username='bob', email='bob@example.com', password='password123')
        self.client.login(username='alice', password='password123')

    def test_create_direct_chat(self):
        url = reverse('chat:get_or_create_direct_chat_api')
        response = self.client.post(url, data={'user_id': self.user2.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('room_id', data)
        room_id = data['room_id']
        
        # Verify room exists in database
        room = ChatRoom.objects.get(id=room_id)
        self.assertFalse(room.is_group)
        self.assertEqual(room.participants.count(), 2)

    def test_send_message(self):
        # Create a room
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(self.user1, self.user2)
        
        url = reverse('chat:send_message_api', args=[room.id])
        response = self.client.post(url, data={'content': 'Hello, Bob!'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['content'], 'Hello, Bob!')
        
        # Verify message exists in database
        msg = ChatMessage.objects.filter(room=room).first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.content, 'Hello, Bob!')
        self.assertEqual(msg.sender, self.user1)

    def test_room_detail_api(self):
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(self.user1, self.user2)
        ChatMessage.objects.create(room=room, sender=self.user1, content='Hey')
        
        url = reverse('chat:chat_room_detail_api', args=[room.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['room_id'], room.id)
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['content'], 'Hey')
