# -*- coding: utf-8 -*-
"""Radar Político de Rio Preto — gera o site (index.html + SEO) a partir de data/*.json.
Uso: python tools/build.py  (roda a partir da raiz do repositório)."""
import os, re, json, html, unicodedata
from collections import Counter

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
try: CONTATOS = load("contatos.json")
except Exception: CONTATOS = {}
try: FREQM = load("frequencia.json")
except Exception: FREQM = {"meta":{},"por_vereador":{}}
FREQMP = FREQM.get("por_vereador", {})
PRES_FULL = any((v or {}).get("total") for v in FREQMP.values())
PRES_NOTA = ("Presença em todas as sessões do mandato, pelos relatórios mensais oficiais de comparecimento da Câmara."
             if PRES_FULL else "Sessões com chamada registrada no SISCAM nesta versão.")
try: EF = load("efetividade.json")
except Exception: EF = {}
def ef_aprov(vid): return (EF.get(str(vid)) or {}).get("aprovados", 0)
try: GV = load("gastos_viagens.json")
except Exception: GV = {"meta":{},"por_vereador":{}}
GVP = GV.get("por_vereador", {})
def gv_total(vid): return (GVP.get(str(vid)) or {}).get("total", 0) or 0
def gv_viagens(vid): return (GVP.get(str(vid)) or {}).get("viagens", 0) or 0
try: EM = load("emendas.json")
except Exception: EM = {"meta":{},"top_beneficiarios":[],"por_vereador":{}}
EMP = EM.get("por_vereador", {})
def em_v(vid): return EMP.get(str(vid)) or {"n":0,"previsto":0,"pago":0,"itens":[]}
def brl(v): return "R$ " + ("{:,.2f}".format(v or 0)).replace(",","X").replace(".",",").replace("X",".")
def brl0(v): return "R$ " + ("{:,.0f}".format(v or 0)).replace(",",".")

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
def busca_aprov(tipo, aid):
    return ("https://riopreto.siscam.com.br/Documentos/Pesquisa?Pesquisa=Avancada&id=78&pagina=1&Modulo=8"
            f"&Documento={tipo}&Numeracao=Documento&AnoInicial=2025&AnoFinal=2026&Situacao=515&Classificacao=0"
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

# ---------- frequência, foto, rosca, barra ----------
FOTO = "https://riopreto.siscam.com.br/Vereadores/Foto/{id}"
PASTEIS = ["#efe7fb","#fde9ef","#fdeede","#e6f3ec","#e7eefb","#fbeede","#eafaf2","#f3e9fb"]
# cores por tipo de propositura
TCOR = {"pl":"#1a7a44","ind":"#2f6fd0","req":"#e07b2a","moc":"#c9398f"}
TLAB = {"pl":"Projetos de lei","ind":"Indicações","req":"Requerimentos","moc":"Moções"}

def iniciais(nome): return "".join([p[0] for p in nome.split()[:2]]).upper()

def freq(vid):
    fm = FREQMP.get(str(vid))
    if fm and fm.get("total"):
        tot=fm["total"]; pres=fm.get("presencas",0)
        return {"pct": round(100*pres/tot) if tot else 0, "pres":pres, "tot":tot, "aus":fm.get("faltas",0), "fonte":"mensal"}
    if not PRES: return None
    pres = sum(1 for s in PRES if any(vid in ch["presentes"] for ch in s["chamadas"]))
    tot = len(PRES)
    return {"pct": round(100*pres/tot) if tot else 0, "pres":pres, "tot":tot, "aus":tot-pres, "fonte":"siscam"}

def donut(pct):
    import math
    r=15.9; c=2*math.pi*r; off=c*(1-pct/100)
    return (f'<svg class="donut" viewBox="0 0 40 40" role="img" aria-label="{pct}% de presença">'
            f'<circle cx="20" cy="20" r="{r}" class="d-bg"/>'
            f'<circle cx="20" cy="20" r="{r}" class="d-fg" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.2f}" transform="rotate(-90 20 20)"/>'
            f'<text x="20" y="21" class="d-txt">{pct}%</text></svg>')

def foto_html(vid, nome, lg=False):
    cls = "foto foto-lg" if lg else "foto"
    return (f'<span class="{cls}"><img loading="lazy" src="{FOTO.format(id=vid)}" alt="Foto oficial de {esc(nome)}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<span class="foto-ini" style="display:none" aria-hidden="true">{esc(iniciais(nome))}</span></span>')

def freq_block(vid, grande=False):
    f = freq(vid)
    if not f: return ""
    aus = f"{f['aus']} ausência" + ("s" if f["aus"]!=1 else "")
    base = "no mandato (relatórios mensais oficiais)" if f.get("fonte")=="mensal" else "nas sessões com chamada registrada"
    return (f'<div class="freq{" freq-lg" if grande else ""}">{donut(f["pct"])}'
            f'<div class="freq-txt"><strong>{f["pres"]} de {f["tot"]} sessões</strong>'
            f'<span class="muted">{aus} · {base}</span></div></div>')

def barra_tipos(vid):
    vals = {"pl":ci(C["pl"],vid)+ci(C["plc"],vid),"ind":ci(C["ind"],vid),"req":ci(C["req"],vid),"moc":ci(C["moc"],vid)}
    tot = sum(vals.values()) or 1
    seg = "".join(f'<span style="width:{100*vals[k]/tot:.1f}%;background:{TCOR[k]}"></span>' for k in ["ind","req","moc","pl"] if vals[k])
    linhas = "".join(f'<li><span class="dot" style="background:{TCOR[k]}"></span>{TLAB[k]}<b>{vals[k]}</b></li>' for k in ["ind","req","moc","pl"])
    return f'<div class="barra">{seg}</div><ul class="cats">{linhas}</ul>'

def card(v, idx):
    vid,slug,nome,part,mesa = v["id"],v["slug"],v["nome"],v["partido"],v["mesa"]
    mesa_chip=f'<span class="chip chip-mesa">{esc(mesa)}</span>' if mesa else ""
    pastel = PASTEIS[idx % len(PASTEIS)]
    return f'''<article class="card" id="card-{slug}"><a class="card-link" href="#v-{slug}" aria-label="Ver detalhes de {esc(nome)}">
  <div class="card-head" style="background:{pastel}">{foto_html(vid,nome)}
    <div class="card-id"><h3 class="card-nome">{esc(nome)}</h3><p class="card-sub">{esc(v["nome_completo"])}</p>
    <div class="chips"><span class="chip chip-part">{esc(part)}</span>{mesa_chip}</div></div></div>
  <div class="card-body">{freq_block(vid)}
    <p class="card-label">O que apresentou no mandato</p>{barra_tipos(vid)}</div></a></article>'''

def fonte(label,url): return f'<a class="fonte" href="{url}" target="_blank" rel="noopener">{esc(label)} <span aria-hidden="true">↗</span></a>'

def contato_html(vid):
    c = CONTATOS.get(str(vid)) or {}
    email=c.get("email",""); tel=c.get("telefone","")
    linhas=[]
    if tel: linhas.append(f'📞 <a href="tel:{re.sub(chr(92)+"D","",tel)}">{esc(tel)}</a>')
    if email: linhas.append(f'✉️ <a href="mailto:{esc(email)}">{esc(email)}</a>')
    if not linhas: return '<p class="muted">Contato individual não disponível nesta versão — veja no perfil oficial.</p>'
    return '<p class="contato-vereador">'+' · '.join(linhas)+'</p>'

def em_box(vid):
    e=em_v(vid); fonte_url=EM.get("meta",{}).get("fonte","https://www.riopreto.sp.gov.br/transparencia/receitas-e-repasses/emendas-parlamentares")
    if not e.get("n"):
        return (f'<p class="muted">Nenhuma emenda impositiva municipal registrada no período. {fonte("ver no Portal da Transparência",fonte_url)}</p>')
    itens=e.get("itens") or []
    lista=""
    for it in itens:
        sit=f'<span class="em-sit">{esc(it.get("sit",""))}</span>' if it.get("sit") else ""
        lista+=(f'<li class="it"><div class="it-top"><span class="it-tipo">{esc(it.get("ben","—"))}</span><span class="it-data">{esc(it.get("ano",""))}</span></div>'
                f'<div class="it-ass">{esc(it.get("fin",""))}</div>'
                f'<div class="it-aut"><strong>{brl(it.get("val",0))}</strong> {sit}</div></li>')
    detalhe_lista=(f'<details class="grupo-card" style="margin-top:10px"><summary><span class="gc-main"><span class="gc-nome" style="font-size:.98rem">Ver as {e["n"]} emendas (instituição, finalidade e valor)</span></span><span class="gc-cta">abrir ▾</span></summary><ul class="lista-itens" style="padding:12px 15px">{lista}</ul></details>') if lista else \
                  (f'<p class="muted" style="margin-top:8px">Detalhamento por emenda em atualização pelo robô. {fonte("ver no Portal da Transparência",fonte_url)}</p>')
    pago_line=(f' · <strong>{brl(e["pago"])}</strong> já pagos pela Prefeitura' if e.get("pago") else ' · ainda não pagas')
    return (f'<div class="efet-box"><div class="efet-num" style="color:#2d6384;font-size:1.4rem;min-width:auto">{brl0(e["previsto"])}</div>'
            f'<div class="efet-txt"><strong>destinados em {e["n"]} emenda(s) impositiva(s)</strong> <button class="ajuda" data-termo="emendas" aria-label="O que é isso?">?</button>'
            f'<span class="muted">valor indicado ao orçamento{pago_line} · {fonte("fonte: Portal da Transparência",fonte_url)}</span></div></div>{detalhe_lista}')

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
    prows2=""; pres_fonte=FREQM.get("meta",{}).get("fonte","https://www.riopreto.sp.leg.br/ContaPublica/Listar/1267")
    fm=FREQMP.get(str(vid))
    if fm and fm.get("sessoes"):
        PRES_CAP=50
        for s in fm["sessoes"][:PRES_CAP]:
            P={"P":("Presente","sim"),"F":("Ausente","nao"),"J":("Falta justificada","neutro")}.get(s.get("status","F"),("Ausente","nao"))
            prows2+=f'<tr><th scope="row">Sessão de {esc(s.get("data","") or "data não informada")}</th><td><span class="status {P[1]}">{P[0]}</span></td><td></td></tr>'
        if len(fm["sessoes"])>PRES_CAP:
            prows2+=f'<tr><td colspan="3" class="muted">+ {len(fm["sessoes"])-PRES_CAP} sessões anteriores no mandato. {fonte("relatórios mensais oficiais",pres_fonte)}</td></tr>'
    else:
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
  <header class="detalhe-head">{foto_html(vid,nome,lg=True)}
  <div><h2 id="h-{slug}">{esc(nome)}</h2><p class="detalhe-nome">{esc(v["nome_completo"])}</p>
  <div class="chips"><span class="chip chip-part">{esc(part)}</span></div>{mesa_line}</div></header>
  <section class="bloco destaque-freq"><h3>Frequência nas sessões <button class="ajuda" data-termo="sessao" aria-label="O que é sessão?">?</button></h3>{freq_block(vid,grande=True)}</section>
  <section class="bloco"><h3>Contato e perfil oficial</h3>{contato_html(vid)}
  <p>{fonte("ver o perfil oficial de "+nome+" na Câmara",prof)}</p>
  <p class="muted">Contato geral da Câmara: camara@riopreto.sp.leg.br · (17) 3214-7777.</p></section>
  <section class="bloco"><h3>Proposições no mandato ({PERIODO_DADOS})</h3>
  <p class="muted">Números de autoria/coautoria no sistema legislativo (SISCAM). Clique na fonte para conferir a lista completa.</p>
  <table class="tab"><thead><tr><th>Tipo</th><th>Quantidade</th><th>Fonte oficial</th></tr></thead><tbody>{prows}</tbody></table>
  <div class="efet-box"><div class="efet-num">{ef_aprov(vid)}</div>
  <div class="efet-txt"><strong>projetos de lei já aprovados</strong> pela Câmara (viraram ou estão prestes a virar lei) <button class="ajuda" data-termo="aprovados" aria-label="O que é projeto aprovado?">?</button>
  <span class="muted">de {ci(C["pl"],vid)+ci(C["plc"],vid)} projetos apresentados · {fonte("ver os aprovados na fonte",busca_aprov(TIPO_ID["pl"],vid))}</span></div></div></section>
  <section class="bloco"><h3>Presença nas sessões <button class="ajuda" data-termo="sessao" aria-label="O que é sessão?">?</button></h3>
  <p class="muted">{PRES_NOTA}</p>
  <table class="tab"><thead><tr><th>Sessão / chamada</th><th>Situação</th><th>Fonte</th></tr></thead><tbody>{prows2}</tbody></table></section>
  <section class="bloco"><h3>Como votou (votações nominais) <button class="ajuda" data-termo="nominal" aria-label="O que é votação nominal?">?</button></h3>
  <p class="muted">Apenas o registro do voto. Em votações simbólicas o voto individual não é registrado.</p>
  <table class="tab"><thead><tr><th>Matéria</th><th>Voto</th><th>Fonte</th></tr></thead><tbody>{vrows}</tbody></table></section>
  <section class="bloco"><h3>Gastos com viagens oficiais ({PERIODO_DADOS})</h3>
  <div class="efet-box"><div class="efet-num" style="color:var(--red);font-size:1.5rem">R$ {("%.2f"%gv_total(vid)).replace(".",",")}</div>
  <div class="efet-txt"><strong>em {gv_viagens(vid)} viagem(ns)</strong> custeada(s) com dinheiro público <button class="ajuda" data-termo="viagens" aria-label="O que é isso?">?</button>
  <span class="muted">diárias e despesas de deslocamento · {fonte("ver as viagens na fonte",'https://www.riopreto.sp.leg.br/paginas/despesas-de-viagens')}</span></div></div>
  <p class="muted">Verba de gabinete e remuneração de assessores não são publicadas separadamente por vereador; quando a Câmara divulgar, entram aqui.</p></section>
  <section class="bloco"><h3>Emendas impositivas (recursos destinados)</h3>
  <p class="muted">Valor obrigatório do orçamento que o vereador destina a instituições e serviços. A execução (empenho e pagamento) é da Prefeitura.</p>
  {em_box(vid)}</section>
</article>'''

cards_html="\n".join(card(v,i) for i,v in enumerate(VERS))
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
 ("aprovados","O que é um projeto aprovado?","É um Projeto de Lei (ou Projeto de Lei Complementar) de autoria do vereador que já foi aprovado pela Câmara — ou seja, saiu do papel e virou (ou está prestes a virar) lei. Diferente da quantidade de projetos apresentados, aqui conta o que de fato foi adiante. Contamos só os projetos com situação “APROVADO” no sistema da Câmara, no mandato atual."),
 ("emendas","O que é uma emenda impositiva?","É uma fatia do orçamento que cada vereador tem direito de destinar, de forma obrigatória, a instituições (hospitais, entidades sociais, associações) ou a serviços públicos. O vereador indica o valor e o destino; a Prefeitura é obrigada a executar. Aqui mostramos o valor indicado (previsto), a quem foi destinado, para qual finalidade e quanto já foi pago. É uma das formas mais concretas de ver para onde cada vereador direciona dinheiro público."),
 ("viagens","O que são os gastos com viagens?","É quanto de dinheiro público a Câmara pagou em diárias e despesas de deslocamento (transporte, hospedagem) de cada vereador em viagens oficiais — reuniões em São Paulo, Brasília, etc. Somamos o “Total da despesa” de cada viagem publicada no Portal da Transparência da Câmara. Em viagens de grupo, o custo é dividido igualmente entre os participantes. No ranking, gastar menos pontua mais (critério de economia)."),
 ("quantos","Quantos vereadores tem São José do Rio Preto?","A Câmara Municipal de São José do Rio Preto tem 23 vereadores no mandato de 2025 a 2028."),
]
gloss_html="".join(f'<div class="gloss-item"><h3>{esc(q)}</h3><p>{esc(a)}</p></div>' for k,q,a in GLOSS)
gloss_js=json.dumps({k:{"q":q,"a":a} for k,q,a in GLOSS}, ensure_ascii=False)

def item_html(r):
    local=" · ".join([x for x in [r["rua"],r["bairro"]] if x]); local=f'<div class="it-local">📍 {esc(local)}</div>' if local else ""
    sub=f'<span class="it-sub">{esc(r["sub"])}</span>' if r["sub"] else ""
    return (f'<li class="it"><div class="it-top"><span class="it-tipo">{esc(r["tipo"])} {esc(r["n"])}</span><span class="it-data">{esc(r["data"])}</span></div>'
            f'<div class="it-ass">{esc(r["assunto"])}</div>{local}<div class="it-aut">por <strong>{esc(r["autor"])}</strong> {sub}</div></li>')
CAP=60
GRUPO_ICON={"melhorias":"🛠️","cobrancas":"❓","homenagens":"🎖️","leis":"📜","outros":"•••"}
grupos_html='<div class="grupos-grid">'
for k in ["melhorias","cobrancas","homenagens","leis","outros"]:
    regs=POR_GRUPO[k]
    if not regs and k=="outros": continue
    mostra=regs[:CAP]
    itens="".join(item_html(r) for r in mostra) or "<li class='it'>Sem itens nesta amostra.</li>"
    extra=f'<li class="it muted">+ {len(regs)-CAP} outros na amostra — use a busca por rua/bairro acima.</li>' if len(regs)>CAP else ""
    chips=""
    if k=="melhorias":
        ct=Counter(r["sub"] for r in regs if r["sub"] and r["sub"]!="Outros serviços")
        chips="".join(f'<span class="gc-chip">{esc(s)} <b>{n}</b></span>' for s,n in ct.most_common(3))
    chips_html=f'<span class="gc-chips">{chips}</span>' if chips else ""
    grupos_html+=(f'<details class="grupo-card"><summary><span class="gc-icon" aria-hidden="true">{GRUPO_ICON[k]}</span>'
      f'<span class="gc-main"><span class="gc-nome">{esc(GRUPOS[k])}</span>'
      f'<span class="gc-cont">{len(regs)} na amostra</span>{chips_html}</span>'
      f'<span class="gc-cta">abrir ▾</span></summary><ul class="lista-itens">{itens}{extra}</ul></details>')
grupos_html+='</div>'
def periodo(items):
    ds=sorted(set(i["data"] for i in items), key=lambda x:(x[6:],x[3:5],x[0:2]))
    return ds[0] if len(ds)==1 else f"{ds[0]} a {ds[-1]}"
def dkey_d(d):
    try: p=d.split("/"); return (p[2],p[1],p[0])
    except: return ("0","0","0")
# --- Bairros com mais solicitações (contagem por bairro, sem alegar que é o mesmo problema) ---
bairro_items={}
for r in REGS:
    if r["bairro"]: bairro_items.setdefault(r["bairro"],[]).append(r)
bairros_rank=sorted(bairro_items.items(), key=lambda kv:(-len(kv[1]), kv[0]))
bairro_cards=""
for loc,items in bairros_rank[:15]:
    items2=sorted(items, key=lambda i:dkey_d(i["data"]), reverse=True)
    nver=len(set(i["autor"] for i in items))
    locd=re.sub(r'^(Bairro|Res\.?|Residencial)\s+','',loc).strip()
    top_sub=Counter(i["sub"] for i in items if i["sub"] and i["sub"]!="Outros serviços").most_common(1)
    tag=f'<span class="rep-tag">{esc(top_sub[0][0])}</span>' if top_sub else ""
    bairro_cards+=(f'<details class="rep"><summary><span class="rep-n">{len(items)}<small>×</small></span>'
       f'<div class="rep-main"><span class="rep-loc">{esc(locd)}</span>'
       f'<div class="rep-meta2">{tag}{" · " if tag else ""}{nver} vereador(es) · {esc(periodo(items))}</div></div>'
       f'<span class="rep-cta">ver →</span></summary>'
       f'<ul class="lista-itens">{"".join(item_html(i) for i in items2)}</ul></details>')
if not bairro_cards: bairro_cards='<p class="muted">Sem bairros identificados na amostra atual.</p>'
# --- Solicitações recentes (pedidos de melhoria/cobrança, mais novos primeiro) ---
recs_tab=sorted([r for r in REGS if r["grupo"] in ("melhorias","cobrancas")], key=lambda i:dkey_d(i["data"]), reverse=True)[:30]
recentes_cards="".join(item_html(r) for r in recs_tab) or '<li class="it muted">Sem solicitações recentes na amostra.</li>'
bairros_html=(
 '<div class="tabs" role="tablist">'
 '<button class="tab-btn active" data-tab="t-bairros" role="tab" aria-selected="true">Por bairro</button>'
 '<button class="tab-btn" data-tab="t-recentes" role="tab" aria-selected="false">Solicitações recentes</button>'
 '</div>'
 f'<div class="tab-panel" id="t-bairros" role="tabpanel"><div class="rep-grid">{bairro_cards}</div></div>'
 f'<div class="tab-panel" id="t-recentes" role="tabpanel" hidden><ul class="lista-itens">{recentes_cards}</ul></div>')

# totais para os tiles do topo
T_IND=sum(ci(C["ind"],v["id"]) for v in VERS)
T_REQ=sum(ci(C["req"],v["id"]) for v in VERS)
T_MOC=sum(ci(C["moc"],v["id"]) for v in VERS)
T_LEIS=sum(ci(C["pl"],v["id"])+ci(C["plc"],v["id"]) for v in VERS)
T_PROPS=T_IND+T_REQ+T_MOC+T_LEIS
def fmt(n): return f"{n:,}".replace(",",".")
tiles_html=(f'<div class="tiles">'
 f'<div class="tile t-navy"><b>{fmt(T_IND)}</b><span>pedidos nos bairros (indicações)</span></div>'
 f'<div class="tile t-blue"><b>{fmt(T_REQ)}</b><span>requerimentos</span></div>'
 f'<div class="tile t-red"><b>{fmt(T_MOC)}</b><span>homenagens (moções)</span></div>'
 f'<div class="tile t-green"><b>{fmt(T_LEIS)}</b><span>projetos de lei</span></div></div>')

# contador de salário (estimativa; subsídio confirmado na fonte oficial da Câmara)
SAL_VALOR=16500.0; SAL_N=23; SAL_FONTE="https://www.riopreto.sp.leg.br/Arquivos/ContasPublicas/1790793899365-991.pdf"
salario_html=(f'<div class="salario-card" data-mensal="{int(SAL_N*SAL_VALOR)}">'
 f'<p class="sal-label">Salário pago aos {SAL_N} vereadores desde a posse</p>'
 f'<p class="sal-valor" id="sal-valor">R$ —</p>'
 f'<p class="sal-sub">e subindo agora · estimativa de {SAL_N} subsídios de R$ 16.500/mês desde 1º de janeiro de 2025 · '
 f'<a href="{SAL_FONTE}" target="_blank" rel="noopener">fonte oficial ↗</a></p></div>')

# ===== dimensões comparáveis (índice) =====
def participacao(vid):
    cast=aus=0
    for m in VOT:
        for voto,ids in m["votos"].items():
            if vid in ids:
                if voto in ("A favor","Contra","Abstenção"): cast+=1
                elif voto=="Ausente": aus+=1
                break
    tot=cast+aus
    return (round(100*cast/tot) if tot else 0, cast, tot)
maxpl = max((ci(C["pl"],v["id"])+ci(C["plc"],v["id"]) for v in VERS), default=1) or 1
maxef = max((ef_aprov(v["id"]) for v in VERS), default=1) or 1
maxgv = max((gv_total(v["id"]) for v in VERS), default=0) or 0   # maior gasto com viagens
# Articulação institucional: ocupar cargo na Mesa Diretora (peso pequeno)
ARTIC_PTS={"presidente":100,"vice-presidente":70,"1º secretário":55,"1 secretario":55,
           "2º secretário":50,"3º secretário":45}
def artic_pts(mesa): return ARTIC_PTS.get(nrm(mesa),0) if mesa else 0
# Pesos: Efetividade 25 · Presença 20 · Participação 20 · Produção 20 · Economia 10 · Articulação 5 = 100
VM=[]
for v in VERS:
    vid=v["id"]; f=freq(vid); pl=ci(C["pl"],vid)+ci(C["plc"],vid)
    partic,cast,totv = participacao(vid)
    presenca = f["pct"] if f else 0
    aprov = ef_aprov(vid)
    efet = round(100*aprov/maxef)          # efetividade: projetos aprovados / maior
    producao = round(100*pl/maxpl)         # produção: projetos de lei / maior
    artic = artic_pts(v["mesa"])           # articulação institucional (Mesa)
    gasto = gv_total(vid)                   # gastos com viagens oficiais (R$)
    econ = round(100*(1 - gasto/maxgv)) if maxgv else 100   # economia: menos gasto = mais pontos
    indice = round(0.25*efet + 0.20*presenca + 0.20*partic + 0.20*producao + 0.10*econ + 0.05*artic)
    VM.append({"id":vid,"slug":v["slug"],"nome":v["nome"],"partido":v["partido"],"mesa":v["mesa"],
               "foto":FOTO.format(id=vid),"ini":iniciais(v["nome"]),
               "presenca":presenca,"presx":f["pres"] if f else 0,"prest":f["tot"] if f else 0,
               "partic":partic,"cast":cast,"votost":totv,
               "pl":pl,"ind":ci(C["ind"],vid),"req":ci(C["req"],vid),"moc":ci(C["moc"],vid),
               "aprov":aprov,"efet":efet,"producao":producao,"artic":artic,
               "gasto":gasto,"viagens":gv_viagens(vid),"econ":econ,
               "inic":producao,"indice":indice})
VM_JS=json.dumps(VM, ensure_ascii=False)
rank_ordenado=sorted(VM, key=lambda x:-x["indice"])
def mini_foto(m):
    return (f'<span class="foto foto-sm"><img loading="lazy" src="{m["foto"]}" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"><span class="foto-ini" style="display:none">{esc(m["ini"])}</span></span>')
rank_rows="".join(
  f'<tr data-indice="{m["indice"]}" data-presenca="{m["presenca"]}" data-partic="{m["partic"]}" data-pl="{m["pl"]}" data-aprov="{m["aprov"]}" data-econ="{m["econ"]}" data-nome="{esc(m["nome"])}">'
  f'<td class="r-pos">{i+1}</td><td class="r-nome"><a href="#v-{m["slug"]}">{mini_foto(m)}<span>{esc(m["nome"])}<small>{esc(m["partido"])}</small></span></a></td>'
  f'<td class="r-strong">{m["aprov"]}</td><td>{m["presenca"]}%</td><td>{m["partic"]}%</td><td>{m["pl"]}</td>'
  f'<td class="r-gasto">R$ {("{:,.0f}".format(m["gasto"])).replace(",",".")}</td><td class="r-indice">{m["indice"]}</td></tr>'
  for i,m in enumerate(rank_ordenado))
ranking_html=(f'<div class="rank-head"><label for="rank-sort">Ordenar por</label>'
 f'<select id="rank-sort"><option value="indice">Índice geral</option><option value="aprov">Projetos aprovados</option>'
 f'<option value="presenca">Presença</option>'
 f'<option value="partic">Participação em votações</option><option value="pl">Projetos de lei</option>'
 f'<option value="econ">Mais econômico (viagens)</option>'
 f'<option value="nome">Nome (A–Z)</option></select></div>'
 f'<div class="tab-wrap"><table class="rank-tab"><thead><tr><th>#</th><th>Vereador</th>'
 f'<th>Projetos aprovados <button class="ajuda" data-termo="aprovados" aria-label="O que é projeto aprovado?">?</button></th>'
 f'<th>Presença</th><th>Participação</th><th>Projetos de lei</th>'
 f'<th>Gastos c/ viagens <button class="ajuda" data-termo="viagens" aria-label="O que é isso?">?</button></th>'
 f'<th>Índice</th></tr></thead>'
 f'<tbody id="rank-body">{rank_rows}</tbody></table></div>')
cmp_opts="".join(f'<option value="{v["id"]}">{esc(v["nome"])} ({esc(v["partido"])})</option>' for v in VERS)
comparar_html=(f'<div class="cmp-pick">'
 f'<select class="cmp-sel" data-i="0" aria-label="Primeiro vereador"><option value="">Escolha um vereador…</option>{cmp_opts}</select>'
 f'<select class="cmp-sel" data-i="1" aria-label="Segundo vereador"><option value="">Escolha para comparar…</option>{cmp_opts}</select>'
 f'<select class="cmp-sel" data-i="2" aria-label="Terceiro vereador (opcional)"><option value="">(opcional) um terceiro…</option>{cmp_opts}</select>'
 f'</div><div id="cmp-result" class="cmp-result"><p class="muted">Escolha ao menos dois vereadores acima para ver lado a lado.</p></div>')
BUSCA_CAP=6000
REGS_BUSCA=sorted(REGS, key=lambda r:dkey_d(r["data"]), reverse=True)[:BUSCA_CAP]
busca_data=json.dumps([{"g":GRUPOS[r["grupo"]],"t":r["tipo"],"n":r["n"],"d":r["data"],"a":r["autor"],"s":r["assunto"][:150],"rua":r["rua"],"bairro":r["bairro"],"q":(r["ruaN"]+" "+r["bairroN"]+" "+r["txtN"][:150])} for r in REGS_BUSCA], ensure_ascii=False)

# ===== Painel "A cidade em números" =====
from collections import Counter
def pan_tot(m): return m["pl"]+m["ind"]+m["req"]+m["moc"]
pan_rank=sorted(VM, key=lambda m:-pan_tot(m))
pan_max=pan_tot(pan_rank[0]) if pan_rank else 1
quem_html=""
for m in pan_rank[:6]:
    tt=pan_tot(m); w=round(100*tt/(pan_max or 1))
    quem_html+=(f'<li><a href="#v-{m["slug"]}">{mini_foto(m)}'
      f'<span class="pq-id"><span class="pq-nome">{esc(m["nome"])}</span><small>{esc(m["partido"])}</small></span>'
      f'<span class="pq-barwrap"><span class="pq-bar" style="width:{w}%"></span></span>'
      f'<b class="pq-num">{fmt(tt)}</b></a></li>')
sub_ct=Counter(r["sub"] for r in REGS if r["grupo"]=="melhorias" and r["sub"] and r["sub"]!="Outros serviços")
pede_max=sub_ct.most_common(1)[0][1] if sub_ct else 1
pede_html="".join(f'<li><span class="pp-cat">{esc(k)}</span><span class="pp-barwrap"><span class="pp-bar" style="width:{round(100*n/pede_max)}%"></span></span><b>{fmt(n)}</b></li>' for k,n in sub_ct.most_common(6))
bai_ct=Counter(r["bairro"] for r in REGS if r["bairro"])
bai_max=bai_ct.most_common(1)[0][1] if bai_ct else 1
bairro_html="".join(f'<li><span class="pb-loc">{esc(k)}</span><span class="pp-barwrap"><span class="pb-bar" style="width:{round(100*n/bai_max)}%"></span></span><b>{fmt(n)}</b></li>' for k,n in bai_ct.most_common(6))
# quem mais aprovou projetos (projetos que viraram lei) — contraponto ao volume
apr_rank=sorted(VM, key=lambda m:-m["aprov"])[:6]
apr_max=(apr_rank[0]["aprov"] if apr_rank and apr_rank[0]["aprov"] else 1) or 1
aprov_html="".join(
  f'<li><a href="#v-{m["slug"]}">{mini_foto(m)}'
  f'<span class="pq-id"><span class="pq-nome">{esc(m["nome"])}</span><small>{esc(m["partido"])}</small></span>'
  f'<span class="pq-barwrap"><span class="pq-bar" style="width:{round(100*m["aprov"]/apr_max)}%"></span></span>'
  f'<b class="pq-num">{m["aprov"]}</b></a></li>'
  for m in apr_rank)
def dkey(d):
    try: p=d.split("/"); return (p[2],p[1],p[0])
    except: return ("0","0","0")
recentes=sorted(REGS, key=lambda r:dkey(r["data"]), reverse=True)[:4]
rec_html=""
for r in recentes:
    local=" · ".join([x for x in [r["rua"],r["bairro"]] if x])
    rec_html+=(f'<li class="pr-item"><div class="pr-top"><span class="pr-tipo">{esc(r["tipo"])} {esc(r["n"])}</span>'
      f'<span class="pr-data">{esc(r["data"])}</span></div>'
      f'<div class="pr-ass">{esc(r["assunto"][:150])}</div>'
      f'<div class="pr-aut">por <strong>{esc(r["autor"])}</strong>{(" · 📍 "+esc(local)) if local else ""}</div></li>')
panorama_html=(f'<div class="pan-total"><b>{fmt(T_PROPS)}</b><span>proposituras dos 23 vereadores no mandato ({PERIODO_DADOS})</span></div>'
 f'<div class="pan-cols">'
 f'<div class="pan-col"><h3>Quem mais propôs</h3><p class="pan-base">no mandato inteiro</p><ol class="pan-quem">{quem_html}</ol></div>'
 f'<div class="pan-col"><h3>O que mais pedem</h3><p class="pan-base">na amostra recente de pedidos</p><ul class="pan-pede">{pede_html or "<li class=muted>—</li>"}</ul></div>'
 f'<div class="pan-col"><h3>Quem mais aprovou projetos</h3><p class="pan-base">projetos que viraram lei no mandato</p><ol class="pan-quem">{aprov_html or "<li class=muted>—</li>"}</ol></div>'
 f'</div>'
 f'<div class="pan-rec"><h3>Propostas mais recentes</h3><ul class="pan-reclist">{rec_html}</ul>'
 f'<a class="pan-vermais" href="#trabalho">Ver todas as propostas por tema →</a></div>')

# ===== Emendas (seção) =====
emeta=EM.get("meta",{}); etop=EM.get("top_beneficiarios",[])
emax=(etop[0][1] if etop else 1) or 1
ebars="".join(f'<li><span class="pb-loc">{esc(nome)}</span><span class="pp-barwrap"><span class="pb-bar" style="width:{round(100*val/emax)}%"></span></span><b>{brl0(val)}</b></li>' for nome,val in etop[:8])
em_rank=sorted(VERS, key=lambda v:-(em_v(v["id"]).get("previsto",0)))[:6]
emvmax=(em_v(em_rank[0]["id"]).get("previsto",0) if em_rank else 1) or 1
equem="".join(
  f'<li><a href="#v-{v["slug"]}">{foto_html(v["id"],v["nome"]) if False else mini_foto({"foto":FOTO.format(id=v["id"]),"ini":iniciais(v["nome"])})}'
  f'<span class="pq-id"><span class="pq-nome">{esc(v["nome"])}</span><small>{esc(v["partido"])}</small></span>'
  f'<span class="pq-barwrap"><span class="pq-bar" style="width:{round(100*em_v(v["id"]).get("previsto",0)/emvmax)}%"></span></span>'
  f'<b class="pq-num">{brl0(em_v(v["id"]).get("previsto",0))}</b></a></li>'
  for v in em_rank)
emendas_html=(f'<div class="pan-total"><b>{brl0(emeta.get("total_previsto",0))}</b>'
 f'<span>destinados pelos vereadores em {emeta.get("n","—")} emendas impositivas municipais ({PERIODO_DADOS})'
 f' · {brl0(emeta.get("total_pago",0))} já pagos pela Prefeitura</span></div>'
 f'<div class="pan-cols" style="grid-template-columns:1fr">'
 f'<div class="pan-col"><h3>Quem mais destinou</h3><p class="pan-base">valor previsto no mandato</p><ol class="pan-quem">{equem}</ol></div>'
 f'<div class="pan-col"><h3>Instituições mais beneficiadas</h3><p class="pan-base">por valor destinado</p><ul class="pan-bairro">{ebars}</ul></div>'
 f'</div><p class="muted" style="margin-top:10px">Abra a ficha de cada vereador para ver todas as emendas — instituição, finalidade e valor. {fonte("Fonte: Portal da Transparência da Prefeitura",emeta.get("fonte","#"))}</p>')

# contagens para verificação
tot_props = sum(ci(C[t],v["id"]) for t in C for v in VERS)
verif_html=f'''<div class="met">
<h3>Presença nas sessões</h3>
{("<p>A presença cobre <strong>todas as sessões do mandato</strong> e vem dos relatórios mensais oficiais da Câmara — <em>“Comparecimento dos Vereadores às Sessões”</em> (um PDF por mês). Cada relatório lista, sessão a sessão, se cada vereador esteve Presente ou Ausente; nós somamos tudo. Falta justificada, quando aparece, é contada como ausência.</p>" if PRES_FULL else "<p>A presença vem da chamada registrada em cada sessão no sistema do Legislativo (SISCAM). Há ainda a fonte oficial independente — o relatório mensal <em>“Comparecimento dos Vereadores às Sessões”</em> (PDF da Câmara).</p>")}
<h3>Proposições</h3>
<p>As contagens por vereador vêm da busca oficial de proposituras (mandato {PERIODO_DADOS}). Os textos nos grupos e na busca por rua são a amostra mais recente coletada.</p>
<h3>Como agrupamos</h3>
<p>A mesma regra vale para todos: Moção → Homenagem; Projeto de Lei → Proposta de lei; Indicação/Requerimento são lidos pelo assunto (congratulação/pesar → Homenagens; pedido de informação → Perguntas e cobranças; serviço no bairro → Pedidos de melhoria; o resto → Outros).</p>
<h3>Como calculamos o índice (ranking)</h3>
<p>A ideia é medir várias dimensões comparáveis, não dar uma nota de “bom” ou “ruim”. Cada dimensão vai de 0 a 100 e é calculada só com dado oficial. O índice final é a média ponderada delas:</p>
<p>• <strong>Efetividade</strong> (peso 25%): quantos projetos de lei do vereador foram <em>aprovados</em> pela Câmara, comparado a quem mais aprovou (esse vira 100). É o que de fato virou lei, não só o que foi apresentado.<br>
• <strong>Presença</strong> (peso 20%): % de comparecimento nas sessões com chamada registrada.<br>
• <strong>Participação em votações</strong> (peso 20%): das votações nominais, em quantas o vereador registrou voto (a favor, contra ou abstenção) — ausências contam contra; quando o presidente não vota por função, isso não entra na conta.<br>
• <strong>Produção legislativa</strong> (peso 20%): quantidade de projetos de lei apresentados (os de conteúdo substantivo), comparada a quem mais apresentou.<br>
• <strong>Economia</strong> (peso 10%): gasto com viagens oficiais custeadas com dinheiro público (diárias e deslocamento) no mandato. Aqui a lógica se inverte — <strong>gastar menos pontua mais</strong>. Quem mais gastou pontua 0; quem não teve gasto de viagem pontua 100.<br>
• <strong>Articulação institucional</strong> (peso 5%): ocupar um cargo na Mesa Diretora (Presidência, Vice, Secretarias), responsabilidade de condução dos trabalhos. Quem não está na Mesa pontua 0 aqui — é o fator de menor peso, de propósito.</p>
<p class="muted">De propósito, o índice <strong>não usa o volume de indicações e requerimentos</strong> — eles são apresentados em massa e inchariam a conta sem medir qualidade. A dimensão de economia mede só as viagens, porque é o único gasto publicado por vereador: verba de gabinete e salários de assessores não saem separados por vereador na Câmara. {("A presença agora cobre o mandato inteiro." if PRES_FULL else "A presença ainda cobre poucas sessões.")} Use como ponto de partida, não como veredito, e confira sempre a ficha de cada um.</p>
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
 .replace("__BAIRROS__",bairros_html).replace("__GRUPOS__",grupos_html).replace("__OPTIONS__",options)
 .replace("__CARDS__",cards_html).replace("__GLOSS__",gloss_html).replace("__VERIF__",verif_html)
 .replace("__DETALHES__",detalhes_html).replace("__GLOSSJS__",gloss_js).replace("__BUSCADATA__",busca_data)
 .replace("__NAOCONF__",naoconf_html).replace("__TILES__",tiles_html)
 .replace("__RANKING__",ranking_html).replace("__COMPARAR__",comparar_html).replace("__VMJS__",VM_JS)
 .replace("__PANORAMA__",panorama_html).replace("__EMENDAS__",emendas_html).replace("__SALARIO__",salario_html))
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
