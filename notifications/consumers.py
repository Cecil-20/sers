import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class IncidentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        # Everyone gets a personal group (in-app notifications). Admins also
        # join the shared admins group; everyone else joins their team's group.
        self.group_names = [f"user_{user.id}"]
        if user.role == 'general_admin':
            self.group_names.append('admins')
        else:
            team_id = await self.get_team_id(user)
            if team_id:
                self.group_names.append(f"team_{team_id}")

        for group in self.group_names:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for group in getattr(self, "group_names", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def force_logout(self, event):
        await self.close()

    async def incident_alert(self, event):
        await self.send(text_data=json.dumps({
            "type": "incident_alert",
            "incident_id": event.get("incident_id"),
            "reference_no": event["reference_no"],
            "severity": event["severity"],
            "category": event["category"],
            "report_method": event.get("report_method"),
        }))

    async def incident_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "incident_status",
            "incident_id": event["incident_id"],
            "reference_no": event["reference_no"],
            "old_status": event["old_status"],
            "status": event["status"],
        }))

    async def user_notification(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "id": event["id"],
            "kind": event["kind"],
            "message": event["message"],
            "incident_id": event["incident_id"],
            "reference_no": event["reference_no"],
            "created_at": event["created_at"],
            "unread_count": event["unread_count"],
        }))

    @database_sync_to_async
    def get_team_id(self, user):
        membership = user.team_memberships.first()
        return membership.team_id if membership else None
