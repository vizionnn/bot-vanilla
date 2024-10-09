import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações dos intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs dos cargos e canais
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
    def __init__(self, bot, user=None, moderator_roles_ids=None):
        super().__init__()
        self.bot = bot
        self.user = user
        self.moderator_roles_ids = moderator_roles_ids

    @discord.ui.button(label="Realizar Prova", style=discord.ButtonStyle.green)
    async def realizar_prova(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Iniciando sua prova!", ephemeral=True)

        # Garantir que o canal seja criado com permissões corretas
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Garantir que os cargos moderadores existam
        for role_id in self.moderator_roles_ids:
            role = interaction.guild.get_role(role_id)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True)
            else:
                print(f"Erro: Cargo com ID {role_id} não encontrado.")

        try:
            # Criação do canal temporário para a prova
            channel = await interaction.guild.create_text_channel(f"prova-{interaction.user.display_name}", overwrites=overwrites)
            print(f"Canal criado: {channel.name} para {interaction.user.display_name}")
            await iniciar_prova(interaction.user, channel)
        except Exception as e:
            print(f"Erro ao criar canal de prova: {e}")
            await interaction.followup.send("Ocorreu um erro ao iniciar sua prova. Por favor, tente novamente mais tarde.", ephemeral=True)

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
            try:
                await user.edit(nick=novo_nome)
                print(f"Apelido alterado para {novo_nome}")
            except discord.Forbidden:
                print(f"Permissão negada para alterar o apelido de {user.display_name}")

            try:
                cargo_em_analise = discord.Object(id=cargo_em_analise_id)
                cargo_membro = discord.Object(id=cargo_membro_id)
                await user.remove_roles(cargo_em_analise)
                await user.add_roles(cargo_membro)
                print(f"Cargo 'membro' adicionado e 'em análise' removido para {user.display_name}")
            except discord.Forbidden:
                print(f"Permissão negada para alterar os cargos de {user.display_name}")
        
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
        async for message in canal_prova.history(limit=20):
            if message.author == bot.user and message.embeds and message.embeds[0].title == "Vanilla: Prova":
                mensagem_inicial = message
                break

        embed = discord.Embed(
            title="Vanilla: Prova", 
            description="Você terá 3 minutos para iniciar a prova após clicar no botão.", 
            color=embed_color
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1221188346206748753/1278505779787206656/image.png")
        embed.set_footer(text="Faça sua parte e se junte a maior família da cidade!")
        
        view = ProvaView(bot, None, moderator_roles_ids)

        if mensagem_inicial:
            # Editar a mensagem existente
            await mensagem_inicial.edit(embed=embed, view=view)
            print("Mensagem existente editada.")
        else:
            # Enviar uma nova mensagem se não existir
            await canal_prova.send(embed=embed, view=view)
            print("Nova mensagem enviada.")
            
@tasks.loop(minutes=3)
async def verificar_interacao():
    await enviar_ou_editar_mensagem_inicial()

@bot.event
async def on_member_join(member):
    cargo_em_analise = member.guild.get_role(cargo_em_analise_id)
    if cargo_em_analise:
        await member.add_roles(cargo_em_analise)
        print(f"{member.display_name} recebeu o cargo 'em análise'.")
    else:
        print("Cargo 'em análise' não encontrado.")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if not verificar_interacao.is_running():
        verificar_interacao.start()

# Rodar o bot com o token do ambiente
bot.run(os.getenv("DISCORD_TOKEN"))
