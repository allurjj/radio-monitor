"""
Notification system tests

Tests all notification providers, trigger logic, rate limiting,
and notification delivery.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


@pytest.mark.unit
class TestNotificationProviders:
    """Test individual notification providers"""

    @pytest.fixture
    def notification_manager(self):
        """Import and return NotificationManager"""
        from radio_monitor.notifications import NotificationManager
        return NotificationManager()

    def test_discord_notification(self, notification_manager):
        """Test Discord notification handler"""
        config = {
            'webhook_url': 'http://test.com/webhook'
        }
        message = {
            'title': 'Test Notification',
            'content': 'Test content',
            'embeds': [{
                'title': 'Test Embed',
                'description': 'Test description'
            }]
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = notification_manager.send_discord(config, message)
            assert result is True
            assert mock_post.called

    def test_slack_notification(self, notification_manager):
        """Test Slack notification handler"""
        config = {
            'webhook_url': 'http://test.com/webhook'
        }
        message = {
            'text': 'Test notification',
            'attachments': [{
                'title': 'Test Attachment',
                'text': 'Test text'
            }]
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = notification_manager.send_slack(config, message)
            assert result is True
            assert mock_post.called

    def test_email_notification(self, notification_manager):
        """Test email notification handler"""
        config = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': 587,
            'username': 'test@test.com',
            'password': 'password',
            'from': 'test@test.com',
            'to': 'recipient@test.com'
        }
        message = {
            'subject': 'Test Subject',
            'body': '<h1>Test HTML Body</h1>'
        }

        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            result = notification_manager.send_email(config, message)
            assert result is True

    def test_telegram_notification(self, notification_manager):
        """Test Telegram notification handler"""
        config = {
            'bot_token': 'test-token',
            'chat_id': 'test-chat-id'
        }
        message = {
            'text': 'Test message',
            'parse_mode': 'Markdown'
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = notification_manager.send_telegram(config, message)
            assert result is True
            assert mock_post.called

    def test_gotify_notification(self, notification_manager):
        """Test Gotify notification handler"""
        config = {
            'server_url': 'http://gotify.test.com',
            'app_token': 'test-token'
        }
        message = {
            'title': 'Test Title',
            'message': 'Test message',
            'priority': 5
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = notification_manager.send_gotify(config, message)
            assert result is True

    def test_ntfy_notification(self, notification_manager):
        """Test Ntfy.sh notification handler"""
        config = {
            'topic': 'test-topic',
            'server': 'https://ntfy.sh'
        }
        message = {
            'title': 'Test',
            'message': 'Test message',
            'priority': 'default'
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = notification_manager.send_ntfy(config, message)
            assert result is True


@pytest.mark.unit
class TestNotificationTriggerLogic:
    """Test notification trigger logic"""

    @pytest.fixture
    def notification_manager(self):
        """Import and return NotificationManager"""
        from radio_monitor.notifications import NotificationManager
        return NotificationManager()

    def test_trigger_scrape_complete(self, notification_manager, test_db):
        """Test scrape_complete trigger"""
        notification_config = {
            'id': 1,
            'type': 'test',
            'enabled': True,
            'config': {},
            'triggers': ['on_scrape_complete']
        }

        event_data = {
            'event_type': 'scrape_complete',
            'severity': 'success',
            'data': {
                'songs_scraped': 100,
                'new_artists': 5
            }
        }

        with patch.object(notification_manager, 'send_discord') as mock_send:
            mock_send.return_value = True

            notification_manager.trigger_notification(
                test_db,
                notification_config,
                event_data
            )
            # Should have been triggered
            # Verify based on your implementation

    def test_trigger_scrape_error(self, notification_manager, test_db):
        """Test scrape_error trigger"""
        notification_config = {
            'id': 1,
            'type': 'test',
            'enabled': True,
            'config': {},
            'triggers': ['on_scrape_error']
        }

        event_data = {
            'event_type': 'scrape_error',
            'severity': 'error',
            'data': {
                'error': 'Scrape failed',
                'station': 'test-station'
            }
        }

        with patch.object(notification_manager, 'send_discord') as mock_send:
            mock_send.return_value = True

            notification_manager.trigger_notification(
                test_db,
                notification_config,
                event_data
            )

    def test_trigger_not_enabled(self, notification_manager, test_db):
        """Test that disabled notifications don't trigger"""
        notification_config = {
            'id': 1,
            'type': 'test',
            'enabled': False,  # Disabled
            'config': {},
            'triggers': ['on_scrape_complete']
        }

        event_data = {
            'event_type': 'scrape_complete',
            'severity': 'success',
            'data': {}
        }

        with patch.object(notification_manager, 'send_discord') as mock_send:
            notification_manager.trigger_notification(
                test_db,
                notification_config,
                event_data
            )

            # Should NOT have been triggered
            assert not mock_send.called

    def test_trigger_mismatch(self, notification_manager, test_db):
        """Test that notifications only trigger on matching events"""
        notification_config = {
            'id': 1,
            'type': 'test',
            'enabled': True,
            'config': {},
            'triggers': ['on_scrape_complete']
        }

        event_data = {
            'event_type': 'import_complete',  # Different event
            'severity': 'success',
            'data': {}
        }

        with patch.object(notification_manager, 'send_discord') as mock_send:
            notification_manager.trigger_notification(
                test_db,
                notification_config,
                event_data
            )

            # Should NOT have been triggered
            assert not mock_send.called


@pytest.mark.unit
class TestNotificationRateLimiting:
    """Test notification rate limiting"""

    def test_rate_limit_prevents_spam(self):
        """Test that rate limiting prevents notification spam"""
        from radio_monitor.notifications import NotificationManager

        manager = NotificationManager()
        manager.rate_limit_minutes = 5  # 5 minute cooldown

        notification_config = {
            'id': 1,
            'type': 'test',
            'enabled': True,
            'config': {},
            'triggers': ['on_test']
        }

        event_data = {
            'event_type': 'test',
            'severity': 'info',
            'data': {}
        }

        with patch.object(manager, 'send_discord') as mock_send:
            mock_send.return_value = True

            # First trigger should work
            manager.trigger_notification(None, notification_config, event_data)
            assert mock_send.call_count == 1

            # Immediate second trigger should be rate-limited
            manager.trigger_notification(None, notification_config, event_data)
            assert mock_send.call_count == 1  # Still 1, not called again


@pytest.mark.unit
class TestNotificationFormatting:
    """Test notification message formatting"""

    @pytest.fixture
    def notification_manager(self):
        """Import and return NotificationManager"""
        from radio_monitor.notifications import NotificationManager
        return NotificationManager()

    def test_format_discord_message(self, notification_manager):
        """Test Discord message formatting"""
        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        formatted = notification_manager.format_discord_message(event_data)
        assert 'embeds' in formatted
        assert len(formatted['embeds']) > 0

    def test_format_slack_message(self, notification_manager):
        """Test Slack message formatting"""
        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        formatted = notification_manager.format_slack_message(event_data)
        assert 'text' in formatted or 'attachments' in formatted

    def test_format_email_message(self, notification_manager):
        """Test email message formatting"""
        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        subject, body = notification_manager.format_email_message(event_data)
        assert subject
        assert body
        assert '<html>' in body.lower()  # HTML format

    def test_format_telegram_message(self, notification_manager):
        """Test Telegram message formatting"""
        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        formatted = notification_manager.format_telegram_message(event_data)
        assert 'text' in formatted


@pytest.mark.integration
class TestNotificationIntegration:
    """Integration tests for notification system"""

    def test_notification_delivery_flow(self, test_db):
        """Test complete notification delivery flow"""
        from radio_monitor.notifications import NotificationManager
        from radio_monitor.database import notifications as notif_db

        manager = NotificationManager()

        # Create a test notification
        config = {'webhook_url': 'http://test.com/webhook'}
        triggers = ['on_test_event']

        notif_id = notif_db.add_notification(
            test_db,
            notification_type='discord',
            name='Test Notification',
            config=config,
            triggers=triggers
        )

        # Trigger the notification
        notification_config = notif_db.get_notifications(test_db)[0]

        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            result = manager.send_notification(
                test_db,
                notification_config['id'],
                event_data
            )

            assert result is True

            # Verify history was logged
            history = notif_db.get_notification_history(test_db, limit=1)
            assert len(history) > 0

    def test_multiple_notifications_single_event(self, test_db):
        """Test triggering multiple notifications from a single event"""
        from radio_monitor.notifications import NotificationManager
        from radio_monitor.database import notifications as notif_db

        manager = NotificationManager()

        # Create multiple notifications
        for i in range(3):
            config = {'webhook_url': f'http://test.com/webhook{i}'}
            notif_db.add_notification(
                test_db,
                notification_type='discord',
                name=f'Test Notification {i}',
                config=config,
                triggers=['on_test_event']
            )

        notifications = notif_db.get_notifications(test_db)
        event_data = {
            'title': 'Test Event',
            'message': 'Test message',
            'severity': 'info'
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            # Trigger all notifications
            for notification in notifications:
                manager.send_notification(test_db, notification['id'], event_data)

            # All should have been called
            assert mock_post.call_count == 3
