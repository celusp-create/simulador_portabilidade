from flask import Flask, render_template, redirect, url_for, request, session, flash
from datetime import datetime, timedelta, date
from finance import estimate_rate, amortization_schedule, idade_ao_fim
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)          # sessão em memória

# ────────────────────────────────
# HOME
# ────────────────────────────────
@app.route("/")
def index():
    cliente = session.get("cliente")
    contratos = session.get("contratos", [])
    total_contratos = len([c for c in contratos if c["ok_idade"]])
    total_saldo = sum(c["saldo_atual"] for c in contratos if c["ok_idade"])
    return render_template("index.html",
                           cliente=cliente,
                           total_contratos=total_contratos,
                           total_saldo=total_saldo,
                           contratos=contratos)

# ────────────────────────────────
# FORMULÁRIO CLIENTE
# ────────────────────────────────
@app.route("/cliente", methods=["GET","POST"])
def cliente():
    if request.method == "POST":
        nome = request.form["nome"].split()[0].title()      # só 1º nome
        nasc = datetime.strptime(request.form["nasc"], "%Y-%m-%d").date()
        taxa_port = float(request.form["taxa_port"] or 0)/100
        session["cliente"] = {"nome":nome,
                              "nasc":nasc,
                              "taxa_port":taxa_port}
        session["contratos"] = []      # zera qualquer coisa anterior
        return redirect(url_for("contrato"))
    return render_template("cliente.html")

# ────────────────────────────────
# FORMULÁRIO CONTRATO
# ────────────────────────────────
@app.route("/contrato", methods=["GET","POST"])
def contrato():
    if "cliente" not in session:
        return redirect(url_for("cliente"))

    if request.method == "POST":
        dados = dict(request.form)
        # cast
        valor = float(dados["valor"])
        parcelas = int(dados["parcelas"])
        data_ini = datetime.strptime(dados["data_ini"], "%Y-%m-%d").date()
        pmt = float(dados["prestacao"])
        possui_taxa = "possui_taxa" in dados
        taxa_informada = float(dados["taxa_informada"])/100 if possui_taxa and dados["taxa_informada"] else None
        possui_cet = "possui_cet" in dados
        cet_mensal = float(dados["cet_mensal"])/100 if possui_cet and dados["cet_mensal"] else None

        # cálculos
        taxa_calc = taxa_informada or estimate_rate(valor, pmt, parcelas)
        saldo = 0
        parcelas_pagas = 0
        for i in range(parcelas):
            if data_ini + timedelta(days=30*i) <= date.today():
                parcelas_pagas += 1
        parcelas_rest = parcelas - parcelas_pagas
        if parcelas_rest>0:
            # Formula para calculo de saldo devedor PV = PMT * [1 - (1 + i)^-n] / i
            # Convertendo para Python (aqui n é parcelas_rest, i é taxa_calc)
            # saldo = pmt * (1 - (1 + taxa_calc)**(-parcelas_rest)) / taxa_calc
            # A função PV do numpy-financial pode ser usada: npf.pv(rate, nper, pmt, fv=0, when='end')
            # npf.pv retorna negativo, então pegamos o abs.
            saldo = abs(npf.pv(taxa_calc, parcelas_rest, -pmt))


        taxa_port = session["cliente"]["taxa_port"]
        prest_port = None
        if taxa_port and saldo and parcelas_rest:
            # PMT = PV * [i * (1 + i)^n] / [(1 + i)^n – 1]
            # npf.pmt(rate, nper, pv, fv=0, when='end')
            prest_port = abs(npf.pmt(taxa_port, parcelas_rest, -saldo))

        data_final = data_ini + timedelta(days=30*(parcelas-1))
        anos, meses = idade_ao_fim(session["cliente"]["nasc"], data_final)
        ok_idade = (anos*12+meses) <= ((79*12)+8)

        # monta dicionário
        contrato = dict(
            banco=dados["banco"].title(),
            banco_num=dados["banco_num"],
            id=dados["id"],
            valor=valor,
            parcelas=parcelas,
            data_ini=data_ini,
            pmt=pmt,
            taxa_calc=taxa_calc,
            taxa_inf=taxa_informada,
            diff_taxa=(taxa_calc - (taxa_informada or taxa_calc))*100, # em pontos percentuais
            cet=cet_mensal or estimate_rate(valor*0.97, pmt, parcelas), # 0.97 como na macro
            saldo_atual=saldo,
            parcelas_rest=parcelas_rest,
            prest_port=prest_port,
            taxa_port=taxa_port,
            anos=anos,
            meses=meses,
            ok_idade=ok_idade
        )
        # agenda no "banco"
        contratos = session.get("contratos",[])
        contratos.append(contrato)
        session["contratos"] = contratos

        if "adicionar_outro" in dados:
            return redirect(url_for("contrato"))
        else:
            return redirect(url_for("index"))

    return render_template("contrato.html")

# ────────────────────────────────
# RELATÓRIO INDIVIDUAL
# ────────────────────────────────
@app.route("/relatorio/<int:idx>")
def relatorio(idx):
    contratos = session.get("contratos",[])
    if idx>=len(contratos):
        return redirect(url_for("index"))
    c = contratos[idx]
    df = amortization_schedule(c["valor"], c["pmt"], c["parcelas"],
                               c["taxa_calc"], c["data_ini"])
    html_tabela = df.to_html(index=False, classes="tabela")
    return render_template("relatorio.html", c=c, cliente=session["cliente"], tabela=html_tabela)

# ────────────────────────────────
# CONSOLIDAÇÃO
# ────────────────────────────────
@app.route("/consolidado")
def consolidado():
    contratos = [c for c in session.get("contratos",[]) if c["ok_idade"]]
    reprov = len(session.get("contratos",[])) - len(contratos)
    return render_template("consolidado.html",
                           cliente=session.get("cliente"),
                           contratos=contratos,
                           reprov=reprov)

# ────────────────────────────────
# LIMPAR TUDO
# ────────────────────────────────
@app.route("/limpar")
def limpar():
    session.clear()
    flash("Todos os relatórios foram limpos.")
    return redirect(url_for("index"))

# ────────────────────────────────
if __name__ == "__main__":
    # Em ambiente de produção, use Gunicorn ou outro servidor WSGI
    # Para desenvolvimento local, o debug=True é útil
    app.run(debug=True)
