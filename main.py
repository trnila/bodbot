import asyncio
import logging
import configparser

from nio import AsyncClient, SyncError, RoomMessageText, InviteEvent, InviteMemberEvent
from nio import ClientConfig

from points import Points

logger = logging.getLogger(__name__)


class BodBot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.points = Points()
        for k, urls in self.config.items():
            if k.startswith('classes.'):
                for clazz, url in urls.items():
                    self.points.add_class(clazz, url)

        self.client = AsyncClient(
                self.config['auth']['homeserver'],
                self.config['auth']['username'],
                device_id='bot',
                config=ClientConfig(store_sync_tokens=True),
                store_path='.'
        )

    def get_login(self, username):
        return username.split(':')[0][1:]

    async def invite_cb(self, room, event):
        logger.info(f"Join: {event.sender}")

        if event.membership == 'join':
            await self.client.join(room.room_id)
        elif event.membership == 'invite':
            await self.send_help(room.room_id, self.get_login(event.sender))

    async def message_cb(self, room, event):
        if event.sender == self.client.user:
            return

        if room.member_count != 2:
            logger.error("Multiple peoples in the room")
            await self.send(room.room_id, "I cant talk due to the GDPR :(")
            return

        if event.body == 'apps':
            await self.send_points(room, self.get_login(event.sender))
        else:
            await self.send_help(room.room_id, self.get_login(event.sender))


    async def send_help(self, room_id, username):
        content = {
            'body': f"Hi @{username}!\nI will give you actual points, if you send me `apps` message.",
            'msgtype': 'm.text',
            "format": "org.matrix.custom.html",
            "formatted_body": f"Hi @{username}!\nI will give you actual points, if you send me <code>apps</code> message."
        }
        await self.client.room_send(room_id, 'm.room.message', content)

    async def send_points(self, room, login):
        pts = await self.points.for_student(login)
        if not pts:
            logger.error("Unknown user: %s", login)
            await self.send(room.room_id, "Unknown user!")
            return
        logging.info("Sending points to: %s", login)

        rows = []
        for task in pts:
            color = "red" if task.points < task.min and task.min > 0 else "green"
            rows.append(f"""
            <tr>
                <th>{task.name}</th>
                <td><font color={color}>{task.points}</font></td>
                <td>{task.min}</td>
                <td>{task.max}</td>
            </tr>""")

        table = "\n".join(rows)

        plain = "\n".join([f"{task.name}: {task.points} min: {task.min}, max: {task.max}" for task in pts])
        content = {
            'body': plain,
            'msgtype': 'm.text',
            "format": "org.matrix.custom.html",
            "formatted_body": f"<table><tr><th>Task</th><th>Points</th><th>Min</th><th>Max</th></tr>{table}</table>"
        }
        await self.client.room_send(room.room_id, 'm.room.message', content)

    async def send(self, room_id, message):
        await self.client.room_send(room_id, 'm.room.message', {"body": message, "msgtype": "m.text"})

    async def start(self):
        await self.points.sync()

        self.client.add_event_callback(self.message_cb, (RoomMessageText, ))
        self.client.add_event_callback(self.invite_cb, (InviteEvent, ))
        await self.client.login(self.config['auth']['password'])
        await self.client.sync_forever(timeout=3000, full_state=True)
 
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('peewee').level = logging.ERROR
bot = BodBot()
asyncio.get_event_loop().run_until_complete(bot.start())
