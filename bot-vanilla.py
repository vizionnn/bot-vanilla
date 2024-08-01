import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
from discord.utils import get
import logging
import pytz
import re
import os
import json
from dotenv import load_dotenv
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta

load_dotenv()

# Configurações dos intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

cargo_em_analise_id = 1267282437315104911
cargo_membro_id = 1267282437315104917
canal_solicitar_set = 1267282438074273794
moderator_roles_ids = [
    1267282437411700828,
    1267282437411700827,
    1267282437411700829,
    1267282437352849539,
]

# Questões da prova
questoes_abertas = [
    "Qual seu nome na cidade?",
    "Qual seu passaporte na cidade (ID)?",
]

# Definindo a cor rosa para os embeds
embed_color = discord.Color.from_rgb(255, 194, 255)

class ProvaView(View):
    def __init__(self, bot, user, moderator_roles_ids):
        super().__init__()
        self.bot = bot
        self.user = user
        self.moderator_roles_ids = moderator_roles_ids

    @discord.ui.button(label="Realizar Prova", style=discord.ButtonStyle.green)
    async def realizar_prova(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Iniciando sua prova!", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role_id in self.moderator_roles_ids:
            role = interaction.guild.get_role(role_id)
            overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        
        channel = await interaction.guild.create_text_channel(f"prova-{interaction.user.display_name}", overwrites=overwrites)
        await iniciar_prova(interaction.user, channel)

async def iniciar_prova(user, channel):
    respostas = {}
    try:
        for questao in questoes_abertas:
            embed = discord.Embed(title="Questão Aberta", description=f"{questao}", color=embed_color)
            await channel.send(embed=embed)
            msg = await bot.wait_for('message', timeout=180.0, check=lambda m: m.author == user)
            respostas[questao] = msg.content
            await channel.purge(limit=100)
        
        nome_na_cidade = respostas.get(questoes_abertas[0], "não respondida")
        id_na_cidade = respostas.get(questoes_abertas[1], "não respondida")

        if nome_na_cidade != "não respondida" and id_na_cidade != "não respondida":
            novo_nome = f"{nome_na_cidade} #{id_na_cidade}"
            await user.edit(nick=novo_nome)
            await user.remove_roles(discord.Object(id=cargo_em_analise_id))
            await user.add_roles(discord.Object(id=cargo_membro_id))
        
        await channel.send("Prova concluída! O canal será fechado em 10 segundos.")
    except asyncio.TimeoutError:
        await channel.send("Tempo esgotado! Você precisará iniciar outra prova.")
    finally:
        await asyncio.sleep(10)
        await channel.delete()

async def enviar_ou_editar_mensagem_inicial():
    canal_prova = bot.get_channel(canal_solicitar_set)
    if canal_prova:
        mensagem_inicial = None
        async for message in canal_prova.history(limit=10):
            if message.author == bot.user and message.embeds and message.embeds[0].title == "Vanilla: Prova":
                mensagem_inicial = message
                break

        embed = discord.Embed(
            title="Vanilla: Prova", 
            description="Você terá 3 minutos para iniciar a prova após clicar no botão.", 
            color=embed_color
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/1215880368167718993/c274073554a24903ae2aa8f51e38a635.webp")
        embed.set_image(url="https://cdn.discordapp.com/attachments/1218681672699220108/1226962867022987395/gif_animado.gif?ex=66abd4b7&is=66aa8337&hm=d351447bebc168606741b0b79d9051bd611239e6ecd3c76582fc6d20dcbcfdf6&")
        embed.set_footer(text="Faça sua parte e se junte a maior família da cidade!")

        view = ProvaView(bot, None, moderator_roles_ids)

        if mensagem_inicial:
            await mensagem_inicial.edit(embed=embed, view=view)
        else:
            await canal_prova.send(embed=embed, view=view)

@tasks.loop(minutes=3)
async def verificar_interacao():
    await enviar_ou_editar_mensagem_inicial()

@bot.event
async def on_member_join(member):
    cargo_em_analise = member.guild.get_role(cargo_em_analise_id)
    await member.add_roles(cargo_em_analise)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if not verificar_interacao.is_running():
        verificar_interacao.start()

# Rodar o bot com o token do ambiente
bot.run(os.getenv("DISCORD_TOKEN"))