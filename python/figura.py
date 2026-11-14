"""Gera figuras/atraso_do_verde_ms.png a partir do GeoTIFF exportado pelo GEE.

Uso:
    pip install rasterio matplotlib numpy
    python python/figura.py caminho/atraso_do_verde_MS_2015_2024.tif
"""
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap

LAGS = [0, 16, 32, 48, 64, 80, 96]
# Rampa sequencial de um unico matiz (claro = resposta rapida, escuro = lenta)
RAMPA = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
SUPERFICIE = '#fcfcfb'
TINTA = '#0b0b0b'
TINTA2 = '#52514e'
MUDO = '#898781'
GRADE = '#e1e0d9'
BARRA = '#2a78d6'

plt.rcParams['font.family'] = ['Segoe UI', 'DejaVu Sans', 'sans-serif']


def main(tif, saida='figuras/atraso_do_verde_ms.png'):
    with rasterio.open(tif) as src:
        lag = src.read(1).astype('float32')
        corr = src.read(2).astype('float32')
        b = src.bounds
    # Fora do limite de MS o GeoTIFF vem com 0 nas duas bandas (ou NaN)
    fora = ~np.isfinite(corr) | ~np.isfinite(lag) | ((corr == 0) & (lag == 0))
    lag_m = np.ma.masked_where(fora, lag)
    validos = lag[~fora]

    contagem = np.array([(validos == v).sum() for v in LAGS], dtype=float)
    pct = 100 * contagem / contagem.sum()
    mediana = float(np.median(validos))
    media = float(validos.mean())
    resumo = {'pixels_validos_1km': int(contagem.sum()), 'mediana_dias': mediana,
              'media_dias': round(media, 2),
              'pct_por_atraso': {str(v): round(float(p), 2) for v, p in zip(LAGS, pct)},
              'corr_max_mediana': round(float(np.median(corr[~fora])), 3)}
    print(json.dumps(resumo, indent=1))
    with open('resultados/resumo_1km.json', 'w', encoding='utf-8') as f:
        json.dump(resumo, f, indent=1)

    fig = plt.figure(figsize=(16, 9), dpi=120, facecolor=SUPERFICIE)

    # ---------------- Mapa ----------------
    ax = fig.add_axes([0.03, 0.06, 0.52, 0.88])
    cmap = ListedColormap(RAMPA)
    norm = BoundaryNorm([v - 8 for v in LAGS] + [104], cmap.N)
    lat_m = (b.top + b.bottom) / 2
    ax.imshow(lag_m, cmap=cmap, norm=norm, interpolation='nearest',
              extent=[b.left, b.right, b.bottom, b.top],
              aspect=1 / np.cos(np.radians(lat_m)))
    ax.contour(np.flipud(fora.astype(float)), levels=[0.5], colors=[TINTA2],
               linewidths=0.8, extent=[b.left, b.right, b.bottom, b.top])
    ax.set_axis_off()

    # ---------------- Texto ----------------
    x0 = 0.58
    fig.text(x0, 0.875, 'O Atraso do Verde', fontsize=44, fontweight='bold',
             color=TINTA)
    fig.text(x0, 0.80, 'Quantos dias a vegetação demora para responder\n'
             'à chuva em Mato Grosso do Sul', fontsize=19, color=TINTA2,
             va='center', linespacing=1.35)
    fig.text(x0, 0.615, f'{mediana:.0f} dias', fontsize=76, fontweight='bold',
             color=TINTA)
    fig.text(x0, 0.565, 'atraso mediano entre a chuva e a resposta do NDVI',
             fontsize=16, color=TINTA2)

    # ---------------- Histograma (tambem serve de legenda do mapa) ----------
    axh = fig.add_axes([x0, 0.215, 0.37, 0.265], facecolor=SUPERFICIE)
    xs = np.arange(len(LAGS))
    axh.bar(xs, pct, width=0.72, color=RAMPA, edgecolor=TINTA2, linewidth=0.6)
    for x, p in zip(xs, pct):
        rot = f'{p:.0f}%' if p >= 1 else '<1%'
        axh.text(x, p + pct.max() * 0.025, rot, ha='center', va='bottom',
                 fontsize=13, color=TINTA2)
    axh.set_xticks(xs)
    axh.set_xticklabels([str(v) for v in LAGS], fontsize=13, color=TINTA2)
    axh.set_xlabel('Atraso (dias)  ·  mesmas cores do mapa', fontsize=13,
                   color=MUDO, labelpad=8)
    axh.set_yticks([])
    axh.set_ylim(0, pct.max() * 1.18)
    for lado in ('top', 'right', 'left'):
        axh.spines[lado].set_visible(False)
    axh.spines['bottom'].set_color('#c3c2b7')
    axh.tick_params(axis='x', length=0)
    axh.set_title('Parcela do estado por atraso', fontsize=15, color=TINTA,
                  loc='left', pad=10)

    fig.text(x0, 0.04,
             'Correlação de Pearson por pixel entre NDVI (MODIS MOD13Q1, 250 m) e chuva\n'
             'acumulada em 16 dias (CHIRPS), defasada de 0 a 96 dias. 2015-2024, grade de 1 km.\n'
             'O atraso é a defasagem com a maior correlação. Processado no Google Earth Engine.',
             fontsize=11, color=MUDO, linespacing=1.45)

    fig.savefig(saida, facecolor=SUPERFICIE)
    print('Figura salva em', saida)


if __name__ == '__main__':
    main(*sys.argv[1:])
