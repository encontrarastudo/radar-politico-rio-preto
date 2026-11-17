# -*- coding: utf-8 -*-
"""Coletor do Radar Político de Rio Preto.
Busca dados oficiais na Câmara (SISCAM), VALIDA e só então grava data/*.json.
Se a coleta vier incompleta ou estranha, sai com código != 0 e NÃO grava nada —
assim o site continua na última versão boa. Uso: python tools/collector.py"""
import os, re, sys, json, time, datetime, unicodedata
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SIS  = "https://riopreto.siscam.com.br"
UA   = {"User-Agent": "RadarPoliticoRioPreto/1.0 (+projeto cidadao de transparencia; contato via GitHub encontrarastudo)"}
TIMEOUT = 30
PAUSA = 0.4   # cortesia entre requisições

S = requests.Session(); S.headers.update(UA)

def get(url, tries=3):
    last=None
    for _ in range(tries):
        try:
            r = S.get(url, timeout=TIMEOUT)
            if r.status_code == 200: return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(1.2)
    raise RuntimeError(f"Falha ao buscar {url}: {last}")

def texto(html):
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" "))

def nrm(s):
    s = unicodedata.normalize("NFD", s or "")
    return re.sub(r"\s+"," ", "".join(c for c in s if unicodedata.category(c)!="Mn").lower()).strip()

# ---- mapeamento id -> nome em caixa alta (como aparece nas atas do SISCAM) ----
NOME_UP = {27253:"ABNER JOAS TOFANELLI",27258:"ALEX SANDRO DE CARVALHO",27250:"ALEXANDRE MONTENEGRO",
 19428:"ANDERSON BRANCO DA SILVA",23565:"BRUNO MARINHO",23566:"BRUNO MOURA",71:"CELSO LUIZ DE OLIVEIRA",
 27249:"FELIPE ALCALÁ DE ASSIS",73:"FRANCISCO SAVIO RUEL JUNIOR",19430:"JEAN DORNELAS",46:"JOAO PAULO RILLO",
 27252:"JONATHAN SANTOS",53:"JORGE MENEZES SILVA",23568:"JULIO DONIZETE",27256:"KLEBINHO KIZUMBA",
 27257:"LUCIANO DE OLIVEIRA JULIÃO",27251:"MÁRCIA CALDAS",23569:"ODÉLIO CHAVES",24556:"PAULO ROBERTO AMBRÓSIO",
 15231:"PEDRO ROBERTO GOMES",77:"RENATO PUPO DE PAULA",23571:"ROSSINI DINIZ",27255:"PROFESSOR TADEU"}
NORM2ID = {nrm(v):k for k,v in NOME_UP.items()}
IDS = list(NOME_UP.keys())
TIPOS = {"pl":"129","plc":"130","req":"134","ind":"135","moc":"136"}

def nomes_para_ids(bloco):
    """Extrai ids a partir de uma lista de nomes separados por vírgula."""
    ids=[]
    for parte in bloco.split(","):
        key = nrm(parte)
        for nn,i in NORM2ID.items():
            if nn in key or key in nn:
                if i not in ids: ids.append(i); break
    return sorted(ids)

# ============ 1) CONTAGENS por vereador/tipo (mandato 2025-2026) ============
def url_count(tipo, aid):
    return (f"{SIS}/Documentos/Pesquisa?Pesquisa=Avancada&id=78&pagina=1&Modulo=8&Documento={tipo}"
            f"&Numeracao=Documento&AnoInicial=2025&AnoFinal=2026&Situacao=0&Classificacao=0"
            f"&TipoAutor=Todos&AutoriaId={aid}&Iniciativa=Nenhum&NoTexto=false")
def parse_count(html):
    m = re.search(r"([\d.]+)\s*registro\(s\)\s*encontrado", html, re.I)
    return int(m.group(1).replace(".","")) if m else 0

def coletar_contagens():
    out = {k:{} for k in TIPOS}
    for k,code in TIPOS.items():
        for aid in IDS:
            out[k][str(aid)] = parse_count(get(url_count(code, aid)))
            time.sleep(PAUSA)
        print(f"  contagens {k}: ok ({sum(out[k].values())} no total)")
    return out

# ============ 2) SESSÕES: presença + votações nominais ============
def lista_sessoes():
    html = get(f"{SIS}/sessoes")
    soup = BeautifulSoup(html, "html.parser")
    out=[]
    for a in soup.find_all("a", href=re.compile(r"/Sessoes/Sessao/\d+")):
        sid = int(re.search(r"/Sessao/(\d+)", a["href"]).group(1))
        tr = a.find_parent("tr"); data=""
        if tr:
            m=re.search(r"\d{2}/\d{2}/\d{4}", tr.get_text(" "))
            if m: data=m.group(0)
        titulo=a.get_text(" ").strip()
        if sid not in [x[0] for x in out]: out.append((sid,titulo,data))
    return out

def parse_sessao(sid):
    t = texto(get(f"{SIS}/Sessoes/Sessao/{sid}"))
    titm = re.search(r"(\d+ª\s+Sessão\s+[A-Za-zÁ-úÀ-ÿ]+(?:\s+[A-Za-zÁ-úÀ-ÿ]+)?\s+de\s+\d{4})", t)
    titulo = re.sub(r"\s+"," ", titm.group(1)).strip() if titm else f"Sessão {sid}"
    dm = re.search(r"Data:\s*(\d{2}/\d{2}/\d{4})", t)
    data = dm.group(1) if dm else ""
    if "Frequências" not in t and "frequencias" not in nrm(t): return titulo, data, None, []
    # presença: cada "Chamada X - HH:MM" seguida de Presentes (n) - ... / Ausentes (n) - ...
    chamadas=[]
    for m in re.finditer(r"(Chamada[^-\n]*?-\s*\d{1,2}:\d{2})(.*?)(?=Chamada[^-\n]*?-\s*\d{1,2}:\d{2}|Votações|Voltar|$)", t):
        bloco=m.group(2); nomech=m.group(1).strip()
        pm=re.search(r"Presentes\s*\(\d+\)\s*-\s*(.+?)(?=Ausentes\s*\(|Chamada|Votações|$)", bloco)
        pres = nomes_para_ids(pm.group(1)) if pm else []
        if pres: chamadas.append({"nome":nomech, "presentes":pres})
    # votações nominais
    votos=[]
    for mv in re.finditer(r"(Projeto de Lei Complementar|Projeto de Lei|Emenda[^N]*?|Requerimento|Moção)\s*Nº\s*([\d.]+/\d{4})(.*?)(?=(?:Projeto de Lei|Emenda|Requerimento|Moção)\s*Nº|Voltar|$)", t):
        corpo=mv.group(3)
        if "Nominal" not in corpo: continue
        autoria=(re.search(r"Autoria:\s*(.+?)\s*(?:Assunto:|Quórum:)", corpo) or [None,""])[1]
        assunto=(re.search(r"Assunto:\s*(.+?)\s*(?:Quórum:|Votação:)", corpo) or [None,""])[1]
        vd={}
        for voto in ["A favor","Contra","Abstenção","Ausente","Não vota"]:
            vm=re.search(re.escape(voto)+r"\s*\(\d+\)\s*-\s*(.+?)(?=A favor|Contra|Abstenção|Ausente|Não vota|Resultado:|$)", corpo)
            if vm: vd[voto]=nomes_para_ids(vm.group(1))
        if vd:
            votos.append({"sid":sid,"materia":f"{mv.group(1)} nº {mv.group(2)}",
                          "assunto":assunto.strip()[:220],"autoria":autoria.strip(),"votos":vd})
    return titulo, data, chamadas, votos

def coletar_sessoes(limite=55):
    # começa pela lista recente e caminha para trás pelos ids, cobrindo o ano
    base = lista_sessoes(); ids=[x[0] for x in base]
    if ids:
        mx=max(ids)
        for sid in range(mx, mx-limite, -1):
            if sid not in ids: ids.append(sid)
    ids = sorted(set(ids), reverse=True)[:limite]
    presenca=[]; votacoes=[]
    for sid in ids:
        try:
            titulo,data,chamadas,votos = parse_sessao(sid)
        except Exception:
            continue
        # apenas mandato atual (2025+)
        ano = data.split("/")[-1] if data else ""
        if ano and ano < "2025": continue
        if chamadas:
            presenca.append({"sid":sid,"titulo":titulo,"data":data,"chamadas":chamadas})
        for v in votos:
            votacoes.append({"sid":sid,"sessao":titulo,"data":data,"materia":v["materia"],
                             "assunto":v["assunto"],"votos":v["votos"]})
        time.sleep(PAUSA)
    # ordena por data (mais recente primeiro)
    def chave(s):
        try: d=s["data"].split("/"); return (d[2],d[1],d[0])
        except: return ("0","0","0")
    presenca.sort(key=chave, reverse=True)
    print(f"  sessões com presença: {len(presenca)} | votações nominais: {len(votacoes)}")
    return presenca, votacoes

# ============ 3) PROPOSTAS (amostra recente: últimos 45 dias) ============
def parse_records(html, label):
    t = texto(html); out=[]
    re_g = re.compile(r"(Indicação|Requerimento|Moção|Projeto de Lei Complementar|Projeto de Lei|Veto|Emenda[^N]*?)\s*Nº\s*([\d.]+/\d{4})"
                      r"[\s\S]*?Data:\s*([\d/]+)[\s\S]*?Autoria:\s*([\s\S]+?)\s*Assunto:\s*([\s\S]+?)"
                      r"(?=(?:Indicação|Requerimento|Moção|Projeto de Lei|Veto|Emenda)\s*Nº|\d[\d.]*\s*registro\(s\)|$)")
    for m in re_g.finditer(t):
        out.append([m.group(1).strip(), m.group(2), m.group(3), m.group(4).strip()[:80], re.sub(r"\s+"," ",m.group(5)).strip()[:320]])
    return out

def coletar_propostas(dias=45):
    hoje = datetime.date.today()
    ini = (hoje - datetime.timedelta(days=dias)).strftime("%d/%m/%Y")
    fim = hoje.strftime("%d/%m/%Y")
    recs=[]; seen=set()
    for k,code in TIPOS.items():
        pagina=1
        while pagina<=40:
            url=(f"{SIS}/Documentos/Pesquisa?Pesquisa=Avancada&id=78&pagina={pagina}&Modulo=8&Documento={code}"
                 f"&Numeracao=Documento&DataInicial={ini}&DataFinal={fim}&Situacao=0&Classificacao=0"
                 f"&TipoAutor=Todos&AutoriaId=0&Iniciativa=Nenhum&NoTexto=false")
            page=get(url); rr=parse_records(page, k)
            if not rr: break
            novos=0
            for r in rr:
                key=r[0]+r[1]
                if key not in seen: seen.add(key); recs.append(r); novos+=1
            if novos==0: break
            pagina+=1; time.sleep(PAUSA)
    print(f"  proposituras na amostra ({ini} a {fim}): {len(recs)}")
    return recs

# ============ 4) CONTATOS (telefone/e-mail oficial por vereador) ============
def coletar_contatos():
    """Best-effort: se um perfil falhar, segue sem ele (contato é complementar)."""
    out={}
    for aid in IDS:
        email=""; tel=""
        try:
            t = texto(get(f"https://www.riopreto.sp.leg.br/Consulta/vereadores/Vereador/{aid}"))
            emails = re.findall(r"[\w.\-]+@riopreto\.sp\.leg\.br", t)
            for e in emails:
                if not e.lower().startswith("camara@"): email=e; break
            tm = re.search(r"(?:\((\d{2})\)\s*)?(3\d{3}-\d{4})", t)
            if tm: tel = (f"({tm.group(1)}) " if tm.group(1) else "(17) ") + tm.group(2)
        except Exception as ex:
            print(f"  contato {aid}: erro ({ex})")
        out[str(aid)] = {"email":email, "telefone":tel}
        time.sleep(PAUSA)
    tem = sum(1 for v in out.values() if v["email"] or v["telefone"])
    print(f"  contatos com e-mail/telefone: {tem}/23")
    return out

# ============ 5) EFETIVIDADE (projetos aprovados: PL+PLC com Situação 515) ============
def url_aprovados(code, aid):
    return (f"{SIS}/Documentos/Pesquisa?Pesquisa=Avancada&id=78&pagina=1&Modulo=8&Documento={code}"
            f"&Numeracao=Documento&AnoInicial=2025&AnoFinal=2026&Situacao=515&Classificacao=0"
            f"&TipoAutor=Todos&AutoriaId={aid}&Iniciativa=Nenhum&NoTexto=false")

def coletar_efetividade():
    """Projetos de Lei (129) e PL Complementar (130) APROVADOS (Situação 515),
    por vereador, mandato 2025-2026. Complementar ao índice (não bloqueia o gate)."""
    out={}
    for aid in IDS:
        try:
            pl  = parse_count(get(url_aprovados("129", aid))); time.sleep(PAUSA)
            plc = parse_count(get(url_aprovados("130", aid))); time.sleep(PAUSA)
            out[str(aid)] = {"pl":pl, "plc":plc, "aprovados":pl+plc}
        except Exception as ex:
            print(f"  efetividade {aid}: erro ({ex})")
    print(f"  efetividade (vereadores com dado): {len(out)}/23")
    return out

# ============ 6) GASTOS COM VIAGENS (despesas de viagem por vereador) ============
PORTAL = "https://www.riopreto.sp.leg.br"
# tokens distintivos -> id (nome de exibição oficial de cada vereador)
VIAG_KEYS = [("abner",27253),("alex de carvalho",27258),("alexandre montenegro",27250),
 ("anderson branco",19428),("bruno marinho",23565),("bruno moura",23566),("celso peixao",71),
 ("celso luiz",71),("felipe alcala",27249),("francisco junior",73),("francisco savio",73),
 ("jean dornelas",19430),("joao paulo rillo",46),("jonathan",27252),("jorge menezes",53),
 ("julio donizete",23568),("klebinho",27256),("luciano juliao",27257),("luciano de oliveira",27257),
 ("marcia caldas",27251),("odelio",23569),("paulera",24556),("paulo roberto ambrosio",24556),
 ("pedro roberto",15231),("renato pupo",77),("rossini",23571),("tadeu",27255)]
def viag_match(frag):
    f = nrm(frag)
    for tok,i in VIAG_KEYS:
        if tok in f: return i
    return None

def coletar_gastos_viagens(anos=("2025","2026")):
    """Soma o 'Total da despesa' das viagens oficiais por vereador solicitante.
    Viagem de grupo: custo dividido igualmente entre participantes. Suplentes/ex e
    servidores não entram. Complementar (não bloqueia o gate)."""
    por = {}; nviag = {}; total_viag = 0; sem_valor = 0
    rec = re.compile(r"Total da despesa[\s\S]{0,40}?R\$\s*([\d.]+,\d{2})", re.I)
    for ano in anos:
        try:
            html_ = get(f"{PORTAL}/paginas/despesas-de-viagens-{ano}")
        except Exception as ex:
            print(f"  viagens {ano}: lista falhou ({ex})"); continue
        soup = BeautifulSoup(html_, "html.parser")
        for tr in soup.find_all("tr"):
            a = tr.find("a", href=re.compile(r"viagem-"))
            if not a: continue
            tds = tr.find_all("td")
            sol = tds[1].get_text(" ").strip() if len(tds) > 1 else ""
            slug = a.get("href","").strip()
            if re.match(r"^(Contador|Diretor|Comiss|Assessor|Procurador|Secret)", sol, re.I): continue
            try:
                det = get(f"{PORTAL}/paginas/{slug}"); time.sleep(PAUSA)
            except Exception: continue
            total_viag += 1
            m = rec.search(det); valor = float(m.group(1).replace(".","").replace(",",".")) if m else 0.0
            if not m: sem_valor += 1
            corpo = re.sub(r"^Vereadores?:?\s*", "", sol, flags=re.I)
            frags = [x.strip() for x in re.split(r",| e ", corpo) if x.strip()]
            n = len(frags) or 1; per = valor/n
            for fr in frags:
                i = viag_match(fr)
                if i is None: continue
                por[i] = round(por.get(i,0.0)+per, 2); nviag[i] = nviag.get(i,0)+1
    if not por: return {}
    out = {"meta":{"periodo":"-".join(anos),"viagens_total":total_viag,"viagens_sem_valor_publicado":sem_valor,
                    "fonte":f"{PORTAL}/paginas/despesas-de-viagens"},
           "por_vereador":{}}
    for aid in IDS:
        out["por_vereador"][str(aid)] = {"total":por.get(aid,0.0), "viagens":nviag.get(aid,0)}
    print(f"  gastos com viagens: {total_viag} viagens, {len([1 for v in out['por_vereador'].values() if v['total']>0])} vereadores com gasto")
    return out

# ============ 7) EMENDAS PARLAMENTARES IMPOSITIVAS (municipais, por vereador) ============
NOVOPAINEL = "https://novopainel.riopreto.sp.gov.br"
EMENDAS_API = NOVOPAINEL + "/api/slugify/slugs/page/emendas-impositivas?publicationState=preview&populate=tabs.fileItem.files"
EMENDAS_PORTAL = "https://www.riopreto.sp.gov.br/transparencia/receitas-e-repasses/emendas-parlamentares"
def brl(s):
    s = (s or "").strip().replace("R$","").replace(".","").replace(" ","").replace(",",".")
    s = re.sub(r"[^\d.\-]", "", s)
    try: return float(s)
    except Exception: return 0.0

def coletar_emendas():
    """Emendas impositivas municipais (autoria dos vereadores) do Portal da Transparência
    da Prefeitura, via CSV oficial. Por vereador: nº, previsto, pago e itens (beneficiário,
    finalidade, valor, situação, ano). Complementar (não bloqueia o gate)."""
    import csv, io
    # 1) descobre o CSV atual
    csv_url = f"{NOVOPAINEL}/uploads/EMENDAS_PARLAMENTARES_ATUALIZADO_PORTAL_Todas_Emendas_6_50feede8ee.csv"
    try:
        api = get(EMENDAS_API)
        m = re.search(r"/uploads/[^\"'\\]+\.csv", api)
        if m: csv_url = NOVOPAINEL + m.group(0)
    except Exception as ex:
        print(f"  emendas: API falhou, usando CSV conhecido ({ex})")
    raw = get(csv_url)
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows: return {}
    H = rows[0]
    def col(name):
        for i,h in enumerate(H):
            if nrm(h)==nrm(name): return i
        return -1
    oi=col("Origem"); ai=col("Autoria"); ci=col("Valor Custeio (Previsto)"); ii=col("Valor Investimento (Previsto)")
    pi=col("Valor Pago"); bi=col("Beneficiário"); fi=col("OBJETIVO/FINALIDADE"); obj=col("OBJETO")
    si=col("Situação"); yi=col("Ano da indicação")
    def mid(autoria):
        key=nrm(autoria)
        for nn,i in NORM2ID.items():
            if nn in key or key in nn: return i
        return None
    por={}; ben_tot={}; n_tot=0; prev_tot=0.0; pago_tot=0.0
    for r in rows[1:]:
        if len(r)<=max(oi,ai,ci,ii): continue
        if nrm(r[oi])!="municipal": continue
        i = mid(r[ai])
        if i is None: continue
        val = brl(r[ci])+brl(r[ii]); pago = brl(r[pi]) if pi>=0 else 0.0
        ben = (r[bi].strip() if bi>=0 else "")
        fin = (r[fi].strip() if fi>=0 else "") or (r[obj].strip() if obj>=0 else "")
        sit = (r[si].strip() if si>=0 else "")
        ano = (r[yi].strip() if yi>=0 else "")
        d=por.setdefault(i,{"n":0,"previsto":0.0,"pago":0.0,"itens":[]})
        d["n"]+=1; d["previsto"]=round(d["previsto"]+val,2); d["pago"]=round(d["pago"]+pago,2)
        d["itens"].append({"ano":ano,"ben":ben[:90],"fin":fin[:170],"val":round(val,2),"sit":sit[:70]})
        n_tot+=1; prev_tot+=val; pago_tot+=pago
        if ben and ben!="-": ben_tot[ben]=round(ben_tot.get(ben,0.0)+val,2)
    if not por: return {}
    for d in por.values():
        d["itens"].sort(key=lambda x:-x["val"])
    top=sorted(ben_tot.items(), key=lambda kv:-kv[1])[:10]
    out={"meta":{"n":n_tot,"total_previsto":round(prev_tot,2),"total_pago":round(pago_tot,2),
                 "n_beneficiarios":len(ben_tot),"fonte":EMENDAS_PORTAL},
         "top_beneficiarios":[[k,v] for k,v in top],
         "por_vereador":{str(aid):por.get(aid,{"n":0,"previsto":0.0,"pago":0.0,"itens":[]}) for aid in IDS}}
    print(f"  emendas municipais: {n_tot} de {len([1 for v in por.values() if v['n']>0])} vereadores, R$ {prev_tot:,.0f} previstos")
    return out

# ============ VALIDAÇÃO (o gate) ============
def carrega_anterior(nome):
    try: return json.load(open(os.path.join(DATA,nome),encoding="utf-8"))
    except: return None

def valida(contagens, presenca, votacoes, propostas, vereadores):
    erros=[]
    if not vereadores or len(vereadores)!=23: erros.append(f"vereadores != 23 ({len(vereadores) if vereadores else 0})")
    for k in TIPOS:
        d=contagens.get(k,{})
        if len(d)!=23: erros.append(f"contagem '{k}' não tem 23 vereadores ({len(d)})")
        if any((not isinstance(x,int)) or x<0 for x in d.values()): erros.append(f"contagem '{k}' com valor inválido")
    total=sum(sum(contagens.get(k,{}).values()) for k in TIPOS)
    if total < 5000: erros.append(f"total de proposituras suspeito (muito baixo): {total}")
    ant=carrega_anterior("contagens.json")
    if ant:
        tant=sum(sum(ant.get(k,{}).values()) for k in TIPOS)
        if tant>0 and total < 0.5*tant: erros.append(f"total despencou vs versão anterior ({total} < 50% de {tant}) — coleta provavelmente incompleta")
        if tant>0 and total > 5*tant: erros.append(f"total explodiu vs versão anterior ({total} > 5x {tant}) — coleta suspeita")
    if not presenca: erros.append("nenhuma sessão com presença coletada")
    else:
        ok=any(10<=len(ch["presentes"])<=23 for s in presenca for ch in s["chamadas"])
        if not ok: erros.append("nenhuma chamada com número de presentes plausível (10 a 23)")
    if len(propostas) < 30: erros.append(f"amostra de proposituras muito pequena: {len(propostas)}")
    if any((not r[3]) or (not r[4]) for r in propostas): erros.append("proposta sem autor ou sem assunto")
    return erros

def main():
    print("== Coleta Radar Político de Rio Preto ==")
    vereadores = carrega_anterior("vereadores.json")   # lista estática (comitada)
    print("1/4 contagens..."); contagens = coletar_contagens()
    print("2/4 sessões...");   presenca, votacoes = coletar_sessoes()
    print("3/5 proposituras..."); propostas = coletar_propostas()
    print("4/6 contatos...")
    try: contatos = coletar_contatos()
    except Exception as ex:
        print("  coleta de contatos falhou inteira:", ex); contatos = carrega_anterior("contatos.json") or {}
    print("5/6 efetividade...")
    try: efetividade = coletar_efetividade()
    except Exception as ex:
        print("  coleta de efetividade falhou inteira:", ex); efetividade = {}
    # efetividade é complementar: se vier incompleta, mantém a última versão boa
    ant_ef = carrega_anterior("efetividade.json") or {}
    if len(efetividade) < 23 and len(ant_ef) >= len(efetividade):
        print(f"  efetividade incompleta ({len(efetividade)}/23) — mantendo versão anterior ({len(ant_ef)})")
        efetividade = ant_ef
    print("6/7 gastos com viagens...")
    try: gastos = coletar_gastos_viagens()
    except Exception as ex:
        print("  coleta de gastos com viagens falhou inteira:", ex); gastos = {}
    ant_gv = carrega_anterior("gastos_viagens.json") or {}
    if (not gastos or len(gastos.get("por_vereador",{}))<23) and ant_gv:
        print("  gastos com viagens incompletos — mantendo versão anterior")
        gastos = ant_gv
    print("7/8 emendas...")
    try: emendas = coletar_emendas()
    except Exception as ex:
        print("  coleta de emendas falhou inteira:", ex); emendas = {}
    ant_em = carrega_anterior("emendas.json") or {}
    if (not emendas or len(emendas.get("por_vereador",{}))<23) and ant_em:
        print("  emendas incompletas — mantendo versão anterior")
        emendas = ant_em
    print("8/8 validando...")
    erros = valida(contagens, presenca, votacoes, propostas, vereadores)
    if erros:
        print("\n❌ VALIDAÇÃO FALHOU — NADA será publicado. Motivos:")
        for e in erros: print("   -", e)
        sys.exit(1)
    # grava (só chega aqui se válido)
    os.makedirs(DATA, exist_ok=True)
    def dump(nome,obj): json.dump(obj, open(os.path.join(DATA,nome),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    dump("contagens.json", contagens)
    dump("presenca.json", presenca)
    dump("votacoes.json", votacoes)
    dump("propostas.json", propostas)
    if contatos: dump("contatos.json", contatos)
    if efetividade: dump("efetividade.json", efetividade)
    if gastos: dump("gastos_viagens.json", gastos)
    if emendas: dump("emendas.json", emendas)
    dump("meta.json", {"atualizado":datetime.date.today().isoformat(),"periodo_dados":"2025-2026",
                       "fonte":"SISCAM / Câmara Municipal de São José do Rio Preto","origem":"coleta automática diária"})
    print("\n✅ Coleta válida e gravada. Pronto para reconstruir o site.")

if __name__ == "__main__":
    main()
