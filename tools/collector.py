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
    print("4/5 contatos...")
    try: contatos = coletar_contatos()
    except Exception as ex:
        print("  coleta de contatos falhou inteira:", ex); contatos = carrega_anterior("contatos.json") or {}
    print("5/5 validando...")
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
    dump("meta.json", {"atualizado":datetime.date.today().isoformat(),"periodo_dados":"2025-2026",
                       "fonte":"SISCAM / Câmara Municipal de São José do Rio Preto","origem":"coleta automática diária"})
    print("\n✅ Coleta válida e gravada. Pronto para reconstruir o site.")

if __name__ == "__main__":
    main()
