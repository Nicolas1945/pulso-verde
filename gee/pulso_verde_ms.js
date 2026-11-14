// =====================================================================
// PULSO VERDE - Mato Grosso do Sul
// Quantos dias a vegetacao (NDVI) demora para responder a chuva?
// Dados: CHIRPS Daily (chuva) + MODIS MOD13Q1 v061 (NDVI 16 dias, 250 m)
// Metodo: correlacao de Pearson por pixel entre NDVI e chuva acumulada
//         em janelas de 16 dias, defasadas de 0 a 96 dias. O "atraso"
//         e a defasagem com a maior correlacao.
// Uso: colar em code.earthengine.google.com, clicar em Run e depois
//      iniciar a exportacao na aba Tasks.
// =====================================================================

// ---------------- Parametros ----------------
var INICIO = '2015-01-01';
var FIM = '2025-01-01';            // 10 anos completos
var LAGS = [0, 1, 2, 3, 4, 5, 6];  // em passos de 16 dias (0 a 96 dias)
var PASSO = 16;                    // dias
var ESCALA_EXPORT = 1000;          // metros

// ---------------- Area de estudo ----------------
var ms = ee.FeatureCollection('FAO/GAUL/2015/level1')
  .filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
  .filter(ee.Filter.stringStartsWith('ADM1_NAME', 'Mato Grosso'))
  .filter(ee.Filter.stringEndsWith('ADM1_NAME', 'Sul'));
print('Feicoes de MS (esperado: 1)', ms.size());
Map.centerObject(ms, 6);

// ---------------- Dados ----------------
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
  .select('precipitation');

var ndvi = ee.ImageCollection('MODIS/061/MOD13Q1')
  .filterDate(INICIO, FIM)
  .map(function (img) {
    var ok = img.select('SummaryQA').lte(1); // 0 = bom, 1 = marginal
    return img.select('NDVI').multiply(0.0001).updateMask(ok)
      .rename('ndvi')
      .copyProperties(img, ['system:time_start']);
  });
print('Imagens NDVI na serie', ndvi.size());

// ---------------- Correlacao por defasagem ----------------
function correlacaoPorLag(k) {
  var pares = ndvi.map(function (img) {
    img = ee.Image(img);
    var t0 = img.date().advance(-k * PASSO, 'day');
    var chuva = chirps.filterDate(t0, t0.advance(PASSO, 'day'))
      .sum().rename('chuva');
    return chuva.addBands(img.select('ndvi'));
  });
  var corr = pares.reduce(ee.Reducer.pearsonsCorrelation())
    .select('correlation').rename('corr');
  var lag = ee.Image.constant(k * PASSO).rename('lag_dias');
  return corr.addBands(lag).toFloat();
}

var porLag = ee.ImageCollection(LAGS.map(correlacaoPorLag));

// Para cada pixel, fica a defasagem com a maior correlacao
var melhor = porLag.qualityMosaic('corr').clip(ms);
var atraso = melhor.select('lag_dias');
var corrMax = melhor.select('corr');

// ---------------- Visualizacao ----------------
var paletaAtraso = ['#fff7bc', '#c7e9b4', '#7fcdbb', '#41b6c4',
                    '#1d91c0', '#225ea8', '#0c2c84'];
Map.addLayer(atraso, {min: 0, max: 96, palette: paletaAtraso},
  'Atraso do verde (dias)');
Map.addLayer(corrMax, {min: 0, max: 0.9,
  palette: ['#f7f7f7', '#fdae61', '#d7191c']},
  'Correlacao maxima', false);
Map.addLayer(ee.Image().byte().paint(ms, 1, 2), {palette: '000000'},
  'Limite MS');

// ---------------- Numeros para o post ----------------
var stats = atraso.reduceRegion({
  reducer: ee.Reducer.mean()
    .combine(ee.Reducer.median(), '', true)
    .combine(ee.Reducer.percentile([10, 90]), '', true),
  geometry: ms.geometry(),
  scale: 5000,
  maxPixels: 1e9,
  tileScale: 4
});
print('Atraso em MS (dias): media, mediana, p10, p90', stats);

print(ui.Chart.image.histogram({
  image: atraso,
  region: ms.geometry(),
  scale: 5000,
  maxPixels: 1e9
}).setOptions({
  title: 'Distribuicao do atraso do verde em MS',
  hAxis: {title: 'Dias entre a chuva e a resposta do NDVI'},
  vAxis: {title: 'Pixels'},
  legend: {position: 'none'}
}));

// ---------------- Exportacao ----------------
Export.image.toDrive({
  image: melhor.select(['lag_dias', 'corr']),
  description: 'pulso_verde_MS_2015_2024',
  folder: 'GEE',
  fileNamePrefix: 'pulso_verde_MS_2015_2024',
  region: ms.geometry(),
  scale: ESCALA_EXPORT,
  crs: 'EPSG:4326',
  maxPixels: 1e10
});
