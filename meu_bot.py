import os
import asyncio
import random
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread

# ==============================================
# SISTEMA DE WEB SERVER PARA MANTER ONLINE
# ==============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Online! Operacional e funcionando perfeitamente."

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def manter_online():
    t = Thread(target=run)
    t.start()

# ==============================================
# CONFIGURAÇÃO DO BOT
# ==============================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_LOGS_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

# ==============================================
# EVENTO QUANDO BOT FICA ONLINE
# ==============================================
@client.event
async def on_ready():
    print(f"[✅ SYS_OK] Conectado como {client.user.name}")
    try:
        synced = await client.tree.sync()
        print(f"[🔄 API_SYNC] {len(synced)} comandos sincronizados com sucesso!")
        print("✨ Dola está 100% operacional!")
    except Exception as e:
        print(f"[❌ ERRO] Falha ao sincronizar comandos: {e}")

# ==============================================
# FUNÇÃO DE ENVIO E LOGS (CORRIGIDA)
# ==============================================
async def background_broadcast(guild, log_channel, payload_msg, operator_name):
    try:
        # Carrega TODOS os membros direito (isso que tava faltando)
        await guild.chunk()
        membros = [m for m in guild.members if not m.bot]
        total_alvos = len(membros)

        if total_alvos == 0:
            await log_channel.send("⚠️ Nenhum membro encontrado para enviar!")
            return

        # Embed de INÍCIO
        start_embed = discord.Embed(
            color=0x00FF00,
            title="⚡ [ROOT_ACCESS] - INJEÇÃO INICIADA",
            description="```ini\n[STATUS] Processo iniciado...\n```"
        )
        start_embed.add_field(name="🎯 Total de Membros", value=f"`{total_alvos}`", inline=True)
        start_embed.add_field(name="👤 Operador", value=f"`{operator_name}`", inline=True)
        start_embed.set_footer(text="Feito por ✨ Dola")
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
                    title=f"[✅] ENVIADO [{contador}/{total_alvos}]",
                    description="```yaml\nStatus: Mensagem entregue com sucesso!\n```"
                )
                log_embed.add_field(name="👤 Usuário", value=f"`{member}`\nID: `{member.id}`", inline=False)
                log_embed.add_field(name="🕒 Hora", value=f"`{timestamp}`", inline=True)
                log_embed.add_field(name="📊 Progresso", value=f"`{round((contador/total_alvos)*100)}%`", inline=True)
                log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.set_footer(text="Feito por ✨ Dola")
                await log_channel.send(embed=log_embed)

            except Exception as e:
                falhas += 1
                error_embed = discord.Embed(
                    color=0xFF0000,
                    title=f"[❌] FALHA [{contador}/{total_alvos}]",
                    description="```fix\nMotivo: DMs fechadas / Bloqueio / Erro\n```"
                )
                error_embed.add_field(name="👤 Usuário", value=f"`{member}`\nID: `{member.id}`", inline=False)
                error_embed.add_field(name="🕒 Hora", value=f"`{timestamp}`", inline=True)
                error_embed.set_footer(text="Feito por ✨ Dola")
                await log_channel.send(embed=error_embed)

            # Tempo entre envios pra não tomar bloqueio do Discord
            await asyncio.sleep(0.4)

        # Embed FINAL / RELATÓRIO
        end_embed = discord.Embed(
            color=0x0099FF,
            title="🔒 OPERAÇÃO FINALIZADA",
            description="```prolog\nProcesso concluído com sucesso!\n```"
        )
        end_embed.add_field(name="✅ Enviadas", value=f"`{enviados}`", inline=True)
        end_embed.add_field(name="❌ Falhas", value=f"`{falhas}`", inline=True)
        end_embed.add_field(name="📦 Total", value=f"`{total_alvos}`", inline=True)
        end_embed.set_footer(text="Feito por ✨ Dola")
        end_embed.set_timestamp()
        await log_channel.send(embed=end_embed)

    except Exception as e:
        print(f"[ERRO GERAL] -> {e}")

# ==============================================
# COMANDO: ALTERAR PERFIL DO BOT
# ==============================================
@client.tree.command(name="config_perfil", description="[ROOT] Mudar nome e foto do bot")
@app_commands.describe(novo_nome="Novo nome do bot", nova_foto_url="Link da imagem (jpg/png)")
@app_commands.default_permissions(administrator=True)
async def config_perfil(interaction: discord.Interaction, novo_nome: str = None, nova_foto_url: str = None):
    await interaction.response.defer(ephemeral=True)
    alteracoes = []

    try:
        if novo_nome:
            await client.user.edit(username=novo_nome)
            alteracoes.append(f"✅ Nome alterado para: **{novo_nome}**")

        if nova_foto_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(nova_foto_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        await client.user.edit(avatar=avatar_bytes)
                        alteracoes.append("✅ Foto de perfil atualizada")
                    else:
                        alteracoes.append("❌ Link da imagem inválido!")

        if not alteracoes:
            return await interaction.edit_reply(content="⚠️ Digite um nome OU um link de imagem!")

        await interaction.edit_reply(content="\n".join(alteracoes))

    except Exception as err:
        print(err)
        await interaction.edit_reply(content="❌ Discord bloqueou: espere alguns minutos e tente novamente!")

# ==============================================
# COMANDO PRINCIPAL: ENVIAR MENSAGEM P/ TODOS
# ==============================================
@client.tree.command(name="executar_payload", description="[ROOT] Envia mensagem para todos os membros")
@app_commands.describe(payload_msg="Mensagem que será enviada")
@app_commands.default_permissions(administrator=True)
async def executar_payload(interaction: discord.Interaction, payload_msg: str):
    await interaction.response.send_message(
        content=f"✅ Iniciado! Acompanhe tudo no canal de logs: <#{CANAL_LOGS_ID}>",
        ephemeral=True
    )

    guild = interaction.guild
    log_channel = guild.get_channel(CANAL_LOGS_ID)

    if not log_channel:
        return await interaction.edit_reply(content="❌ Canal de logs não encontrado! Verifique a variável LOG_CHANNEL_ID")

    asyncio.create_task(
        background_broadcast(
            guild=guild,
            log_channel=log_channel,
            payload_msg=payload_msg,
            operator_name=str(interaction.user)
        )
    )

# ==============================================
# INICIAR TUDO
# ==============================================
if __name__ == "__main__":
    if not TOKEN:
        print("🚨 ERRO: Coloque seu TOKEN na variável DISCORD_TOKEN!")
    else:
        manter_online()
        client.run(TOKEN)

