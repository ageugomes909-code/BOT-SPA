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
DONO_ID = 1410272734012772524  # Seu ID Principal (Único com acesso total e /servidores)

# Lista dinâmica de usuários autorizados a usar o /enviar (gerenciada pelos comandos /autorizar e /remover)
usuarios_autorizados_enviar = set()

# ==============================================
# WEB SERVER PARA MANTER O RENDER ONLINE (24/7)
# ==============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Sistema Operacional & Núcleo Ativo!"

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
    print(f"[✅ KERNEL_OK] Conectado como {client.user} | ID: {client.user.id}")
    try:
        synced = await client.tree.sync()
        print(f"[🔄 API_SYNC] {len(synced)} comandos sincronizados com sucesso.")
    except Exception as e:
        print(f"[❌ ERRO_SYNC] {e}")

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
        super().__init__(placeholder="🚨 [ROOT] Selecione um servidor para evacuação...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        # Trava absoluta: Apenas o Dono Principal pode expulsar o bot
        if interaction.user.id != DONO_ID:
            await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
            return

        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)

        if guild:
            nome_guild = guild.name
            await guild.leave()
            await interaction.response.send_message(
                content=f"⚠️ **[BYPASS EXECUTADO]** O bot foi desconectado à força do servidor **{nome_guild}** (`{guild_id}`).",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ [ERRO] Servidor alvo não encontrado na cache local.", ephemeral=True)

# ==============================================
# FUNÇÃO DE LOGS AVANÇADOS (HACKER/KERNEL STYLE)
# ==============================================
async def processar_envio_avancado(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ `[CRITICAL_WARN]` Nenhum alvo humano elegível na subnet.")
            return

        # BARRA DE PROGRESSO EM ASCII
        def gerar_barra(atual, maximo, tamanho=15):
            if maximo == 0:
                porcentagem = 0
            else:
                porcentagem = int((atual / maximo) * tamanho)
            barra = "█" * porcentagem + "░" * (tamanho - porcentagem)
            pct = int((atual / maximo) * 100) if maximo > 0 else 0
            return f"[{barra}] {pct}%"

        # 1. EMBED DE INICIALIZAÇÃO DE KERNEL
        embed_inicio = discord.Embed(
            title="⚡ [ROOT_ACCESS] - INJEÇÃO DE PAYLOAD GLOBAL",
            description="```ini\n[CORE] Alocando sockets de transmissão em massa...\n[NET] Ignorando nós de IA/Bots...\n[STATUS] Conexão estabelecida com sucesso.\n```",
            color=0x00FF66
        )
        embed_inicio.add_field(name="🎯 Alvos Carregados", value=f"`{total} nós`", inline=True)
        embed_inicio.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_inicio.set_footer(text="Sistemas de telemetria ativa — Aguardando pacotes...")
        embed_inicio.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_inicio)

        # 2. PAINEL DE CONTROLE EM TEMPO REAL
        embed_painel = discord.Embed(
            title="🛡️ [TELEMETRIA DE REDE] - MONITORAMENTO",
            color=0x0099FF
        )
        embed_painel.add_field(name="Estado da Task", value="🔄 `INJETANDO PACOTES...`", inline=False)
        embed_painel.add_field(name="✅ Entregues (200 OK)", value="`0`", inline=True)
        embed_painel.add_field(name="❌ Bloqueados (403/451)", value="`0`", inline=True)
        embed_painel.add_field(name="📊 Progresso de Rede", value=gerar_barra(0, total), inline=False)
        
        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # LOOP DE INJEÇÃO
        for idx, membro in enumerate(membros, start=1):
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S.%f")[:-3]
            
            try:
                # Tenta injetar a mensagem no socket privado do usuário
                await membro.send(mensagem)
                sucessos += 1
                
                # LOG TÉCNICO DE SUCESSO (HACKER STYLE)
                log_embed = discord.Embed(
                    title=f"💻 [SOCKET_OK] -> PACOTE ENVIADO [{idx}/{total}]",
                    color=0x00FF66
                )
                log_embed.add_field(name="🎯 Alvo ID", value=f"`{membro.id}` ({membro.mention})", inline=False)
                log_embed.add_field(name="📦 Payload Entregue", value=f"```text\n{mensagem[:400]}\n```", inline=False)
                log_embed.add_field(name="🕒 Timestamp", value=f"`{timestamp}`", inline=True)
                log_embed.add_field(name="⚡ Código HTTP", value="`0x00 - 200 OK`", inline=True)
                
                if membro.display_avatar:
                    log_embed.set_thumbnail(url=membro.display_avatar.url)
                
                await log_channel.send(embed=log_embed)

            except Exception:
                falhas += 1
                
                # LOG TÉCNICO DE FALHA/BARREIRA DE SEGURANÇA
                err_embed = discord.Embed(
                    title=f"⚠️ [SOCKET_BYPASS_FAIL] -> BARREIRA ATIVADA [{idx}/{total}]",
                    color=0xFF0033
                )
                err_embed.add_field(name="🎯 Alvo ID", value=f"`{membro.id}` ({membro.mention})", inline=False)
                err_embed.add_field(name="🔒 Erro de Sistema", value="```fix\n[403 FORBIDDEN] DM Encerrada / Restrição de Privacidade Ativa\n```", inline=False)
                err_embed.add_field(name="🕒 Timestamp", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            # Atualiza o painel a cada 3 envios para eficiência de fluxo
            if idx % 3 == 0 or idx == total:
                embed_painel.set_field_at(0, name="Estado da Task", value="🔄 `FLUXO DE PACOTES ATIVO...`", inline=False)
                embed_painel.set_field_at(1, name="✅ Entregues (200 OK)", value=f"`{sucessos}`", inline=True)
                embed_painel.set_field_at(2, name="❌ Bloqueados (403/451)", value=f"`{falhas}`", inline=True)
                embed_painel.set_field_at(3, name="📊 Progresso de Rede", value=gerar_barra(idx, total), inline=False)
                await painel_msg.edit(embed=embed_painel)

            # Throttle de segurança para evitar rate-limit global do Discord
            await asyncio.sleep(0.8)

        tempo_decorrido = round(time.time() - inicio_tempo, 2)

        # Atualiza painel para Concluído
        embed_painel.color = 0x00FF66
        embed_painel.set_field_at(0, name="Estado da Task", value="🟢 `TRANSMISSÃO CONCLUÍDA COM SUCESSO`", inline=False)
        embed_painel.set_field_at(3, name="📊 Progresso de Rede", value=gerar_barra(total, total), inline=False)
        await painel_msg.edit(embed=embed_painel)

        # RELATÓRIO TÉCNICO FINAL
        embed_fim = discord.Embed(
            title="🏁 [KERNEL_REPORT] - OPERAÇÃO FINALIZADA",
            description="```prolog\nTodos os pacotes foram despachados pelo núcleo.\n```",
            color=0x00FF66
        )
        embed_fim.add_field(name="✅ Sucessos", value=f"`{sucessos}`", inline=True)
        embed_fim.add_field(name="❌ Falhas/Bloqueios", value=f"`{falhas}`", inline=True)
        embed_fim.add_field(name="📦 Total processado", value=f"`{total}`", inline=True)
        embed_fim.add_field(name="⏱️ Latência de Execução", value=f"`{tempo_decorrido}s`", inline=False)
        embed_fim.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"[CRITICAL_ERROR] {e}")
        await log_channel.send(f"🚨 `[FATAL_EXCEPTION]` Erro no núcleo de transmissão: `{e}`")

# ==============================================
# COMANDO SLASH: /autorizar (GERENCIAR PERMISSÕES DE ENVIO)
# ==============================================
@client.tree.command(name="autorizar", description="[DONO] Concede permissão para um usuário usar o comando /enviar")
@app_commands.describe(usuario="Membro que receberá a autorização")
async def autorizar(interaction: discord.Interaction, usuario: discord.User):
    # Apenas o Dono Principal pode dar permissão de envio
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode autorizar novos operadores.", ephemeral=True)
        return

    usuarios_autorizados_enviar.add(usuario.id)
    await interaction.response.send_message(
        content=f"✅ **[AUTORIZAÇÃO CONCEDIDA]** O usuário {usuario.mention} (`{usuario.id}`) agora tem acesso ao comando `/enviar`.",
        ephemeral=True
    )

@client.tree.command(name="remover", description="[DONO] Remove a permissão de um usuário do comando /enviar")
@app_commands.describe(usuario="Membro que perderá a autorização")
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode revogar acessos.", ephemeral=True)
        return

    if usuario.id in usuarios_autorizados_enviar:
        usuarios_autorizados_enviar.remove(usuario.id)
        await interaction.response.send_message(
            content=f"⚠️ **[ACESSO REVOGADO]** O usuário {usuario.mention} (`{usuario.id}`) foi removido da lista de operadores.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(f"❌ O usuário {usuario.mention} não estava na lista de autorizados.", ephemeral=True)

# ==============================================
# COMANDO SLASH: /enviar
# ==============================================
@client.tree.command(name="enviar", description="Inicia a injeção de mensagens para todos os membros (Requer Autorização)")
@app_commands.describe(
    mensagem="Mensagem de payload que será injetada no PV de todos",
    canal_logs="Canal para telemetria e logs avançados (Opcional)"
)
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    # Verifica se é o dono, se está na lista dinâmica ou se é administrador do servidor
    is_owner = interaction.user.id == DONO_ID
    is_authorized = interaction.user.id in usuarios_autorizados_enviar
    is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False

    if not (is_owner or is_authorized or is_admin):
        await interaction.response.send_message("❌ Você não possui credenciais de acesso para executar este payload!", ephemeral=True)
        return

    target_channel = canal_logs
    if not target_channel and LOG_CHANNEL_ID != 0:
        target_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if not target_channel:
        target_channel = interaction.channel

    await interaction.response.send_message(
        content=f"⚡ **[DISPARADOR ACIONADO]** Injeção iniciada. Acompanhe a telemetria avançada em: {target_channel.mention}",
        ephemeral=True
    )

    asyncio.create_task(
        processar_envio_avancado(
            guild=interaction.guild,
            log_channel=target_channel,
            mensagem=mensagem,
            operador=str(interaction.user)
        )
    )

# ==============================================
# COMANDO SLASH: /servidores (EXCLUSIVO DONO PRINCIPAL)
# ==============================================
@client.tree.command(name="servidores", description="Gerencia as conexões ativas do bot nos servidores")
async def servidores(interaction: discord.Interaction):
    # Trava restrita estritamente ao Dono Principal
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
        return

    guilds = client.guilds
    if not guilds:
        await interaction.response.send_message("O bot não está conectado a nenhuma subnet no momento.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🌐 [KERNEL_NODES] - SERVIDORES CONECTADOS",
        description=f"O bot está operacional em **{len(guilds)}** servidor(es):",
        color=0x00FF66
    )

    for g in guilds[:10]:
        embed.add_field(
            name=f"📌 {g.name}",
            value=f"🆔 `ID: {g.id}`\n👥 `Nodes/Membros: {g.member_count}`",
            inline=False
        )

    view = ServidoresView(client, guilds)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==============================================
# INICIALIZAÇÃO DO NÚCLEO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 [FATAL] Variável DISCORD_TOKEN não encontrada nas configurações do Render!")
