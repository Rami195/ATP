"""Entrega 4: datos del pipeline + modelos -> métricas y gráficos Altair -> dist/.

python build.py                 reconstruye la app con la versión guardada en inputs/.
python build.py --pipeline DIR  toma los CSV que dejó el DAG en DIR, reentrena con la
                                misma semilla, reemplaza inputs/ y genera la app.

En los dos casos comprueba cada asignación contra la referencia antes de publicar.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import numpy as np
import pandas as pd
import altair as alt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_samples

ROOT = Path(__file__).resolve().parent
SUPS = ['cemento', 'clay', 'grass']
SUP_LABELS = {'cemento': 'Cemento', 'clay': 'Polvo de ladrillo', 'grass': 'Césped'}
ORDER = ['Sacadores de potencia', 'Restadores sólidos', 'Saque frágil']
COLORS = ['#E69F00', '#56B4E9', '#009E73']
SHAPES = ['circle', 'square', 'triangle-up']
QUALITY = ['Con evidencia suficiente', 'Con partidos, sin evidencia suficiente', 'Sin partidos']
SIDES = alt.Scale(domain=['A', 'B'], range=['#243D39', '#899B93'])
CONDITIONS = ['Todos sus partidos', 'Llega como mejor rankeado', 'Llega como peor rankeado']
# Lo que necesitan los gráficos: el resto de las columnas queda en datos.json.
# Texto corto de cada hipótesis de la Entrega 2; sus números salen de fichas_hipotesis.csv.
HYPOTHESES = {'H1': ('Con menos de 20 partidos, los valores son más extremos', 'separación'),
              'H2': ('Aces y efectividad del primer saque son casi redundantes', 'r'),
              'H3': ('Sumar aces en césped va con rendir mejor en césped', 'r'),
              'H4': ('Los jugadores más altos hacen más aces', 'r'),
              'H5': ('Más aces van con menos puntos ganados al resto', 'r'),
              'H6': ('Los que mejor devuelven juegan partidos más largos', 'r')}
STATES = {'confirmada': 'Se sostuvo', 'inconclusa': 'Inconclusa', 'refutada': 'No se sostuvo'}
CHART_COLUMNS = ['clave', 'nombre', 'superficie', 'superficie_nombre', 'estilo', 'partidos', 'winrate',
                 'silhouette', 'PC1', 'PC2', 'tasa_aces_z', 'puntos_ganados_resto_z']
LABELS = {'tasa_aces': 'Aces', 'tasa_dobles_faltas': 'Dobles faltas',
          'primer_saque_dentro': 'Primer saque dentro', 'efectividad_segundo': 'Segundo saque ganado',
          'bp_salvados': 'Break points salvados', 'puntos_ganados_resto': 'Puntos ganados al resto',
          'bp_convertidos': 'Break points convertidos'}
SOURCE = {'tasa_aces': 'tasa-aces', 'tasa_dobles_faltas': 'tasa-dobles-faltas',
          'primer_saque_dentro': 'tasa-primer-saque-dentro', 'efectividad_segundo': 'efectividad-segundo-saque',
          'bp_salvados': 'tasa-break-points-salvados', 'puntos_ganados_resto': 'tasa-puntos-ganados-resto',
          'bp_convertidos': 'tasa-break-points-convertidos', 'efectividad_primero': 'efectividad-primer-saque'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def style_color(legend=None):
    return alt.Color('estilo:N', title='Estilo', scale=alt.Scale(domain=ORDER, range=COLORS), legend=legend)


def style_shape(legend=None):
    return alt.Shape('estilo:N', title='Estilo', scale=alt.Scale(domain=ORDER, range=SHAPES), legend=legend)


def percent(value):
    return f'{value:.1%}'.replace('.', ',')


def finish(chart):
    """Misma configuración para los 13 gráficos: fondo, tipografía y densidad de marcas."""
    return (chart.configure(background='#FFFFFF', font='Segoe UI, system-ui, sans-serif')
            .configure_view(stroke=None)
            .configure_axis(labelColor='#4C5F58', titleColor='#364940', gridColor='#EDF0EB', labelFontSize=12,
                            titleFontSize=12, titlePadding=14, labelLimit=290, tickCount=6)
            .configure_legend(labelFontSize=12, titleFontSize=12, labelColor='#4C5F58', titleColor='#364940', columns=3, labelLimit=320)
            .to_dict())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')


def long_profiles(players):
    """Del Silver ancho a una fila por jugador y superficie."""
    blocks = []
    for surface in SUPS:
        block = pd.DataFrame({'id': players['id-jugador'], 'nombre': players['nombre-jugador'],
                              'superficie': surface, 'partidos': players[f'partidos-{surface}'],
                              'winrate': players[f'tasa-victorias-{surface}'],
                              'cobertura_saque': players[f'cobertura-saque-{surface}'],
                              'cobertura_resto': players[f'cobertura-resto-{surface}']})
        for name, original in SOURCE.items():
            block[name] = players[f'{original}-{surface}']
        blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def enough_matches(profiles, config):
    return profiles.partidos.ge(config['filtro_perfil']['partidos_min'])


def reliable(profiles, config):
    # Igual que la celda 4 de E3: exige las ocho tasas, aunque siete entran a K-means.
    return (enough_matches(profiles, config) &
            profiles.cobertura_saque.ge(config['filtro_perfil']['cobertura_min']) &
            profiles.cobertura_resto.ge(config['filtro_perfil']['cobertura_min']) &
            profiles[list(SOURCE)].notna().all(axis=1))


def train_styles(jugadores):
    """Reentrena el clustering de E3 con datos nuevos: mismo filtro, k, semilla y regla de nombres."""
    config = json.loads((ROOT/'inputs/modelo_exacto.json').read_text(encoding='utf-8'))
    cols = config['columnas']
    players = pd.read_csv(jugadores, dtype={'id-jugador': str})
    profiles = long_profiles(players)
    df = profiles[reliable(profiles, config)].reset_index(drop=True)
    means, stds = df.groupby('superficie')[cols].mean(), df.groupby('superficie')[cols].std()
    z = (df[cols].to_numpy() - means.loc[df.superficie].to_numpy()) / stds.loc[df.superficie].to_numpy()
    model = KMeans(n_clusters=config['k'], n_init=10, random_state=config['semilla']).fit(z)
    centers = pd.DataFrame(model.cluster_centers_, columns=cols)
    power = int(centers.tasa_aces.idxmax())
    others = centers.drop(index=power)
    fragile = int(others.efectividad_segundo.idxmin())
    solid = int(others.index.drop(fragile)[0])
    names = {str(power): ORDER[0], str(solid): ORDER[1], str(fragile): ORDER[2]}
    config |= {'nombres_por_grupo': names, 'media_por_superficie': means.T.to_dict(), 'desvio_por_superficie': stds.T.to_dict(),
               'centros_z': {str(i): dict(zip(cols, map(float, row))) for i, row in enumerate(model.cluster_centers_)},
               'precision': f'Reentrenado por build.py desde {Path(jugadores).name}'}
    reference = df[['id', 'nombre', 'superficie', 'partidos', 'winrate']].copy()
    reference['estilo'] = [names[str(i)] for i in model.labels_]
    for j, c in enumerate(cols):
        reference[c + '_z'] = z[:, j]
    (ROOT/'inputs/modelo_exacto.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    reference.to_csv(ROOT/'inputs/estilos_referencia.csv', index=False)
    shutil.copy2(jugadores, ROOT/'inputs/jugadores.csv')


def pipeline_funnel(folder, matches_path):
    """Filas de cada paso del DAG: de los CSV de temporada a los partidos con superficie válida."""
    seasons = [path for path in (folder/'bronze').glob('*.csv') if path.stem.isdigit()]
    matches = pd.read_csv(matches_path, usecols=['surface', 'winner_id', 'loser_id', 'anio'], dtype=str)
    surfaces = matches.surface.isin(['Hard', 'Clay', 'Grass'])
    write_json(ROOT/'inputs/embudo_pipeline.json',
               {'bronce': sum(len(pd.read_csv(path, usecols=['tourney_id'])) for path in seasons),
                'consolidado': len(matches), 'superficies': int(surfaces.sum()),
                'carpet': int(matches.surface.eq('Carpet').sum()), 'carpet_ultimo': int(matches.anio[matches.surface.eq('Carpet')].astype(float).max()), 'sin_superficie': int(matches.surface.isna().sum()),
                'jugadores_en_partidos': int(pd.concat([matches.winner_id, matches.loser_id]).nunique())})


def refresh_from_pipeline(folder):
    """Datos nuevos del DAG -> estilos, predicción y catálogo reentrenados -> inputs/."""
    latest = lambda pattern: max(folder.glob(pattern), key=lambda path: path.name)
    jugadores, partidos = latest('atp_jugadores_*.csv'), latest('atp_partidos_*.csv')
    print(f'Datos del pipeline: {jugadores.name}, {partidos.name}')
    train_styles(jugadores)
    pipeline_funnel(folder, partidos)
    sys.path.insert(0, str(ROOT.parent/'entrega3'))
    import completar_prediccion
    import generar_enfrentamientos
    completar_prediccion.main(partidos)
    generar_enfrentamientos.main(partidos)


def miles(value):
    return f'{value:,}'.replace(',', '.')


def funnel_steps(players, profiles, config, kept):
    pipeline = json.loads((ROOT/'inputs/embudo_pipeline.json').read_text(encoding='utf-8'))
    return [
        {'paso': 'Temporadas 2000–2025 descargadas', 'filas': pipeline['bronce'], 'unidad': 'partidos', 'motivo': 'Una fila por partido, tal como la publica la fuente.'},
        {'paso': 'Sin partidos repetidos', 'filas': pipeline['consolidado'], 'unidad': 'partidos', 'motivo': 'Un partido se identifica por torneo y número de partido.'},
        {'paso': 'Cemento, polvo de ladrillo y césped', 'filas': pipeline['superficies'], 'unidad': 'partidos', 'motivo': f"Salen {miles(pipeline['carpet'])} de Carpet, con último registro en {pipeline['carpet_ultimo']}, y {miles(pipeline['sin_superficie'])} sin superficie."},
        {'paso': 'Jugadores del Silver', 'filas': len(players), 'unidad': 'jugadores', 'motivo': f"De {miles(pipeline['jugadores_en_partidos'])} jugadores, quedan los que tienen 3 partidos o más y estadísticas válidas."},
        {'paso': 'Jugador × superficie', 'filas': len(profiles), 'unidad': 'perfiles', 'motivo': 'Un jugador puede rendir distinto en cada superficie, así que aporta hasta tres filas.'},
        {'paso': 'Con algún partido en esa superficie', 'filas': int(profiles.partidos.gt(0).sum()), 'unidad': 'perfiles', 'motivo': 'Sin partidos no hay nada que medir.'},
        {'paso': 'Con 20 partidos o más', 'filas': int(enough_matches(profiles, config).sum()), 'unidad': 'perfiles', 'motivo': 'Con menos, los valores son más extremos e inestables (hipótesis H1).'},
        {'paso': 'Con cobertura de 80 % o más', 'filas': kept, 'unidad': 'perfiles', 'motivo': 'Hacen falta estadísticas de saque y de resto en casi todos sus partidos, y las ocho tasas definidas.'}]


def hypotheses():
    table = pd.read_csv(ROOT/'inputs/hipotesis.csv').set_index('id')
    return [{'id': key, 'hipotesis': text, 'medida': measure, 'valor': float(table.loc[key, 'valor']),
             'n': int(table.loc[key, 'n']), 'estado': STATES[table.loc[key, 'estado']]}
            for key, (text, measure) in HYPOTHESES.items()]


def prepare(jugadores, config_path, reference_path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    cols = config['columnas']
    players = pd.read_csv(jugadores, dtype={'id-jugador': str})
    assert players['id-jugador'].is_unique
    all_profiles = long_profiles(players)
    df = all_profiles[reliable(all_profiles, config)].copy().reset_index(drop=True)
    assert df[cols].ge(0).all().all() and df[cols].le(1).all().all()
    # La entrega guardó Z y el pipeline. Ésa es la instantánea analítica de E3.
    # El Silver local tiene pequeñas diferencias: se auditan, no se mezclan.
    means = pd.DataFrame(config['media_por_superficie']).T[cols]
    stds = pd.DataFrame(config['desvio_por_superficie']).T[cols]
    reference = pd.read_csv(reference_path, dtype={'id': str})
    ref = reference.set_index(['id','superficie']).loc[pd.MultiIndex.from_frame(df[['id','superficie']])]
    z = ref[[c+'_z' for c in cols]].to_numpy()
    reconstructed = z * stds.loc[df.superficie].to_numpy() + means.loc[df.superficie].to_numpy()
    changed = np.abs(df[cols].to_numpy()-reconstructed)>1e-7
    audit=[]
    for i,j in zip(*np.where(changed)):
        audit.append({'id':df.iloc[i].id,'nombre':df.iloc[i].nombre,'superficie':df.iloc[i].superficie,
                      'rasgo':cols[j],'silver_actual':float(df.iloc[i][cols[j]]),'instantanea_E3':float(reconstructed[i,j])})
    write_json(ROOT/'inputs/auditoria_versiones.json',audit)
    df[cols]=reconstructed
    groups = sorted(config['centros_z'], key=int)
    centers = np.array([[config['centros_z'][g][c] for c in cols] for g in groups])
    distances = np.linalg.norm(z[:, None, :] - centers[None, :, :], axis=2)
    lab = distances.argmin(axis=1)
    df['estilo'] = [config['nombres_por_grupo'][groups[i]] for i in lab]
    comparison = df.merge(reference, on=['id', 'superficie'], suffixes=('', '_ref'), validate='one_to_one')
    assert len(comparison) == len(df) == len(reference), 'Cambió el universo: regenerar primero la Entrega 3.'
    assert (comparison.estilo == comparison.estilo_ref).all(), 'El modelo y la referencia no coinciden.'
    for j, c in enumerate(cols):
        df[c + '_z'] = z[:, j]
        np.testing.assert_allclose(df.set_index(['id','superficie']).loc[pd.MultiIndex.from_frame(reference[['id','superficie']]), c+'_z'], reference[c+'_z'], atol=1e-7)
    pca = PCA(random_state=42).fit(z)
    projection = pca.transform(z)
    df['PC1'], df['PC2'] = projection[:, 0], projection[:, 1]
    df['silhouette'] = silhouette_samples(z, lab)
    df['distancia'] = distances.min(axis=1)
    df['superficie_nombre'] = df.superficie.map(SUP_LABELS)
    df['clave'] = df.id + '|' + df.superficie
    summary = []
    for s in SUPS:
        subset = all_profiles[all_profiles.superficie.eq(s)]
        kept, played = int(df.superficie.eq(s).sum()), int(subset.partidos.gt(0).sum())
        for order, (state, n) in enumerate([(QUALITY[0], kept), (QUALITY[1], played-kept), (QUALITY[2], len(subset)-played)]):
            summary.append({'superficie': SUP_LABELS[s], 'estado': state, 'orden': order, 'perfiles': n})
    model = {'columns': cols, 'labels': LABELS, 'surfaces': SUP_LABELS,
             'means': means.T.to_dict(), 'stds': stds.T.to_dict(),
             'centers': centers.tolist(), 'names': [config['nombres_por_grupo'][g] for g in groups],
             'ranges': {s: {c: [float(df.loc[df.superficie.eq(s),c].min()),float(df.loc[df.superficie.eq(s),c].max())] for c in cols} for s in SUPS},
             'distance95': float(np.quantile(distances.min(axis=1), .95)),
             'pca_mean': pca.mean_.tolist(), 'pca_components': pca.components_[:2].tolist()}
    stats = {'n': len(df), 'players': int(df.id.nunique()), 'silver_players': len(players),
             'candidate_profiles': len(all_profiles), 'played_profiles': int(all_profiles.partidos.gt(0).sum()),
             'funnel': funnel_steps(players, all_profiles, config, len(df)), 'hypotheses': hypotheses(),
             'correlation_raw': float(df.tasa_aces.corr(df.puntos_ganados_resto)), 'silhouette': float(df.silhouette.mean()),
             'negative': float(df.silhouette.lt(0).mean()), 'below025': float(df.silhouette.lt(.25).mean()),
             'correlation': float(np.corrcoef(z[:,0],z[:,5])[0,1]),
             'pca': pca.explained_variance_ratio_.tolist(),
             'counts': {k:int(v) for k,v in df.estilo.value_counts().items()},
             'surface_counts': {k:int(v) for k,v in df.superficie.value_counts().items()},
             'verified_predictions': len(comparison), 'source_differences':len(audit),
             'profiles_source_differences':int(changed.any(axis=1).sum())}
    return df, pd.DataFrame(summary), model, stats


def charts(df, quality, stats):
    legend = alt.Legend(orient='bottom')
    color, shape = style_color(legend), style_shape(legend)
    visible = df[CHART_COLUMNS]
    tip = [alt.Tooltip('nombre:N',title='Jugador'), alt.Tooltip('superficie_nombre:N',title='Superficie'),
           alt.Tooltip('estilo:N',title='Asignación del modelo'), alt.Tooltip('partidos:Q',format='.0f',title='Partidos'),
           alt.Tooltip('winrate:Q',format='.1%',title='Victorias (descriptivo)'),
           alt.Tooltip('silhouette:Q',format='.3f',title='Silhouette individual')]
    quality_chart = alt.Chart(quality).mark_bar(size=28).encode(
        y=alt.Y('superficie:N',title=None,sort=list(SUP_LABELS.values())),
        x=alt.X('perfiles:Q',title='Perfiles candidatos (jugador × superficie)',scale=alt.Scale(zero=True)),
        color=alt.Color('estado:N',scale=alt.Scale(domain=QUALITY,range=['#243D39','#B9C6BB','#E6EAE3']),legend=alt.Legend(orient='bottom',title=None)),
        order=alt.Order('orden:O',sort='ascending'), tooltip=['superficie:N','estado:N','perfiles:Q']).properties(height=180)
    relation = alt.Chart(visible).mark_circle(size=28,opacity=.4,color='#526C64').encode(
        x=alt.X('tasa_aces_z:Q',title='Aces · desvíos respecto de su superficie',scale=alt.Scale(zero=False)),
        y=alt.Y('puntos_ganados_resto_z:Q',title='Puntos al resto · desvíos',scale=alt.Scale(zero=False)),tooltip=tip)
    regression = relation.transform_regression('tasa_aces_z','puntos_ganados_resto_z').mark_line(color='#243D39',strokeWidth=2)
    pca = alt.Chart(visible).mark_point(filled=True,size=37,opacity=.6).encode(
        x=alt.X('PC1:Q',title=f"PC1 · {percent(stats['pca'][0])} de la variación",scale=alt.Scale(domain=[float(np.floor(df.PC1.min())),float(np.ceil(df.PC1.max()))])),
        y=alt.Y('PC2:Q',title=f"PC2 · {percent(stats['pca'][1])} de la variación",scale=alt.Scale(domain=[float(np.floor(df.PC2.min())),float(np.ceil(df.PC2.max()))])),
        color=color, shape=shape, tooltip=tip)
    surface = alt.param(name='superficie',value='Todas')
    style = alt.param(name='estiloFiltro',value='Todos')
    minimum = alt.param(name='minPartidos',value=20)
    search = alt.param(name='busqueda',value='')
    explore = pca.add_params(surface,style,minimum,search).transform_filter(
        "(superficie === 'Todas' || datum.superficie === superficie) && (estiloFiltro === 'Todos' || datum.estilo === estiloFiltro) && datum.partidos >= minPartidos && indexof(lower(datum.nombre), lower(busqueda)) >= 0")
    centroid_data=[]
    for name, g in df.groupby('estilo'):
        for col in LABELS:
            centroid_data.append({'estilo':name,'rasgo':LABELS[col],'z':float(g[col+'_z'].mean())})
    centers_chart=alt.Chart(pd.DataFrame(centroid_data)).mark_point(filled=True,size=90).encode(
        y=alt.Y('rasgo:N',title=None,sort=list(LABELS.values())),x=alt.X('z:Q',title='Desvíos respecto de la superficie',scale=alt.Scale(domain=[-1.5,1.5])),
        color=color,shape=shape,tooltip=['estilo:N','rasgo:N',alt.Tooltip('z:Q',format='+.2f')]).properties(height=280)
    # Datos cambiados desde JavaScript; la gramática de estos gráficos también es Altair.
    distances = alt.Chart(alt.NamedData(name='distancias')).mark_bar().encode(
        y=alt.Y('estilo:N',sort=ORDER,title=None),x=alt.X('distancia:Q',title='Distancia al centro (menor = más parecido)',scale=alt.Scale(zero=True)),color=style_color(),
        tooltip=['estilo:N',alt.Tooltip('distancia:Q',format='.3f')]).properties(height=140)
    comparison = alt.Chart(alt.NamedData(name='comparacion')).mark_point(filled=True,size=80).encode(
        y=alt.Y('rasgo:N',sort=list(LABELS.values()),title=None),x=alt.X('z:Q',title='Desvíos respecto de la superficie',scale=alt.Scale(zero=False)),
        color=alt.Color('serie:N',scale=alt.Scale(domain=['Tu perfil','Centro asignado'],range=['#243D39','#899B93']),legend=alt.Legend(orient='bottom',title=None)),
        shape=alt.Shape('serie:N',scale=alt.Scale(domain=['Tu perfil','Centro asignado'],range=['square','circle']),legend=alt.Legend(orient='bottom',title=None)),tooltip=['rasgo:N','serie:N',alt.Tooltip('z:Q',format='+.2f')]).properties(height=260)
    result={'calidad':quality_chart,'relacion':(relation+regression).properties(height=380),'grupos':pca.properties(height=350),
            'explorar':explore.properties(height=440),'centros':centers_chart,'distancias':distances,'comparacion':comparison}
    return {name:finish(chart.properties(width='container')) for name,chart in result.items()}


def predictive_charts(report):
    legend=alt.Legend(orient='bottom',title=None)
    winrate_scale=alt.Scale(domain=[.2,.8])
    # Cada fila es una condición del partido y adentro se separan los tres estilos.
    base=alt.Chart(pd.DataFrame(report['association_rank'])).encode(
        y=alt.Y('condicion:N',title=None,sort=CONDITIONS),yOffset=alt.YOffset('estilo:N',sort=ORDER),color=style_color(legend))
    interval=base.mark_rule(strokeWidth=3).encode(x=alt.X('lower:Q',scale=winrate_scale,title='Proporción de victorias · test 2023–2025',axis=alt.Axis(format='%')),x2='upper:Q')
    dots=base.mark_point(filled=True,size=120,opacity=1).encode(x=alt.X('winrate:Q',scale=winrate_scale),shape=style_shape(legend),tooltip=[alt.Tooltip('condicion:N',title='Condición'),alt.Tooltip('estilo:N',title='Estilo'),alt.Tooltip('n:Q',format=',.0f',title='Participaciones'),alt.Tooltip('winrate:Q',format='.1%',title='Victorias'),alt.Tooltip('lower:Q',format='.1%',title='IC95 % inferior'),alt.Tooltip('upper:Q',format='.1%',title='IC95 % superior')])
    midpoint=alt.Chart(pd.DataFrame({'x':[.5]})).mark_rule(color='#82948C',strokeDash=[4,4]).encode(x=alt.X('x:Q',scale=winrate_scale))
    short={'Gana el mejor rankeado':'Piso: gana el mejor rankeado','Ranking + contexto':'Ranking + contexto','Ranking + contexto + estilos':'Ranking + contexto + estilos'}
    comparison=pd.DataFrame([{'modelo':n,**report['metrics'][n]} for n in short])
    comparison['modelo_corto']=comparison.modelo.map(short)
    bar=alt.Chart(comparison).mark_bar(color='#294B40',size=28).encode(
        y=alt.Y('modelo_corto:N',title=None,sort=list(short.values())),x=alt.X('accuracy:Q',title='Aciertos en partidos posteriores (2023–2025)',scale=alt.Scale(domain=[0,1]),axis=alt.Axis(format='%')),
        tooltip=['modelo:N',alt.Tooltip('accuracy:Q',format='.2%')])
    labels=bar.mark_text(align='left',dx=8,color='#203B34').encode(text=alt.Text('accuracy:Q',format='.2%'))
    calibration=alt.Chart(pd.DataFrame(report['calibration'])).mark_line(point=True).encode(
        x=alt.X('probabilidad_media:Q',title='Probabilidad predicha media',scale=alt.Scale(domain=[0,1])),
        y=alt.Y('frecuencia_real:Q',title='Frecuencia observada',scale=alt.Scale(domain=[0,1])),
        strokeDash=alt.StrokeDash('modelo:N',legend=alt.Legend(orient='bottom',title=None)),color=alt.value('#294B40'),tooltip=['modelo:N','probabilidad_media:Q','frecuencia_real:Q'])
    diag=alt.Chart(pd.DataFrame({'x':[0,1],'y':[0,1]})).mark_line(color='#A8B3AC').encode(x='x:Q',y='y:Q')
    weights=alt.Chart(pd.DataFrame(report['coefficients'])).encode(
        y=alt.Y('variable:N',title=None,sort=[row['variable'] for row in report['coefficients']]),
        color=alt.Color('bloque:N',title=None,scale=alt.Scale(domain=['Ranking','Estilos'],range=['#243D39','#899B93']),legend=alt.Legend(orient='bottom')))
    weight_bars=weights.mark_bar(size=14).encode(x=alt.X('coef:Q',title='Coeficiente: a la derecha favorece al primero del par',scale=alt.Scale(domain=[-.6,.6])),
        tooltip=['variable:N',alt.Tooltip('coef:Q',format='+.3f',title='Coeficiente')])
    win=alt.Chart(alt.NamedData(name='ganador')).mark_bar(color='#294B40').encode(
        y=alt.Y('jugador:N',title=None),x=alt.X('probabilidad:Q',scale=alt.Scale(domain=[0,1]),axis=alt.Axis(format='%'),title='Probabilidad estimada de victoria'),tooltip=['jugador:N',alt.Tooltip('probabilidad:Q',format='.1%')])
    duel=alt.Chart(alt.NamedData(name='enfrentamiento')).mark_bar(size=24).encode(
        y=alt.Y('metodo:N',title=None,sort=['Ranking + contexto','Estilos · ranking igualado','Ranking + estilos']),
        x=alt.X('probabilidad:Q',title='Probabilidad de ganar · cada fila suma 100 %',stack='zero',scale=alt.Scale(domain=[0,1]),axis=alt.Axis(format='%',values=[0,.25,.5,.75,1])),
        color=alt.Color('lado:N',title='Jugador',scale=SIDES,legend=alt.Legend(orient='bottom')),
        order=alt.Order('lado:O'),tooltip=['metodo:N','jugador:N',alt.Tooltip('probabilidad:Q',format='.1%')])
    duel_profiles=alt.Chart(alt.NamedData(name='rasgos_enfrentamiento')).mark_point(filled=True,size=95).encode(
        y=alt.Y('rasgo:N',title=None,sort=list(LABELS.values())),
        x=alt.X('z:Q',title='Desvíos respecto de la superficie · referencia del modelo',scale=alt.Scale(zero=False)),
        color=alt.Color('lado:N',title='Jugador',scale=SIDES,legend=alt.Legend(orient='bottom')),
        shape=alt.Shape('lado:N',title='Jugador',scale=alt.Scale(domain=['A','B'],range=['circle','square']),legend=alt.Legend(orient='bottom')),tooltip=['jugador:N','rasgo:N',alt.Tooltip('z:Q',format='+.2f'),alt.Tooltip('tasa:Q',format='.1%')])
    return {n:finish(c.properties(width='container',height=h))
            for n,c,h in [('victorias',midpoint+interval+dots,270),('rendimiento',bar+labels,190),('coeficientes',weight_bars,340),('calibracion',diag+calibration,260),('ganador',win,110),('enfrentamiento',duel,190),('rasgos-enfrentamiento',duel_profiles,290)]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--jugadores',type=Path,default=ROOT/'inputs/jugadores.csv')
    parser.add_argument('--config',type=Path,default=ROOT/'inputs/modelo_exacto.json')
    parser.add_argument('--referencia',type=Path,default=ROOT/'inputs/estilos_referencia.csv')
    parser.add_argument('--pipeline',type=Path,help='Carpeta con los CSV del DAG: reentrena y reemplaza inputs/.')
    args=parser.parse_args()
    if args.pipeline: refresh_from_pipeline(args.pipeline.resolve())
    hipotesis=ROOT.parent/'entrega2/resultados/fichas_hipotesis.csv'
    if hipotesis.exists(): shutil.copy2(hipotesis,ROOT/'inputs/hipotesis.csv')
    df,quality,model,stats=prepare(args.jugadores,args.config,args.referencia)
    dist=ROOT/'dist'; dist.mkdir(exist_ok=True)
    for file in (ROOT/'web').iterdir():
        if file.is_file(): shutil.copy2(file,dist/file.name)
        elif file.is_dir(): shutil.copytree(file,dist/file.name,dirs_exist_ok=True)
    write_json(dist/'datos.json',{'profiles':json.loads(df.to_json(orient='records',double_precision=15)), 'model':model,'stats':stats})
    chart_dir=dist/'charts'; chart_dir.mkdir(exist_ok=True)
    for name,spec in charts(df,quality,stats).items(): write_json(chart_dir/f'{name}.json',spec)
    shutil.copy2(ROOT/'inputs/auditoria_versiones.json',dist/'auditoria_versiones.json')
    predictive=ROOT.parent/'entrega3/resultados/prediccion'
    if predictive.exists():
        for name in ['informe.json','modelo_prediccion.json','predicciones_test.csv','victorias_por_estilo.csv','enfrentamientos.json']:
            shutil.copy2(predictive/name,ROOT/'inputs'/name)
    report=json.loads((ROOT/'inputs/informe.json').read_text(encoding='utf-8'))
    write_json(dist/'prediccion.json',{'report':report,'model':json.loads((ROOT/'inputs/modelo_prediccion.json').read_text(encoding='utf-8')),
        'matches':json.loads(pd.read_csv(ROOT/'inputs/predicciones_test.csv').to_json(orient='records',double_precision=15))})
    for name,spec in predictive_charts(report).items():write_json(chart_dir/f'{name}.json',spec)
    shutil.copy2(ROOT/'inputs/predicciones_test.csv',dist/'predicciones_test.csv')
    shutil.copy2(ROOT/'inputs/enfrentamientos.json',dist/'enfrentamientos.json')
    df.to_csv(dist/'perfiles.csv',index=False)
    manifest={'inputs':{p.name:sha(p) for p in [args.jugadores,args.config,args.referencia]},'stats':stats,
              'versions':{'python':sys.version.split()[0],'altair':alt.__version__,'numpy':np.__version__,'pandas':pd.__version__},
              'model':'Estandarización por superficie (ddof=1) + centros K-means E3; sin reentrenamiento',
              'scope':'Mapa descriptivo 2000–2025, evaluación temporal de ganadores y enfrentamientos hipotéticos con perfiles al cierre de 2019–2025.',
              'matchup_catalog':{'sha256':sha(ROOT/'inputs/enfrentamientos.json'),'scope':'Ranking de última aparición registrada del año, no ranking actual.'}}
    write_json(dist/'trazabilidad.json',manifest)
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
