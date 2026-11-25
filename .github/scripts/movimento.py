#!/usr/bin/env python3
"""Registra, ao longo do dia, quais BAs de REP-FTTH entram e saem de MASSIVO e de ÁREA DE RISCO.
Roda a cada atualização do atividades.csv e mantém movimento.json (só dados da BA, sem técnico)."""
import csv, io, json, re, sys, os

ESTADO_FIM = re.compile(r'conclu|cancel', re.I)
RISCO_LIVRE = re.compile(r'^(liberad|n[ãa]o consta|sem cdo)', re.I)
ARQ = 'movimento.json'


def ler(texto):
    rd = csv.DictReader(io.StringIO(texto), delimiter=';')
    return list(rd)


def conjuntos(rows):
    """devolve (extração, abertas, massivo, risco, todas) de REP-FTTH"""
    ext = ''
    abertas, mass, risco, todas = {}, {}, {}, {}
    for r in rows:
        e = (r.get('dh_extracao') or '')[:16]
        if e > ext:
            ext = e
        if r.get('ds_macro_atividade') != 'REP-FTTH':
            continue
        ba = r.get('cd_nrba') or ''
        if not ba:
            continue
        todas[ba] = r
        if ESTADO_FIM.search(r.get('ds_estado') or ''):
            continue
        info = {'cp': r.get('cp') or '', 'setor': r.get('cd_setor') or '', 'cdo': r.get('cdo') or ''}
        abertas[ba] = info
        if r.get('massivo_comunicado'):
            mass[ba] = dict(info, com=r.get('massivo_comunicado'))
        v = r.get('area_risco') or ''
        mot = r.get('area_risco_motivo') or ''
        # só conta área de risco com OBRA DESCARTADA (status IMPEDIMENTO); o INDETERMINADO fica de fora
        if v and not RISCO_LIVRE.match(v) and re.search(r'obra descartada', mot, re.I):
            risco[ba] = dict(info, mot=mot)
    return ext, abertas, mass, risco, todas


def passo(est, ext, abertas, mass, risco, todas):
    dia, hora = ext[:10], ext[11:16]
    novo = not est or est.get('dia') != dia
    if novo:
        est = {'v': 1, 'dia': dia, 'massivo': {}, 'risco': {}}
    est['ext'] = ext
    for nome, atual in (('massivo', mass), ('risco', risco)):
        g = est[nome]
        for ba, info in atual.items():
            x = g.get(ba)
            if x is None:
                g[ba] = dict(info, ent=hora, sai=None)
                if novo:
                    g[ba]['b'] = 1  # já estava na lista quando o dia começou
            elif x.get('sai'):  # voltou para a lista
                x['sai'] = None
                x.pop('mot_sai', None)
        for ba, x in g.items():
            if not x.get('sai') and ba not in atual:
                x['sai'] = hora
            if x.get('sai'):  # reavalia sempre: a BA que saiu da lista pode ser concluída depois
                x['mot_sai'] = 'aberta' if ba in abertas else 'fechada'
    return est


def main():
    txt = open('atividades.csv', encoding='utf-8-sig').read()
    ext, abertas, mass, risco, todas = conjuntos(ler(txt))
    if not ext or len(abertas) < 20:
        print('base vazia/incompleta, nada a fazer'); return
    try:
        est = json.load(open(ARQ, encoding='utf-8'))
    except Exception:
        est = None
    if est and est.get('ext') == ext:
        print('mesma extração, nada a fazer'); return
    est = passo(est, ext, abertas, mass, risco, todas)
    with open(ARQ, 'w', encoding='utf-8') as f:
        json.dump(est, f, ensure_ascii=False, separators=(',', ':'))
    print('ok', ext, len(est['massivo']), len(est['risco']))


if __name__ == '__main__':
    main()
