import asyncio
import json
import time
import uuid

import disnake
from disnake.ext import commands, tasks
from datetime import datetime, timedelta
import random

class GiveawayBot(commands.InteractionBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.giveaways = []
        self.check_giveaways.start()
        self.update_giveaways.start()

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        await self.load_giveaways()

    @tasks.loop(minutes=1)  # Запуск каждую минуту для более частого обновления
    async def update_giveaways(self):
        for giveaway in self.giveaways:
            if not giveaway.ended and giveaway.message_id:
                channel = self.get_channel(giveaway.announcement_channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(giveaway.message_id)
                        unix_timestamp = int(time.mktime(giveaway.end_time.timetuple()))
                        formatted_end_time = f"<t:{unix_timestamp}:R> (<t:{unix_timestamp}:D>)"
                        new_embed = disnake.Embed(title=giveaway.name,
                                                  description=f"Ends: {formatted_end_time}\nEntries: {len(giveaway.entries)}\nWinners: {giveaway.winners_count}",
                                                  color=disnake.Color.blue())
                        await message.edit(embed=new_embed)  # Обновление Embed с новым временем окончания
                    except Exception as e:
                        print(f"Error while updating giveaway: {e}")

    @update_giveaways.before_loop
    async def before_update_giveaways(self):
        await self.wait_until_ready()

    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        current_time = datetime.now().replace(microsecond=0)
        giveaways_to_remove = []
        for giveaway in self.giveaways[:]:  # Итерация по копии списка для безопасного удаления
            if current_time >= giveaway.end_time and not giveaway.ended:
                giveaway.ended = True
                winners = giveaway.pick_winners() if giveaway.entries else []

                channel = self.get_channel(giveaway.announcement_channel_id)
                if channel and giveaway.message_id:
                    try:
                        # Преобразование объекта datetime в Unix timestamp
                        unix_timestamp = int(time.mktime(giveaway.end_time.timetuple()))
                        # Форматирование времени окончания в формате Discord
                        formatted_end_time = f"<t:{unix_timestamp}:R> (<t:{unix_timestamp}:D>)"
                        message = await channel.fetch_message(giveaway.message_id)
                        winners_mentions = ', '.join([f'<@{winner_id}>' for winner_id in winners])
                        new_embed = message.embeds[0]  # Копируем исходный Embed
                        new_embed.description = f"Ended: {formatted_end_time}\nEntries: {len(giveaway.entries)}\nWinners: {winners_mentions}"
                        await message.edit(embed=new_embed)  # Обновляем сообщение с новым Embed
                    except Exception as e:
                        print(f"Error fetching message: {e}")

                # Дополнительно, вы можете отправить отдельное сообщение с объявлением победителей
                if winners:
                    await channel.send(f"Поздравляем {winners_mentions}! Вы выйграли {giveaway.name}")
                else:
                    await channel.send(f"Розыгрыш '{giveaway.name}' завершен. Победителей нет.")

                giveaways_to_remove.append(giveaway)

        # Удаляем завершенные розыгрыши из списка и сохраняем изменения в файл
        for giveaway in giveaways_to_remove:
            self.giveaways.remove(giveaway)
        self.save_giveaways()

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.wait_until_ready()

    def get_next_giveaway_id(self):
        last_id = max((giveaway.id for giveaway in self.giveaways), default=0)
        return last_id + 1

    def save_giveaways(self):
        with open('giveaways.json', 'w') as file:
            json.dump([giveaway.to_dict() for giveaway in self.giveaways], file)

    async def load_giveaways(self):
        try:
            with open('giveaways.json', 'r') as file:
                giveaways_data = json.load(file)
                for data in giveaways_data:
                    giveaway = Giveaway.from_dict(data)
                    self.giveaways.append(giveaway)
                    await self.recreate_giveaway_view(giveaway)
        except FileNotFoundError:
            pass

    async def recreate_giveaway_view(self, giveaway):
        if giveaway.message_id:
            channel = self.get_channel(giveaway.announcement_channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(giveaway.message_id)
                    # Создаём новый GiveawayView и Embed
                    embed = disnake.Embed(title=giveaway.name, description=f"Ends: {giveaway.formatted_end_time()}\nEntries: {len(giveaway.entries)}\nWinners: {giveaway.winners_count}", color=disnake.Color.blue())
                    view = GiveawayView(giveaway, embed)
                    await message.edit(embed=embed, view=view)  # Обновляем сообщение
                except Exception as e:
                    print(f"Error while recreating giveaway view: {e}")

class Giveaway:
    def __init__(self, id, name, end_time_str, winners_count):
        self.id = id
        self.name = name
        self.end_time = datetime.strptime(end_time_str, "%d-%m-%Y %H:%M")  # Преобразование строки в datetime
        self.entries = set()
        self.winners_count = winners_count
        self.ended = False
        self.announcement_channel_id = 742147410834489455
        self.message_id = None

    def formatted_end_time(self):
        unix_timestamp = int(time.mktime(self.end_time.timetuple()))
        return f"<t:{unix_timestamp}:R> (<t:{unix_timestamp}:D>)"

    def add_entry(self, user_id):
        self.entries.add(user_id)

    def set_message_id(self, message_id):
        self.message_id = message_id

    def pick_winners(self):
        return random.sample(list(self.entries), min(self.winners_count, len(self.entries)))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "end_time": self.end_time.strftime("%d-%m-%Y %H:%M"),
            "entries": list(self.entries),
            "winners_count": self.winners_count,
            "ended": self.ended,
            "announcement_channel_id": self.announcement_channel_id,
            "message_id": self.message_id
        }

    @staticmethod
    def from_dict(data):
        giveaway = Giveaway(data['id'], data['name'], data['end_time'], data['winners_count'])
        giveaway.entries = set(data['entries'])
        giveaway.ended = data['ended']
        giveaway.announcement_channel_id = data['announcement_channel_id']
        giveaway.message_id = data['message_id']
        return giveaway

bot = GiveawayBot(test_guilds=[409066217475670016], allowed_mentions= disnake.AllowedMentions(everyone = True))

async def giveaway_id_autocomplete(inter: disnake.ApplicationCommandInteraction, user_input: str):
    active_giveaways = [str(giveaway.id) for giveaway in bot.giveaways if not giveaway.ended]
    return [giveaway_id for giveaway_id in active_giveaways if user_input in giveaway_id]

@bot.slash_command(name="end_giveaway", description="Завершить розыгрыш и удалить его из базы данных")
async def end_giveaway(inter, giveaway_id: str = commands.Param(autocomplete=giveaway_id_autocomplete)):
    giveaway_to_end = next((giveaway for giveaway in bot.giveaways if str(giveaway.id) == giveaway_id and not giveaway.ended), None)
    if giveaway_to_end:
        # Удаляем сообщение Discord
        if giveaway_to_end.message_id:
            channel = bot.get_channel(giveaway_to_end.announcement_channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(giveaway_to_end.message_id)
                    await message.delete()
                except Exception as e:
                    await inter.response.send_message(f"Не удалось удалить сообщение: {e}", ephemeral=True)
                    return
            else:
                await inter.response.send_message("Не найден канал объявления.", ephemeral=True)
                return
        else:
            await inter.response.send_message("Message ID не найден.", ephemeral=True)
            return

        # Удаляем розыгрыш из списка и файла JSON
        bot.giveaways.remove(giveaway_to_end)
        bot.save_giveaways()
        await inter.response.send_message(f"Розыгрыш '{giveaway_to_end.name}' завершен и удален.", ephemeral=True)
    else:
        await inter.response.send_message(f"Розыгрыш с ID '{giveaway_id}' не найден.", ephemeral=True)

@bot.slash_command(name="start_giveaway", description="Начать розыгрыш")
async def start_giveaway(inter, name: str, ends: str, winners: int):
    # Преобразование строки с датой и временем в объект datetime
    end_time = datetime.strptime(ends, "%d-%m-%Y %H:%M")

    # Преобразование объекта datetime в Unix timestamp
    unix_timestamp = int(time.mktime(end_time.timetuple()))

    # Создание нового розыгрыша
    new_id = bot.get_next_giveaway_id()
    giveaway = Giveaway(new_id, name, ends, winners)

    # Форматирование времени окончания в формате Discord
    formatted_end_time = f"<t:{unix_timestamp}:R> (<t:{unix_timestamp}:D>)"
    embed = disnake.Embed(title=name, description=f"Ends: {formatted_end_time}\nEntries: 0\nWinners: {winners}", color=disnake.Color.blue())
    view = GiveawayView(giveaway, embed)
    file_path = "lineagechristmas.png"
    file = disnake.File(file_path, filename="lineagechristmas.png")

    await inter.response.send_message(
        f'{inter.guild.default_role} \n 🇷🇺  Участвуйте в НОВОГОДНЕМ КОНКУРСЕ от РПГ-Клуба! ☃️ \n Стань автором самой красивой елочной игрушки и получи подарок! 🎄 \n\n 🇬🇧  Participate in RPG Club\'s NEW YEAR\'S CONTEST! ☃️ \n Become the author of the most beautiful Christmas tree toy and get a gift! 🎄\n https://forum.rpg-club.org/threads/new-year-contest-2024-novogodnij-konkurs-2024.135992/ ',
        file=file,
        embed=embed,
        view=view
    )
    message = await inter.original_response()

    if message:
        giveaway.set_message_id(message.id)  # Сохраняем ID сообщения
        bot.giveaways.append(giveaway)
        bot.save_giveaways()
    else:
        print("Не удалось отправить сообщение или получить его ID")

class GiveawayView(disnake.ui.View):
    def __init__(self, giveaway, embed):
        super().__init__(timeout=None)
        self.giveaway = giveaway
        self.embed = embed

    @disnake.ui.button(style=disnake.ButtonStyle.primary, emoji="🎉", custom_id="join_giveaway")
    async def join_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        # Преобразование объекта datetime в Unix timestamp
        unix_timestamp = int(time.mktime(self.giveaway.end_time.timetuple()))
        # Форматирование времени окончания в формате Discord
        formatted_end_time = f"<t:{unix_timestamp}:R> (<t:{unix_timestamp}:D>)"
        self.giveaway.add_entry(interaction.user.id)
        self.embed.description = f"Ends: {formatted_end_time}\nEntries: {len(self.giveaway.entries)}\nWinners: {self.giveaway.winners_count}"
        await interaction.response.edit_message(embed=self.embed)
        await interaction.followup.send(f"{interaction.user.mention} присоединился к розыгрышу!", ephemeral=True)

bot.run('MTE4MDEwODMxMTAzNTY1ODI2MA.GLH4d2.9Af5SmZi9R5WTJAi-dVC_LZuhMQaceNVQdQkFI')