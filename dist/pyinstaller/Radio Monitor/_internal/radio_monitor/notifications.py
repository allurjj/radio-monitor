"""
Notification system for Radio Monitor 1.0

Supports 17 notification providers:
- Discord: Webhook with embed support
- Slack: Webhook with attachments
- Email: SMTP with HTML support
- Telegram: Bot API with markdown
- Gotify: Self-hosted push notifications
- Ntfy.sh: Simple HTTP pub/sub
- Mattermost: Webhook with attachments
- Rocket.Chat: Webhook with attachments
- Matrix: Decentralized messaging
- Pushover: Simple mobile push
- Pushbullet: Cross-platform notifications
- Prowl: iOS push notifications
- Boxcar: Multi-platform push
- MQTT: IoT/home automation messaging

Notification Triggers:
- on_scrape_complete: Scrape finished successfully
- on_scrape_error: Scrape failed
- on_import_complete: Lidarr import finished
- on_import_error: Lidarr import failed
- on_playlist_update: Plex playlist updated
- on_playlist_error: Plex playlist failed
- on_high_failure_rate: X% songs failed to match
- on_station_health: Station failed consecutive times
- on_system_error: System-level errors
"""

import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

# Notification trigger definitions
NOTIFICATION_TRIGGERS = {
    'on_scrape_complete': 'Scrape Completed',
    'on_scrape_error': 'Scrape Error',
    'on_import_complete': 'Lidarr Import Complete',
    'on_import_error': 'Lidarr Import Error',
    'on_playlist_update': 'Playlist Updated',
    'on_playlist_error': 'Playlist Error',
    'on_high_failure_rate': 'High Failure Rate',
    'on_station_health': 'Station Health Issue',
    'on_system_error': 'System Error'
}


class NotificationHandler:
    """Base class for notification handlers"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize handler with configuration

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.enabled = config.get('enabled', True)

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level (info, warning, error, critical)
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully, False otherwise
        """
        raise NotImplementedError("Subclasses must implement send()")


class DiscordHandler(NotificationHandler):
    """Discord webhook notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Discord webhook notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        # Map severity to colors
        colors = {
            'info': 0x3498db,      # Blue
            'success': 0x2ecc71,   # Green
            'warning': 0xf39c12,   # Orange
            'error': 0xe74c3c,     # Red
            'critical': 0x8e44ad   # Purple
        }
        color = colors.get(severity, colors['info'])

        # Build embed
        embed = {
            'title': title,
            'description': message,
            'color': color,
            'timestamp': datetime.now().isoformat(),
            'footer': {'text': 'Radio Monitor 1.0'}
        }

        # Add metadata as fields if provided
        if metadata:
            fields = []
            for key, value in metadata.items():
                if value is not None:
                    # Convert value to string and truncate if too long
                    value_str = str(value)
                    if len(value_str) > 1024:
                        value_str = value_str[:1021] + '...'
                    fields.append({'name': key.replace('_', ' ').title(), 'value': value_str, 'inline': True})

            # Limit to 25 fields (Discord limit)
            if fields:
                embed['fields'] = fields[:25]

        payload = {
            'embeds': [embed],
            'username': 'Radio Monitor'
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 204 or 200 <= response.status < 300:
                    logger.info(f"Discord notification sent: {title}")
                    return True
                else:
                    logger.error(f"Discord webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False


class SlackHandler(NotificationHandler):
    """Slack webhook notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Slack webhook notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False

        # Map severity to colors
        colors = {
            'info': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'critical': '#8e44ad'
        }
        color = colors.get(severity, colors['info'])

        # Build attachment
        attachment = {
            'color': color,
            'title': title,
            'text': message,
            'footer': 'Radio Monitor 1.0',
            'ts': int(datetime.now().timestamp())
        }

        # Add metadata as fields
        if metadata:
            fields = []
            for key, value in metadata.items():
                if value is not None:
                    value_str = str(value)
                    if len(value_str) > 2000:
                        value_str = value_str[:1997] + '...'
                    fields.append({'title': key.replace('_', ' ').title(), 'value': value_str, 'short': True})
            if fields:
                attachment['fields'] = fields

        payload = {
            'attachments': [attachment],
            'username': 'Radio Monitor'
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Slack notification sent: {title}")
                    return True
                else:
                    logger.error(f"Slack webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class EmailHandler(NotificationHandler):
    """Email notifications via SMTP"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send email notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        smtp_server = self.config.get('smtp_server')
        smtp_port = self.config.get('smtp_port', 587)
        username = self.config.get('username')
        password = self.config.get('password')
        from_addr = self.config.get('from_addr', username)
        to_addr = self.config.get('to_addr')

        if not all([smtp_server, username, password, to_addr]):
            logger.error("Email configuration incomplete")
            return False

        # Build HTML message
        severity_colors = {
            'info': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'critical': '#8e44ad'
        }
        color = severity_colors.get(severity, severity_colors['info'])

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f5f5f5; }}
                .footer {{ padding: 10px; text-align: center; color: #666; }}
                .metadata {{ margin-top: 20px; padding: 10px; background-color: #fff; border-left: 3px solid {color}; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{title}</h2>
                </div>
                <div class="content">
                    <p>{message}</p>
        """

        # Add metadata if provided
        if metadata:
            html += '<div class="metadata"><h3>Details</h3><table border="0" cellpadding="5">'
            for key, value in metadata.items():
                if value is not None:
                    html += f'<tr><td><strong>{key.replace("_", " ").title()}:</strong></td><td>{value}</td></tr>'
            html += '</table></div>'

        html += f"""
                </div>
                <div class="footer">
                    <p>Sent by Radio Monitor 1.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[Radio Monitor] {title}"
        msg['From'] = from_addr
        msg['To'] = to_addr

        msg.attach(MIMEText(html, 'html'))

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
                logger.info(f"Email notification sent: {title} to {to_addr}")
                return True
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class TelegramHandler(NotificationHandler):
    """Telegram Bot API notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Telegram bot notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        bot_token = self.config.get('bot_token')
        chat_id = self.config.get('chat_id')

        if not all([bot_token, chat_id]):
            logger.error("Telegram configuration incomplete")
            return False

        # Build message with markdown
        severity_emojis = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'critical': '🚨'
        }
        emoji = severity_emojis.get(severity, severity_emojis['info'])

        text = f"{emoji} *{title}*\n\n{message}"

        # Add metadata
        if metadata:
            text += "\n\n*Details:*\n"
            for key, value in metadata.items():
                if value is not None:
                    text += f"• {key.replace('_', ' ').title()}: {value}\n"

        text += f"\n_Sent by Radio Monitor 1.0_"

        # Send message via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }

        try:
            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    logger.info(f"Telegram notification sent: {title}")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description')}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False


class GotifyHandler(NotificationHandler):
    """Gotify server notifications (self-hosted push notifications)"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Gotify notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        server_url = self.config.get('server_url')
        app_token = self.config.get('app_token')
        priority = self.config.get('priority', 5)

        if not all([server_url, app_token]):
            logger.error("Gotify server URL or app token not configured")
            return False

        # Map severity to priority (1-10)
        severity_priority = {
            'info': 5,
            'success': 4,
            'warning': 7,
            'error': 9,
            'critical': 10
        }
        final_priority = severity_priority.get(severity, priority)

        # Build message
        full_message = message
        if metadata:
            details = '\n\n'.join([f"{k}: {v}" for k, v in metadata.items() if v is not None])
            if details:
                full_message += f"\n\n**Details:**\n{details}"

        payload = {
            'title': title,
            'message': full_message,
            'priority': final_priority,
            'extras': {
                'client::display': {
                    'contentType': 'text/markdown'
                }
            }
        }

        try:
            url = f"{server_url.rstrip('/')}/message?token={app_token}"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    logger.info(f"Gotify notification sent: {title}")
                    return True
                else:
                    logger.error(f"Gotify server returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Gotify notification: {e}")
            return False


class NtfyHandler(NotificationHandler):
    """Ntfy.sh notifications (simple HTTP pub/sub)"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Ntfy.sh notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        topic = self.config.get('topic')
        server_url = self.config.get('server_url', 'https://ntfy.sh')
        priority = self.config.get('priority', 3)
        auth_token = self.config.get('auth_token')

        if not topic:
            logger.error("Ntfy topic not configured")
            return False

        # Map severity to priority (1-5)
        severity_priority = {
            'info': 3,
            'success': 2,
            'warning': 4,
            'error': 5,
            'critical': 5
        }
        final_priority = severity_priority.get(severity, priority)

        # Build message
        full_message = f"{title}\n\n{message}"
        if metadata:
            details = '\n'.join([f"{k}: {v}" for k, v in metadata.items() if v is not None])
            if details:
                full_message += f"\n\n{details}"

        payload = full_message.encode('utf-8')

        try:
            url = f"{server_url.rstrip('/')}/{topic}"
            req = urllib.request.Request(url, data=payload, method='POST')

            # Add headers
            headers = {
                'Title': title,
                'Priority': str(final_priority),
                'Content-Type': 'text/plain; charset=utf-8'
            }

            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"

            for key, value in headers.items():
                req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Ntfy notification sent: {title}")
                    return True
                else:
                    logger.error(f"Ntfy server returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Ntfy notification: {e}")
            return False


class MattermostHandler(NotificationHandler):
    """Mattermost webhook notifications (similar to Slack)"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Mattermost webhook notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        webhook_url = self.config.get('webhook_url')
        channel = self.config.get('channel')
        username = self.config.get('username', 'Radio Monitor')
        icon_url = self.config.get('icon_url', '')

        if not webhook_url:
            logger.error("Mattermost webhook URL not configured")
            return False

        # Map severity to colors
        colors = {
            'info': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'critical': '#8e44ad'
        }
        color = colors.get(severity, colors['info'])

        # Build attachment
        text = f"**{title}**\n{message}"

        payload = {
            'channel': channel,
            'username': username,
            'icon_url': icon_url,
            'text': text,
            'props': {
                'attachments': [{
                    'title': title,
                    'text': message,
                    'color': color
                }]
            }
        }

        # Add metadata as fields
        if metadata:
            fields = []
            for key, value in metadata.items():
                if value is not None:
                    value_str = str(value)
                    if len(value_str) > 2000:
                        value_str = value_str[:1997] + '...'
                    fields.append({'title': key.replace('_', ' ').title(), 'value': value_str, 'short': True})
            if fields:
                payload['props']['attachments'][0]['fields'] = fields

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Mattermost notification sent: {title}")
                    return True
                else:
                    logger.error(f"Mattermost webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Mattermost notification: {e}")
            return False


class RocketchatHandler(NotificationHandler):
    """Rocket.Chat webhook notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Rocket.Chat webhook notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        webhook_url = self.config.get('webhook_url')
        username = self.config.get('username', 'Radio Monitor')
        emoji = self.config.get('emoji', ':robot_face:')

        if not webhook_url:
            logger.error("Rocket.Chat webhook URL not configured")
            return False

        # Map severity to colors
        colors = {
            'info': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'critical': '#8e44ad'
        }
        color = colors.get(severity, colors['info'])

        # Build attachment
        text = f"**{title}**\n{message}"

        payload = {
            'username': username,
            'emoji': emoji,
            'text': text,
            'attachments': [{
                'title': title,
                'text': message,
                'color': color
            }]
        }

        # Add metadata as fields
        if metadata:
            fields = []
            for key, value in metadata.items():
                if value is not None:
                    value_str = str(value)
                    if len(value_str) > 2000:
                        value_str = value_str[:1997] + '...'
                    fields.append({'title': key.replace('_', ' ').title(), 'value': value_str, 'short': True})
            if fields:
                payload['attachments'][0]['fields'] = fields

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Rocket.Chat notification sent: {title}")
                    return True
                else:
                    logger.error(f"Rocket.Chat webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Rocket.Chat notification: {e}")
            return False


class MatrixHandler(NotificationHandler):
    """Matrix notifications (decentralized messaging)"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Matrix notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        homeserver = self.config.get('homeserver')
        access_token = self.config.get('access_token')
        room_id = self.config.get('room_id')

        if not all([homeserver, access_token, room_id]):
            logger.error("Matrix homeserver, access token, or room ID not configured")
            return False

        # Build formatted message (Markdown)
        formatted_message = f"**{title}**\n\n{message}"

        if metadata:
            details = '\n'.join([f"**{k}:** {v}" for k, v in metadata.items() if v is not None])
            if details:
                formatted_message += f"\n\n{details}"

        # Matrix requires formatted body to be HTML
        html_formatted = formatted_message.replace('\n', '<br>').replace('**', '<strong>')

        payload = {
            'msgtype': 'm.text',
            'body': f"{title}\n\n{message}",
            'format': 'org.matrix.custom.html',
            'formatted_body': html_formatted
        }

        try:
            url = f"{homeserver.rstrip('/')}/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{int(datetime.now().timestamp())}?access_token={access_token}"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='PUT'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    logger.info(f"Matrix notification sent: {title}")
                    return True
                else:
                    logger.error(f"Matrix API returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Matrix notification: {e}")
            return False


class PushoverHandler(NotificationHandler):
    """Pushover mobile push notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Pushover notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        api_token = self.config.get('api_token')
        user_key = self.config.get('user_key')
        device = self.config.get('device', '')
        priority = self.config.get('priority', 0)

        if not all([api_token, user_key]):
            logger.error("Pushover API token or user key not configured")
            return False

        # Map severity to priority (-2 to 2)
        severity_priority = {
            'info': 0,
            'success': -1,
            'warning': 1,
            'error': 1,
            'critical': 2
        }
        final_priority = severity_priority.get(severity, priority)

        # Build message
        full_message = message
        if metadata:
            details = '\n'.join([f"{k}: {v}" for k, v in metadata.items() if v is not None])
            if details:
                full_message += f"\n\n{details}"

        payload = {
            'token': api_token,
            'user': user_key,
            'title': title,
            'message': full_message,
            'priority': final_priority
        }

        if device:
            payload['device'] = device

        try:
            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(
                'https://api.pushover.net/1/messages.json',
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('status') == 1:
                    logger.info(f"Pushover notification sent: {title}")
                    return True
                else:
                    logger.error(f"Pushover API error: {result.get('errors', 'Unknown error')}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")
            return False


class PushbulletHandler(NotificationHandler):
    """Pushbullet cross-platform notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Pushbullet notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        api_key = self.config.get('api_key')
        device_iden = self.config.get('device_iden', '')

        if not api_key:
            logger.error("Pushbullet API key not configured")
            return False

        # Build notification
        payload = {
            'type': 'note',
            'title': title,
            'body': message
        }

        if device_iden:
            payload['device_iden'] = device_iden

        try:
            data = json.dumps(payload).encode('utf-8')
            url = 'https://api.pushbullet.com/v2/pushes'
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Access-Token': api_key
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Pushbullet notification sent: {title}")
                    return True
                else:
                    logger.error(f"Pushbullet API returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Pushbullet notification: {e}")
            return False


class ProwlHandler(NotificationHandler):
    """Prowl iOS push notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Prowl notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        api_key = self.config.get('api_key')
        provider_key = self.config.get('provider_key', '')
        priority = self.config.get('priority', 0)

        if not api_key:
            logger.error("Prowl API key not configured")
            return False

        # Map severity to priority (-2 to 2)
        severity_priority = {
            'info': 0,
            'success': -1,
            'warning': 1,
            'error': 1,
            'critical': 2
        }
        final_priority = severity_priority.get(severity, priority)

        # Build application name
        application = self.config.get('application', 'Radio Monitor')

        try:
            params = {
                'apikey': api_key,
                'providerkey': provider_key,
                'application': application,
                'event': title,
                'description': message,
                'priority': final_priority
            }

            data = urllib.parse.urlencode(params).encode('utf-8')
            req = urllib.request.Request(
                'https://api.prowlapp.com/publicapi/add',
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    result = response.read().decode('utf-8')
                    if 'success code="200"' in result:
                        logger.info(f"Prowl notification sent: {title}")
                        return True
                    else:
                        logger.error(f"Prowl API error: {result}")
                        return False
                else:
                    logger.error(f"Prowl API returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Prowl notification: {e}")
            return False


class BoxcarHandler(NotificationHandler):
    """Boxcar multi-platform push notifications"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send Boxcar notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        access_token = self.config.get('access_token')

        if not access_token:
            logger.error("Boxcar access token not configured")
            return False

        # Build notification
        payload = {
            'title': title,
            'body': message,
            'sound': 'cosmic'
        }

        # Map severity to sound
        sounds = {
            'info': 'notifier-2',
            'success': 'magic-1',
            'warning': 'warning-1',
            'error': 'glass',
            'critical': 'alarm'
        }
        if severity in sounds:
            payload['sound'] = sounds[severity]

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                'https://boxcar-api-production.herokuapp.com/notifications',
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {access_token}"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 201:
                    logger.info(f"Boxcar notification sent: {title}")
                    return True
                else:
                    logger.error(f"Boxcar API returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Boxcar notification: {e}")
            return False


class MQTTPublisher(NotificationHandler):
    """MQTT notifications for IoT/home automation"""

    def send(self, title: str, message: str,
             severity: str = 'info',
             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send MQTT notification

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt library not installed. Install with: pip install paho-mqtt")
            return False

        broker = self.config.get('broker')
        port = self.config.get('port', 1883)
        topic = self.config.get('topic', 'radio-monitor/notifications')
        username = self.config.get('username', '')
        password = self.config.get('password', '')
        qos = self.config.get('qos', 1)
        retain = self.config.get('retain', False)

        if not broker:
            logger.error("MQTT broker not configured")
            return False

        # Build payload
        payload = {
            'title': title,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }

        if metadata:
            payload['metadata'] = metadata

        try:
            client = mqtt.Client()

            if username and password:
                client.username_pw_set(username, password)

            client.connect(broker, port, timeout=10)

            result = client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"MQTT notification sent: {title} to {topic}")
                return True
            else:
                logger.error(f"MQTT publish failed with code: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Failed to send MQTT notification: {e}")
            return False


def get_handler(notification_type: str, config: Dict[str, Any]) -> Optional[NotificationHandler]:
    """Factory function to get notification handler

    Args:
        notification_type: Type of notification (discord, slack, email, telegram)
        config: Configuration dictionary

    Returns:
        NotificationHandler instance or None if type not found
    """
    handlers = {
        'discord': DiscordHandler,
        'slack': SlackHandler,
        'email': EmailHandler,
        'telegram': TelegramHandler,
        'gotify': GotifyHandler,
        'ntfy': NtfyHandler,
        'mattermost': MattermostHandler,
        'rocketchat': RocketchatHandler,
        'matrix': MatrixHandler,
        'pushover': PushoverHandler,
        'pushbullet': PushbulletHandler,
        'prowl': ProwlHandler,
        'boxcar': BoxcarHandler,
        'mqtt': MQTTPublisher
    }

    handler_class = handlers.get(notification_type)
    if not handler_class:
        logger.error(f"Unknown notification type: {notification_type}")
        return None

    return handler_class(config)


def send_notification(notification_type: str, config: Dict[str, Any],
                     title: str, message: str,
                     severity: str = 'info',
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Send a notification using the specified provider

    Args:
        notification_type: Type of notification (discord, slack, email, telegram)
        config: Configuration dictionary for the provider
        title: Notification title
        message: Notification message
        severity: Severity level (info, warning, error, critical)
        metadata: Additional metadata

    Returns:
        bool: True if sent successfully, False otherwise
    """
    handler = get_handler(notification_type, config)
    if not handler:
        return False

    if not handler.enabled:
        logger.debug(f"Notification handler {notification_type} is disabled")
        return False

    return handler.send(title, message, severity, metadata)


def send_notifications(db, event_type: str, title: str,
                      message: str, severity: str = 'info',
                      metadata: Optional[Dict[str, Any]] = None) -> int:
    """Send notifications to all enabled providers for the given event type

    Args:
        db: RadioDatabase instance
        event_type: Event type (must match a trigger)
        title: Notification title
        message: Notification message
        severity: Severity level
        metadata: Additional metadata

    Returns:
        int: Number of notifications sent successfully
    """
    from radio_monitor.database import notifications as notif_db

    cursor = db.get_cursor()
    try:
        # Get enabled notifications that should trigger on this event
        notifications = notif_db.get_notifications_for_event(cursor, event_type)

        sent_count = 0
        for notification in notifications:
            # Config is already decoded as dict by get_notifications_for_event
            config = notification['config']
            success = send_notification(
                notification['notification_type'],
                config,
                title,
                message,
                severity,
                metadata
            )

            # Log to history
            notif_db.log_notification_send(
                cursor,
                notification['id'],
                event_type,
                severity,
                title,
                message,
                success
            )

            # Update notification stats
            if success:
                sent_count += 1
                notif_db.update_notification_triggered(cursor, notification['id'])
            else:
                notif_db.increment_notification_failures(cursor, notification['id'])

        db.conn.commit()
        return sent_count
    finally:
        cursor.close()
