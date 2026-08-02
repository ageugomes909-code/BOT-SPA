import os
import asyncio
import time
import io
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ==============================================
# CONFIGURAÇÕES DE SEGURANÇA E PERMISSÃO
# ==============================================
DONO_ID = 1410272734012772524  # ID Principal

# Lista dinâmica de usuários autorizados a usar o /enviar
usuarios_autorizados_enviar = set()

# ==============================================
# WEB SERVER PARA MANTER O RENDER ONLINE (24/7)
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
        print(f"🔄 {len(synced)} comandos slash sincronizados com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# VIEW INTERATIVA PARA GERENCIAR SERVIDORES
# ==============================================
class ServidoresView(discord.ui.View):
    def __init__(self, bot, guilds):
        super().__init__(timeout=120)
        self.bot = bot
        
        options = [
            discord.SelectOption(
                label=g.name[:90],
                value=str(g.id),
                description=f"ID: {g.id} | Membros: {g.member_count}"
            ) for g in guilds[:25]
        ]
        
        if options:
            self.add_item(ServidorSelect(options, bot))

class ServidorSelect(discord.ui.Select):
    def __init__(self, options, bot):
        super().__init__(placeholder="📌 Selecione um servidor para gerenciar...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != DONO_ID:
            await interaction.response.send_message("❌ Este comando é exclusivo do dono.", ephemeral=True)
            return

        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)

        if guild:
            nome_guild = guild.name
            await guild.leave()
            await interaction.response.send_message(
                content=f"✅ O bot saiu com sucesso do servidor **{nome_guild}** (`{guild_id}`).",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True)

# ==============================================
# FUNÇÕES DE LOGS E DASHBOARD EM TEMPO REAL
# ==============================================
class StatusEnvio:
    def __init__(self, total):
        self.total = total
        self.sucessos = 0
        self.falhas = 0
        self.processados = 0
        self.inicio_tempo = time.time()
        self.log_txt = []
        self.concluido = False

def gerar_barra_progresso(atual, maximo, tamanho=20):
    if maximo == 0:
        return "░" * tamanho
    porcentagem = atual / maximo
    preenchido = int(porcentagem * tamanho)
    barra = "█" * preenchido + "░" * (tamanho - preenchido)
    return f"`[{barra}] {int(porcentagem * 100)}%`"

async def atualizar_dashboard(mensagem_painel, status: StatusEnvio):
    """Atualiza o painel no Discord a cada 3 segundos para evitar rate limit do próprio canal."""
    while not status.concluido:
        await asyncio.sleep(3)
        
        tempo_decorrido = time.time() - status.inicio_tempo
        velocidade = status.processados / tempo_decorrido if tempo_decorrido > 0 else 0
        restantes = status.total - status.processados
        eta = (restantes / velocidade) if velocidade > 0 else 0

        embed = discord.Embed(title="📡 Transmissão Global em Andamento", color=0xF1C40F)
        embed.add_field(name="📈 Progresso Geral", value=gerar_barra_progresso(status.processados, status.total), inline=False)
        embed.add_field(name="✅ Entregues", value=f"`{status.sucessos}`", inline=True)
        embed.add_field(name="❌ Falhas", value=f"`{status.falhas}`", inline=True)
        embed.add_field(name="👥 Restantes", value=f"`{restantes}`", inline=True)
        embed.add_field(name="⚡ Velocidade", value=f"`{velocidade:.1f} msgs/s`", inline=True)
        embed.add_field(name="⏱️ Tempo Decorrido", value=f"`{int(tempo_decorrido)}s`", inline=True)
        embed.add_field(name="⏳ ETA (Restante)", value=f"`{int(eta)}s`", inline=True)
        embed.set_footer(text="O relatório final será gerado ao terminar. Por favor, aguarde...")
        
        try:
            await mensagem_painel.edit(embed=embed)
        except:
            pass # Ignora se houver algum erro de edição momentâneo

async def disparar_mensagem(membro, mensagem, semaforo, status: StatusEnvio):
    """Tenta enviar a mensagem respeitando o limite de concorrência e limites do Discord."""
    async with semaforo:
        try:
            await membro.send(mensagem)
            status.sucessos += 1
            status.log_txt.append(f"[SUCESSO] {membro.name} ({membro.id})")
        except discord.Forbidden:
            status.falhas += 1
            status.log_txt.append(f"[FALHA - DMs Fechadas] {membro.name} ({membro.id})")
        except discord.HTTPException as e:
            # 429 = Too Many Requests (Rate Limit). O discord.py lida com isso, 
            # mas se estourar, registramos como falha.
            status.falhas += 1
            status.log_txt.append(f"[FALHA - API Limit {e.status}] {membro.name} ({membro.id})")
        except Exception as e:
            status.falhas += 1
            status.log_txt.append(f"[FALHA - {str(e)[:30]}] {membro.name} ({membro.id})")
        finally:
            status.processados += 1

async def iniciar_envio_massa(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro válido (não-bot) encontrado no servidor.")
            return

        status = StatusEnvio(total)

        # Dashboard Inicial
        embed_inicial = discord.Embed(title="🚀 Iniciando Transmissão...", color=0x3498DB)
        embed_inicial.description = f"**Operador:** `{operador}`\n**Alvos:** `{total} membros`"
        painel_msg = await log_channel.send(embed=embed_inicial)

        # Inicia a task de atualização do Dashboard (roda em background)
        task_dashboard = asyncio.create_task(atualizar_dashboard(painel_msg, status))

        # Define a quantidade máxima de envios SIMULTÂNEOS. 
        # 7 é um número agressivo o suficiente para ser muito rápido, mas seguro contra bans do Discord.
        semaforo = asyncio.Semaphore(7) 
        
        # Cria as tarefas e executa todas usando concorrência
        tasks = [disparar_mensagem(membro, mensagem, semaforo, status) for membro in membros]
        await asyncio.gather(*tasks)

        # Sinaliza que acabou para parar o Dashboard
        status.concluido = True
        await task_dashboard # Espera a última atualização

        # Atualiza Dashboard para Finalizado
        tempo_total = int(time.time() - status.inicio_tempo)
        embed_final = discord.Embed(title="🏁 Transmissão Concluída!", color=0x2ECC71)
        embed_final.add_field(name="📈 Progresso Geral", value=gerar_barra_progresso(status.total, status.total), inline=False)
        embed_final.add_field(name="✅ Entregues", value=f"`{status.sucessos}`", inline=True)
        embed_final.add_field(name="❌ Falhas (DMs fechadas)", value=f"`{status.falhas}`", inline=True)
        embed_final.add_field(name="⏱️ Tempo Total", value=f"`{tempo_total} segundos`", inline=True)
        await painel_msg.edit(embed=embed_final)

        # Gera Arquivo TXT de Logs para não floodar o canal
        conteudo_log = "\n".join(status.log_txt)
        arquivo_log = io.BytesIO(conteudo_log.encode('utf-8'))
        
        await log_channel.send(
            content="📄 **Relatório Detalhado:** Abaixo está o arquivo completo com os detalhes de quem recebeu ou falhou.",
            file=discord.File(fp=arquivo_log, filename="relatorio_envio.txt")
        )

    except Exception as e:
        print(f"Erro no processamento: {e}")
        await log_channel.send(f"🚨 Ocorreu um erro crítico durante o envio: `{e}`")

# ==============================================
# COMANDOS SLASH: /autorizar E /remover
# ==============================================
@client.tree.command(name="autorizar", description="Concede permissão para um usuário usar o comando /enviar")
@app_commands.describe(usuario="Membro que receberá a autorização")
async def autorizar(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode autorizar novos operadores.", ephemeral=True)
        return

    usuarios_autorizados_enviar.add(usuario.id)
    await interaction.response.send_message(
        content=f"✅ O usuário {usuario.mention} (`{usuario.id}`) agora tem permissão para usar o comando `/enviar`.",
        ephemeral=True
    )

@client.tree.command(name="remover", description="Remove a permissão de um usuário do comando /enviar")
@app_commands.describe(usuario="Membro que perderá a autorização")
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode revogar acessos.", ephemeral=True)
        return

    if usuario.id in usuarios_autorizados_enviar:
        usuarios_autorizados_enviar.remove(usuario.id)
        await interaction.response.send_message(
            content=f"⚠️ O usuário {usuario.mention} (`{usuario.id}`) foi removido da lista de autorizados.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(f"❌ O usuário {usuario.mention} não estava na lista de autorizados.", ephemeral=True)

# ==============================================
# COMANDO SLASH: /enviar
# ==============================================
@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros do servidor (Alta Velocidade)")
@app_commands.describe(
    mensagem="Mensagem que será enviada no PV de todos",
    canal_logs="Canal de logs onde será exibido o dashboard (Opcional)"
)
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    is_owner = interaction.user.id == DONO_ID
    is_authorized = interaction.user.id in usuarios_autorizados_enviar
    is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False

    if not (is_owner or is_authorized or is_admin):
        await interaction.response.send_message("❌ Você não possui permissão para usar este comando!", ephemeral=True)
        return

    target_channel = canal_logs
    if not target_channel and LOG_CHANNEL_ID != 0:
        target_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if not target_channel:
        target_channel = interaction.channel

    await interaction.response.send_message(
        content=f"🚀 **Iniciando protocolo de envio ** Acompanhe o dashboard em: {target_channel.mention}",
        ephemeral=True
    )

    asyncio.create_task(
        iniciar_envio_massa(
            guild=interaction.guild,
            log_channel=target_channel,
            mensagem=mensagem,
            operador=str(interaction.user)
        )
    )

# ==============================================
# COMANDO SLASH: /servidores
# ==============================================
@client.tree.command(name="servidores", description="Exibe a lista de servidores em que o bot está instalado")
async def servidores(interaction: discord.Interaction):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Este comando é exclusivo do dono.", ephemeral=True)
        return

    guilds = client.guilds
    if not guilds:
        await interaction.response.send_message("O bot não está conectado a nenhum servidor no momento.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🌐 Lista de Servidores Conectados",
        description=f"O bot está ativo em **{len(guilds)}** servidor(es):",
        color=0x2b2d31
    )

    for g in guilds[:10]:
        embed.add_field(
            name=f"📌 {g.name}",
            value=f"🆔 `ID: {g.id}`\n👥 `Membros: {g.member_count}`",
            inline=False
        )

    view = ServidoresView(client, guilds)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 ERRO: Adicione a variável DISCORD_TOKEN nas configurações do Render!")

