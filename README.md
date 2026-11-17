# Radar Político de Rio Preto

Site de transparência, **só com dados oficiais**, sobre os 23 vereadores da Câmara Municipal de
São José do Rio Preto–SP (mandato 2025–2028): presença nas sessões, proposições apresentadas,
votos em votações nominais, e **busca por rua ou bairro**. Cada número tem link para a fonte oficial.
O site apenas mostra os dados — não dá notas nem classifica ninguém.

**Site:** https://encontrarastudo.github.io/radar-politico-rio-preto/

## Como funciona (robô diário)

Um robô (GitHub Actions) roda **todo dia de madrugada**:

1. `tools/collector.py` busca os dados na Câmara (SISCAM), **valida** e só grava `data/*.json` se
   a coleta vier completa e consistente. Se vier incompleta ou estranha, ele **falha de propósito**
   e nada é publicado — o site fica na última versão boa.
2. `tools/build.py` reconstrói o `index.html` a partir de `data/*.json`.
3. Se algo mudou, o robô dá commit e o GitHub Pages republica sozinho.

Rodar manualmente: aba **Actions → Atualizar site → Run workflow**.

## Validação (o que impede publicar lixo)

- Precisa ter exatamente 23 vereadores.
- Contagem de proposituras por tipo precisa cobrir os 23 e ter total plausível.
- O total não pode despencar (nem explodir) em relação à última coleta — pega coleta parcial.
- Pelo menos uma sessão com chamada de presença plausível (10 a 23 presentes).
- Amostra de proposituras recente não pode vir vazia; toda proposta precisa de autor e assunto.

## Estrutura

- `index.html`, `robots.txt`, `sitemap.xml`, `llms.txt` — o site (gerados; servidos pelo Pages).
- `data/*.json` — os dados coletados (a "última versão boa").
- `tools/collector.py` — coleta + validação.
- `tools/build.py` — monta o site a partir dos dados.
- `tools/template.html`, `tools/estilo.css` — modelo e estilo.
- `.github/workflows/atualizar.yml` — o robô.

## Fontes oficiais

- Câmara: https://www.riopreto.sp.leg.br/
- Sessões, presença e votações (SISCAM): https://riopreto.siscam.com.br/sessoes
- Proposituras (SISCAM): https://riopreto.siscam.com.br/index/78/8
- Relatório mensal de presença: https://www.riopreto.sp.leg.br/ContaPublica/Listar/1267

Projeto cidadão independente, sem vínculo com a Câmara, a Prefeitura ou qualquer partido.
A coleta é feita com parcimônia (ritmo lento, identificada). Se a Câmara publicar os dados em
formato aberto, o coletor pode ser adaptado para usá-lo.
