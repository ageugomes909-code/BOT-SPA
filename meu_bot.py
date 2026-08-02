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
            await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
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
# SISTEMA DE LOGS ESTILO OBSERVADOR (RÁPIDO E FLUIDO)
# ==============================================
async def processar_envio_elegante(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro encontrado para o envio.")
            return

        def gerar_barra(atual, maximo, tamanho=15):
            if maximo == 0:
                return f"[{'░'*tamanho}] 0%"
            pct = int((atual / maximo) * 100)
            preenchido = int((atual / maximo) * tamanho)
            barra = "█" * preenchido + "░" * (tamanho - preenchido)
            return f"[{barra}] {pct}%"

        # PAINEL OBSERVADOR INICIAL
        embed_painel = discord.Embed(
            title="👁️ [OBSERVADOR] - MONITOR DE TRANSMISSÃO",
            description="```ini\n[STATUS]: Operando em Modo Turbo Concorrente (Alta Performance)\n```",
            color=0x00E5FF
        )
        embed_painel.add_field(name="🎯 Alvos Detectados", value=f"`{total} membros`", inline=True)
        embed_painel.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_painel.add_field(name="⚡ Velocidade", value="`Otimizada`", inline=True)
        embed_painel.add_field(name="📊 Progresso", value="`[░░░░░░░░░░░░░░░] 0%` (✅ 0 | ❌ 0)", inline=False)
        embed_painel.set_footer(text="Central de Inteligência • Sistema de Monitoramento v3.0")
        embed_painel.timestamp = discord.utils.utcnow()

        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # Semáforo para controlar requisições em paralelo com segurança
        semaphore = asyncio.Semaphore(8)

        async def enviar_dm(membro):
            nonlocal sucessos, falhas
            async with semaphore:
                try:
                    await membro.send(mensagem)
                    sucessos += 1
                except Exception:
                    falhas += 1

        # Criação de tarefas para disparo simultâneo
        tarefas = [enviar_dm(membro) for membro in membros]
        
        # Execução em lotes rápidos atualizando a tela dinamicamente
        bloco_tamanho = 12
        for i in range(0, len(tarefas), bloco_tamanho):
            lote = tarefas[i:i + bloco_tamanho]
            await asyncio.gather(*lote)
            concluidos = min(i + bloco_tamanho, total)

            # Atualiza o painel do observador em tempo real
            embed_painel.set_field_at(
                3,
                name="📊 Progresso",
                value=f"`{gerar_barra(concluidos, total)}` (✅ {sucessos} | ❌ {falhas})",
                inline=False
            )
            try:
                await painel_msg.edit(embed=embed_painel)
            except:
                pass

            await asyncio.sleep(0.2)

        tempo_decorrido = round(time.time() - inicio_tempo, 2)
        velocidade_media = round(total / tempo_decorrido, 1) if tempo_decorrido > 0 else total

        # PAINEL FINAL DE RELATÓRIO DO OBSERVADOR
        embed_fim = discord.Embed(
            title="🏁 [OBSERVADOR] - RELATÓRIO DE MISSÃO CONCLUÍDO",
            description="```ini\n[DIAGNÓSTICO]: Transmissão finalizada com sucesso absoluto.\n```",
            color=0x00FF66
        )
        embed_fim.add_field(name="✅ Entregas Bem-Sucedidas", value=f"`{sucessos}`", inline=True)
        embed_fim.add_field(name="❌ Falhas (DMs Fechadas)", value=f"`{falhas}`", inline=True)
        embed_fim.add_field(name="📦 Total Processado", value=f"`{total}`", inline=True)
        embed_fim.add_field(name="⏱️ Tempo Gasto", value=f"`{tempo_decorrido}s`", inline=True)
        embed_fim.add_field(name="🚀 Performance Média", value=f"`{velocidade_media} msgs/s`", inline=True)
        embed_fim.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"Erro no processamento: {e}")
        await log_channel.send(f"🚨 Ocorreu um erro crítico no sistema observador: `{e}`")

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
@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros do servidor")
@app_commands.describe(
    mensagem="Mensagem que será enviada no PV de todos",
    canal_logs="Canal de logs onde será exibido o andamento (Opcional)"
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
        content=f"⚡ **Modo Turbo Ativado!** O Observador iniciou o envio. Acompanhe no canal: {target_channel.mention}",
        ephemeral=True
    )

    asyncio.create_task(
        processar_envio_elegante(
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
        await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
        return

    guilds = client.guilds
    if not guilds:
        await interaction.response.send_message("O bot não está conectado a nenhum servidor no momento.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🌐 Lista de Servidores Conectados",
        description=f"O bot está ativo em **{len(guilds)}** servidor(es):",
        color=0x3498DB
    )

    for g in guilds[:10]:
        embed.add_field(
            name=f"📌 {g.name}",
            value=f"🆔 `ID: {g.id}`\n👥 `Membros: {g.member_count}`",
            inline=False,
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

