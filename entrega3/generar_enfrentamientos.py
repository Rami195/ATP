"""Catálogo para elegir dos jugadores y una superficie sin cargar sus tasas.

Perfiles acumulados al cierre de cada temporada (2019–2025), sólo jugadores
con aparición y ranking válido ese año. Se conserva la fecha del ranking
registrado y la última participación por superficie; no se inventa un ranking actual.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from completar_prediccion import COLS, MAP, SUPS, STATS, participations, rates, assign, features, dump, OUT

# Cruces de muestra para el simulador. Acá sólo se eligen los nombres; el resultado lo decide el modelo.
EJEMPLOS=[(2019,'clay','Rafael Nadal','Roger Federer'),(2021,'clay','Daniil Medvedev','Rafael Nadal'),(2019,'grass','Novak Djokovic','John Isner')]


def catalog(matches, style_model, years=range(2019,2026)):
    parts=participations(matches)
    numeric=['n','wins','valid','valid_rest',*STATS,'rest_points','rest_won','bp_chances','bp_converted']
    bios=pd.concat([matches[['winner_id','winner_name','winner_rank','fecha','id_partido']].rename(columns={'winner_id':'id','winner_name':'nombre','winner_rank':'ranking'}),
                    matches[['loser_id','loser_name','loser_rank','fecha','id_partido']].rename(columns={'loser_id':'id','loser_name':'nombre','loser_rank':'ranking'})],ignore_index=True)
    profiles=[]
    for year in years:
        cutoff=pd.Timestamp(year+1,1,1)
        past=parts[parts.fecha<cutoff]
        totals=past.groupby(['id','surface'])[numeric].sum().reset_index()
        rs=rates(totals)
        eligible=pd.concat([totals[['id','surface','n','valid','valid_rest']],rs],axis=1).loc[rs.eligible].copy()
        # Último ranking conocido de una aparición del año, no ranking de fin de año.
        season=bios[bios.fecha.lt(cutoff)&bios.fecha.ge(pd.Timestamp(year,1,1))&bios.ranking.gt(0)].sort_values(['fecha','id_partido'])
        latest=season.drop_duplicates('id',keep='last').rename(columns={'fecha':'ranking_fecha'})
        eligible=eligible.merge(latest[['id','nombre','ranking','ranking_fecha']],on='id',validate='many_to_one')
        last=past.groupby(['id','surface']).fecha.max().rename('ultima_superficie').reset_index()
        eligible=eligible.merge(last,on=['id','surface'],validate='one_to_one')
        eligible['cluster']=assign(eligible,style_model)
        eligible['estilo']=[style_model['names'][int(i)] for i in eligible.cluster]
        eligible['season']=year
        eligible['cobertura_saque']=eligible.valid/eligible.n
        eligible['cobertura_resto']=eligible.valid_rest/eligible.n
        assert eligible.ranking_fecha.lt(cutoff).all() and eligible.ultima_superficie.lt(cutoff).all()
        keep=['id','nombre','season','surface','n','ranking','ranking_fecha','ultima_superficie','cobertura_saque','cobertura_resto','cluster','estilo',*COLS]
        eligible['ranking_fecha']=eligible.ranking_fecha.dt.strftime('%Y-%m-%d')
        eligible['ultima_superficie']=eligible.ultima_superficie.dt.strftime('%Y-%m-%d')
        profiles.extend(eligible[keep].to_dict('records'))
    return profiles


def main(path=None):
    source=Path(path) if path else Path(__file__).resolve().parent.parent/'airflow-atp/include/output/atp_partidos_2026-09-23.csv'
    raw=pd.read_csv(source,dtype={'winner_id':str,'loser_id':str},parse_dates=['fecha'])
    allowed=raw.surface.isin(MAP)&raw.fecha.notna()&~raw.score.fillna('').str.contains(r'W/O|\bWO\b|Walkover',case=False,regex=True)
    matches=raw[allowed].sort_values(['fecha','id_partido']).reset_index(drop=True)
    models=json.loads((OUT/'modelo_prediccion.json').read_text(encoding='utf-8'))
    profiles=catalog(matches,models['styles'])
    def fixture(a,b,surface,year):
        case=pd.DataFrame([{'rank_a':a['ranking'],'rank_b':b['ranking'],'surface':surface,'best_of':3,'cluster_a':a['cluster'],'cluster_b':b['cluster']}])
        probabilities={}
        for name,key in [('Ranking + contexto','ranking'),('Ranking + contexto + estilos','combined')]:
            x,_=features(case,key=='combined')
            probabilities[key]=float(1/(1+np.exp(-float(x[0]@np.array(models['models'][name]['coef'])))))
        equal=case.assign(rank_a=100,rank_b=100)
        x,_=features(equal,True)
        probabilities['equal_ranking']=float(1/(1+np.exp(-float(x[0]@np.array(models['models']['Ranking + contexto + estilos']['coef'])))))
        return {'a':a['id'],'b':b['id'],'surface':surface,'season':year,'best_of':3,**probabilities}
    fixtures=[]
    # Controles contra Python: misma pareja en cada superficie y estilos diferentes.
    for year in [2019,2021,2025]:
        for surface in SUPS:
            pool=[p for p in profiles if p['season']==year and p['surface']==surface]
            pair=[next((p for p in pool if p['nombre']==name),None) for name in ['Rafael Nadal','Roger Federer']]
            if all(pair): candidates=[pair]
            else: candidates=[]
            if len(pool)>1: candidates.append([pool[0],next((p for p in pool if p['cluster']!=pool[0]['cluster']),pool[1])])
            fixtures.extend(fixture(a,b,surface,year) for a,b in candidates)
    ejemplos=[]
    for year,surface,name_a,name_b in EJEMPLOS:
        a,b=[next(p for p in profiles if p['season']==year and p['surface']==surface and p['nombre']==name) for name in (name_a,name_b)]
        case=fixture(a,b,surface,year);fixtures.append(case);ejemplos.append({**case,'nombre_a':name_a,'nombre_b':name_b})
    out={'profiles':profiles,'years':sorted(set(p['season'] for p in profiles)),
         'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
         'scope':'Perfiles acumulados al cierre de temporada. Ranking de última aparición registrada del año, no ranking actual ni oficial de fin de año.',
         'fixtures':fixtures,'ejemplos':ejemplos}
    dump(OUT/'enfrentamientos.json',out)
    print(json.dumps({'profiles':len(profiles),'players':len(set(p['id'] for p in profiles)),'years':out['years'],
                      'nadal_federer_2019':[p for p in profiles if p['season']==2019 and p['nombre'] in ['Rafael Nadal','Roger Federer']]},ensure_ascii=False,indent=2))
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partidos',type=Path)
    main(parser.parse_args().partidos)
