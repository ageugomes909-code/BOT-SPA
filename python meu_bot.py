const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildMessages
    ]
});

// Pegando as chaves direto do ambiente do Render (Segurança máxima)
const TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.CLIENT_ID;
const CANAL_LOGS_ID = process.env.LOG_CHANNEL_ID;

client.once('ready', async () => {
    console.log(`[SYS_OK] Core conectado como ${client.user.tag}`);

    const commands = [
        new SlashCommandBuilder()
            .setName('executar_payload')
            .setDescription('[ROOT] Inicia varredura e broadcast em massa com telemetria.')
            .addStringOption(option =>
                option.setName('payload_msg')
                    .setDescription('Mensagem a ser injetada nos alvos.')
                    .setRequired(true))
            .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    ].map(command => command.toJSON());

    const rest = new REST({ version: '10' }).setToken(TOKEN);

    try {
        await rest.put(Routes.applicationCommands(CLIENT_ID), { body: commands });
        console.log('[API_SYNC] Módulos Slash injetados na API do Discord.');
    } catch (error) {
        console.error('[CRITICAL_ERROR]', error);
    }
});

client.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;

    if (interaction.commandName === 'executar_payload') {
        await interaction.deferReply({ ephemeral: true });

        const mensagem = interaction.options.getString('payload_msg');
        const guild = interaction.guild;
        const logChannel = guild.channels.cache.get(CANAL_LOGS_ID);

        if (!logChannel) {
            return interaction.editReply({
                content: `⚠️ **[ERRO]** Canal de logs não encontrado! Verifique se o ID configurado no Render está correto e se o bot tem acesso a ele.`
            });
        }

        await guild.members.fetch();
        const membros = guild.members.cache.filter(m => !m.user.bot);
        const totalAlvos = membros.size;

        await interaction.editReply({
            content: `💻 **[ROOT ACCESS]** Rotina iniciada. Acompanhe o fluxo de pacotes em tempo real no canal <#${CANAL_LOGS_ID}>.`
        });

        const startEmbed = new EmbedBuilder()
            .setColor('#00FF00')
            .setTitle('⚡ [ROOT_ACCESS] - INJEÇÃO INICIADA')
            .setDescription('```ini\n[STATUS] Alocando threads e disparando pacotes...\n```')
            .addFields(
                { name: '🎯 Alvos Alocados', value: `\`${totalAlvos}\``, inline: true },
                { name: '👤 Operador', value: `\`${interaction.user.tag}\``, inline: true }
            )
            .setTimestamp();
        await logChannel.send({ embeds: [startEmbed] });

        let enviados = 0;
        let falhas = 0;
        let contador = 0;

        for (const [id, member] of membros) {
            contador++;
            const timestamp = new Date().toLocaleTimeString();

            try {
                await member.send(mensagem);
                enviados++;

                const logEmbed = new EmbedBuilder()
                    .setColor('#00FF66')
                    .setTitle(`[+] PACOTE TRANSMITIDO [${contador}/${totalAlvos}]`)
                    .setDescription('```yaml\nStatus: 200 OK - Payload entregue com sucesso\n```')
                    .addFields(
                        { name: '👤 Alvo Conectado', value: `\`${member.user.tag}\` (${member.id})`, inline: false },
                        { name: '🕒 Timestamp', value: `\`${timestamp}\``, inline: true },
                        { name: '📊 Taxa de Progresso', value: `\`${Math.round((contador/totalAlvos)*100)}%\``, inline: true }
                    )
                    .setThumbnail(member.user.displayAvatarURL({ dynamic: true }))
                    .setFooter({ text: `Node ID: ${Math.floor(Math.random() * 89999 + 10000)} // Render Cloud` });

                await logChannel.send({ embeds: [logEmbed] });

            } catch (err) {
                falhas++;
                const errorEmbed = new EmbedBuilder()
                    .setColor('#FF0000')
                    .setTitle(`[-] FALHA NO LINK [${contador}/${totalAlvos}]`)
                    .setDescription('```fix\nErro: 403 Forbidden (DMs fechadas/Bloqueado)\n```')
                    .addFields(
                        { name: '👤 Alvo Ignorado', value: `\`${member.user.tag}\` (${member.id})`, inline: false },
                        { name: '🕒 Timestamp', value: `\`${timestamp}\``, inline: true }
                    );
                await logChannel.send({ embeds: [errorEmbed] });
            }

            // Delay para proteger contra rate-limit e simular o rastreio visual em tempo real
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        const endEmbed = new EmbedBuilder()
            .setColor('#0099FF')
            .setTitle('🔒 [RELATÓRIO DE OPERAÇÃO ENCERRADA]')
            .setDescription('```prolog\nVarredura concluída. Desconectando sockets.\n```')
            .addFields(
                { name: '✅ Entregas Bem-Sucedidas', value: `\`${enviados}\``, inline: true },
                { name: '❌ Falhas de Conexão', value: `\`${falhas}\``, inline: true },
                { name: '📦 Total Varrido', value: `\`${totalAlvos}\``, inline: true }
            )
            .setTimestamp();
        await logChannel.send({ embeds: [endEmbed] });
    }
});

client.login(TOKEN);

