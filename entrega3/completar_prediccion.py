"""Ampliación E3: asociación estilo-victorias y predicción temporal sin fuga.

Ejecutar desde cualquier directorio: python completar_prediccion.py
Cada historial excluye TODOS los partidos con la misma fecha de inicio de torneo.
El clustering predictivo se ajusta sólo con datos hasta 2018 y se congela.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss
from sklearn.calibration import calibration_curve

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'resultados'/'prediccion'
COLS = ['tasa_aces','tasa_dobles_faltas','primer_saque_dentro','efectividad_segundo','bp_salvados','puntos_ganados_resto','bp_convertidos']
SUPS = ['cemento','clay','grass']
MAP = {'Hard':'cemento','Clay':'clay','Grass':'grass'}
STATS = ['ace','df','svpt','1stIn','1stWon','2ndWon','SvGms','bpSaved','bpFaced']
PAIRS = [(0,1),(0,2),(1,2)]


def dump(path, obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def participations(matches):
    blocks=[]
    for side,opp,prefix,win in [('w','l','winner',1),('l','w','loser',0)]:
        own=matches[[side+'_'+s for s in STATS]].rename(columns=lambda x:x[2:])
        other=matches[[opp+'_'+s for s in STATS]].rename(columns=lambda x:x[2:])
        valid=own.notna().all(axis=1)&own.ge(0).all(axis=1)
        valid &= (own.ace.le(own.svpt)&own.df.le(own.svpt-own['1stIn'])&own['1stIn'].le(own.svpt)&
                  own['1stWon'].le(own['1stIn'])&own['2ndWon'].le(own.svpt-own['1stIn'])&own.bpSaved.le(own.bpFaced))
        rest_cols=['svpt','1stWon','2ndWon','bpSaved','bpFaced']
        valid_rest=other[rest_cols].notna().all(axis=1)&other[rest_cols].ge(0).all(axis=1)
        valid_rest &= ((other['1stWon']+other['2ndWon']).le(other.svpt)&other.bpSaved.le(other.bpFaced))
        b=pd.DataFrame({'id':matches[prefix+'_id'].astype(str),'surface':matches.surface.map(MAP),'fecha':matches.fecha,
                        'id_partido':matches.id_partido,'lado':side,'n':1,'wins':win,'valid':valid.astype(int),'valid_rest':valid_rest.astype(int)})
        for s in STATS: b[s]=own[s].where(valid,0).fillna(0)
        b['rest_points']=other.svpt.where(valid_rest,0).fillna(0)
        b['rest_won']=(other.svpt-other['1stWon']-other['2ndWon']).where(valid_rest,0).fillna(0)
        b['bp_chances']=other.bpFaced.where(valid_rest,0).fillna(0)
        b['bp_converted']=(other.bpFaced-other.bpSaved).where(valid_rest,0).fillna(0)
        blocks.append(b)
    return pd.concat(blocks,ignore_index=True)


def rates(t):
    r=pd.DataFrame(index=t.index)
    for c,num,den in [('tasa_aces','ace','svpt'),('tasa_dobles_faltas','df','svpt'),('primer_saque_dentro','1stIn','svpt'),
                      ('efectividad_segundo','2ndWon',None),('bp_salvados','bpSaved','bpFaced'),
                      ('puntos_ganados_resto','rest_won','rest_points'),('bp_convertidos','bp_converted','bp_chances')]:
        d=t[den] if den else t.svpt-t['1stIn']
        r[c]=t[num]/d.replace(0,np.nan)
    r['eligible']=t.n.ge(20)&(t.valid/t.n).ge(.8)&(t.valid_rest/t.n).ge(.8)&r[COLS].notna().all(axis=1)&r[COLS].ge(0).all(axis=1)&r[COLS].le(1).all(axis=1)
    return r


def history(parts):
    keys=['id','surface','fecha']
    numeric=['n','wins','valid','valid_rest',*STATS,'rest_points','rest_won','bp_chances','bp_converted']
    daily=parts.groupby(keys,as_index=False)[numeric].sum().sort_values(keys).reset_index(drop=True)
    before=daily.groupby(['id','surface'])[numeric].cumsum()-daily[numeric]
    hist=pd.concat([daily[keys],before],axis=1)
    r=rates(hist)
    hist=pd.concat([hist,r],axis=1)
    hist['ultima_fecha_previa']=daily.groupby(['id','surface']).fecha.shift(1)
    assert (hist.loc[hist.n.gt(0),'ultima_fecha_previa']<hist.loc[hist.n.gt(0),'fecha']).all()
    return hist, numeric


def fit_styles(parts,numeric):
    # Un perfil por jugador-superficie: evita ponderar el clustering por cantidad de partidos.
    totals=parts[parts.fecha<'2019-01-01'].groupby(['id','surface'])[numeric].sum().reset_index()
    rs=rates(totals)
    profiles=pd.concat([totals[['id','surface']],rs],axis=1).loc[rs.eligible].copy()
    means=profiles.groupby('surface')[COLS].mean(); stds=profiles.groupby('surface')[COLS].std(ddof=1)
    z=(profiles[COLS].to_numpy()-means.loc[profiles.surface].to_numpy())/stds.loc[profiles.surface].to_numpy()
    km=KMeans(n_clusters=3,n_init=10,random_state=42).fit(z)
    centers=km.cluster_centers_
    power=int(centers[:,0].argmax()); others=[i for i in range(3) if i!=power]
    fragile=min(others,key=lambda i:centers[i,3]); solid=next(i for i in others if i!=fragile)
    names={power:'Sacadores de potencia',fragile:'Saque frágil',solid:'Restadores sólidos'}
    return {'columns':COLS,'means':means.T.to_dict(),'stds':stds.T.to_dict(),'centers':centers.tolist(),
            'names':[names[i] for i in range(3)],'fit_until':'2018-12-31','n_profiles_fit':len(profiles),
            'ranges':{s:{c:[float(profiles.loc[profiles.surface.eq(s),c].min()),float(profiles.loc[profiles.surface.eq(s),c].max())] for c in COLS} for s in SUPS}}


def assign(df,model):
    means=pd.DataFrame(model['means']).T.loc[df.surface,COLS].to_numpy()
    stds=pd.DataFrame(model['stds']).T.loc[df.surface,COLS].to_numpy()
    z=(df[COLS].to_numpy()-means)/stds
    return np.linalg.norm(z[:,None,:]-np.array(model['centers'])[None,:,:],axis=2).argmin(axis=1)


def features(df,expanded=False):
    # Variables antisimétricas: invertir A/B invierte el logit, sin intercepto.
    d=np.log(df.rank_b.to_numpy()/df.rank_a.to_numpy())
    x=np.column_stack([d, d*(df.surface=='clay'),d*(df.surface=='grass'),d*(df.best_of==5)])
    names=['log(rank_b/rank_a)','log_ratio × clay','log_ratio × grass','log_ratio × best_of5']
    if expanded:
        extras=[]
        for s in SUPS:
            for i,j in PAIRS:
                signed=((df.cluster_a==i)&(df.cluster_b==j)).astype(int)-((df.cluster_a==j)&(df.cluster_b==i)).astype(int)
                extras.append(signed.to_numpy()*(df.surface==s).to_numpy())
                names.append(f'{s}: estilo {i} vs {j}')
        x=np.column_stack([x,*extras])
    return x,names


def metrics(y,p):
    return {'accuracy':float(accuracy_score(y,p>=.5)),'auc':float(roc_auc_score(y,p)),
            'log_loss':float(log_loss(y,p)),'brier':float(brier_score_loss(y,p))}


def bootstrap_delta(test,p0,p1,repetitions=2000):
    # Pareado y agrupado por torneo: conserva la dependencia intratorneo.
    y=test.gana_a.to_numpy(); eps=1e-12
    loss=lambda p:-(y*np.log(np.clip(p,eps,1-eps))+(1-y)*np.log(np.clip(1-p,eps,1-eps)))
    dif=pd.DataFrame({'torneo':test.tourney_id.to_numpy(),'loss':loss(p1)-loss(p0),
                      'accuracy':((p1>=.5)==y).astype(float)-((p0>=.5)==y).astype(float),'n':1}).groupby('torneo').sum()
    rng=np.random.default_rng(42); samples=[]
    a=dif.to_numpy()
    for _ in range(repetitions):
        total=a[rng.integers(0,len(a),len(a))].sum(axis=0)
        samples.append(total[:2]/total[2])
    intervals=np.quantile(samples,[.025,.975],axis=0)
    return {'delta_log_loss':float((loss(p1)-loss(p0)).mean()),'log_loss_ci95':intervals[:,0].tolist(),
            'delta_accuracy':float((((p1>=.5)==y).astype(float)-((p0>=.5)==y).astype(float)).mean()),
            'accuracy_ci95':intervals[:,1].tolist(),'resamples':repetitions,'tournaments':len(dif)}


def association_rows(sub,repetitions=1000):
    """Tasa de victoria por estilo, con IC95 % remuestreando torneos completos."""
    by_tournament=sub.groupby(['tourney_id','estilo']).gano.agg(['sum','count']).unstack('estilo',fill_value=0)
    rows=[]
    for style,g in sub.groupby('estilo'):
        totals=by_tournament.loc[:,[('sum',style),('count',style)]].to_numpy()
        rng=np.random.default_rng(42); boot=[]
        for _ in range(repetitions):
            v=totals[rng.integers(0,len(totals),len(totals))].sum(axis=0)
            if v[1]:boot.append(v[0]/v[1])
        lo,hi=np.quantile(boot,[.025,.975])
        rows.append({'estilo':style,'n':len(g),'winrate':float(g.gano.mean()),'lower':float(lo),'upper':float(hi)})
    return rows


def main(path=None):
    OUT.mkdir(parents=True,exist_ok=True)
    source=Path(path) if path else ROOT.parent/'airflow-atp/include/output/atp_partidos_2026-09-23.csv'
    raw=pd.read_csv(source,dtype={'winner_id':str,'loser_id':str},parse_dates=['fecha'])
    assert raw.id_partido.is_unique
    # W/O no es un partido disputado. Retirados sí cuentan como el desenlace registrado.
    allowed=raw.surface.isin(MAP)&raw.fecha.notna()&~raw.score.fillna('').str.contains(r'W/O|\bWO\b|Walkover',case=False,regex=True)
    matches=raw[allowed].sort_values(['fecha','id_partido']).reset_index(drop=True)
    parts=participations(matches); hist,numeric=history(parts); model=fit_styles(parts,numeric)
    valid=hist[hist.eligible].copy(); valid['cluster']=assign(valid,model)
    each=parts[['id','surface','fecha','id_partido','lado']].merge(valid[['id','surface','fecha','cluster',*COLS,'n','ultima_fecha_previa']],on=['id','surface','fecha'],validate='many_to_one')
    eligible=matches.copy()
    for side in ['w','l']:
        h=each[each.lado==side][['id_partido','cluster',*COLS,'n','ultima_fecha_previa']]
        eligible=eligible.merge(h.rename(columns={c:f'{c}_{side}' for c in h.columns if c!='id_partido'}),on='id_partido',validate='one_to_one')
    eligible=eligible[eligible.winner_rank.gt(0)&eligible.loser_rank.gt(0)&eligible.best_of.isin([3,5])].copy()
    rng=np.random.default_rng(42); a_wins=rng.integers(0,2,len(eligible)).astype(bool)
    data=eligible[['id_partido','fecha','tourney_id','best_of']].copy()
    data['surface']=eligible.surface.map(MAP); data['gana_a']=a_wins.astype(int)
    for dest,w,l in [('rank','winner_rank','loser_rank'),('nombre','winner_name','loser_name'),('id','winner_id','loser_id'),('cluster','cluster_w','cluster_l'),('n','n_w','n_l'),*[(c,c+'_w',c+'_l') for c in COLS]]:
        data[dest+'_a']=np.where(a_wins,eligible[w],eligible[l]);data[dest+'_b']=np.where(a_wins,eligible[l],eligible[w])
    train=data.fecha<'2019-01-01'; val=(data.fecha>='2019-01-01')&(data.fecha<'2023-01-01'); testmask=data.fecha>='2023-01-01'
    assert train.any() and val.any() and testmask.any()
    candidates=[]; exports={}; predictions={}; reports={}
    for name,expanded in [('Ranking + contexto',False),('Ranking + contexto + estilos',True)]:
        x,names=features(data,expanded); y=data.gana_a.to_numpy(); options=[]
        for c in [.01,.1,1,10]:
            lr=LogisticRegression(C=c,fit_intercept=False,max_iter=2000,solver='lbfgs',random_state=42).fit(x[train],y[train])
            p=lr.predict_proba(x[val])[:,1]; score=log_loss(y[val],p)
            options.append((score,c)); candidates.append({'modelo':name,'C':c,'log_loss_validacion':float(score)})
        score,c=min(options)
        lr=LogisticRegression(C=c,fit_intercept=False,max_iter=2000,solver='lbfgs',random_state=42).fit(x[~testmask],y[~testmask])
        p=lr.predict_proba(x[testmask])[:,1]; predictions[name]=p; reports[name]=metrics(y[testmask],p)
        exports[name]={'coef':lr.coef_[0].tolist(),'intercept':0,'features':names,'C':c,'validation_log_loss':float(score),'expanded':expanded}
        # Control de la implementación portable y de simetría.
        portable=1/(1+np.exp(-(x[testmask]@lr.coef_[0])))
        np.testing.assert_allclose(p,portable,atol=1e-12)
    test=data[testmask].copy(); y=test.gana_a.to_numpy()
    ranking_pred=(test.rank_a<test.rank_b).to_numpy()
    reports['Gana el mejor rankeado']={'accuracy':float(accuracy_score(y,ranking_pred)),'auc':None,'log_loss':None,'brier':None}
    reports['Azar 50/50']=metrics(y,np.full(len(y),.5))
    # Selección de modelo para la app sólo con validación, antes de usar el test.
    selected=min(exports,key=lambda n:exports[n]['validation_log_loss'])
    difference=bootstrap_delta(test,predictions['Ranking + contexto'],predictions['Ranking + contexto + estilos'])
    calibration=[]
    for name,p in predictions.items():
        true,pred=calibration_curve(y,p,n_bins=8,strategy='quantile')
        calibration.extend({'modelo':name,'probabilidad_media':float(a),'frecuencia_real':float(b)} for a,b in zip(pred,true))
    test['p_ranking']=predictions['Ranking + contexto'];test['p_estilos']=predictions['Ranking + contexto + estilos']
    test['estilo_a']=[model['names'][int(i)] for i in test.cluster_a];test['estilo_b']=[model['names'][int(i)] for i in test.cluster_b]
    # Asociación en test: cada partido aporta una victoria y una derrota.
    appearances=pd.concat([test[['surface','tourney_id','estilo_a','gana_a','rank_a','rank_b']].rename(columns={'estilo_a':'estilo','gana_a':'gano','rank_a':'rank','rank_b':'rival'}),
                           test[['surface','tourney_id','estilo_b','gana_a','rank_b','rank_a']].rename(columns={'estilo_b':'estilo','gana_a':'gano','rank_b':'rank','rank_a':'rival'}).assign(gano=lambda d:1-d.gano)],ignore_index=True)
    association=[{'surface':surface}|row for surface in ['Todas',*SUPS]
                 for row in association_rows(appearances if surface=='Todas' else appearances[appearances.surface==surface])]
    # El ranking del partido como control: describe, no reemplaza a la comparación de modelos.
    association_rank=[{'condicion':'Todos sus partidos'}|row for row in association_rows(appearances)]
    for name,mask in [('Llega como mejor rankeado',appearances['rank']<appearances.rival),('Llega como peor rankeado',appearances['rank']>appearances.rival)]:
        association_rank.extend({'condicion':name}|row for row in association_rows(appearances[mask]))
    best_ranked={style:float(g['rank'].lt(g.rival).mean()) for style,g in appearances.groupby('estilo')}
    # Partidos donde sumar estilos cambia al favorito: explican toda la diferencia de accuracy.
    p0,p1=predictions['Ranking + contexto'],predictions['Ranking + contexto + estilos']
    changed=(p0>=.5)!=(p1>=.5)
    favorite_changes={'changed':int(changed.sum()),'share':float(changed.mean()),
                      'ranking_right':int(((p0>=.5)==y)[changed].sum()),'styles_right':int(((p1>=.5)==y)[changed].sum())}
    favorite_changes['net_matches']=favorite_changes['styles_right']-favorite_changes['ranking_right']
    assert abs(favorite_changes['net_matches']/len(y)-difference['delta_accuracy'])<1e-12
    counts={'raw':len(raw),'valid_surface_non_walkover':len(matches),'eligible':len(data),'train':int(train.sum()),'validation':int(val.sum()),'test':int(testmask.sum()),
            'test_candidates':int(matches.fecha.ge('2023-01-01').sum()),'target_balance_test':float(y.mean())}
    report={'counts':counts,'metrics':reports,'comparison':difference,'selected_by_validation':selected,'candidates':candidates,
            'calibration':calibration,'association':association,'association_rank':association_rank,'best_ranked_share':best_ranked,
            'favorite_changes':favorite_changes,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'protocol':{'train':'2000–2018','validation':'2019–2022','test':'2023–2025','cluster_fit':'hasta 2018, congelado',
                        'history':'Sólo fechas de inicio de torneo estrictamente anteriores. Excluye todos los partidos de la misma fecha.',
                        'scope':'Ambos jugadores con >=20 partidos previos en superficie, cobertura >=80%, siete tasas definidas y ranking válido.'}}
    dump(OUT/'informe.json',report);dump(OUT/'modelo_prediccion.json',{'styles':model,'models':exports,'selected':selected,'surfaces':SUPS,'pairs':PAIRS,
          'rank_range':[float(data.loc[~testmask,['rank_a','rank_b']].min().min()),float(data.loc[~testmask,['rank_a','rank_b']].max().max())]})
    test.to_csv(OUT/'predicciones_test.csv',index=False)
    pd.DataFrame(association).to_csv(OUT/'victorias_por_estilo.csv',index=False)
    data.to_csv(OUT/'dataset_temporal.csv',index=False)
    print(json.dumps({'counts':counts,'metrics':reports,'comparison':difference,'selected':selected},ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partidos',type=Path)
    main(parser.parse_args().partidos)
