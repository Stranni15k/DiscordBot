import asyncio
import json
import os
from collections import deque
from datetime import datetime
import disnake
from disnake.ext import commands, tasks
import random

intents = disnake.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)

class Boss:
    MAX_HP = 1500

    def __init__(self):
        self.hp = 1500
        self.users_who_reacted = set()
        self.image_message = None
        self.end_date = None
        self.event_ended = False  # Добавление флага завершения события
        self.last_five_reactions = deque(maxlen=3)
        self.check_event_status.start()

    def damage(self, user_id):
        if user_id not in self.users_who_reacted and datetime.now() < self.end_date:
            self.hp -= 10
            self.users_who_reacted.add(user_id)
            self.last_five_reactions.append(user_id)  # Добавляем ID пользователя
            save_boss_state(self)
            return True
        return False
    def reset(self):
        self.hp = 1500  # Сброс HP
        self.users_who_reacted.clear()  # Очистка списка пользователей
        self.image_message = None  # Сброс сообщения с изображением
        self.end_date = None  # Сброс даты окончания события
        self.event_ended = False  # Сброс флага завершения события

    def health_percentage(self):
        return (self.hp / self.MAX_HP) * 100

    @tasks.loop(seconds=5)
    async def check_event_status(self):
        if self.end_date is not None and datetime.now() >= self.end_date and not self.event_ended:
            self.event_ended = True
            if self.hp > 0:
                # Обновляем сообщение, так как босс не был повержен
                image_url = "https://media.discordapp.net/attachments/1186689230630551552/1186689837143687219/lose.png?ex=65942a08&is=6581b508&hm=db47559a9f69d7ff640de2016dab7d22d7b3cab6cb662bf4c89eee72cbf0fabf&=&format=webp&quality=lossless&width=1433&height=819"  # URL для изображения "босс не повержен"
                embed = disnake.Embed(title="Нападающие захватили город!", description="Рыцари не смогли защитить свой город, нападющие сожгли его до тла \n Армия короля была повержена", color=0xff0000)
                embed.set_image(url=image_url)
                if self.image_message:
                    await self.image_message.edit(embed=embed)
                    save_boss_state(self)

# Функция для сохранения состояния босса в файл
def save_boss_state(boss):
    data = {
        "hp": boss.hp,
        "users_who_reacted": list(boss.users_who_reacted),
        "end_date": boss.end_date.isoformat() if boss.end_date else None,
        "event_ended": boss.event_ended,
        "message_id": boss.image_message.id if boss.image_message else None
    }
    with open("boss_state.json", "w") as file:
        json.dump(data, file)

# Функция для загрузки состояния босса из файла
def load_boss_state(boss):
    if os.path.exists("boss_state.json"):
        with open("boss_state.json", "r") as file:
            data = json.load(file)
            boss.hp = data.get("hp", Boss.MAX_HP)
            boss.users_who_reacted = set(data.get("users_who_reacted", []))
            boss.end_date = datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None
            boss.event_ended = data.get("event_ended", False)
            boss.message_id = data.get("message_id")

def get_boss_image_url(hp):
    if hp >= 1000:
        return "https://media.discordapp.net/attachments/1186689230630551552/1186689840402665532/1.png?ex=65942a09&is=6581b509&hm=c6e1fb916db168d25845dc1ce2726dba7215f3a76044c15f52f621f3f9d8ebfa&=&format=webp&quality=lossless&width=1433&height=819"
    elif hp < 1000 and hp > 500:
        return "https://media.discordapp.net/attachments/1186689230630551552/1186689839551225926/2.png?ex=65942a09&is=6581b509&hm=df4f6ab71363601344026a44e1b1c045c235e9bb708ac456f6d18fbce06b4738&=&format=webp&quality=lossless&width=1433&height=819"
    elif hp < 500:
        return "https://media.discordapp.net/attachments/1186689230630551552/1186689838766882906/3.png?ex=65942a09&is=6581b509&hm=d289e9fdce1797b72db81397235ef464a2b57bee21789ba99bc1cb38d531e94d&=&format=webp&quality=lossless&width=1433&height=819"

boss = Boss()
load_boss_state(boss)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    load_boss_state(boss)
    if boss.message_id:
        channel = bot.get_channel(1186687603320303766)
        if channel:
            try:
                boss.image_message = await channel.fetch_message(boss.message_id)
                print(f"Message restored: {boss.image_message.embeds}")
            except disnake.NotFound:
                print("Message not found.")
        else:
            print("Channel not found.")

@bot.slash_command(name="start_event", description="Босс")
async def start_event(inter, end_date: str):
    if inter.author.id != 564585498555711518:
        await inter.response.send_message("У вас нет доступа к этой команде.", ephemeral=True)
        return

    boss.reset()
    boss.end_date = datetime.strptime(end_date, '%d-%m-%Y %H:%M')
    save_boss_state(boss)

    if boss.check_event_status.is_running():
        boss.check_event_status.restart()
    else:
        boss.check_event_status.start()

    image_url = get_boss_image_url(boss.hp)
    health_percent = boss.health_percentage()
    embed = disnake.Embed(title="На город напала армия противника!", description=f"Нападающих: {boss.hp} человек \n Нужно уничтожить всех и отбить город!", color=0x00ff00)
    embed.set_image(url=image_url)
    boss.image_message = await inter.channel.send(embed=embed)
    await boss.image_message.add_reaction("⚔️")
    await inter.response.send_message(f"Конкурс запущен.", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload: disnake.RawReactionActionEvent):
    # Проверяем, что реакция была добавлена к нужному сообщению
    if payload.message_id != boss.image_message.id or payload.user_id == bot.user.id:
        print(boss.image_message.id)
        return

    channel = await bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user = await bot.fetch_user(payload.user_id)

    if payload.emoji.name == "⚔️":
        if boss.damage(payload.user_id):
            if boss.hp <= 0:
                # Выбираем 5 случайных участников
                lucky_winners = random.sample(boss.users_who_reacted, min(5, len(boss.users_who_reacted)))

                # Асинхронно получаем данные о пользователях
                winners_info = await asyncio.gather(*[bot.fetch_user(winner_id) for winner_id in lucky_winners])

                # Создаем упоминания пользователей
                winners_mentions = [f"<@{winner.id}>" for winner in winners_info]
                winners_message = ", ".join(winners_mentions)

                embed = disnake.Embed(title=f"Город был отбит!", description=f"\n Слава доблестным рыцарям \n Король наградил самых отважных: {winners_message}!", color=0x00ff00)
                embed.set_image(url="https://media.discordapp.net/attachments/1186689230630551552/1186689837932220527/win.png?ex=65942a08&is=6581b508&hm=e0da4a20d0c7fab6ba824047381736de4d7cc3036be2864009a2c7e33330af1f&=&format=webp&quality=lossless&width=1433&height=819")
                await message.edit(embed=embed)
                boss.event_ended = True  # Отмечаем событие как завершенное
            else:
                image_url = get_boss_image_url(boss.hp)
                last_five = list(boss.last_five_reactions)

                # Асинхронно получаем данные о пользователях, которые атаковали
                who_attacked_info = await asyncio.gather(*[bot.fetch_user(attacked_id) for attacked_id in last_five])

                # Создаем упоминания пользователей
                who_attacked_mentions = [f"<@{attacker.id}>" for attacker in who_attacked_info]
                who_attacked_str = ", ".join(who_attacked_mentions)

                health_percent = boss.health_percentage()
                embed = disnake.Embed(title=f"Нанесён удар по армии врага!", description=f"Их осталось {boss.hp} человек. \n Последние удары нанесли: {who_attacked_str}", color=0x00ff00)
                embed.set_image(url=image_url)
                await message.edit(embed=embed)
        else:
            dm_channel = await user.create_dm()
            try:
                await dm_channel.send(f"{user.mention}, вы уже атаковали врага!")
            except disnake.HTTPException:
                # Обработка ошибок
                pass

# Запуск бота
bot.run('MTE4MDEwODMxMTAzNTY1ODI2MA.GLH4d2.9Af5SmZi9R5WTJAi-dVC_LZuhMQaceNVQdQkFI')