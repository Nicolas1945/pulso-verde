"""O Atraso do Verde - Mato Grosso do Sul.

Versao em Python (API do Earth Engine) do script gee/atraso_do_verde_ms.js.

Uso:
    pip install earthengine-api
    earthengine authenticate
    set EE_PROJECT=seu-projeto-cloud      (Linux/macOS: export EE_PROJECT=...)
    python python/atraso_do_verde_ms.py            # estatisticas + exportacao
    python python/atraso_do_verde_ms.py --sem-export
"""
import json
import os
import sys

import ee

INICIO = '2015-01-01'
FIM = '2025-01-01'             # 10 anos completos
LAGS = [0, 1, 2, 3, 4, 5, 6]   # em passos de 16 dias (0 a 96 dias)
PASSO = 16                     # dias
ESCALA_EXPORT = 1000           # metros
ESCALA_STATS = 5000            # metros


def area_de_estudo():
    return (ee.FeatureCollection('FAO/GAUL/2015/level1')
            .filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
            .filter(ee.Filter.stringStartsWith('ADM1_NAME', 'Mato Grosso'))
            .filter(ee.Filter.stringEndsWith('ADM1_NAME', 'Sul')))


def serie_ndvi():
    def prep(img):
        ok = img.select('SummaryQA').lte(1)  # 0 = bom, 1 = marginal
        return (img.select('NDVI').multiply(0.0001).updateMask(ok)
                .rename('ndvi').copyProperties(img, ['system:time_start']))
    return (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(INICIO, FIM).map(prep))


def correlacao_por_lag(ndvi, chirps, k):
    """Pearson por pixel entre NDVI e a chuva acumulada k passos antes."""
    def par(img):
        img = ee.Image(img)
        t0 = img.date().advance(-k * PASSO, 'day')
        chuva = (chirps.filterDate(t0, t0.advance(PASSO, 'day'))
                 .sum().rename('chuva'))
        return chuva.addBands(img.select('ndvi'))
    corr = (ndvi.map(par).reduce(ee.Reducer.pearsonsCorrelation())
            .select('correlation').rename('corr'))
    lag = ee.Image.constant(k * PASSO).rename('lag_dias')
    return corr.addBands(lag).toFloat()


def main():
    projeto = os.environ.get('EE_PROJECT')
    if not projeto:
        sys.exit('Defina a variavel de ambiente EE_PROJECT com o seu projeto Cloud.')
    ee.Initialize(project=projeto)

    ms = area_de_estudo()
    print('Feicoes de MS (esperado: 1):', ms.size().getInfo(), flush=True)

    chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation')
    ndvi = serie_ndvi()
    print('Imagens NDVI na serie:', ndvi.size().getInfo(), flush=True)

    por_lag = ee.ImageCollection(
        [correlacao_por_lag(ndvi, chirps, k) for k in LAGS])
    # Para cada pixel, fica a defasagem com a maior correlacao
    melhor = por_lag.qualityMosaic('corr').clip(ms)
    atraso = melhor.select('lag_dias')

    if '--sem-export' not in sys.argv:
        task = ee.batch.Export.image.toDrive(
            image=melhor.select(['lag_dias', 'corr']),
            description='atraso_do_verde_MS_2015_2024',
            folder='GEE',
            fileNamePrefix='atraso_do_verde_MS_2015_2024',
            region=ms.geometry(),
            scale=ESCALA_EXPORT,
            crs='EPSG:4326',
            maxPixels=1e10)
        task.start()
        print('Exportacao iniciada. Task id:', task.id, flush=True)

    stats = atraso.reduceRegion(
        reducer=(ee.Reducer.mean()
                 .combine(ee.Reducer.median(), '', True)
                 .combine(ee.Reducer.percentile([10, 90]), '', True)),
        geometry=ms.geometry(), scale=ESCALA_STATS, maxPixels=1e9,
        tileScale=4).getInfo()
    hist = atraso.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=ms.geometry(), scale=ESCALA_STATS, maxPixels=1e9,
        tileScale=4).getInfo()

    saida = {'periodo': [INICIO, FIM], 'escala_m': ESCALA_STATS,
             'estatisticas': stats, 'histograma_pixels': hist['lag_dias']}
    print(json.dumps(saida, indent=1))
    os.makedirs('resultados', exist_ok=True)
    with open('resultados/estatisticas.json', 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=1)


if __name__ == '__main__':
    main()
