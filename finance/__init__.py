import numpy as np
import numpy_financial as npf
import pandas as pd
from datetime import date, timedelta

def estimate_rate(pv, pmt, n):
    """
    Aproxima a função RATE do Excel.
    pv  – valor presente (positivo)
    pmt – prestação (positiva)
    n   – número de parcelas
    """
    try:
        return npf.rate(n, -pmt, pv)
    except (ValueError, FloatingPointError):
        return 0.01      # 1 % a.m. se falhar

def amortization_schedule(valor, pmt, n, taxa, data_inicial):
    """
    Gera um DataFrame igual à planilha:
    Parcela | Data | Prestação | Juros | Amortização | Saldo
    """
    saldo = valor
    linhas = []
    for i in range(1, n+1):
        data = data_inicial + timedelta(days=30*(i-1)) # Simplificação: considera mês como 30 dias
        juros = saldo * taxa
        amort = pmt - juros
        saldo = max(saldo - amort, 0) # Saldo não pode ser negativo
        linhas.append([i, data, pmt, juros, amort, saldo])
    cols = ["Parcela","Data","Prestação","Juros","Amortização","Saldo Devedor"]
    df = pd.DataFrame(linhas, columns=cols)
    return df

def idade_ao_fim(data_nasc, data_final):
    anos = data_final.year - data_nasc.year
    if (data_final.month, data_final.day) < (data_nasc.month, data_nasc.day):
        anos -= 1
    meses = (data_final.year - data_nasc.year)*12 + data_final.month - data_nasc.month
    if data_final.day < data_nasc.day:
        meses -= 1
    meses %= 12
    return anos, meses
