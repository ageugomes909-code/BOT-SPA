import os
import asyncio
import time
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ==============================================
# CONFIGURAÇÕES DE SEGURANÇA E PERMISSÃO
# ==============================================
DONO_ID = 1410272734012772524  # Seu ID

usuarios_autorizados_enviar = set()

# ==============================================
# WEB SERVER PARA MANTER O RENDER ONLINE
# ==============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Sistema Operacional & Bot Online!"

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
intents.members = True

client = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

@client.event
async def on_ready():
    print(f"✅ Bot conectado com sucesso como {client.user} | ID: {client.user.id}")
    try:
        synced = await client.tree.sync()
        print(f"🔄 {len(synced)} comandos slash sincronizados.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# CLASSES DE STATUS E DASHBOARD
# ==============================================
class StatusEnvio:
    def __init__(self, total):
        self.total = total
        self.sucessos = 0
        self.falhas = 0
        self.processados = 0
        self.inicio_tempo = time.time()
        self.concluido = False

def gerar_barra_progresso(atual, maximo, tamanho=15):
    if maximo == 0:
        return "░" * tamanho
    porcentagem = atual / maximo
    preenchido = int(porcentagem * tamanho)
    barra = "█" * preenchido + "░" * (tamanho - preenchido)
    return f"`[{barra}] {int(porcentagem * 100)}%`"

# ==============================================
# SISTEMA DE LOGS LINDAS NO CHAT (SEM TXT)
# ==============================================
async def processador_de_logs_visuais(log_channel, fila_logs, status):
    """Agrupa logs e manda em Embeds bonitos a cada 10 envios para não floodar a API"""
    buffer = []
    
    while not status.concluido or not fila_logs.empty():
        try:
            # Aguarda até 1.5s por um novo log
            item = await asyncio.wait_for(fila_logs.get(), timeout=1.5)
            buffer.append(item)
            fila_logs.task_done()
        except asyncio.TimeoutError:
            pass # Segue para verificar se precisa enviar o que já tem

        # Se juntou 10 ou se o envio acabou e sobrou algo no buffer
        if len(buffer) >= 10 or (len(buffer) > 0 and status.concluido and fila_logs.empty()):
            embed = discord.Embed(title="📨 Registro de Envios (Tempo Real)", color=0x2b2d31)
            desc = ""
            for estado, membro, motivo in buffer:
                if estado == "ok":
                    desc += f"✅ {membro.mention} (`{membro.id}`) - **Entregue**\n"
                else:
                    desc += f"❌ {membro.mention} (`{membro.id}`) - *{motivo}*\n"
            
            embed.description = desc
            await log_channel.send(embed=embed)
            buffer.clear()

async def atualizar_dashboard(mensagem_painel, status: StatusEnvio):
    """Atualiza o painel principal a cada 4 segundos"""
    while not status.concluido:
        await asyncio.sleep(4)
        tempo_decorrido = time.time() - status.inicio_tempo
        velocidade = status.processados / tempo_decorrido if tempo_decorrido > 0 else 0
        
        embed = discord.Embed(title="📡 Transmissão Global em Andamento", color=0xF1C40F)
        embed.add_field(name="📈 Progresso Geral", value=gerar_barra_progresso(status.processados, status.total), inline=False)
        embed.add_field(name="✅ Entregues", value=f"`{status.sucessos}`", inline=True)
        embed.add_field(name="❌ Falhas", value=f"`{status.falhas}`", inline=True)
        embed.add_field(name="⚡ Velocidade", value=f"`{velocidade:.1f} msg/s`", inline=True)
        
        try:
            await mensagem_painel.edit(embed=embed)
        except:
            pass

# ==============================================
# LÓGICA DE ENVIO (RÁPIDA, MAS ANTI-SPAM)
# ==============================================
async def disparar_mensagem(membro, mensagem, semaforo, status: StatusEnvio, fila_logs):
    async with semaforo:
        # Delay minúsculo mas vital para o Discord não dar falso-positivo de "DM fechada"
        await asyncio.sleep(0.3) 
        try:
            await membro.send(mensagem)
            status.sucessos += 1
            await fila_logs.put(("ok", membro, "Sucesso"))
        except discord.Forbidden:
            status.falhas += 1
            await fila_logs.put(("erro", membro, "DM Fechada/Bloqueado"))
        except discord.HTTPException as e:
            status.falhas += 1
            motivo = "Rate Limit (Muito Rápido)" if e.status == 429 else f"Erro API {e.status}"
            await fila_logs.put(("erro", membro, motivo))
        except Exception:
            status.falhas += 1
            await fila_logs.put(("erro", membro, "Erro Desconhecido"))
        finally:
            status.processados += 1

async def iniciar_envio_massa(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro válido encontrado.")
            return

        status = StatusEnvio(total)
        fila_logs = asyncio.Queue()

        # Inicia painel
        embed_inicial = discord.Embed(title="🚀 Iniciando Transmissão...", color=0x3498DB)
        painel_msg = await log_channel.send(embed=embed_inicial)

        # Inicia tarefas em background (Dashboard e Fila de Logs)
        task_dash = asyncio.create_task(atualizar_dashboard(painel_msg, status))
        task_logs = asyncio.create_task(processador_de_logs_visuais(log_channel, fila_logs, status))

        # Semáforo controla max de 4 conexões simultâneas (ideal contra ban do Discord)
        semaforo = asyncio.Semaphore(4) 
        
        tasks = [disparar_mensagem(membro, mensagem, semaforo, status, fila_logs) for membro in membros]
        await asyncio.gather(*tasks)

        # Encerramento
        status.concluido = True
        await task_dash
        await task_logs 

        # Atualiza painel final
        tempo_total = int(time.time() - status.inicio_tempo)
        embed_final = discord.Embed(title="🏁 Transmissão Concluída!", color=0x2ECC71)
        embed_final.add_field(name="📈 Progresso Geral", value=gerar_barra_progresso(status.total, status.total), inline=False)
        embed_final.add_field(name="✅ Total Entregues", value=f"`{status.sucessos}`", inline=True)
        embed_final.add_field(name="❌ Total Falhas", value=f"`{status.falhas}`", inline=True)
        embed_final.add_field(name="⏱️ Tempo Decorrido", value=f"`{tempo_total}s`", inline=True)
        await painel_msg.edit(embed=embed_final)

    except Exception as e:
        await log_channel.send(f"🚨 Ocorreu um erro crítico: `{e}`")

# ==============================================
# COMANDOS SLASH
# ==============================================
@client.tree.command(name="autorizar", description="Concede permissão para um usuário usar o comando /enviar")
async def autorizar(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode autorizar novos operadores.", ephemeral=True)
        return
    usuarios_autorizados_enviar.add(usuario.id)
    await interaction.response.send_message(f"✅ {usuario.mention} autorizado.", ephemeral=True)

@client.tree.command(name="remover", description="Remove a permissão de um usuário do comando /enviar")
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode revogar acessos.", ephemeral=True)
        return
    usuarios_autorizados_enviar.discard(usuario.id)
    await interaction.response.send_message(f"⚠️ {usuario.mention} removido.", ephemeral=True)

@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros")
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    is_owner = interaction.user.id == DONO_ID
    is_authorized = interaction.user.id in usuarios_autorizados_enviar
    is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False

    if not (is_owner or is_authorized or is_admin):
        await interaction.response.send_message("❌ Você não possui permissão!", ephemeral=True)
        return

    target_channel = canal_logs or interaction.guild.get_channel(LOG_CHANNEL_ID) or interaction.channel

    await interaction.response.send_message(f"🚀 **Iniciando envio veloz!** Logs em: {target_channel.mention}", ephemeral=True)

    asyncio.create_task(iniciar_envio_massa(interaction.guild, target_channel, mensagem, str(interaction.user)))

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)

