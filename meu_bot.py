import os
import sys
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
# BOTÃO INTERATIVO PARA PARAR O ENVIO
# ==============================================
class PainelEnvioView(discord.ui.View):
    def __init__(self, operador_id):
        super().__init__(timeout=None)
        self.parado = False
        self.operador_id = operador_id

    @discord.ui.button(label="Parar Envio", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def parar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.operador_id and interaction.user.id != DONO_ID and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores ou quem iniciou pode parar o envio.", ephemeral=True)
            return
        
        self.parado = True
        button.disabled = True
        button.label = "Envio Cancelado"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("⚠️ Solicitação de interrupção recebida. O bot vai parar no próximo ciclo.", ephemeral=True)

# ==============================================
# SISTEMA DE ENVIO LIMPO COM PROTEÇÃO ANTI-BUG
# ==============================================
async def processar_envio_elegante(guild: discord.Guild, log_channel: discord.TextChannel, mensagem: str, operador: str, operador_id: int):
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

        view = PainelEnvioView(operador_id)

        # PAINEL INICIAL
        embed_painel = discord.Embed(
            title="📊 Painel de Transmissão de Mensagens",
            description="O envio está em andamento. Você pode interromper a qualquer momento clicando no botão abaixo.",
            color=0x3498DB
        )
        embed_painel.add_field(name="🎯 Total de Alvos", value=f"`{total} membros`", inline=True)
        embed_painel.add_field(name="👤 Operador", value=f"`{operador}`", inline=True)
        embed_painel.add_field(name="📈 Progresso", value=f"`[░░░░░░░░░░░░░░░] 0%`\n✅ Sucessos: `0` | ❌ Falhas: `0`", inline=False)
        embed_painel.set_footer(text="Sistema de Disparo Seguro • Proteção contra Rate Limit")
        embed_painel.timestamp = discord.utils.utcnow()

        painel_msg = await log_channel.send(embed=embed_painel, view=view)

        sucessos = 0
        falhas = 0
        inicio_tempo = time.time()

        # Semáforo e pequeno delay para evitar falsos positivos de DM fechada (Rate Limit do Discord)
        semaphore = asyncio.Semaphore(3)

        async def enviar_dm(membro):
            nonlocal sucessos, falhas
            if view.parado:
                return
            async with semaphore:
                if view.parado:
                    return
                try:
                    await membro.send(mensagem)
                    sucessos += 1
                    await asyncio.sleep(0.4) # Respiro seguro para a API do Discord
                except discord.Forbidden:
                    falhas += 1 # Realmente DMs fechadas ou bloqueado
                except discord.HTTPException as e:
                    if e.status == 429: # Se tomar rate limit, aguarda um instante e tenta de novo
                        await asyncio.sleep(2.0)
                        try:
                            await membro.send(mensagem)
                            sucessos += 1
                        except:
                            falhas += 1
                    else:
                        falhas += 1
                except Exception:
                    falhas += 1

        # LOOP DE ENVIO CONTROLADO
        for i in range(len(membros)):
            if view.parado:
                break
            
            membro = membros[i]
            await enviar_dm(membro)
            
            concluidos = sucessos + falhas
            if concluidos % 3 == 0 or concluidos == total or view.parado:
                embed_painel.set_field_at(
                    2,
                    name="📈 Progresso",
                    value=f"`{gerar_barra(concluidos, total)}`\n✅ Sucessos: `{sucessos}` | ❌ Falhas: `{falhas}`",
                    inline=False
                )
                try:
                    await painel_msg.edit(embed=embed_painel, view=view)
                except:
                    pass

        tempo_decorrido = round(time.time() - inicio_tempo, 2)

        # Desativa o botão ao finalizar
        for child in view.children:
            child.disabled = True

        if view.parado:
            embed_painel.color = 0xE74C3C
            embed_painel.title = "⏹️ Transmissão Interrompida"
            await painel_msg.edit(embed=embed_painel, view=view)
            await log_channel.send(f"⚠️ O envio foi cancelado manualmente. Mensagens entregues até o momento: **{sucessos}**.")
        else:
            embed_painel.color = 0x2ECC71
            embed_painel.title = "✅ Transmissão Concluída com Sucesso!"
            await painel_msg.edit(embed=embed_painel, view=view)

            # RELATÓRIO FINAL LIMPO
            embed_fim = discord.Embed(
                title="🏁 Relatório Final de Envio",
                color=0x2ECC71
            )
            embed_fim.add_field(name="✅ Entregas com Sucesso", value=f"`{sucessos}`", inline=True)
            embed_fim.add_field(name="❌ Falhas (DMs Fechadas)", value=f"`{falhas}`", inline=True)
            embed_fim.add_field(name="📦 Total de Alvos", value=f"`{total}`", inline=True)
            embed_fim.add_field(name="⏱️ Tempo Gasto", value=f"`{tempo_decorrido}s`", inline=False)
            embed_fim.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=embed_fim)

    except Exception as e:
        print(f"Erro no processamento: {e}")
        await log_channel.send(f"🚨 Ocorreu um erro crítico: `{e}`")

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
        content=f"🚀 Envio iniciado com painel interativo em: {target_channel.mention}",
        ephemeral=True
    )

    asyncio.create_task(
        processar_envio_elegante(
            guild=interaction.guild,
            log_channel=target_channel,
            mensagem=mensagem,
            operador=str(interaction.user),
            operador_id=interaction.user.id
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
# COMANDO SLASH: /atualizar (ATUALIZAÇÃO POR ARQUIVO)
# ==============================================
@client.tree.command(name="atualizar", description="[DONO] Substitui o código inteiro do bot por um arquivo .py enviado")
@app_commands.describe(arquivo="Arquivo .py com o novo código completo")
async def atualizar(interaction: discord.Interaction, arquivo: discord.Attachment):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode atualizar o código.", ephemeral=True)
        return

    if not arquivo.filename.endswith('.py'):
        await interaction.response.send_message("❌ O arquivo precisa ser um script Python (.py)!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        novo_codigo = await arquivo.read()
        caminho_atual = __file__
        
        with open(caminho_atual, 'wb') as f:
            f.write(novo_codigo)
            
        await interaction.edit_reply(content="✅ **Código atualizado com sucesso!** Reiniciando o bot...")
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        await interaction.edit_reply(content=f"❌ Erro ao atualizar: `{e}`")

# ==============================================
# COMANDO SLASH: /reiniciar
# ==============================================
@client.tree.command(name="reiniciar", description="[DONO] Reinicia o bot instantaneamente")
async def reiniciar(interaction: discord.Interaction):
    if interaction.user.id != DONO_ID:
        await interaction.response.send_message("❌ Apenas o desenvolvedor principal pode reiniciar.", ephemeral=True)
        return

    await interaction.response.send_message("🔄 Reiniciando o bot...", ephemeral=True)
    os.execv(sys.executable, ['python'] + sys.argv)

# ==============================================
# INICIALIZAÇÃO
# ==============================================
if __name__ == "__main__":
    manter_online()
    if TOKEN:
        client.run(TOKEN)
    else:
        print("🚨 ERRO: Adicione a variável DISCORD_TOKEN!")
