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
            await interaction.response.send_message("Este comando não dá para usar, ele é automático do bot.", ephemeral=True)
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
# FUNÇÃO DE LOGS LIMPA E ELEGANTE
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
                porcentagem = 0
            else:
                porcentagem = int((atual / maximo) * tamanho)
            barra = "█" * porcentagem + "░" * (tamanho - porcentagem)
            pct = int((atual / maximo) * 100) if maximo > 0 else 0
            return f"[{barra}] {pct}%"

        # 1. EMBED DE INÍCIO
        embed_inicio = discord.Embed(
            title="🚀 Transmissão de Mensagens Iniciada",
            description="O processo de envio em massa foi iniciado com sucesso.",
            color=0x3498DB
        )
        embed_inicio.add_field(name="🎯 Total de Alvos", value=f"`{total} membros`", inline=True)
        embed_inicio.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_inicio.set_footer(text="Acompanhe o andamento detalhado abaixo.")
        embed_inicio.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_inicio)

        # 2. PAINEL DE CONTROLE EM TEMPO REAL
        embed_painel = discord.Embed(
            title="📊 Painel de Status do Envio",
            color=0xF1C40F
        )
        embed_painel.add_field(name="Status", value="🔄 `Enviando mensagens...`", inline=False)
        embed_painel.add_field(name="✅ Entregues", value="`0`", inline=True)
        embed_painel.add_field(name="❌ Falhas", value="`0`", inline=True)
        embed_painel.add_field(name="📈 Progresso", value=gerar_barra(0, total), inline=False)
        
        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # LOOP DE ENVIO
        for idx, membro in enumerate(membros, start=1):
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
            
            try:
                await membro.send(mensagem)
                sucessos += 1
                
                # LOG DE SUCESSO
                log_embed = discord.Embed(
                    title=f"✅ Mensagem Entregue [{idx}/{total}]",
                    color=0x2ECC71
                )
                log_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                log_embed.add_field(name="💬 Mensagem", value=f"```text\n{mensagem[:400]}\n```", inline=False)
                log_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                log_embed.add_field(name="Status", value="`Entregue com Sucesso`", inline=True)
                
                if membro.display_avatar:
                    log_embed.set_thumbnail(url=membro.display_avatar.url)
                
                await log_channel.send(embed=log_embed)

            except discord.Forbidden:
                falhas += 1
                # DM realmente fechada ou usuário bloqueou
                err_embed = discord.Embed(
                    title=f"❌ Falha na Entrega [{idx}/{total}]",
                    color=0xE74C3C
                )
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo", value="```DMs Fechadas ou Usuário Bloqueou o Bot```", inline=False)
                err_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            except discord.HTTPException as e:
                falhas += 1
                # Erro de Rate Limit ou bloqueio do próprio Discord
                err_embed = discord.Embed(
                    title=f"⚠️ Erro de API/Rate Limit [{idx}/{total}]",
                    color=0xE67E22
                )
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo Real", value=f"```text\nErro Discord {e.status}: {e.text}\n```", inline=False)
                err_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            except Exception as e:
                falhas += 1
                # Outro erro genérico
                err_embed = discord.Embed(
                    title=f"🚨 Erro Inesperado [{idx}/{total}]",
                    color=0x95A5A6
                )
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo Real", value=f"```text\n{type(e).__name__}: {e}\n```", inline=False)
                err_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            # Atualiza o painel principal a cada 3 envios
            if idx % 3 == 0 or idx == total:
                embed_painel.set_field_at(0, name="Status", value="🔄 `Em andamento...`", inline=False)
                embed_painel.set_field_at(1, name="✅ Entregues", value=f"`{sucessos}`", inline=True)
                embed_painel.set_field_at(2, name="❌ Falhas", value=f"`{falhas}`", inline=True)
                embed_painel.set_field_at(3, name="📈 Progresso", value=gerar_barra(idx, total), inline=False)
                await painel_msg.edit(embed=embed_painel)

            # Pausa de 1.5s entre envios para não sofrer bloqueio da API por SPAM
            await asyncio.sleep(1.5)

        tempo_decorrido = round(time.time() - inicio_tempo, 2)

        # Atualiza painel para Concluído
        embed_painel.color = 0x2ECC71
        embed_painel.set_field_at(0, name="Status", value="✅ **Transmissão Concluída com Sucesso!**", inline=False)
        embed_painel.set_field_at(3, name="📈 Progresso", value=gerar_barra(total, total), inline=False)
        await painel_msg.edit(embed=embed_painel)

        # RELATÓRIO FINAL LIMPO
        embed_fim = discord.Embed(
            title="🏁 Relatório Final da Transmissão",
            description="Todas as mensagens foram processadas e enviadas.",
            color=0x2ECC71
        )
        embed_fim.add_field(name="✅ Sucessos", value=f"`{sucessos}`", inline=True)
        embed_fim.add_field(name="❌ Falhas", value=f"`{falhas}`", inline=True)
        embed_fim.add_field(name="📦 Total", value=f"`{total}`", inline=True)
        embed_fim.add_field(name="⏱️ Tempo Gasto", value=f"`{tempo_decorrido}s`", inline=False)
        embed_fim.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"Erro no processamento geral: {e}")
        await log_channel.send(f"🚨 Ocorreu um erro durante o processamento: `{e}`")

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
        content=f"✅ **Envio iniciado!** Acompanhe os logs detalhados em: {target_channel.mention}",
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
        await interaction.response.send_message("Este comando não dá para usar, ele é automático do bot.", ephemeral=True)
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
