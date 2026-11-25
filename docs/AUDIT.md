# Auditoria de transmissões — 25/11/2026

Execução local, somente leitura e geração de prévias. Nenhuma mensagem enviada.
Dados das fontes podem mudar após esta auditoria. Os snapshots e resultados
detalhados estão em `output/audit/`, ignorado pelo Git.

## Resultado por requisito

| Requisito | Resultado | Limite restante |
| --- | --- | --- |
| NFL: canais ESPN numerados | FA.wiki integrada; teste real identificou ESPN 3 em Lions × Buccaneers e ESPN 2 em Broncos × Raiders de 22/11 | Não há grade completa garantida para todos os jogos futuros; não inferir canal a partir do pacote de direitos |
| Grades ESPN | Acesso às seis páginas atuais do Guia de TV verificado; adaptador integrado | Programas genéricos, reprises e títulos sem os dois times não confirmam partida; JSON estruturado pode cobrir menos dias que a página visual |
| Divergências | Canais ESPN numerados diferentes por fonte são retidos como evidência, mas substituídos por ESPN (número a confirmar) no resumo | Simulcast real também pode produzir aviso; outros tipos de exclusividade não são inferidos automaticamente |
| Cobertura | Cada execução registra 28 resultados de consulta com datas observadas, status, quantidade e data de consulta | Datas observadas não comprovam cobertura contínua; ausência numa agenda seletiva não prova ausência de transmissão |
| Atualização | Captura dateModified quando publicado; grade Globo traz modified | Várias fontes não publicam atualização; valor fica nulo. Página antiga pode conter calendário válido e página recente pode estar incompleta |
| Prime e pacotes | Mantém Prime Video separado de League Pass/Game Pass; acesso adicional marcado | Não há consulta autenticada ao catálogo individual do usuário; texto ambíguo não confirma inclusão no Prime |
| Globo São Paulo | URL regional oficial integrada; identidade da grade GGP1 verificada; intervalo inclui pré-jogo | Outros canais abertos e afiliadas ainda não têm validação regional automática |
| Futebol | Overdrive ampliado para competições reconhecidas; jogos oficiais da Globo cruzados com nomes/competição | Amostra real não abrange todas as competições/fases do escopo |
| Falhas e formatos | Respostas 200 sem estrutura válida são falhas, não confirmação vazia; desconhecidos e cruzamentos sem correspondência produzem avisos | Mudanças futuras ainda exigirão manutenção; execução contínua não foi testada |

## Verificação real de múltiplas datas

| Data do resumo | Jogos selecionados | Sem canal identificado |
| --- | ---: | ---: |
| 22/11/2026 | 23 | 19 |
| 25/11/2026 | 20 | 0 |
| 27/11/2026 | 13 | 9 |
| 28/11/2026 | 8 | 5 |
| 29/11/2026 | 28 | 15 |

Total: 92 jogos em cinco janelas. São contagens das fontes disponíveis em 25/11,
não uma aferição independente de acerto de todos os canais. Ter um canal listado
também não comprova que todas as opções de transmissão foram encontradas.
Datas históricas e futuras sofrem com a janela curta das grades diárias.

Confirmações obtidas pelo cruzamento:

- 22/11: Lions × Buccaneers — ESPN 3, Disney+ e NFL Game Pass/DAZN (FA.wiki).
- 25/11: três partidas NBA com ESPN 2 e Disney+ Premium (Hoops Brasil,
  Overdrive e grade da ESPN 2); Rams × Packers com Netflix e Game Pass.
- 27/11: Knicks × Heat e Spurs × Lakers no Prime Video (ge e Hoops Brasil).
- 27/11: Steelers × Broncos no SporTV e Game Pass (FA.wiki).
- 28/11: Palmeiras × Estudiantes — Globo São Paulo, em grade regional oficial.
- 29/11: Vitória × Santos — Globo São Paulo, em grade regional oficial.

Correções descobertas na auditoria:

- PSG e Paris Saint-Germain, Estudiantes e Estudiantes de La Plata: aliases
  explícitos corrigidos; novos nomes não são unidos por aproximação.
- FA.wiki usa marcação de horário diferente em jogos encerrados; ambos os
  formatos agora são reconhecidos.
- Globo pode iniciar a transmissão antes do jogo. Somente a grade regional
  oficial com confronto explícito usa intervalo, em vez da tolerância de 15 min.
- Alguns títulos do TV Inside coincidem com reprises sem marca explícita.
  Horários divergentes e confrontos sem jogo correspondente são avisados,
  sem atribuição automática de canal.
- Evidências do ge e ESPN são registradas separadamente, sem atribuir o canal
  descoberto em uma delas à outra.

## Testes automatizados

30 testes locais passaram. Além do escopo original, cobrem conflito ESPN 2/3,
ausência que não configura conflito, assinatura adicional, grade genérica/reprise,
horário sem classe CSS no FA.wiki, praça incorreta, pré-jogo regional, outras
divisões e futebol feminino. Nenhum teste depende de rede.

## O que continua pendente

1. Cobertura completa dos canais brasileiros da NFL futura e das datas fora das
   janelas públicas; manter a indicação a confirmar.
2. Confirmação regional de SBT, Record, Band e outras emissoras abertas.
3. Amostras reais de Copa do Brasil da 5ª fase em diante, Paulista, Sul-Americana,
   La Liga e clássicos da Premier League; testes de filtro não substituem isso.
4. Regras de conflito para exclusividades de plataformas, somente se uma fonte
   declarar exclusividade explicitamente. Opções diferentes podem coexistir.
5. Piloto de operação diária, incluindo Telegram e GitHub Actions, depois da
   configuração das credenciais. Esta auditoria não ativou o envio.

## Fontes

- https://futebolamericano.wiki.br/nfl/calendario/
- https://futebolamericano.wiki.br/nfl/onde-assistir/espn-disney-plus/
- https://www.guiadetv.com/canal/espn-3 (e páginas dos demais canais)
- https://redeglobo.globo.com/sao-paulo/programacao/
- https://gameoverdrive.com.br/jogos-de-hoje/
- https://hoopsbrasil.com.br/nba-2026-27-calendario-de-transmissoes-da-espn-e-disney/
- https://hoopsbrasil.com.br/nba-2026-27-calendario-de-transmissoes-do-prime-video/
- https://www.primevideo.com/-/pt/help/?nodeId=TXsV81Exq70bTlr2Xw
