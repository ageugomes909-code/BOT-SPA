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
DONO_ID = 1410272734012772524  # Seu ID Principal

# Lista dinâmica de usuários autorizados
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
    await client.change_presence(activity=discord.Game(name="Pronto para operar 🚀"))
    try:
        synced = await client.tree.sync()
        print(f"🔄 {len(synced)} comandos slash (/) sincronizados com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==============================================
# FUNÇÃO DE LOGS LIMPA E ELEGANTE (ENVIO)
# ==============================================
async def processar_envio_elegante(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str):
    try:
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total = len(membros)

        if total == 0:
            await log_channel.send("⚠️ Nenhum membro válido (sem ser bot) encontrado para o envio.")
            return

        def gerar_barra(atual, maximo, tamanho=15):
            if maximo == 0:
                porcentagem = 0
            else:
                porcentagem = int((atual / maximo) * tamanho)
            barra = "█" * porcentagem + "░" * (tamanho - porcentagem)
            pct = int((atual / maximo) * 100) if maximo > 0 else 0
            return f"[{barra}] {pct}%"

        # EMBED DE INÍCIO
        embed_inicio = discord.Embed(
            title="🚀 Transmissão de Mensagens Iniciada",
            description="O processo de envio em massa foi iniciado.",
            color=0x3498DB
        )
        embed_inicio.add_field(name="🎯 Total de Alvos", value=f"`{total} membros`", inline=True)
        embed_inicio.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_inicio.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed_inicio)

        # PAINEL EM TEMPO REAL
        embed_painel = discord.Embed(title="📊 Painel de Status do Envio", color=0xF1C40F)
        embed_painel.add_field(name="Status", value="🔄 `Enviando mensagens...`", inline=False)
        embed_painel.add_field(name="✅ Entregues", value="`0`", inline=True)
        embed_painel.add_field(name="❌ Falhas", value="`0`", inline=True)
        embed_painel.add_field(name="📈 Progresso", value=gerar_barra(0, total), inline=False)
        
        painel_msg = await log_channel.send(embed=embed_painel)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        for idx, membro in enumerate(membros, start=1):
            timestamp = discord.utils.utcnow().strftime("%H:%M:%S")
            
            try:
                await membro.send(mensagem)
                sucessos += 1
                
                log_embed = discord.Embed(title=f"✅ Mensagem Entregue [{idx}/{total}]", color=0x2ECC71)
                log_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                log_embed.add_field(name="🕒 Horário", value=f"`{timestamp}`", inline=True)
                await log_channel.send(embed=log_embed)

            except discord.Forbidden:
                falhas += 1
                err_embed = discord.Embed(title=f"❌ Falha na Entrega [{idx}/{total}]", color=0xE74C3C)
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo", value="```DMs Fechadas ou Usuário Bloqueou o Bot```", inline=False)
                await log_channel.send(embed=err_embed)

            except discord.HTTPException as e:
                falhas += 1
                err_embed = discord.Embed(title=f"⚠️ Rate Limit / Bloqueio [{idx}/{total}]", color=0xE67E22)
                err_embed.add_field(name="👤 Destinatário", value=f"{membro.mention} (`{membro.id}`)", inline=False)
                err_embed.add_field(name="⚠️ Motivo Real", value=f"```text\nErro Discord: {e.text}\n```", inline=False)
                await log_channel.send(embed=err_embed)

            if idx % 3 == 0 or idx == total:
                embed_painel.set_field_at(1, name="✅ Entregues", value=f"`{sucessos}`", inline=True)
                embed_painel.set_field_at(2, name="❌ Falhas", value=f"`{falhas}`", inline=True)
                embed_painel.set_field_at(3, name="📈 Progresso", value=gerar_barra(idx, total), inline=False)
                await painel_msg.edit(embed=embed_painel)

            # Pausa estendida para evitar flag de SPAM do Discord
            await asyncio.sleep(2.0)

        tempo_decorrido = round(time.time() - inicio_tempo, 2)
        embed_painel.color = 0x2ECC71
        embed_painel.set_field_at(0, name="Status", value="✅ **Transmissão Concluída!**", inline=False)
        embed_painel.set_field_at(3, name="📈 Progresso", value=gerar_barra(total, total), inline=False)
        await painel_msg.edit(embed=embed_painel)

    except Exception as e:
        await log_channel.send(f"🚨 Ocorreu um erro crítico durante o envio: `{e}`")

# ==============================================
# COMANDOS SLASH (/)
# ==============================================

@client.tree.command(name="enviar", description="Envia mensagem privada para todos os membros do servidor")
@app_commands.describe(mensagem="Mensagem que será enviada no PV de todos", canal_logs="Canal para exibir o andamento (Opcional)")
async def enviar(interaction: discord.Interaction, mensagem: str, canal_logs: discord.TextChannel = None):
    if interaction.user.id != DONO_ID and interaction.user.id not in usuarios_autorizados_enviar:
        await interaction.response.send_message("❌ Você não possui permissão para usar este comando!", ephemeral=True)
        return

    target_channel = canal_logs or (interaction.guild.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID != 0 else interaction.channel)

    await interaction.response.send_message(f"✅ **Envio iniciado!** Logs em: {target_channel.mention}", ephemeral=True)
    
    asyncio.create_task(
        processar_envio_elegante(interaction.guild, target_channel, mensagem, str(interaction.user))
    )

@client.tree.command(name="reset", description="Limpa os dados internos do bot e atualiza o status")
async def reset(interaction: discord.Interaction):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o dono pode resetar o bot.", ephemeral=True)
        return

    # Limpa a memória local
    usuarios_autorizados_enviar.clear()
    
    # Atualiza a presença para forçar uma "atualização" visual no Discord
    await client.change_presence(activity=discord.Game(name="Sistema Resetado 🔄"), status=discord.Status.idle)
    await asyncio.sleep(2)
    await client.change_presence(activity=discord.Game(name="Pronto para operar 🚀"), status=discord.Status.online)

    embed = discord.Embed(
        title="🔄 Reset Concluído",
        description="O cache do bot foi limpo com sucesso para tentar evitar bugs.",
        color=0x9B59B6
    )
    embed.add_field(name="🗑️ Dados Limpos", value="Lista de autorizados zerada.", inline=False)
    embed.add_field(name="🔌 Conexão", value="Status atualizado junto ao Discord.", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="autorizar", description="Autoriza um usuário a usar o /enviar")
async def autorizar(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o dono pode autorizar.", ephemeral=True)
        return
    usuarios_autorizados_enviar.add(usuario.id)
    await interaction.response.send_message(f"✅ {usuario.mention} autorizado.", ephemeral=True)

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 ERRO: Adicione a variável DISCORD_TOKEN nas configurações do Render!")
