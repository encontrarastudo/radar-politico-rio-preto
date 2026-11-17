# -*- coding: utf-8 -*-
"""Radar Político de Rio Preto — gera o site (index.html + SEO) a partir de data/*.json.
Uso: python tools/build.py  (roda a partir da raiz do repositório)."""
import os, re, json, html, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT  = ROOT  # o site vai na raiz (GitHub Pages)
BASE = "https://encontrarastudo.github.io/radar-politico-rio-preto"

def load(n): return json.load(open(os.path.join(DATA, n), encoding="utf-8"))
VERS = load("vereadores.json")
C = load("contagens.json")
PRES = load("presenca.json")
VOT = load("votacoes.json")
PROPOSTAS = load("propostas.json")
META = load("meta.json")

def esc(s): return html.escape(str(s), quote=True)
def nrm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()

ATUALIZADO_ISO = META.get("atualizado","2026-11-17")
def data_br(iso):
    try:
        y,m,d = iso.split("-"); meses=["","janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
        return f"{int(d)} de {meses[int(m)]} de {y}"
    except: return iso
ATUALIZADO = data_br(ATUALIZADO_ISO)
PERIODO = "2025–2028"; PERIODO_DADOS = META.get("periodo_dados","2025-2026")

BYID = {v["id"]:v for v in VERS}
def vget(vid,k): return BYID.get(vid,{}).get(k,"")

PROF = "https://www.riopreto.sp.leg.br/Consulta/vereadores/Vereador/{id}"
TIPO_ID = {"pl":"129","plc":"130","req":"134","ind":"135","moc":"136"}
def busca(tipo, aid):
    return ("https://riopreto.siscam.com.br/Documentos/Pesquisa?Pesquisa=Avancada&id=78&pagina=1&Modulo=8"
            f"&Documento={tipo}&Numeracao=Documento&AnoInicial=2025&AnoFinal=2026&Situacao=0&Classificacao=0"
            f"&TipoAutor=Todos&AutoriaId={aid}&Iniciativa=Nenhum&NoTexto=false")
SESSAO = "https://riopreto.siscam.com.br/Sessoes/Sessao/{id}"
def ci(d,i): return d.get(str(i),0) or 0

# ---------- classificação / extração ----------
HOME=["congratula","aplauso","pesar","falecimento","homenagem","titulo de cidad","cidadao rio","parabens","denomina","dia municipal","semana municipal","data comemorativa","calendario oficial","aniversario"]
INFO=["informacoes","informacao","preste informac","esclareci","motivos que levaram","requer informac","preste contas","presta contas","prestacao de contas"]
MELH=["buraco","recape","asfalt","paviment","calcad","ilumina","lampada","luminaria","poste","rocada","limpeza","arvore","poda","supressao","bueiro","boca de lobo","galeria","drenagem","lombada","redutor","semaforo","sinaliz","praca","parque","parquinho","academia","calistenia","nivelamento","cascalho","patrol","estacionamento","bolsao","esgoto","passarela","rotatoria","muro","viela","campo de futebol","ar-condicionado","ar condicionado","quadra","ponto de onibus","abrigo"]
def classify(tipo, a):
    a=nrm(a)
    if tipo.startswith("Moção"): return "homenagens"
    if tipo.startswith("Projeto"): return "leis"
    if any(k in a for k in HOME): return "homenagens"
    if any(k in a for k in INFO): return "cobrancas"
    if any(k in a for k in MELH): return "melhorias"
    return "outros"
def subtype(a):
    a=nrm(a)
    if any(k in a for k in ["buraco","recape","asfalt","paviment"]): return "Asfalto e buracos"
    if any(k in a for k in ["ilumina","lampada","luminaria","poste"]): return "Iluminação"
    if any(k in a for k in ["rocada","limpeza","arvore","poda","supressao","mato"]): return "Limpeza e mato"
    if "calcad" in a: return "Calçada"
    if any(k in a for k in ["bueiro","boca de lobo","drenagem","galeria"]): return "Drenagem e bueiro"
    if any(k in a for k in ["estacionamento","bolsao"]): return "Estacionamento"
    if any(k in a for k in ["lombada","redutor","semaforo","sinaliz"]): return "Trânsito"
    if any(k in a for k in ["nivelamento","cascalho","patrol"]): return "Nivelamento de via"
    if any(k in a for k in ["praca","parque","parquinho","academia","calistenia","campo","quadra"]): return "Praça e lazer"
    return "Outros serviços"
RUA_RE=re.compile(r"\b(Rua|Avenida|Av\.?|Travessa|Pra[çc]a|Estrada(?:\s+Municipal)?|Estr\.?\s*Mun\.?|Rodovia|Alameda|Viela|Largo)\s+([A-ZÀ-Ú][\wçãáéíóúâêôà'’.\-]+(?:\s+(?:de|da|do|das|dos|e)?\s*[A-ZÀ-Ú0-9][\wçãáéíóúâêôà'’.\-]+){0,4})")
BAIRRO_RE=re.compile(r"\b(Bairro|Vila|Jardim|Parque|Residencial|Res\.?|Est[âa]ncia|N[úu]cleo(?:\s+Habitacional)?|Conjunto|Distrito|Ch[áa]cara)\s+([A-ZÀ-Ú][\wçãáéíóúâêôà'’.\-]+(?:\s+[A-ZÀ-Ú0-9][\wçãáéíóúâêôà'’.\-]+){0,3})")
def extrai(reg,s):
    m=reg.search(s)
    return re.sub(r"\s+"," ",(m.group(1)+" "+m.group(2))).strip(" .,–-") if m else ""

GRUPOS={"melhorias":"Pedidos de melhoria nos bairros","cobrancas":"Perguntas e cobranças","homenagens":"Homenagens","leis":"Propostas de lei","outros":"Outros"}
REGS=[]
for p in PROPOSTAS:
    tipo,n,data,autor,assunto = p
    g=classify(tipo,assunto); rua=extrai(RUA_RE,assunto); bairro=extrai(BAIRRO_RE,assunto)
    REGS.append({"grupo":g,"tipo":tipo,"n":n,"data":data,"autor":autor.title() if autor.isupper() else autor,
                 "assunto":assunto,"rua":rua,"bairro":bairro,"sub":subtype(assunto) if g=="melhorias" else "",
                 "ruaN":nrm(rua),"bairroN":nrm(bairro),"txtN":nrm(assunto+" "+autor)})
POR_GRUPO={k:[r for r in REGS if r["grupo"]==k] for k in GRUPOS}
def repeticoes(chave):
    b={}
    for r in REGS:
        if r["grupo"]!="melhorias" or not r[chave]: continue
        b.setdefault((r[chave],r["sub"]),[]).append(r)
    out=[(l,s,it) for (l,s),it in b.items() if len(it)>=2]; out.sort(key=lambda x:-len(x[2])); return out
REP_BAIRRO=repeticoes("bairro")

# ---------- render vereadores ----------
def card(v):
    vid,slug,nome,part,mesa = v["id"],v["slug"],v["nome"],v["partido"],v["mesa"]
    mesa_chip=f'<span class="chip chip-mesa">{esc(mesa)}</span>' if mesa else ""
    ini="".join([p[0] for p in nome.split()[:2]]).upper()
    return f'''<article class="card" id="card-{slug}"><a class="card-link" href="#v-{slug}" aria-label="Ver detalhes de {esc(nome)}">
  <div class="avatar" aria-hidden="true">{esc(ini)}</div>
  <div class="card-body"><h3 class="card-nome">{esc(nome)}</h3><p class="card-sub">{esc(v["nome_completo"])}</p>
  <div class="chips"><span class="chip chip-part">{esc(part)}</span>{mesa_chip}</div>
  <dl class="mini"><div><dt>Projetos de lei</dt><dd>{ci(C["pl"],vid)+ci(C["plc"],vid)}</dd></div>
  <div><dt>Indicações</dt><dd>{ci(C["ind"],vid)}</dd></div><div><dt>Requerimentos</dt><dd>{ci(C["req"],vid)}</dd></div>
  <div><dt>Moções</dt><dd>{ci(C["moc"],vid)}</dd></div></dl></div></a></article>'''

def fonte(label,url): return f'<a class="fonte" href="{url}" target="_blank" rel="noopener">{esc(label)} <span aria-hidden="true">↗</span></a>'

def detalhe(v):
    vid,slug,nome,part,mesa = v["id"],v["slug"],v["nome"],v["partido"],v["mesa"]
    prof=PROF.format(id=vid); ini="".join([p[0] for p in nome.split()[:2]]).upper()
    props=[("Projetos de lei",ci(C["pl"],vid),busca(TIPO_ID["pl"],vid),"pl"),
           ("Projetos de lei complementar",ci(C["plc"],vid),busca(TIPO_ID["plc"],vid),"pl"),
           ("Indicações",ci(C["ind"],vid),busca(TIPO_ID["ind"],vid),"ind"),
           ("Requerimentos",ci(C["req"],vid),busca(TIPO_ID["req"],vid),"req"),
           ("Moções",ci(C["moc"],vid),busca(TIPO_ID["moc"],vid),"moc")]
    prows="".join(f'<tr><th scope="row">{esc(l)} <button class="ajuda" data-termo="{t}" aria-label="O que é {esc(l)}?">?</button></th><td class="num">{n}</td><td>{fonte("ver a lista oficial",u)}</td></tr>' for (l,n,u,t) in props)
    # presença
    prows2=""
    for s in PRES:
        for ch in s["chamadas"]:
            pres = vid in ch["presentes"]; st="Presente" if pres else "Ausente"; cls="sim" if pres else "nao"
            prows2+=f'<tr><th scope="row">{esc(s["titulo"])} — {esc(s["data"])}<br><span class="muted">{esc(ch["nome"])}</span></th><td><span class="status {cls}">{st}</span></td><td>{fonte("ver a sessão",SESSAO.format(id=s["sid"]))}</td></tr>'
    # votos
    vrows=""
    for m in VOT:
        meuvoto=None
        for voto,ids in m["votos"].items():
            if vid in ids: meuvoto=voto; break
        reg=meuvoto or "Sem registro nominal"; cls={"A favor":"sim","Contra":"nao"}.get(meuvoto,"neutro")
        vrows+=f'<tr><th scope="row">{esc(m["materia"])}<br><span class="muted">{esc(m.get("assunto",""))} · {esc(m["sessao"])}, {esc(m["data"])}</span></th><td><span class="status {cls}">{esc(reg)}</span></td><td>{fonte("ver a votação",SESSAO.format(id=m["sid"]))}</td></tr>'
    mesa_line=f'<p class="detalhe-mesa">{esc(mesa)} da Mesa Diretora</p>' if mesa else ""
    return f'''<article class="detalhe" id="v-{slug}" aria-labelledby="h-{slug}">
  <a class="voltar" href="#vereadores">← Voltar para a lista</a>
  <header class="detalhe-head"><div class="avatar avatar-lg" aria-hidden="true">{esc(ini)}</div>
  <div><h2 id="h-{slug}">{esc(nome)}</h2><p class="detalhe-nome">{esc(v["nome_completo"])}</p>
  <div class="chips"><span class="chip chip-part">{esc(part)}</span></div>{mesa_line}</div></header>
  <section class="bloco"><h3>Contato e perfil oficial</h3><p>{fonte("ver o perfil oficial de "+nome+" na Câmara",prof)}</p>
  <p class="muted">Contato geral da Câmara: camara@riopreto.sp.leg.br · (17) 3214-7777.</p></section>
  <section class="bloco"><h3>Proposições no mandato ({PERIODO_DADOS})</h3>
  <p class="muted">Números de autoria/coautoria no sistema legislativo (SISCAM). Clique na fonte para conferir a lista completa.</p>
  <table class="tab"><thead><tr><th>Tipo</th><th>Quantidade</th><th>Fonte oficial</th></tr></thead><tbody>{prows}</tbody></table></section>
  <section class="bloco"><h3>Presença nas sessões <button class="ajuda" data-termo="sessao" aria-label="O que é sessão?">?</button></h3>
  <p class="muted">Sessões com chamada registrada no SISCAM nesta versão.</p>
  <table class="tab"><thead><tr><th>Sessão / chamada</th><th>Situação</th><th>Fonte</th></tr></thead><tbody>{prows2}</tbody></table></section>
  <section class="bloco"><h3>Como votou (votações nominais) <button class="ajuda" data-termo="nominal" aria-label="O que é votação nominal?">?</button></h3>
  <p class="muted">Apenas o registro do voto. Em votações simbólicas o voto individual não é registrado.</p>
  <table class="tab"><thead><tr><th>Matéria</th><th>Voto</th><th>Fonte</th></tr></thead><tbody>{vrows}</tbody></table></section>
  <section class="bloco"><h3>Verba de gabinete e despesas</h3><p>Informação não disponível nesta versão. Consulte no {fonte("Portal da Transparência",'https://www.riopreto.sp.leg.br/Home/PortalTransparencia')}.</p></section>
</article>'''

cards_html="\n".join(card(v) for v in VERS)
detalhes_html="\n".join(detalhe(v) for v in VERS)
partidos=sorted(set(v["partido"] for v in VERS))
options="".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in partidos)

GLOSS=[
 ("pl","O que é um Projeto de Lei?","Uma proposta para criar ou mudar uma lei da cidade. Se os vereadores aprovam e o prefeito sanciona, vira lei e vale para todos. Aqui somamos também os Projetos de Lei Complementar, um tipo especial usado para assuntos que a Lei Orgânica do município exige tratar com regras mais detalhadas."),
 ("ind","O que é uma Indicação?","Um pedido ou sugestão do vereador ao prefeito — por exemplo, tapar um buraco, podar uma árvore ou trocar uma lâmpada. Não vira lei e a prefeitura não é obrigada a atender. É o tipo mais comum e costuma ser apresentado em grande quantidade, então um número alto não significa, sozinho, mais trabalho."),
 ("req","O que é um Requerimento?","Um pedido formal feito dentro da própria Câmara — pedir uma informação, convidar alguém, registrar uma congratulação ou um voto de pesar."),
 ("moc","O que é uma Moção?","Uma manifestação oficial da Câmara: de apoio, de pesar, de repúdio ou de congratulação a uma pessoa, grupo ou causa."),
 ("sessao","O que é uma Sessão?","A reunião em que os vereadores debatem e votam. As ordinárias costumam ser semanais. Cada uma tem duas listas de presença: a Chamada Regimental (na abertura) e a Chamada da Ordem do Dia (na hora de votar)."),
 ("nominal","O que é votação nominal?","Quando fica registrado o voto de cada vereador, um por um. Na votação simbólica a Câmara registra só o resultado geral, sem o nome de cada um — nesses casos não dá para saber como cada um votou."),
 ("quantos","Quantos vereadores tem São José do Rio Preto?","A Câmara Municipal de São José do Rio Preto tem 23 vereadores no mandato de 2025 a 2028."),
]
gloss_html="".join(f'<div class="gloss-item"><h3>{esc(q)}</h3><p>{esc(a)}</p></div>' for k,q,a in GLOSS)
gloss_js=json.dumps({k:{"q":q,"a":a} for k,q,a in GLOSS}, ensure_ascii=False)

def item_html(r):
    local=" · ".join([x for x in [r["rua"],r["bairro"]] if x]); local=f'<div class="it-local">📍 {esc(local)}</div>' if local else ""
    sub=f'<span class="it-sub">{esc(r["sub"])}</span>' if r["sub"] else ""
    return (f'<li class="it"><div class="it-top"><span class="it-tipo">{esc(r["tipo"])} {esc(r["n"])}</span><span class="it-data">{esc(r["data"])}</span></div>'
            f'<div class="it-ass">{esc(r["assunto"])}</div>{local}<div class="it-aut">por <strong>{esc(r["autor"])}</strong> {sub}</div></li>')
grupos_html=""
for k in ["melhorias","cobrancas","homenagens","leis","outros"]:
    regs=POR_GRUPO[k]
    if not regs and k=="outros": continue
    itens="".join(item_html(r) for r in regs) or "<li class='it'>Sem itens nesta amostra.</li>"
    grupos_html+=f'<details class="grupo"><summary><span class="g-nome">{esc(GRUPOS[k])}</span><span class="g-cont">{len(regs)} na amostra</span></summary><ul class="lista-itens">{itens}</ul></details>'
rep_html=""
for loc,sub,items in REP_BAIRRO[:8]:
    datas=sorted(set(i["data"] for i in items)); autores=sorted(set(i["autor"] for i in items))
    rep_html+=f'<details class="rep"><summary><span class="rep-loc">{esc(loc)}</span><span class="rep-tag">{esc(sub)}</span><span class="rep-n">{len(items)}×</span></summary><p class="rep-meta">Datas: {esc(", ".join(datas))} · Por: {esc(", ".join(autores))}</p><ul class="lista-itens">{"".join(item_html(i) for i in items)}</ul></details>'
busca_data=json.dumps([{"g":GRUPOS[r["grupo"]],"t":r["tipo"],"n":r["n"],"d":r["data"],"a":r["autor"],"s":r["assunto"],"rua":r["rua"],"bairro":r["bairro"],"q":(r["ruaN"]+" "+r["bairroN"]+" "+r["txtN"])} for r in REGS], ensure_ascii=False)

# contagens para verificação
tot_props = sum(ci(C[t],v["id"]) for t in C for v in VERS)
verif_html=f'''<div class="met">
<h3>Presença nas sessões</h3>
<p>A presença vem da chamada registrada em cada sessão no sistema do Legislativo (SISCAM). Há ainda a fonte oficial independente — o relatório mensal <em>“Comparecimento dos Vereadores às Sessões”</em> (PDF da Câmara). Onde as duas existem, os nomes coincidem na maioria dos casos; divergências pontuais ocorrem porque o relatório mensal pode contar falta justificada como presença, e nem toda sessão tem a chamada estruturada preenchida no SISCAM.</p>
<h3>Proposições</h3>
<p>As contagens por vereador vêm da busca oficial de proposituras (mandato {PERIODO_DADOS}). Os textos nos grupos e na busca por rua são a amostra mais recente coletada.</p>
<h3>Como agrupamos</h3>
<p>A mesma regra vale para todos: Moção → Homenagem; Projeto de Lei → Proposta de lei; Indicação/Requerimento são lidos pelo assunto (congratulação/pesar → Homenagens; pedido de informação → Perguntas e cobranças; serviço no bairro → Pedidos de melhoria; o resto → Outros).</p>
<p class="muted">Origem desta carga de dados: {esc(META.get("origem","—"))}. Total de proposituras contabilizadas (mandato): {tot_props:,}.</p></div>'''.replace(",", ".")

naoconf_html='''<ul class="aviso-lista">
<li><strong>Partido de alguns vereadores pode divergir entre fontes oficiais</strong> (lista da Câmara x relatório mensal). Usamos a lista do portal da Câmara; a diferença pode refletir troca de partido.</li>
<li><strong>Presença:</strong> confirmada no nível da chamada apenas nas sessões com o bloco preenchido no SISCAM. O histórico completo depende do relatório mensal oficial (PDF) ou da coleta automática diária.</li>
<li><strong>Textos das proposições:</strong> amostra recente. As contagens totais por vereador são completas.</li>
<li><strong>Contato, foto e verba de gabinete por vereador:</strong> coletados quando disponíveis; onde faltar, o card leva ao perfil oficial.</li>
<li><strong>Repetições:</strong> calculadas sobre a amostra atual.</li>
</ul>'''

CSS = open(os.path.join(os.path.dirname(__file__), "estilo.css"), encoding="utf-8").read()

TITLE="Radar Político de Rio Preto — o que cada vereador faz | SP"
DESC=(f"Radar Político de Rio Preto: presença, proposições e votos dos 23 vereadores de São José do Rio Preto (SP), "
      f"mandato {PERIODO}, com busca por rua ou bairro. Cada número tem link para a fonte oficial. Atualizado em {ATUALIZADO}.")
jsonld=[
 {"@context":"https://schema.org","@type":"WebSite","name":"Radar Político de Rio Preto","url":BASE,"inLanguage":"pt-BR",
  "potentialAction":{"@type":"SearchAction","target":{"@type":"EntryPoint","urlTemplate":BASE+"/?rua={search_term_string}"},"query-input":"required name=search_term_string"}},
 {"@context":"https://schema.org","@type":"GovernmentOrganization","name":"Câmara Municipal de São José do Rio Preto","url":"https://www.riopreto.sp.leg.br/","email":"camara@riopreto.sp.leg.br","telephone":"+551732147777","address":{"@type":"PostalAddress","addressLocality":"São José do Rio Preto","addressRegion":"SP","addressCountry":"BR"}},
 {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for k,q,a in GLOSS]},
]
jsonld_html="\n".join(f'<script type="application/ld+json">{json.dumps(x,ensure_ascii=False)}</script>' for x in jsonld)

TPL = open(os.path.join(os.path.dirname(__file__), "template.html"), encoding="utf-8").read()
page = (TPL.replace("__TITLE__",esc(TITLE)).replace("__DESC__",esc(DESC)).replace("__BASE__",BASE)
 .replace("__JSONLD__",jsonld_html).replace("__CSS__",CSS).replace("__ATUALIZADO__",ATUALIZADO)
 .replace("__REP__",rep_html).replace("__GRUPOS__",grupos_html).replace("__OPTIONS__",options)
 .replace("__CARDS__",cards_html).replace("__GLOSS__",gloss_html).replace("__VERIF__",verif_html)
 .replace("__DETALHES__",detalhes_html).replace("__GLOSSJS__",gloss_js).replace("__BUSCADATA__",busca_data)
 .replace("__NAOCONF__",naoconf_html))
open(os.path.join(OUT,"index.html"),"w",encoding="utf-8").write(page)

# robots / sitemap / llms
open(os.path.join(OUT,"robots.txt"),"w",encoding="utf-8").write(
"User-agent: *\nAllow: /\nUser-agent: GPTBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: CCBot\nAllow: /\n\nSitemap: "+BASE+"/sitemap.xml\n")
urls=[BASE+"/",BASE+"/#vereadores",BASE+"/#busca",BASE+"/#glossario"]+[BASE+"/#v-"+v["slug"] for v in VERS]
sm='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls: sm+=f'  <url><loc>{esc(u)}</loc><lastmod>{ATUALIZADO_ISO}</lastmod><changefreq>daily</changefreq></url>\n'
sm+="</urlset>\n"; open(os.path.join(OUT,"sitemap.xml"),"w",encoding="utf-8").write(sm)
linhas="\n".join(f"- {v['nome']} ({v['partido']}"+(f", {v['mesa']}" if v['mesa'] else "")+f"): {ci(C['pl'],v['id'])+ci(C['plc'],v['id'])} projetos de lei, {ci(C['ind'],v['id'])} indicações, {ci(C['req'],v['id'])} requerimentos, {ci(C['moc'],v['id'])} moções. Perfil: {PROF.format(id=v['id'])}" for v in VERS)
open(os.path.join(OUT,"llms.txt"),"w",encoding="utf-8").write(
f"# Radar Político de Rio Preto\n\n> Site de transparência, com dados oficiais, sobre os 23 vereadores da Câmara Municipal de São José do Rio Preto (SP), mandato {PERIODO}. Presença, proposições e votos, com busca por rua/bairro. Atualizado em {ATUALIZADO}.\n\n## Vereadores (mandato {PERIODO})\n{linhas}\n")

print(f"OK build: {len(VERS)} vereadores, {len(REGS)} proposituras na amostra, {len(PRES)} sessões, {len(VOT)} votações nominais.")
print(f"index.html: {os.path.getsize(os.path.join(OUT,'index.html'))} bytes")
