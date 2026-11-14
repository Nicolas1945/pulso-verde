"""Gera figuras/atraso_do_verde_ms.gif: o verde chegando, dia a dia, apos a chuva.

Cada pixel "acende" no dia do seu atraso (a defasagem de maior correlacao
entre chuva e NDVI). Usa o mesmo GeoTIFF de python/figura.py.

Uso:
    pip install rasterio matplotlib numpy pillow
    python python/animacao.py caminho/atraso_do_verde_MS_2015_2024.tif
"""
import io
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import to_rgb
from PIL import Image

from figura import (GRADE, LAGS, MUDO, RAMPA, SECO, SUPERFICIE, TINTA, TINTA2,
                    ler_raster)

FADE = 6            # quadros de transicao por passo
T_FADE = 70         # ms por quadro de transicao
T_PASSO = 900       # ms parado em cada passo
T_INICIO = 1600
T_FIM = 5000


def quadro(lag, fora, b, alfas, pct, titulo_num, legenda, final=False):
    """alfas[i] em [0, 1]: quanto a classe i ja passou de seco para verde."""
    seco = np.array(to_rgb(SECO))
    img = np.zeros(lag.shape + (4,), dtype='float32')
    img[..., :3] = seco
    for v, cor, a in zip(LAGS, RAMPA, alfas):
        if a > 0:
            m = lag == v
            img[m, :3] = (1 - a) * seco + a * np.array(to_rgb(cor))
    img[..., 3] = (~fora).astype('float32')

    fig = plt.figure(figsize=(12, 6.75), dpi=100, facecolor=SUPERFICIE)
    ax = fig.add_axes([0.03, 0.06, 0.52, 0.88])
    lat_m = (b.top + b.bottom) / 2
    ext = [b.left, b.right, b.bottom, b.top]
    ax.imshow(img, interpolation='nearest', extent=ext,
              aspect=1 / np.cos(np.radians(lat_m)))
    ax.contour(np.flipud(fora.astype(float)), levels=[0.5], colors=[TINTA2],
               linewidths=0.7, extent=ext)
    ax.set_axis_off()

    x0 = 0.58
    fig.text(x0, 0.865, 'O Atraso do Verde', fontsize=33, fontweight='bold',
             color=TINTA)
    fig.text(x0, 0.785, 'Quantos dias a vegetação demora para responder\n'
             'à chuva em Mato Grosso do Sul', fontsize=14, color=TINTA2,
             va='center', linespacing=1.35)
    fig.text(x0, 0.60, titulo_num, fontsize=58, fontweight='bold', color=TINTA)
    fig.text(x0, 0.548, legenda, fontsize=13, color=TINTA2)

    axh = fig.add_axes([x0, 0.20, 0.37, 0.27], facecolor=SUPERFICIE)
    xs = np.arange(len(LAGS))
    axh.bar(xs, pct, width=0.72, color=GRADE)                 # trilho
    axh.bar(xs, pct * np.array(alfas), width=0.72, color=RAMPA,
            edgecolor=TINTA2, linewidth=0.5)
    for x, p, a in zip(xs, pct, alfas):
        if a >= 1:
            rot = f'{p:.0f}%' if p >= 1 else '<1%'
            axh.text(x, p + pct.max() * 0.03, rot, ha='center', va='bottom',
                     fontsize=10, color=TINTA2)
    axh.set_xticks(xs)
    axh.set_xticklabels([str(v) for v in LAGS], fontsize=10, color=TINTA2)
    axh.set_xlabel('Dias depois da chuva', fontsize=10, color=MUDO, labelpad=6)
    axh.set_yticks([])
    axh.set_ylim(0, pct.max() * 1.2)
    for lado in ('top', 'right', 'left'):
        axh.spines[lado].set_visible(False)
    axh.spines['bottom'].set_color('#c3c2b7')
    axh.tick_params(axis='x', length=0)
    axh.set_title('Parcela do estado que responde em cada janela',
                  fontsize=11.5, color=TINTA, loc='left', pad=8)

    fig.text(x0, 0.045,
             'NDVI (MODIS MOD13Q1) x chuva de 16 dias (CHIRPS), 2015-2024, grade de 1 km.\n'
             'Atraso = defasagem de maior correlação. Processado no Google Earth Engine.',
             fontsize=8.5, color=MUDO, linespacing=1.45)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=SUPERFICIE)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert('RGB')


def main(tif, saida='figuras/atraso_do_verde_ms.gif'):
    lag, corr, fora, b = ler_raster(tif)
    validos = lag[~fora]
    pct = np.array([100.0 * (validos == v).sum() / validos.size for v in LAGS])
    acum = np.cumsum(pct)
    mediana = float(np.median(validos))

    quadros, tempos = [], []
    n = len(LAGS)
    quadros.append(quadro(lag, fora, b, [0] * n, pct, 'A chuva cai',
                          'e o verde ainda não apareceu'))
    tempos.append(T_INICIO)
    for i, dia in enumerate(LAGS):
        txt = f'{acum[i]:.0f}%' if acum[i] >= 1 else '<1%'
        leg = f'{txt} do estado já respondeu à chuva'
        for f in range(1, FADE + 1):
            alfas = [1] * i + [f / FADE] + [0] * (n - i - 1)
            quadros.append(quadro(lag, fora, b, alfas, pct, f'Dia {dia}', leg))
            tempos.append(T_PASSO if f == FADE else T_FADE)
    quadros.append(quadro(lag, fora, b, [1] * n, pct, f'{mediana:.0f} dias',
                          'atraso mediano entre a chuva e a resposta do NDVI'))
    tempos.append(T_FIM)

    # Paleta unica para todos os quadros (evita cintilacao entre quadros)
    amostra = Image.new('RGB', (quadros[0].width * 2, quadros[0].height))
    amostra.paste(quadros[0], (0, 0))                # tem a cor de 'seco'
    amostra.paste(quadros[-1], (quadros[0].width, 0))  # tem todos os verdes
    base = amostra.quantize(colors=128, method=Image.Quantize.MEDIANCUT,
                                dither=Image.Dither.NONE)
    pal = [q.quantize(palette=base, dither=Image.Dither.NONE) for q in quadros]
    pal[0].save(saida, save_all=True, append_images=pal[1:], duration=tempos,
                loop=0, optimize=False, disposal=1)
    print('GIF salvo em', saida, '-', len(pal), 'quadros')


if __name__ == '__main__':
    main(*sys.argv[1:])
