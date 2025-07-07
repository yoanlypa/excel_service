# parser.py
import pandas as pd
from io import BytesIO
from .exceptions import ParseError

def parse_excel(content: bytes) -> dict:
    """
    Parsea un archivo Excel y devuelve:
      - general: dict con todos los campos previos a 'Sign'
      - maletas: lista de dicts {excursion, guia, pax, languages, arrival_time}
    """
    try:
        df_full = pd.read_excel(BytesIO(content),
                                sheet_name='Supplier Confirmation',
                                header=None)
    except Exception as e:
        raise ParseError(f"No se pudo leer el Excel: {e}")

    # 1) Encontrar fila de encabezados (col0 == 'Sign')
    sign_rows = df_full.index[df_full.iloc[:,0].astype(str).str.strip() == 'Sign']
    if sign_rows.empty:
        raise ParseError("No encuentro fila de encabezado con 'Sign'.")
    header_idx = sign_rows[0]

    # 2) Metadatos (todas las filas previas, columnas 0 y 1)
    meta_rows = df_full.iloc[1:header_idx, :2]
    general = {}
    for _, row in meta_rows.iterrows():
        key = str(row[0]).strip()
        value = row[1]
        general[key] = str(value) if pd.notna(value) else None
    general['type_servicio'] = 'barco'

    # 3) Cargar tabla de maletas desde header_idx
    bags_df = pd.read_excel(BytesIO(content),
                            sheet_name='Supplier Confirmation',
                            header=header_idx)

    rename_map = {
        'Excursion local name': 'excursion',
        'Guide':                 'guia',
        'Ad':                    'pax',
        'Language':              'languages',
        'Arrival / Meeting time':'arrival_time'
    }
    df = bags_df.rename(columns=rename_map)

    # 4) Validar columnas clave
    required = ['excursion','guia','pax','languages','arrival_time']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ParseError(f"Faltan columnas en maletas: {missing}")

    # 5) Filtrar filas válidas y parsear
    df = df[df['excursion'].notna()]
    maletas = []
    for idx, r in df.iterrows():
        try:
            pax = int(r['pax']) if pd.notna(r['pax']) else 0
        except ValueError:
            raise ParseError(f"Valor de pax inválido en fila {idx}")
        maletas.append({
            'excursion':    r['excursion'].strip(),
            'guia':         (r.get('guia') or '').strip(),
            'pax':          pax,
            'languages':    r['languages'].strip() if pd.notna(r['languages']) else '',
            'arrival_time': r['arrival_time'] if pd.notna(r['arrival_time']) else None
        })

    if not maletas:
        raise ParseError("No se encontraron maletas válidas.")

    return {'general': general, 'maletas': maletas}
