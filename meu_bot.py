import os
import asyncio
import time
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ==============================================
# WEB SERVER PARA MANTER O RENDER ONLINE (24/7)
# ==============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot de Transmissão Online e Operacional!"

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
intents.members = True # Necessário para carregar os membros

client = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

@client.event
async def on_ready():
    print(f"✅ Bot conectado como: {client.user}")
    try:
        synced = await client.tree.sync()
        print(f"🔄 {len(synced)} comando(s) slash sincronizado(s) com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# SISTEMA DE ENVIO E LOGS EM TEMPO REAL
# ==============================================
async def processar_envio(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        # Carrega a lista completa de membros do servidor
        await guild.chunk()
        
        # Filtra apenas usuários humanos (IGNORA BOTS)
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro (humano) foi encontrado para envio.")
            return

        # 1. EMBED DE INÍCIO
        embed_inicio = discord.Embed(
            title="🚀 Envio em Massa Iniciado",
            description="O processo de transmissão de mensagens no PV foi iniciado.",
            color=0x3498DB
        )
        embed_inicio.add_field(name="🎯 Total de Alvos", value=f"`{total} membros`", inline=True)
        embed_inicio.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_inicio.set_footer(text="Acompanhe os logs abaixo em tempo real.")
        embed_inicio.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_inicio)

        # 2. PAINEL DE PROGRESSO (Atualizado dinamicamente)
        embed_painel = discord.Embed(
            title="📊 Status do Envio em Tempo Real",
            color=0xF1C40F
        )
        embed_painel.add_field(name="Status", value="🔄 Enviando...", inline=False)
        embed_painel.add_field(name="✅ Enviados", value="`0`", inline=True)
        embed_painel.add_field(name="❌ Falhas", value="`0`", inline=True)
        embed_painel.add_field(name="📈 Progresso", value="`0%`", inline=True)
        
        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # Loop de envio para cada membro
        for idx, membro in enumerate(membros, start=1):
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
            
            try:
                # Tenta enviar no PV
                await membro.send(mensagem)
                sucessos += 1
                
                # Log individual de SUCESSO
                log_embed = discord.Embed(
                    title=f"✅ Entregue [{idx}/{total}]",
                    color=0x2ECC71
                )
                log_embed.add_field(name="👤 Membro", value=f"{membro.mention} (`{membro.id}`)", inline=True)
                log_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                if membro.display_avatar:
                    log_embed.set_thumbnail(url=membro.display_avatar.url)
                
                await log_channel.send(embed=log_embed)

            except Exception:
                # Caso a DM esteja fechada ou o usuário tenha bloqueado o bot
                falhas += 1
                
                # Log individual de FALHA
                err_embed = discord.Embed(
                    title=f"❌ Falha [{idx}/{total}]",
                    description="Motivo: DM Fechada / Bloqueado pelo Usuário",
                    color=0xE74C3C
                )
                err_embed.add_field(name="👤 Membro", value=f"{membro.mention} (`{membro.id}`)", inline=True)
                err_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                
                await log_channel.send(embed=err_embed)

            # Atualiza o Painel de Progresso a cada 3 envios para evitar rate-limit
            if idx % 3 == 0 or idx == total:
                porcentagem = round((idx / total) * 100)
                embed_painel.set_field_at(0, name="Status", value="🔄 Em andamento...", inline=False)
                embed_painel.set_field_at(1, name="✅ Enviados", value=f"`{sucessos}`", inline=True)
                embed_painel.set_field_at(2, name="❌ Falhas", value=f"`{falhas}`", inline=True)
                embed_painel.set_field_at(3, name="📈 Progresso", value=f"`{porcentagem}%` ({idx}/{total})", inline=True)
                await painel_msg.edit(embed=embed_painel)

            # Intervalo de 1 segundo entre envios para o Discord não bloquear o bot por SPAM
            await asyncio.sleep(1.0)

        tempo_decorrido = round(time.time() - inicio_tempo, 1)

        # Atualiza painel para Concluído
        embed_painel.color = 0x2ECC71
        embed_painel.set_field_at(0, name="Status", value="✅ **PROCESSO CONCLUÍDO!**", inline=False)
        await painel_msg.edit(embed=embed_painel)

        # 3. EMBED FINAL DE RELATÓRIO
        embed_fim = discord.Embed(
            title="🏁 Transmissão Finalizada",
            description="Todas as mensagens foram processadas!",
            color=0x2ECC71
        )
        embed_fim.add_field(name="✅ Total Entregue", value=f"`{sucessos}`", inline=True)
        embed_fim.add_field(name="❌ Total de Falhas", value=f"`{falhas}`", inline=True)
        embed_fim.add_field(name="📦 Total de Alvos", value=f"`{total}`", inline=True)
        embed_fim.add_field(name="⏱️ Tempo Total", value=f"`{tempo_decorrido}s`", inline=False)
        embed_fim.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"Erro no envio em massa: {e}")
        await log_channel.send(f"🚨 Ocorreu um erro durante a execução: `{e}`")

# ==============================================
# COMANDO SLASH: /enviar
# ==============================================
@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros com logs em tempo real")
@app_commands.describe(
    mensagem="Escreva a mensagem que será enviada para todos",
    canal_logs="Selecione o canal onde os logs serão mostrados (Opcional)"
)
@app_commands.default_permissions(administrator=True)
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    # Seleção inteligente do canal de logs
    target_channel = canal_logs
    if not target_channel and LOG_CHANNEL_ID != 0:
        target_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if not target_channel:
        target_channel = interaction.channel

    # Resposta rápida no Discord para o comando não dar erro de "timeout"
    await interaction.response.send_message(
        content=f"✅ **Envio iniciado!** Acompanhe os logs em tempo real em: {target_channel.mention}",
        ephemeral=True
    )

    # Roda a função em segundo plano
    asyncio.create_task(
        processar_envio(
            guild=interaction.guild,
            log_channel=target_channel,
            mensagem=mensagem,
            operador=str(interaction.user)
        )
    )

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 ERRO: Adicione a variável de ambiente DISCORD_TOKEN no Render!")
