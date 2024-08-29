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
from discord.ext import commands
from discord.ext.commands import CooldownMapping, BucketType
import time
from datetime import datetime, timezone, timedelta

# Configurações dos intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Data de início e fim da contagem ~~SEMANAL~~
data_inicio_semanal = datetime(2024, 8, 19, tzinfo=timezone.utc)  # Define a data de início com fuso horário UTC
data_fim_semanal = datetime(2024, 8, 25, tzinfo=timezone.utc)     # Define a data de fim com fuso horário UTC

# Variável para armazenar a mensagem do ranking
mensagem_ranking_smnl = None

# Canal de destino para o ranking
canal_ranking_semanal_id = 1273558603256692822 # ID do canal semanal ranking-tunning

# Variável global para armazenar relatórios
relatorios_smnl = {}

# -------------------------------------------------------------------- RANKING RELATÓRIOS SEMANAL

async def buscar_mensagem_ranking_smnl(canal):
    async for mensagem in canal.history(limit=100):
        if mensagem.author == bot.user and mensagem.embeds and mensagem.embeds[0].title == "👑 Ranking de Relatórios de Tunning Semanal":
            return mensagem
    return None

async def carregar_relatorios_antigos_semanal(channelsemanal):
    global relatorios_smnl
    print(f"Carregando relatórios antigos entre {data_inicio_semanal} e {data_fim_semanal}...")
    async for message in channelsemanal.history(after=data_inicio_semanal, before=data_fim_semanal, limit=None):  # Busca todas as mensagens dentro do período
        print(f"Processando mensagem antiga: {message.content}")
        await processar_relatorio_semanal(message, atualizacao_antiga=True)
    print("Carregamento de relatórios antigos concluído.")

# Função para processar um relatório (novo ou antigo)
async def processar_relatorio_semanal(message, atualizacao_antiga=False):
    global relatorios_smnl

    # Criar dicionário de membros por ID (uma vez, no início da função)
    membros_por_id = {membro.id: membro for membro in message.guild.members}

    # Procura por números na mensagem que são IDs inteiros (não partes de outros números)
    for id_match in re.finditer(r"\b\d+\b", message.content):
        user_id = int(id_match.group(0))
        for membro in membros_por_id.values():
            if str(user_id) == membro.display_name.split()[-1]:  # Verifica se o nome de exibição termina com o ID
                if any(cargo.id in cargos_desejados for cargo in membro.roles):
                    relatorios_smnl[membro.id] = relatorios_smnl.get(membro.id, 0) + 1
                    print(f"Relatório adicionado: {membro.display_name} agora tem {relatorios_smnl[membro.id]} relatórios")
                break
        else:
            print(f"Erro: ID {user_id} não encontrado na lista de membros.")  # Mensagem de erro para ID não encontrado

    if not atualizacao_antiga:
        await exibir_ranking()  # Atualiza o ranking imediatamente se não for uma atualização antiga

# Função para atualizar o ranking
async def exibir_ranking():
    global relatorios_smnl
    global mensagem_ranking_smnl

    # Buscar o canal correto para o ranking
    channelsemanal = bot.get_channel(canal_ranking_semanal_id)

    if not channelsemanal:
        print("Erro: Canal de ranking não encontrado.")
        return

    # Buscar membros com os cargos desejados e seus totais de relatórios
    membros_validos = []
    for role_id in cargos_desejados:
        role = channelsemanal.guild.get_role(role_id)
        if role:
            membros_validos.extend(role.members)

    # Ordenar os membros pelo total de relatórios (decrescente)
    membros_validos.sort(key=lambda membro: relatorios_smnl.get(membro.id, 0), reverse=True)

    # Criar o ranking em formato de texto
    ranking_str = ""
    for i, membro in enumerate(membros_validos, start=1):
        posicao = "🏆`º`" if i == 1 else f"`{i}º`"
        total_relatorios_smnl = relatorios_smnl.get(membro.id, 0)  # Obter o total de relatórios do membro
        ranking_str += f"{posicao} - {membro.mention}: {total_relatorios_smnl} relatórios\n"

    # Obter o horário atual no fuso horário de São Paulo
    current_time_semanal = datetime.now(timezone_brasil).strftime('%H:%M:%S')

    # Criar o embed do ranking
    embed = discord.Embed(title="👑 Ranking de Relatórios de Tunning Semanal\n", description=ranking_str, color=0xffa500)
    embed.set_thumbnail(url=channelsemanal.guild.icon.url)
    embed.add_field(name="\u200b", value=f"**📬 Total de relatórios: {sum(relatorios_smnl.values())}**", inline=False)
    embed.set_footer(text=f"📅 De `{data_inicio_semanal.strftime('%d %B')}` a `{data_fim_semanal.strftime('%d %B')}` \n\n ⏰ Última atualização: {current_time_semanal}")

    # Editar a mensagem existente ou enviar uma nova
    try:
        if mensagem_ranking_smnl:
            # Tentativa de editar a mensagem existente
            await mensagem_ranking_smnl.edit(embed=embed)
        else:
            # Enviar uma nova mensagem se mensagem_ranking_smnl não existir
            mensagem_ranking_smnl = await channelsemanal.send(embed=embed)
    except discord.errors.NotFound:
        # Enviar uma nova mensagem se a mensagem existente não for encontrada (foi deletada)
        mensagem_ranking_smnl = await channelsemanal.send(embed=embed)
    except discord.errors.HTTPException as e:
        print(f"Erro ao atualizar o ranking: {e}")

# Evento para registrar relatórios
@bot.event
async def on_message(message):
    if message.channelsemanal.id == 1235035965945413649:  # Canal #relat-tunning
        # Converter a data da mensagem para offset-aware (UTC) e ajustar para o fuso horário de São Paulo
        message_created_at_aware = message.created_at.replace(tzinfo=timezone.utc).astimezone(timezone_brasil)
        if data_inicio_semanal <= message_created_at_aware < data_fim_semanal:
            await processar_relatorio_semanal(message)

    await bot.process_commands(message)

# Evento para reduzir a contagem de relatórios se a mensagem for apagada
@bot.event
async def on_message_delete(message):
    if message.channelsemanal.id == 1235035965945413649:  # Canal #relat-tunning
        await processar_relatorio_remocao(message)

# Evento para atualizar a contagem de relatórios se a mensagem for editada
@bot.event
async def on_message_edit(before, after):
    if before.channelsemanal.id == 1235035965945413649:  # Canal #relat-tunning
        await processar_relatorio_remocao(before)
        await processar_relatorio_semanal(after)

# Função para processar a remoção de um relatório
async def processar_relatorio_remocao(message):
    global relatorios_smnl

    # Criar dicionário de membros por ID (uma vez, no início da função)
    membros_por_id = {membro.id: membro for membro in message.guild.members}

    # Procura por números na mensagem que são IDs inteiros (não partes de outros números)
    for id_match in re.finditer(r"\b\d+\b", message.content):
        user_id = int(id_match.group(0))
        for membro in membros_por_id.values():
            if str(user_id) == membro.display_name.split()[-1]:  # Verifica se o nome de exibição termina com o ID
                if any(cargo.id in cargos_desejados for cargo in membro.roles):
                    relatorios_smnl[membro.id] = relatorios_smnl.get(membro.id, 0) - 1
                    if relatorios_smnl[membro.id] < 0:
                        relatorios_smnl[membro.id] = 0  # Garante que a contagem não seja negativa
                    print(f"Relatório removido: {membro.display_name} agora tem {relatorios_smnl[membro.id]} relatórios")
                break
        else:
            print(f"Erro: ID {user_id} não encontrado na lista de membros.")  # Mensagem de erro para ID não encontrado

    await exibir_ranking()  # Atualiza o ranking imediatamente

#hierarquia devedores
class HierarquiaDevedores:
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1255178131707265066  # ID do canal de devedores
        self.roles_ids = {
            'adv1': 1235035964556972100,
            'adv2': 1235035964556972101,
            'adv3': 1235035964573880390,
            'adv4': 1255195989778628739,
            'rebaixado': 1235035964556972097,
            'devedor_manutencao': 1255196288698552321,
            'devedor_adv': 1255196379609825350
        }
        self.thumbnail_url = "https://cdn.discordapp.com/attachments/1235035964624080994/1273292957646327898/4a8075045e92cfa895a6c672fad7d1fa.png"
        self.hierarchy_message_id = None

    async def construir_hierarquia(self, guild):
        embed = discord.Embed(
            title="⛔ Hierarquia: Devedores",
            color=discord.Color.dark_red()
        )
        embed.set_thumbnail(url=self.thumbnail_url)

        for role_name, role_id in self.roles_ids.items():
            role = guild.get_role(role_id)
            members_with_role = role.members
            member_mentions = "\n".join([member.mention for member in members_with_role])
            embed.add_field(name=f"{role.name}: ```{len(members_with_role)}```", value=member_mentions if member_mentions else "ㅤ", inline=False)

        return embed

    async def buscar_mensagem_hierarquia(self, channel):
        async for message in channel.history(limit=100):
            if message.author == self.bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.title == "⛔ Hierarquia: Devedores":
                    return message
        return None

    async def atualizar_hierarquia(self, guild):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("Erro: Canal de hierarquia devedores não encontrado.")
            return

        embed = await self.construir_hierarquia(guild)

        if self.hierarchy_message_id:
            try:
                message = await channel.fetch_message(self.hierarchy_message_id)
                await message.edit(embed=embed)
            except discord.errors.NotFound:
                message = await channel.send(embed=embed)
                self.hierarchy_message_id = message.id
        else:
            message = await self.buscar_mensagem_hierarquia(channel)
            if message:
                self.hierarchy_message_id = message.id
                await message.edit(embed=embed)
            else:
                message = await channel.send(embed=embed)
                self.hierarchy_message_id = message.id

    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            await self.atualizar_hierarquia(after.guild)

    async def on_ready(self):
        guild = self.bot.guilds[0]
        await self.atualizar_hierarquia(guild)

# Instancia a classe e associa os eventos
hierarquia_devedores = HierarquiaDevedores(bot)

@bot.event
async def on_member_update(before, after):
    await hierarquia_devedores.on_member_update(before, after)

@bot.event
async def on_ready():
    #CANAL ~~DEVEDORES    
    await hierarquia_devedores.on_ready()   

    # Criar um dicionário de membros por ID ~~RANKING semanal
    global membros_por_id
    membros_por_id = {membro.id: membro for membro in bot.get_all_members()}

    # Carregar relatórios antigos e exibir o ranking inicial
    try:
        canal_relatorios = bot.get_channel(1235035965945413649)  # Canal #relat-tunning
        if canal_relatorios:
            await bot.wait_until_ready()  # Esperar o bot estar pronto
            await carregar_relatorios_antigos_semanal(canal_relatorios)  # Carregar relatórios antigos
            await exibir_ranking()  # Exibir o ranking inicial
    except discord.errors.NotFound:
        print("Erro: Canal de relatórios não encontrado.")
    except discord.errors.Forbidden:
        print("Erro: O bot não tem permissão para ler o histórico de mensagens do canal.")

bot.run(os.getenv("DISCORD_TOKEN"))