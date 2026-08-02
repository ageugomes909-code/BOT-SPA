import os
import asyncio
import time
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ==============================================
# CONFIGURAÇÕES DE PERMISSÃO E DONO
# ==============================================
DONO_ID = 1410272734012772524  # Seu ID fixo no código

# Lista de IDs adicionais autorizados a usar o comando /enviar (Além de você e dos Admins do servidor)
USUARIOS_AUTORIZADOS = [
    1410272734012772524,
    # Adicione mais IDs de amigos/parceiros aqui se quiser (separados por vírgula)
]

# ==============================================
# WEB SERVER PARA MANTER O RENDER ONLINE (24/7)
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
intents.members = True

client = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

@client.event
async def on_ready():
    print(f"✅ Bot conectado como: {client.user} (ID: {client.user.id})")
    try:
        synced = await client.tree.sync()
        print(f"🔄 {len(synced)} comando(s) slash sincronizado(s) com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# VIEW INTERATIVA PARA GERENCIAR SERVIDORES (SAIR)
# ==============================================
class ServidoresView(discord.ui.View):
    def __init__(self, bot, guilds):
        super().__init__(timeout=120)
        self.bot = bot
        
        # Cria as opções do menu suspenso (até 25 servidores)
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
        super().__init__(placeholder="🚨 Selecione um servidor para REMOVER o bot...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        # Trava de Segurança extra
        if interaction.user.id != DONO_ID:
            await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
            return

        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)

        if guild:
            nome_guild = guild.name
            await guild.leave()
            await interaction.response.send_message(
                content=f"✅ **Sucesso!** O bot saiu do servidor **{nome_guild}** (`{guild_id}`).",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Servidor não encontrado ou o bot já foi removido.", ephemeral=True)

# ==============================================
# SISTEMA DE ENVIO E LOGS EM TEMPO REAL
# ==============================================
async def processar_envio(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro humano encontrado para envio.")
            return

        # 1. EMBED DE INÍCIO
        embed_inicio = discord.Embed(
            title="🚀 Transmissão em Massa Iniciada",
            description="```yaml\nStatus: Processamento de mensagens em andamento...\n```",
            color=0x3498DB
        )
        embed_inicio.add_field(name="🎯 Membros Alvo", value=f"`{total}`", inline=True)
        embed_inicio.add_field(name="👤 Autor", value=f"`{operador}`", inline=True)
        embed_inicio.set_footer(text="Logs de envio individual em tempo real abaixo.")
        embed_inicio.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_inicio)

        # 2. PAINEL DE PROGRESSO
        embed_painel = discord.Embed(
            title="📊 Painel de Controle de Envio",
            color=0xF1C40F
        )
        embed_painel.add_field(name="Estado", value="🔄 Enviando DMs...", inline=False)
        embed_painel.add_field(name="✅ Entregues", value="`0`", inline=True)
        embed_painel.add_field(name="❌ Bloqueados", value="`0`", inline=True)
        embed_painel.add_field(name="📈 Progresso", value="`0%`", inline=True)
        
        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # LOOP DE ENVIO
        for idx, membro in enumerate(membros, start=1):
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
            
            try:
                # Envia mensagem no PV
                await membro.send(mensagem)
                sucessos += 1
                
                # LOG COM PROVA VISUAL / PRINTSIMULADO DA DM
                log_embed = discord.Embed(
                    title=f"📸 CONFIRMAÇÃO DE ENTREGA [{idx}/{total}]",
                    color=0x2ECC71
                )
                log_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                # Simulação visual da DM enviada
                log_embed.add_field(name="💬 Conteúdo Entregue no PV", value=f"```text\n{mensagem[:500]}\n```", inline=False)
                log_embed.add_field(name="🕒 Horário do Envio", value=f"`{timestamp}`", inline=True)
                log_embed.add_field(name="STATUS", value="`✅ DM ENTREGUE`", inline=True)
                
                if membro.display_avatar:
                    log_embed.set_thumbnail(url=membro.display_avatar.url)
                
                await log_channel.send(embed=log_embed)

            except Exception:
                falhas += 1
                
                # LOG DE FALHA
                err_embed = discord.Embed(
                    title=f"❌ FALHA DE ENTREGA [{idx}/{total}]",
                    color=0xE74C3C
                )
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo", value="```DMs Fechadas / Usuário Bloqueou o Bot```", inline=False)
                err_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            # Atualiza o painel principal a cada 3 envios
            if idx % 3 == 0 or idx == total:
                porcentagem = round((idx / total) * 100)
                embed_painel.set_field_at(0, name="Estado", value="🔄 Em andamento...", inline=False)
                embed_painel.set_field_at(1, name="✅ Entregues", value=f"`{sucessos}`", inline=True)
                embed_painel.set_field_at(2, name="❌ Bloqueados", value=f"`{falhas}`", inline=True)
                embed_painel.set_field_at(3, name="📈 Progresso", value=f"`{porcentagem}%` ({idx}/{total})", inline=True)
                await painel_msg.edit(embed=embed_painel)

            # Intervalo anti-spam
            await asyncio.sleep(1.0)

        tempo_decorrido = round(time.time() - inicio_tempo, 1)

        # Atualiza painel para Concluído
        embed_painel.color = 0x2ECC71
        embed_painel.set_field_at(0, name="Estado", value="✅ **TRANSMISSÃO FINALIZADA!**", inline=False)
        await painel_msg.edit(embed=embed_painel)

        # EMBED FINAL
        embed_fim = discord.Embed(
            title="🏁 Relatório Final de Disparos",
            description="O bot concluiu o envio de todas as mensagens.",
            color=0x2ECC71
        )
        embed_fim.add_field(name="✅ Total Sucesso", value=f"`{sucessos}`", inline=True)
        embed_fim.add_field(name="❌ Total Falhas", value=f"`{falhas}`", inline=True)
        embed_fim.add_field(name="📦 Total Processado", value=f"`{total}`", inline=True)
        embed_fim.add_field(name="⏱️ Tempo Decorrido", value=f"`{tempo_decorrido}s`", inline=False)
        embed_fim.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"Erro no envio: {e}")
        await log_channel.send(f"🚨 Erro interno no processo: `{e}`")

# ==============================================
# COMANDO SLASH: /enviar (RESTRITO)
# ==============================================
@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros (Apenas Autorizados)")
@app_commands.describe(
    mensagem="Mensagem que será enviada no PV de todos",
    canal_logs="Canal de logs onde será exibido o status (Opcional)"
)
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    # Verificação de Permissão: Dono, Lista Autorizada ou Admin do Servidor
    is_owner = interaction.user.id == DONO_ID
    is_authorized = interaction.user.id in USUARIOS_AUTORIZADOS
    is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False

    if not (is_owner or is_authorized or is_admin):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando!", ephemeral=True)
        return

    target_channel = canal_logs
    if not target_channel and LOG_CHANNEL_ID != 0:
        target_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if not target_channel:
        target_channel = interaction.channel

    await interaction.response.send_message(
        content=f"✅ **Disparo iniciado!** Acompanhe as confirmações em tempo real em: {target_channel.mention}",
        ephemeral=True
    )

    asyncio.create_task(
        processar_envio(
            guild=interaction.guild,
            log_channel=target_channel,
            mensagem=mensagem,
            operador=str(interaction.user)
        )
    )

# ==============================================
# COMANDO SLASH: /servidores (EXCLUSIVO DO DONO)
# ==============================================
@client.tree.command(name="servidores", description="Exibe a lista de servidores em que o bot está instalado")
async def servidores(interaction: discord.Interaction):
    # Se NÃO for o dono (ID 1410272734012772524) dá a mensagem exata solicitada
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("Este comando não dá para usa ele é feito automático do bot", ephemeral=True)
        return

    guilds = client.guilds
    if not guilds:
        await interaction.response.send_message("O bot não está presente em nenhum servidor no momento.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🌐 Painel de Servidores Conectados",
        description=f"O bot está atualmente ativo em **{len(guilds)}** servidor(es):",
        color=0x7289DA
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
        print("🚨 ERRO: Adicione a variável DISCORD_TOKEN no Render!")
