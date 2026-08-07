import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
from flask import Flask
from threading import Thread
import os
import json

# --- SISTEMA DE WEB SERVER PARA MANTER O BOT ONLINE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def manter_online():
    t = Thread(target=run)
    t.start()

# --- CONFIGURAÇÕES DO BOT ---
class InviteTrackerBot(commands.Bot):
    def __init__(self):
        # Configurando as intenções (Intents) necessárias
        intents = discord.Intents.default()
        intents.members = True # ESSENCIAL: Permite ver quando alguém entra
        intents.invites = True # ESSENCIAL: Permite ler os convites
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)

        # Sistema para guardar quem usou qual convite
        self.invites_cache = {}
        # Arquivo para salvar o canal escolhido (para não resetar ao reiniciar)
        self.config_file = "config.json"
        self.log_channels = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.log_channels, f)

    async def setup_hook(self):
        # Sincroniza os comandos / com o Discord
        await self.tree.sync()
        print("Comandos (Slash Commands) sincronizados com sucesso!")

    async def update_invite_cache(self, guild):
        try:
            invites = await guild.invites()
            self.invites_cache[guild.id] = {invite.code: invite for invite in invites}
        except discord.errors.Forbidden:
            print(f"O bot precisa de permissão de 'Gerenciar Servidor' em: {guild.name}")

bot = InviteTrackerBot()

# --- EVENTOS ---
@bot.event
async def on_ready():
    print(f'Logado com sucesso como {bot.user}!')
    # Salva todos os convites atuais assim que o bot liga
    for guild in bot.guilds:
        await bot.update_invite_cache(guild)

@bot.event
async def on_invite_create(invite):
    await bot.update_invite_cache(invite.guild)

@bot.event
async def on_invite_delete(invite):
    await bot.update_invite_cache(invite.guild)

@bot.event
async def on_member_join(member):
    guild = member.guild
    old_invites = bot.invites_cache.get(guild.id, {})
    
    try:
        new_invites = await guild.invites()
    except discord.errors.Forbidden:
        return

    used_invite = None
    # Compara os convites antigos com os novos para ver qual teve o uso aumentado
    for invite in new_invites:
        if invite.code in old_invites:
            if invite.uses > old_invites[invite.code].uses:
                used_invite = invite
                break
        elif invite.uses > 0:
            used_invite = invite
            break

    # Atualiza a lista após descobrir quem convidou
    await bot.update_invite_cache(guild)

    # Verifica se o comando /setar_canal foi usado neste servidor
    canal_id = bot.log_channels.get(str(guild.id))
    if canal_id:
        canal = guild.get_channel(int(canal_id))
        if canal:
            # === COMO COLOCAR EMOJIS PERSONALIZADOS AQUI ===
            # No Discord, digite \ na frente do emoji (ex: \:emoji_bonito:) e envie.
            # Vai sair algo assim: <:nome:123456789>. Copie isso e cole nas variáveis abaixo:
            emoji_seta = "➡️" # Troque por <:sua_seta:ID>
            emoji_coroa = "👑" # Troque por <:sua_coroa:ID>
            emoji_membro = "👤" # Troque por <:seu_membro:ID>
            
            embed = discord.Embed(
                title=f"Novo Membro no Servidor!",
                description=f"{emoji_seta} Bem-vindo(a) {member.mention}!",
                color=discord.Color.from_rgb(43, 45, 49), # Cor estilo Dark Mode do Discord
                timestamp=datetime.now()
            )
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            
            if used_invite:
                inviter = used_invite.inviter
                # Calcula quantos convites a pessoa que convidou tem no total
                total_invites = sum(i.uses for i in new_invites if i.inviter == inviter)
                
                embed.add_field(name=f"{emoji_coroa} Convidado por:", value=f"{inviter.mention}", inline=False)
                embed.add_field(name="Link Usado:", value=f"`discord.gg/{used_invite.code}`", inline=True)
                embed.add_field(name="Convites dessa pessoa:", value=f"`{total_invites}`", inline=True)
            else:
                embed.add_field(name=f"{emoji_coroa} Convidado por:", value="Não identificado (ou link personalizado).", inline=False)
            
            embed.set_footer(text=f"ID: {member.id}")
            
            await canal.send(embed=embed)

# --- COMANDOS (SLASH COMMANDS) ---
@bot.tree.command(name="setar_canal", description="Escolha em qual canal as mensagens de entrada (invites) vão aparecer.")
@app_commands.checks.has_permissions(administrator=True) # Só admins podem usar
async def setar_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    bot.log_channels[str(interaction.guild.id)] = canal.id
    bot.save_config()
    
    embed = discord.Embed(
        title="✅ Canal Configurado com Sucesso!",
        description=f"Todas as notificações de convites agora serão enviadas em {canal.mention}.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True) # ephemeral=True faz só quem digitou ver a confirmação

@bot.tree.command(name="invites", description="Veja quantos convites você ou outra pessoa tem no servidor.")
async def ver_invites(interaction: discord.Interaction, membro: discord.Member = None):
    if membro is None:
        membro = interaction.user
        
    try:
        invites = await interaction.guild.invites()
    except discord.errors.Forbidden:
        await interaction.response.send_message("O bot precisa de permissão para ler convites!", ephemeral=True)
        return

    # Soma os usos de todos os links criados pelo usuário
    total_uses = sum(i.uses for i in invites if i.inviter == membro)
    
    embed = discord.Embed(
        title="📊 Estatísticas de Convites",
        description=f"{membro.mention} convidou um total de **{total_uses} membros** válidos para o servidor.",
        color=discord.Color.blue()
    )
    if membro.avatar:
        embed.set_thumbnail(url=membro.avatar.url)
        
    await interaction.response.send_message(embed=embed)

# --- INICIALIZAÇÃO E TOKEN ---
manter_online()

# O token é puxado diretamente das Environment Variables (Variáveis de Ambiente) do Render
token = os.environ.get("DISCORD_TOKEN")

if token:
    bot.run(token)
else:
    print("ERRO CRÍTICO: O TOKEN NÃO FOI ENCONTRADO NAS VARIÁVEIS DE AMBIENTE!")

