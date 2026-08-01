import os
import asyncio
import random
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread

# --- SISTEMA DE WEB SERVER PARA O RENDER NÃO CAIR ---

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

# --- CONFIGURAÇÃO DO BOT ---

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_LOGS_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

@client.event
async def on_ready():
    print(f"[SYS_OK] Core conectado como {client.user.name}")
    try:
        synced = await client.tree.sync()
        print(f"[API_SYNC] {len(synced)} comandos Slash sincronizados com sucesso.")
    except Exception as e:
        print(f"[CRITICAL_ERROR] Erro ao sincronizar comandos: {e}")

# Tarefa em segundo plano otimizada para envio e registro de logs em tempo real
async def background_broadcast(guild, log_channel, payload_msg, operator_name):
    try:
        await guild.fetch_members()
        membros = [m for m in guild.members if not m.bot]
        total_alvos = len(membros)

        start_embed = discord.Embed(
            color=0x00FF00,
            title="⚡ [ROOT_ACCESS] - INJEÇÃO INICIADA",
            description="```ini\n[STATUS] Alocando threads e disparando pacotes em alta velocidade...\n```"
        )
        start_embed.add_field(name="🎯 Alvos Alocados", value=f"`{total_alvos}`", inline=True)
        start_embed.add_field(name="👤 Operador", value=f"`{operator_name}`", inline=True)
        start_embed.set_timestamp()
        await log_channel.send(embed=start_embed)

        enviados = 0
        falhas = 0
        contador = 0

        for member in membros:
            contador += 1
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S")

            try:
                await member.send(payload_msg)
                enviados += 1

                log_embed = discord.Embed(
                    color=0x00FF66,
                    title=f"[+] PACOTE TRANSMITIDO [{contador}/{total_alvos}]",
                    description="```yaml\nStatus: 200 OK - Payload entregue com sucesso\n```"
                )
                log_embed.add_field(name="👤 Alvo Conectado", value=f"`{member}` ({member.id})", inline=False)
                log_embed.add_field(name="🕒 Timestamp", value=f"`{timestamp}`", inline=True)
                log_embed.add_field(name="📊 Progresso", value=f"`{round((contador/total_alvos)*100)}%`", inline=True)
                log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.set_footer(text=f"Node ID: {random.randint(10000, 99999)} // Render Cloud")

                await log_channel.send(embed=log_embed)

            except Exception:
                falhas += 1
                error_embed = discord.Embed(
                    color=0xFF0000,
                    title=f"[-] FALHA NO LINK [{contador}/{total_alvos}]",
                    description="```fix\nErro: 403 Forbidden (DMs fechadas/Bloqueado)\n```"
                )
                error_embed.add_field(name="👤 Alvo Ignorado", value=f"`{member}` ({member.id})", inline=False)
                error_embed.add_field(name="🕒 Timestamp", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=error_embed)

            # Intervalo ajustado para 0.2 segundos (acelera bastante o processo sem estourar o limite rígido da API do Discord)
            await asyncio.sleep(0.2)

        end_embed = discord.Embed(
            color=0x0099FF,
            title="🔒 [RELATÓRIO DE OPERAÇÃO ENCERRADA]",
            description="```prolog\nVarredura concluída. Desconectando sockets.\n```"
        )
        end_embed.add_field(name="✅ Entregas Bem-Sucedidas", value=f"`{enviados}`", inline=True)
        end_embed.add_field(name="❌ Falhas de Conexão", value=f"`{falhas}`", inline=True)
        end_embed.add_field(name="📦 Total Varrido", value=f"`{total_alvos}`", inline=True)
        end_embed.set_timestamp()
        
        await log_channel.send(embed=end_embed)
    except Exception as e:
        print(f"[CRITICAL_ERROR] No background broadcast: {e}")

@client.tree.command(name="config_perfil", description="[ROOT] Altera o nome e a foto de perfil do bot em tempo de execução.")
@app_commands.describe(novo_nome="Novo nome para o bot", nova_foto_url="Link direto da nova foto (URL PNG/JPG)")
@app_commands.default_permissions(administrator=True)
async def config_perfil(interaction: discord.Interaction, novo_nome: str = None, nova_foto_url: str = None):
    await interaction.response.defer(ephemeral=True)
    
    atualizacoes = []

    try:
        if novo_nome:
            await client.user.edit(username=novo_nome)
            atualizacoes.append(f"Nome alterado para: **{novo_nome}**")

        if nova_foto_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(nova_foto_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        await client.user.edit(avatar=avatar_bytes)
                        atualizacoes.append("Avatar atualizado com sucesso.")
                    else:
                        atualizacoes.append("Falha ao baixar a nova imagem (URL inválida).")

        if not atualizacoes:
            return await interaction.edit_reply(content="⚠️ **[AVISO]** Forneça pelo menos um novo nome ou uma nova foto!")

        await interaction.edit_reply(content=f"💻 **[SUCCESS]** Perfil reconfigurado:\n- " + "\n- ".join(atualizacoes))

    except Exception as err:
        print(err)
        await interaction.edit_reply(content="❌ **[ERRO]** O Discord restringe alterações rápidas de perfil (Rate Limit global). Tente mais tarde.")

@client.tree.command(name="executar_payload", description="[ROOT] Inicia varredura e broadcast em massa com telemetria.")
@app_commands.describe(payload_msg="Mensagem a ser injetada nos alvos.")
@app_commands.default_permissions(administrator=True)
async def executar_payload(interaction: discord.Interaction, payload_msg: str):
    # Responde imediatamente ao Discord para evitar o erro 10062 (Unknown interaction)
    await interaction.response.send_message(
        content=f"💻 **[ROOT ACCESS]** Rotina iniciada. Acompanhe os logs em tempo real no canal <#{CANAL_LOGS_ID}>.", 
        ephemeral=True
    )

    guild = interaction.guild
    log_channel = guild.get_channel(CANAL_LOGS_ID)

    if not log_channel:
        return

    # Inicia o processo em segundo plano de forma isolada
    asyncio.create_task(background_broadcast(guild, log_channel, payload_msg, str(interaction.user)))

if __name__ == "__main__":
    if not TOKEN:
        print("[CRITICAL_ERROR] Token do Discord não encontrado nas variáveis de ambiente!")
    else:
        manter_online() # Inicializa o servidor web do Flask para manter ativo no Render
        client.run(TOKEN)

