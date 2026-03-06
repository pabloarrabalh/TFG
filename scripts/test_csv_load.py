import logging
logging.disable(logging.CRITICAL)

import os, sys, glob, io, contextlib
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/app')
sys.path.insert(0, '/app')

import django
django.setup()

from main.scrapping.popularDB import procesar_csv_partido, obtener_o_crear_temporada
from main.models import Partido

temp = obtener_o_crear_temporada('23_24')
csvs = sorted(glob.glob('/app/data/temporada_23_24/jornada_*/p*.csv'))

resultado = []
resultado.append(f'Total CSVs 23_24: {len(csvs)}')
resultado.append(f'Partidos antes: {Partido.objects.filter(jornada__temporada=temp).count()}')

ok = 0; fail = 0; errors = []
for csv in csvs[:50]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = procesar_csv_partido(csv, temp)
    out = buf.getvalue().strip()
    if result:
        ok += 1
    else:
        fail += 1
        errors.append(f'{csv}: {out}')

resultado.append(f'OK={ok} FAIL={fail}')
resultado.append(f'Partidos despues: {Partido.objects.filter(jornada__temporada=temp).count()}')
for e in errors[:10]:
    resultado.append(f'  FAIL: {e}')

with open('/tmp/resultado.txt', 'w') as f:
    f.write('\n'.join(resultado))
print('\n'.join(resultado))


