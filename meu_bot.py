import os
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands

# ==============================================
# WEB SERVER PARA O RENDER (KEEP ALIVE)
# ==============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Online e Operacional!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def manter_online():
    t = Thread(target=run, daemon=True)
    t.start()

# ==============================================
# CONFIGURAÇÃO DO BOT DISCORD
# ==============================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True # Necessário para listar os membros

client = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")

@client.event
async def on_ready():
    print(f"✅ Bot conectado como: {client.user}")
    try:
        synced = await client.tree.sync()
        print(f"🔄 {len(synced)} comando(s) slash sincronizado(s) com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# COMANDO SLASH: /enviar
# ==============================================
@client.tree.command(name="enviar", description="Envia uma mensagem privada (DM) para todos os membros do servidor")
@app_commands.describe(mensagem="Escreva a mensagem que deseja enviar para todos")
@app_commands.default_permissions(administrator=True)
async def enviar(interaction: discord.Interaction, mensagem: str):
    # Responde imediatamente ao administrador para não dar timeout
    await interaction.response.send_message("🚀 Iniciando envio da mensagem para todos os membros...", ephemeral=True)

    guild = interaction.guild
    if not guild:
        return

    # Carrega a lista completa de membros do servidor
    await guild.chunk()
    membros = [m for m in guild.members if not m.bot]

    for membro in membros:
        try:
            await membro.send(mensagem)
            # Intervalo recomendado para evitar restrições de taxa (rate-limit) do Discord
            await asyncio.sleep(1)
        except Exception:
            # Ignora membros com DM fechada ou que bloquearam o bot
            pass

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 ERRO: Adicione a variável de ambiente DISCORD_TOKEN nas configurações do servidor/Render!")
