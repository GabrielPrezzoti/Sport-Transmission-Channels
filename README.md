# Agenda esportiva diária

Programa em Python para preparar e enviar ao Telegram uma agenda esportiva com
transmissões no Brasil. Usa fontes públicas sem assinatura de dados, sem IA paga.

## Estado atual

- Coleta de jogos da ESPN e complemento da agenda do ge implementados.
- Filtros, normalização de nomes e resumo por esporte/competição implementados.
- Prévia real de 25/11/2026 validada localmente, com 20 jogos e sem duplicatas.
- Envio real ao Telegram confirmado pelo usuário e pelos logs de 26/11/2026.
- Remoto GitHub configurado; ativação controlada por `delivery.enabled`.
- Mensagens com confrontos em negrito e espaço entre jogos. O envio usa HTML
  escapado, preservando blocos de jogo e tags válidas na divisão em mensagens.

## Escopo

Todos os horários usam `America/Sao_Paulo`. O resumo das 9h inclui partidas com
início a partir das 9h daquele dia e antes das 9h do seguinte (até 8h59min59s).
Jogos do dia seguinte mostram também a data completa: `00h30 — 26/11/2026`.
O recorte é masculino principal; Brasileiro Série A e Paulista Série A1.

| Competição | Seleção |
| --- | --- |
| NBA e NFL | Temporada regular e playoffs; sem pré-temporada |
| Brasileirão Série A | Todos os jogos |
| Copa do Brasil | 5ª fase em diante |
| Libertadores | Todos, incluindo preliminares |
| Sul-Americana | Todos |
| Paulista A1 | Jogos de Corinthians, Palmeiras, Santos ou São Paulo |
| Champions League | Fase de liga e mata-mata; sem classificatórias/playoffs de acesso |
| La Liga | Jogos de Real Madrid ou Barcelona |
| Premier League | Confrontos entre dois integrantes do Big Six |

Big Six: Arsenal, Chelsea, Liverpool, Manchester City, Manchester United e Tottenham.
Os playoffs do mata-mata da Champions entram; playoffs de acesso não entram.
Fases desconhecidas em competições com restrições são omitidas com aviso, nunca
tratadas silenciosamente como aprovadas. As preferências ficam em
`config/preferences.toml`.

O resumo contém blocos por esporte e sub-blocos por campeonato, com times,
horário e onde assistir, sem placares. Dias sem eventos têm mensagem própria.
Falha de fonte nunca é apresentada como certeza de que não haverá jogos.
Nesta versão há um resumo por dia para uma conversa privada, sem alertas de alteração.

## Executar no Windows

Requer Python 3.11 ou superior. Na pasta do projeto, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m sports_digest.main
```

O padrão gera apenas prévia. Os arquivos de texto e JSON com URLs das fontes
ficam em `output/`, que não é versionado. Para uma data específica:

```powershell
.\.venv\Scripts\python.exe -m sports_digest.main --date 2026-11-25
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Configurar o Telegram

1. Abra o bot oficial [BotFather](https://t.me/BotFather), use `/newbot` e guarde o token.
2. Abra a conversa com seu novo bot e envie `/start`.
3. Execute o comando abaixo e cole o token na entrada oculta. O programa consulta
   `getUpdates` e mostra o ID das conversas privadas encontradas. Escolha a sua.

```powershell
.\.venv\Scripts\python.exe -m sports_digest.telegram_setup
```

Não envie o token pelo chat nem o inclua no Git. O `.env.example` documenta os nomes
das variáveis, mas arquivos `.env` não são carregados automaticamente.

## Ativar no GitHub

1. Crie um repositório, preferencialmente privado, e publique os arquivos do projeto.
2. Em **Settings → Secrets and variables → Actions**, crie os segredos:
   `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
3. Em **Actions → Agenda esportiva diária → Run workflow**, execute primeiro com
   `send` desmarcado e confira o artefato da agenda.
4. Altere `delivery.enabled` para `true` em `config/preferences.toml` e publique.
5. Execute manualmente com `send` marcado para testar a entrega. Cada execução
   manual envia novamente o resumo recém-gerado, mesmo que já tenha sido enviado
   naquele dia. Com `send` desmarcado, continua sendo apenas uma prévia.

O workflow agenda a execução às 03h UTC, equivalentes a meia-noite em Brasília.
Há disparos de recuperação às 03h17 e 03h37 UTC (00h17/00h37 de Brasília).
O disparo foi antecipado para dar margem aos atrasos do GitHub antes das 9h;
isso não garante entrega até esse horário. A coleta e o envio acontecem assim
que o workflow executa, mantendo a janela de jogos das 9h do dia às 9h do seguinte.
Fontes ainda incompletas na madrugada podem resultar em transmissões a confirmar.
Eles usam o mesmo registro diário e não repetem partes confirmadas como enviadas.
Isso reduz o risco de perder o resumo, mas não garante disparo pontual pelo GitHub.
Ele precisa estar na branch padrão e o GitHub Actions deve estar habilitado.
O GitHub pode atrasar ou deixar de executar um agendamento sob carga; não há garantia
de pontualidade. Repositórios públicos podem ter agendamentos desativados após
60 dias sem atividade. Para pausar, desative o workflow na aba Actions.

Uma execução diária curta foi projetada para caber no uso gratuito do Actions,
mas confira o consumo da sua conta, compartilhado com outros projetos. Não ative
cobrança excedente para manter o requisito de custo zero. Os artefatos expiram em
14 dias; remova logs/artefatos se não forem mais necessários.

## Confiabilidade e limites conhecidos

- A ESPN usa endpoints públicos sem contrato de estabilidade. São consultadas
  individualmente as duas datas da janela, porque o intervalo de datas foi
  recusado pela fonte nos testes.
- O ge publica dados JSON na página da agenda. O adaptador não executa JavaScript.
  A janela de datas disponível é limitada; prévias históricas podem ficar incompletas.
- As fontes são consultadas; erros de conexão e falhas transitórias recebem
  até três tentativas. Novos adaptadores podem ser adicionados em `sources/`.
  Não existe cobertura garantida de todos os canais nas fontes gratuitas atuais.
- Canais da ESPN sem região brasileira explícita são descartados, mesmo quando
  têm nomes iguais aos canais brasileiros. Direitos gerais da liga não são usados
  para inventar transmissão de partidas individuais.
- O ge fornece opções de TV/streaming por partida. Links promocionais como Cartola
  são excluídos. A lista de canais reconhecidos fica em `sources/ge.py`.
- A praça de São Paulo da TV aberta nem sempre está identificada na fonte. Esses
  canais aparecem como **praça de São Paulo a confirmar**, em vez de confirmados.
  Confirmar a grade regional com uma fonte adicional é uma melhoria ainda pendente.
- Onde faltam dados, aparece **Transmissão a confirmar**. Isso não quer dizer que
  o jogo não tem transmissão no Brasil. Os serviços pagos também são listados.
- A referência de horário é a ESPN; divergências acima de 15 minutos com o ge
  produzem aviso e impedem copiar canais entre horários divergentes.
- Nomes diferentes dos times são conciliados por aliases explícitos. Novas
  divergências podem exigir novos aliases; não há casamento aproximado arriscado.

## Reexecuções e entrega incerta

O programa registra cada parte enviada em `.state/`, por data e destinatário,
reutilizando a mensagem original em retomadas. O workflow serializa execuções e
restaura esse registro via cache. Também o inclui no artefato para recuperação.
O cache do Actions pode expirar ou ser removido: sua ausência pode permitir reenvio.
O Telegram não oferece uma chave de idempotência em `sendMessage`, portanto não
há garantia absoluta de entrega única entre falhas e perda de estado.

Antes de fazer cada requisição, a parte é marcada como `pending`; após confirmação,
como `sent`. Se houver timeout ou interrupção, a execução seguinte exige revisão
manual, evitando reenvio automático de uma mensagem possivelmente entregue.

Para reconciliar: confira a conversa, restaure o JSON do artefato se necessário e
marque a parte como `sent` caso tenha chegado, ou `new` somente se não tiver chegado.
Execute localmente com as variáveis de ambiente configuradas e o estado recuperado.
Não apague o registro do dia para simplesmente repetir um envio.

Para um teste manual local, use `sports-digest --send --force-resend`. Essa opção
requer `--send` e `delivery.enabled = true`. O workflow usa a opção somente nos
disparos manuais com `send` marcado; os disparos agendados mantêm a proteção.
O registro anterior é arquivado em `.state/history/` e o resumo atual recebe um
novo registro diário. Assim, o próximo disparo agendado também reconhece o teste
como entrega concluída. Um reenvio forçado é intencional e pode repetir mensagens
de um envio anterior cujo resultado ficou incerto.

## Complemento de transmissões brasileiras de NBA e NFL

O módulo `sources/broadcasts.py` consulta também:

- **Overdrive**: agenda brasileira de NBA/NFL, com data/hora e canais por partida.
- **Hoops Brasil**: calendários de NBA separados para ESPN/Disney+ e Prime Video.
  O endereço da temporada é calculado automaticamente; página ausente gera aviso.
- **TV Inside**: grade individual da ESPN 2. As outras grades ainda usam nomes
  legados (Brasil/Extra/International) e não foram associadas aos canais atuais.
  ESPN 3 a 6 são reconhecidos quando informados explicitamente pelas demais fontes.
  São aceitos somente títulos
  explícitos de confronto NBA/NFL. Reprises identificadas e programas genéricos
  são ignorados. A grade deve trazer a data real; o dia da semana da URL não basta.

Essas fontes são editoriais/guias brasileiros, não APIs oficiais das emissoras.
Servem como evidências de programação, sujeitas a alterações e erros editoriais.
Uma transmissão só é incorporada se os dois times e a competição coincidirem,
com horário a até 15 minutos da referência. Não são criados jogos a partir dessas
grades, nem importados direitos americanos como se fossem brasileiros.
Ausência de um canal em uma fonte não é prova de exclusividade de outro serviço.


Cada novo canal recebe URL, fonte, país e horário de consulta em
`broadcast_evidence`, no JSON da agenda. Os links ficam no arquivo de evidências;
o resumo enviado ao Telegram permanece compacto. Calendários que associam uma
partida de 0h à rodada anterior são convertidos para a data civil seguinte antes
do cruzamento com o horário da ESPN.

Para datas futuras, a agenda diária do Overdrive e as grades do ge/TV Inside podem
ainda não estar completas. “Transmissão a confirmar” continua sendo necessário.

## Referências das integrações

### Diagnóstico do agendamento em 26/11/2026

O cron `0 12 * * *` está correto para 9h de Brasília. O job manual
`140112367726` iniciou às 18h47 UTC (15h47 de Brasília) e confirmou uma parte
enviada. O job automático `140173344549` iniciou às 21h16 UTC (18h16 de Brasília),
restaurou o cache da execução manual e informou zero partes enviadas.
Portanto, houve atraso na execução automática e o controle de duplicatas
impediu uma segunda entrega. Os logs não identificam a causa interna do atraso.
O aviso de Node 20 não impediu o envio: ambos os jobs concluíram com sucesso.

As actions foram atualizadas para runtimes Node 24. O workflow agora escreve
um resumo com tipo de evento, cron, data da agenda e contagem do registro de
entrega. A contagem restaurada não é a quantidade enviada naquela execução;
para isso, veja `Partes enviadas nesta execução` na etapa de coleta/envio.

### Auditoria de qualidade

Consulte `docs/AUDIT.md` para os resultados e as limitações por requisito.
Os arquivos JSON da agenda incluem `source_reports` (consulta, datas observadas,
status, cobertura e última atualização quando publicada) e `broadcast_evidence`
(canal, fonte e acesso quando identificado). Datas observadas em calendários
seletivos não comprovam cobertura contínua nem ausência de transmissão.

Novos complementos: FA.wiki para NFL; Guia de TV com grades ESPN 1 a 6; grade
oficial da Globo São Paulo. O Overdrive agora complementa também as competições
de futebol reconhecidas. Canais ESPN numerados divergentes entre fontes geram
aviso e a indicação “ESPN (número a confirmar)”; não são publicados como confirmados.

Para repetir as verificações com rede, sem enviar mensagens:

```powershell
python scripts/audit_sources.py
python scripts/verify_digest.py 2026-11-22 2026-11-25 2026-11-27 2026-11-28 2026-11-29
```


- [Agenda do ge](https://ge.globo.com/agenda/)
- [Exemplo de consulta pública da ESPN](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard)
- [Telegram Bot API — sendMessage](https://core.telegram.org/bots/api#sendmessage)
- [Agendamentos do GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Custos e franquias do GitHub Actions](https://docs.github.com/en/actions/concepts/billing-and-usage)
