"""
Servidor web de rendimiento para NSP Notebooks.
SQLite + Python puro -- no requiere instalacion extra.
"""

import http.server
import sqlite3
import json
import os
import io
import urllib.parse
import textwrap
import calendar
from datetime import datetime
from socketserver import ThreadingMixIn

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF = None
    FPDF_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BS4_AVAILABLE = False

import csv

DB_PATH = os.path.join(os.path.dirname(__file__), "rendimiento.db")
PORT = 8500

# -- Base de datos -------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("SELECT COUNT(*) FROM empresas")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO empresas (nombre) VALUES ('NSP Notebooks')")
    c.execute("""
        CREATE TABLE IF NOT EXISTS ordenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER NOT NULL,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            fecha TEXT NOT NULL,
            placa TEXT DEFAULT '',
            falla TEXT DEFAULT '',
            diagnostico TEXT DEFAULT '',
            proceso TEXT DEFAULT '',
            solucion TEXT DEFAULT '',
            estado TEXT DEFAULT 'en_curso',
            resultado TEXT DEFAULT 'n/a',
            tipo TEXT DEFAULT '',
            puntaje REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(numero, empresa_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS puntajes (
            tipo TEXT PRIMARY KEY,
            puntaje REAL NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reparaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            orden INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            puntaje REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS circuitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            placa TEXT NOT NULL,
            cantidad INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(codigo, placa)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS soluciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            falla TEXT DEFAULT '',
            solucion TEXT DEFAULT '',
            ics TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS mediciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            placa TEXT NOT NULL,
            pin TEXT NOT NULL,
            nombre TEXT DEFAULT '',
            valor_esperado TEXT DEFAULT '',
            notas TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(codigo, placa, pin)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS mediciones_placa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_placa TEXT NOT NULL,
            punto_medicion TEXT NOT NULL,
            nombre TEXT DEFAULT '',
            valor_esperado TEXT DEFAULT '',
            categoria TEXT DEFAULT '',
            ic_referencia TEXT DEFAULT '',
            notas TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(modelo_placa, punto_medicion)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tipos_equipo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS placas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_placa TEXT NOT NULL UNIQUE,
            tipo_equipo_id INTEGER REFERENCES tipos_equipo(id),
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notas_placa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_placa TEXT NOT NULL,
            contenido TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)
    c.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('valor_punto', '2000')")
    # Migrate: add bloque column to existing tables
    for tbl in ("mediciones_placa", "notas_placa"):
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN bloque TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # ya existe
    # Migrate: add sort_order column to mediciones_placa
    try:
        c.execute("ALTER TABLE mediciones_placa ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Migrate: add sort_order column to notas_placa
    try:
        c.execute("ALTER TABLE notas_placa ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Create bloques_placa table
    c.execute("""
        CREATE TABLE IF NOT EXISTS bloques_placa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_placa TEXT NOT NULL,
            nombre TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            UNIQUE(modelo_placa, nombre)
        )
    """)
    # Populate bloques_placa from existing data
    c.execute("""
        INSERT OR IGNORE INTO bloques_placa (modelo_placa, nombre, sort_order)
        SELECT DISTINCT modelo_placa, bloque, 0 FROM mediciones_placa WHERE bloque != '' AND bloque IS NOT NULL
    """)
    c.execute("""
        INSERT OR IGNORE INTO bloques_placa (modelo_placa, nombre, sort_order)
        SELECT DISTINCT modelo_placa, bloque, 0 FROM notas_placa WHERE bloque != '' AND bloque IS NOT NULL
    """)
    # Initialize sort_order for bloques (based on alphabetical order within each model)
    c.execute("""
        UPDATE bloques_placa SET sort_order = (
            SELECT COUNT(*) FROM bloques_placa b2
            WHERE b2.modelo_placa = bloques_placa.modelo_placa
            AND b2.nombre < bloques_placa.nombre
        ) WHERE sort_order = 0
    """)
    # Initialize sort_order for mediciones (only for legacy items that have NULL)
    # This runs only once; after reordering, sort_order persists across restarts.
    c.execute("""
        UPDATE mediciones_placa SET sort_order = (
            SELECT COUNT(*) FROM mediciones_placa m2
            WHERE m2.modelo_placa = mediciones_placa.modelo_placa
            AND COALESCE(m2.bloque, '') = COALESCE(mediciones_placa.bloque, '')
            AND m2.punto_medicion < mediciones_placa.punto_medicion
        ) WHERE sort_order IS NULL
    """)
    # Initialize sort_order for notas (only for legacy items that have NULL)
    c.execute("""
        UPDATE notas_placa SET sort_order = (
            SELECT COUNT(*) FROM notas_placa n2
            WHERE n2.modelo_placa = notas_placa.modelo_placa
            AND COALESCE(n2.bloque, '') = COALESCE(notas_placa.bloque, '')
            AND n2.created_at > notas_placa.created_at
        ) WHERE sort_order IS NULL
    """)
    # Migrate: add tipo_equipo, marca, modelo to ordenes
    for col in ("tipo_equipo", "marca", "modelo"):
        try:
            c.execute(f"ALTER TABLE ordenes ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    try:
        c.execute("ALTER TABLE ordenes ADD COLUMN checklist TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE ordenes ADD COLUMN resultado TEXT DEFAULT 'n/a'")
    except sqlite3.OperationalError:
        pass
    # Migrate: add estado column to sesiones_reparacion
    try:
        c.execute("ALTER TABLE sesiones_reparacion ADD COLUMN estado TEXT DEFAULT 'finalizada'")
    except sqlite3.OperationalError:
        pass
    # Data migration: map old estado values to new estado+resultado (idempotent)
    c.execute("UPDATE ordenes SET resultado='reparado', estado='completado' WHERE estado='reparado'")
    c.execute("UPDATE ordenes SET resultado='no_reparado', estado='completado' WHERE estado='no_reparado'")
    c.execute("UPDATE ordenes SET resultado='n/a' WHERE resultado IS NULL")
    c.execute("SELECT COUNT(*) FROM tipos_equipo")
    if c.fetchone()[0] == 0:
        for te in ("Notebook", "TV", "Monitor", "Tablet", "Motherboard", "Fuente", "All-in-One"):
            c.execute("INSERT INTO tipos_equipo (nombre) VALUES (?)", (te,))
    c.execute("SELECT COUNT(*) FROM puntajes")
    if c.fetchone()[0] == 0:
        puntajes_default = [
            ("Placa madre", 10.0),
            ("Cambio de placa", 9.0),
            ("Rev. HW Avanzado", 6.0),
            ("Pin de carga", 5.0),
            ("Conectores / USB", 5.0),
            ("Pantalla", 3.0),
            ("Limpieza", 3.0),
            ("Rev. HW Basico", 2.0),
            ("Bateria", 1.0),
            ("Colocacion piezas", 1.0),
            ("Disco / RAM", 1.0),
            ("Otros", 1.0),
            ("Sin Solucion", 0.0),
            ("Garantia", 0.0),
            ("Rotura", -5.0),
        ]
        c.executemany("INSERT INTO puntajes (tipo, puntaje) VALUES (?, ?)", puntajes_default)

    # ── Referencias table ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS referencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL DEFAULT 'Electronica General',
            titulo TEXT NOT NULL,
            contenido_html TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # Insert default categories if empty
    c.execute("SELECT COUNT(*) FROM referencias")
    if c.fetchone()[0] == 0:
        refs_default = [
            ("Electronica General", "MOSFET Canal N (NMOS)",
             """<h4>MOSFET Canal N <span style="font-size:0.7rem;color:var(--muted);font-weight:400">(NMOS)</span></h4>
<div style="display:flex;gap:0.75rem;align-items:flex-start;flex-wrap:wrap">
<svg width="120" height="100" viewBox="0 0 120 100" style="flex-shrink:0">
<line x1="60" y1="5" x2="60" y2="25" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="4" fill="#e0e0e0" font-size="10" font-weight="bold">D</text>
<line x1="60" y1="25" x2="60" y2="60" stroke="#e0e0e0" stroke-width="2"/>
<line x1="56" y1="30" x2="64" y2="34" stroke="#e0e0e0" stroke-width="1.5"/>
<line x1="56" y1="34" x2="64" y2="38" stroke="#e0e0e0" stroke-width="1.5"/>
<line x1="56" y1="38" x2="64" y2="42" stroke="#e0e0e0" stroke-width="1.5"/>
<line x1="60" y1="60" x2="60" y2="65" stroke="#e0e0e0" stroke-width="1.5"/>
<polygon points="56,63 60,68 64,63" fill="#e0e0e0"/>
<line x1="60" y1="25" x2="80" y2="35" stroke="#f0b429" stroke-width="1.5"/>
<line x1="80" y1="35" x2="60" y2="60" stroke="#f0b429" stroke-width="1.5"/>
<polygon points="75,50 68,56 74,58" fill="#f0b429"/>
<line x1="60" y1="68" x2="60" y2="88" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="96" fill="#e0e0e0" font-size="10" font-weight="bold">S</text>
<line x1="45" y1="45" x2="60" y2="45" stroke="#e0e0e0" stroke-width="2"/>
<text x="22" y="42" fill="#e0e0e0" font-size="10" font-weight="bold">G</text>
</svg>
<div style="flex:1;min-width:180px;font-size:0.85rem">
<div style="font-weight:600;color:var(--accent);margin-bottom:0.5rem">Regla: Gate mas positivo que Source</div>
<table style="width:100%;font-size:0.8rem;background:none;margin:0">
<tr><th style="padding:2px 4px">Modo</th><th style="padding:2px 4px">Valor esperado</th></tr>
<tr><td style="padding:2px 4px">D-S apagado</td><td style="padding:2px 4px">&#8734; (circuito abierto)</td></tr>
<tr><td style="padding:2px 4px">D-S encendido</td><td style="padding:2px 4px">0.3&ndash;0.7V (body diode)</td></tr>
<tr><td style="padding:2px 4px">G-S</td><td style="padding:2px 4px">&#8734; o &gt;1M&#937;</td></tr>
<tr><td style="padding:2px 4px">Gate threshold</td><td style="padding:2px 4px">1&ndash;4V para empezar a conducir</td></tr>
</table>
<div style="margin-top:0.5rem;padding:0.4rem;background:var(--redbg);border-radius:0.5rem;font-size:0.8rem">
&#9888; <strong>Corto:</strong> D-S mide 0&#937; = MOSFET quemado<br>
&#9888; <strong>Abierto:</strong> No conduce ni con gate voltage = quemado<br>
&#9888; <strong>Fuga:</strong> Mide resistencia baja entre D-S sin gate voltage
</div></div></div>"""),
            ("Electronica General", "MOSFET Canal P (PMOS)",
             """<h4>MOSFET Canal P <span style="font-size:0.7rem;color:var(--muted);font-weight:400">(PMOS)</span></h4>
<div style="display:flex;gap:0.75rem;align-items:flex-start;flex-wrap:wrap">
<svg width="120" height="100" viewBox="0 0 120 100" style="flex-shrink:0">
<line x1="60" y1="5" x2="60" y2="25" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="4" fill="#e0e0e0" font-size="10" font-weight="bold">S</text>
<line x1="60" y1="25" x2="60" y2="60" stroke="#e0e0e0" stroke-width="2"/>
<circle cx="60" cy="35" r="4" fill="none" stroke="#e0e0e0" stroke-width="1.5"/>
<circle cx="60" cy="42" r="4" fill="none" stroke="#e0e0e0" stroke-width="1.5"/>
<circle cx="60" cy="49" r="4" fill="none" stroke="#e0e0e0" stroke-width="1.5"/>
<line x1="60" y1="60" x2="60" y2="65" stroke="#e0e0e0" stroke-width="1.5"/>
<polygon points="56,63 60,68 64,63" fill="#e0e0e0"/>
<line x1="60" y1="25" x2="80" y2="35" stroke="#f0b429" stroke-width="1.5"/>
<line x1="80" y1="35" x2="60" y2="60" stroke="#f0b429" stroke-width="1.5"/>
<polygon points="75,50 68,56 74,58" fill="#f0b429"/>
<line x1="60" y1="68" x2="60" y2="88" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="96" fill="#e0e0e0" font-size="10" font-weight="bold">D</text>
<line x1="45" y1="45" x2="60" y2="45" stroke="#e0e0e0" stroke-width="2"/>
<text x="22" y="42" fill="#e0e0e0" font-size="10" font-weight="bold">G</text>
</svg>
<div style="flex:1;min-width:180px;font-size:0.85rem">
<div style="font-weight:600;color:var(--accent);margin-bottom:0.5rem">Regla: Gate mas negativo que Source</div>
<table style="width:100%;font-size:0.8rem;background:none;margin:0">
<tr><th style="padding:2px 4px">Modo</th><th style="padding:2px 4px">Valor esperado</th></tr>
<tr><td style="padding:2px 4px">S-D apagado</td><td style="padding:2px 4px">&#8734; (circuito abierto)</td></tr>
<tr><td style="padding:2px 4px">D-S encendido</td><td style="padding:2px 4px">0.3&ndash;0.7V (body diode)</td></tr>
<tr><td style="padding:2px 4px">G-S</td><td style="padding:2px 4px">&#8734; o &gt;1M&#937;</td></tr>
</table>
<div style="margin-top:0.5rem;padding:0.4rem;background:var(--redbg);border-radius:0.5rem;font-size:0.8rem">
&#9888; <strong>Corto:</strong> S-D mide 0&#937; = quemado<br>
&#9888; <strong>Fuga:</strong> Gate a 0V y S-D mide baja resistencia<br>
&#9888; <strong>Abierto:</strong> Gate bajo y no conduce
</div></div></div>"""),
            ("Electronica General", "Transistor NPN (BJT)",
             """<h4>Transistor NPN <span style="font-size:0.7rem;color:var(--muted);font-weight:400">(BJT)</span></h4>
<div style="display:flex;gap:0.75rem;align-items:flex-start;flex-wrap:wrap">
<svg width="120" height="100" viewBox="0 0 120 100" style="flex-shrink:0">
<line x1="60" y1="5" x2="60" y2="28" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="4" fill="#e0e0e0" font-size="10" font-weight="bold">C</text>
<line x1="60" y1="28" x2="60" y2="82" stroke="#e0e0e0" stroke-width="2"/>
<line x1="45" y1="50" x2="60" y2="50" stroke="#e0e0e0" stroke-width="2"/>
<text x="26" y="47" fill="#e0e0e0" font-size="10" font-weight="bold">B</text>
<line x1="60" y1="82" x2="60" y2="90" stroke="#e0e0e0" stroke-width="2"/>
<polygon points="55,85 60,90 65,85" fill="#e0e0e0"/>
<text x="48" y="98" fill="#e0e0e0" font-size="10" font-weight="bold">E</text>
</svg>
<div style="flex:1;min-width:180px;font-size:0.85rem">
<div style="font-weight:600;color:var(--accent);margin-bottom:0.5rem">Regla: Base mas positiva que Emisor (~0.6V)</div>
<table style="width:100%;font-size:0.8rem;background:none;margin:0">
<tr><th style="padding:2px 4px">Medicion</th><th style="padding:2px 4px">Modo diodo</th></tr>
<tr><td style="padding:2px 4px">B&rarr;E</td><td style="padding:2px 4px">0.5&ndash;0.8V (conduce)</td></tr>
<tr><td style="padding:2px 4px">E&rarr;B</td><td style="padding:2px 4px">&#8734; (no conduce)</td></tr>
<tr><td style="padding:2px 4px">B&rarr;C</td><td style="padding:2px 4px">0.5&ndash;0.8V (conduce)</td></tr>
<tr><td style="padding:2px 4px">C&rarr;E</td><td style="padding:2px 4px">&#8734; (no conduce)</td></tr>
</table>
<div style="margin-top:0.5rem;padding:0.4rem;background:var(--redbg);border-radius:0.5rem;font-size:0.8rem">
&#9888; <strong>Corto:</strong> C-E mide 0&#937; o B-C/E mide 0V en diodo<br>
&#9888; <strong>Abierto:</strong> B-E no da caida de diodo (~0V o &#8734;)<br>
&#9888; <strong>Fuga:</strong> B-C o C-E miden baja resistencia
</div></div></div>"""),
            ("Electronica General", "Transistor PNP (BJT)",
             """<h4>Transistor PNP <span style="font-size:0.7rem;color:var(--muted);font-weight:400">(BJT)</span></h4>
<div style="display:flex;gap:0.75rem;align-items:flex-start;flex-wrap:wrap">
<svg width="120" height="100" viewBox="0 0 120 100" style="flex-shrink:0">
<line x1="60" y1="5" x2="60" y2="28" stroke="#e0e0e0" stroke-width="2"/>
<text x="48" y="4" fill="#e0e0e0" font-size="10" font-weight="bold">E</text>
<line x1="60" y1="28" x2="60" y2="82" stroke="#e0e0e0" stroke-width="2"/>
<line x1="45" y1="50" x2="60" y2="50" stroke="#e0e0e0" stroke-width="2"/>
<text x="26" y="47" fill="#e0e0e0" font-size="10" font-weight="bold">B</text>
<line x1="60" y1="82" x2="60" y2="90" stroke="#e0e0e0" stroke-width="2"/>
<polygon points="55,90 60,85 65,90" fill="#e0e0e0"/>
<text x="48" y="98" fill="#e0e0e0" font-size="10" font-weight="bold">C</text>
</svg>
<div style="flex:1;min-width:180px;font-size:0.85rem">
<div style="font-weight:600;color:var(--accent);margin-bottom:0.5rem">Regla: Base mas negativa que Emisor (~0.6V)</div>
<table style="width:100%;font-size:0.8rem;background:none;margin:0">
<tr><th style="padding:2px 4px">Medicion</th><th style="padding:2px 4px">Modo diodo</th></tr>
<tr><td style="padding:2px 4px">E&rarr;B</td><td style="padding:2px 4px">0.5&ndash;0.8V (conduce)</td></tr>
<tr><td style="padding:2px 4px">B&rarr;E</td><td style="padding:2px 4px">&#8734; (no conduce)</td></tr>
<tr><td style="padding:2px 4px">C&rarr;B</td><td style="padding:2px 4px">0.5&ndash;0.8V (conduce)</td></tr>
<tr><td style="padding:2px 4px">C&rarr;E</td><td style="padding:2px 4px">&#8734; (no conduce)</td></tr>
</table>
<div style="margin-top:0.5rem;padding:0.4rem;background:var(--redbg);border-radius:0.5rem;font-size:0.8rem">
&#9888; <strong>Corto:</strong> E-C mide 0&#937; o C-B mide 0V en diodo<br>
&#9888; <strong>Abierto:</strong> E-B no da caida de diodo<br>
&#9888; <strong>Fuga:</strong> Resistencia anormal entre C-E
</div></div></div>"""),
            ("Electronica en Notebooks", "Tips de medicion en placa",
             """<h4>&#128270; Tips de medicion en placa</h4>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:0.75rem;font-size:0.85rem">
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>1. MOSFET en corto:</strong> medi D-S (o S-D) sin energizar. Si da 0&#937; en modo resistencia o pita el continuidad, esta muerto.</div>
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>2. MOSFET con fuga:</strong> medi resistencia D-S. Si da baja (ej: 10&ndash;100&#937;) sin gate voltage, esta con fuga.</div>
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>3. Transistor bipolar:</strong> siempre medi en modo diodo. Si no ves la caida ~0.6V entre B-E o B-C, esta abierto.</div>
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>4. Gate siempre en alta impedancia:</strong> si medi resistencia baja entre gate y source, el MOSFET perdio el oxido de compuerta.</div>
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>5. Carga fantasma:</strong> si una placa consume mas de lo normal y hay MOSFETs que calientan sin tener carga, probablemente uno esta en fuga parcial.</div>
<div style="padding:0.5rem;background:var(--surface);border-radius:0.5rem"><strong>6. Body diode:</strong> la union D-S debe comportarse como un diodo rectificador. Si no da caida en una direccion y en la otra da &#8734;, el MOSFET esta bien.</div>
</div>"""),
            ("Electronica en Notebooks", "VCCGT 1.5V — Siempre 0V en reposo",
             """<h4>VCCGT (1d5v_vccgt) — Graphics Core Voltage</h4>
<p><strong>QUE ES:</strong> Alimentacion especifica del iGPU (graficos integrados del CPU).</p>
<p><strong>COMPORTAMIENTO:</strong></p>
<ul>
<li>Durante POST/BIOS: <strong>0V</strong> — <span style="color:var(--success)">ES NORMAL</span></li>
<li>Con driver de video cargado: ~1.05V-1.3V (varia segun carga)</li>
</ul>
<p><strong>POR QUE ESTA EN 0V:</strong></p>
<ul>
<li>El iGPU comparte VCC_CORE durante el arranque</li>
<li>VCCGT es un riel independiente que solo se activa cuando el SO carga el driver</li>
<li>Si la placa no da video pero backlight funciona: revisar VCC_CORE primero, no VCCGT</li>
</ul>
<p><strong>CONCLUSION:</strong> VCCGT en 0V NO es una falla. Es comportamiento esperado.</p>"""),
        ]
        for cat, tit, html in refs_default:
            c.execute("INSERT INTO referencias (categoria, titulo, contenido_html) VALUES (?, ?, ?)",
                      (cat, tit, html))

    # ── BoardDoctor tables ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS diagramas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL DEFAULT '',
            modelo TEXT NOT NULL DEFAULT '',
            tipo TEXT NOT NULL DEFAULT '',
            gdrive_id TEXT NOT NULL DEFAULT '',
            nombre_archivo TEXT NOT NULL DEFAULT '',
            tamaño_mb REAL DEFAULT 0,
            ultima_sync TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ic_marcas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marking TEXT NOT NULL DEFAULT '',
            modelo TEXT NOT NULL DEFAULT '',
            fabricante TEXT NOT NULL DEFAULT '',
            funcion TEXT NOT NULL DEFAULT '',
            compatibilidad TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ic_compatibilidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabricante TEXT NOT NULL DEFAULT '',
            modelo TEXT NOT NULL DEFAULT '',
            compatibles TEXT NOT NULL DEFAULT ''
        )
    """)
    # Auto-import BoardDoctor data if tables are empty
    conn.commit()  # commit tables first so importar_boarddoctor_data() can see them
    c.execute("SELECT COUNT(*) FROM diagramas")
    if c.fetchone()[0] == 0:
        importar_boarddoctor_data()

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -- Helpers ----------------------------------------------------

def _normalize_estado_resultado(data):
    """Map legacy estado values (reparado, no_reparado) to new (estado, resultado)."""
    data = dict(data)
    estado = data.get("estado", "en_curso")
    resultado = data.get("resultado")
    if resultado is None:
        if estado == "reparado":
            estado, resultado = "completado", "reparado"
        elif estado == "no_reparado":
            estado, resultado = "completado", "no_reparado"
        elif estado == "completado":
            resultado = "n/a"
        else:
            resultado = "n/a"
    data["estado"] = estado
    data["resultado"] = resultado
    return data

# -- API Handlers -------------------------------------------------

class APIHandler:
    @staticmethod
    def listar_meses(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT valor FROM config WHERE clave = 'valor_punto'")
        row = c.fetchone()
        valor_punto = float(row["valor"]) if row else 2000
        c.execute("""
            SELECT strftime('%Y-%m', fecha) as mes,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos_totales
            FROM reparaciones
            GROUP BY mes
            ORDER BY mes DESC
        """)
        meses = [dict(r) for r in c.fetchall()]
        conn.close()
        for m in meses:
            m["ganancia"] = round(m["puntos_totales"] * valor_punto, 2)
        total_puntos = sum(m["puntos_totales"] for m in meses)
        total_ganancia = sum(m["ganancia"] for m in meses)
        return {"meses": meses, "total_puntos": total_puntos, "total_ganancia": total_ganancia}

    @staticmethod
    def listar_ordenes(params):
        mes = params.get("mes", "")
        conn = get_db()
        c = conn.cursor()
        if mes:
            c.execute("""
                SELECT id, fecha, orden, tipo, puntaje
                FROM reparaciones
                WHERE strftime('%Y-%m', fecha) = ?
                ORDER BY fecha DESC, id DESC
            """, (mes,))
        else:
            c.execute("""
                SELECT id, fecha, orden, tipo, puntaje
                FROM reparaciones
                ORDER BY fecha DESC, id DESC
            """)
        ordenes = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"ordenes": ordenes}

    @staticmethod
    def agregar_orden(data):
        fecha = data.get("fecha", datetime.now().strftime("%Y-%m-%d"))
        orden = data.get("orden")
        tipo = data.get("tipo")
        if not orden or not tipo:
            return {"error": "Falta orden o tipo"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT puntaje FROM puntajes WHERE tipo = ?", (tipo,))
        row = c.fetchone()
        if not row:
            return {"error": "Tipo no encontrado"}, 400
        puntaje = row["puntaje"]
        c.execute(
            "INSERT INTO reparaciones (fecha, orden, tipo, puntaje) VALUES (?, ?, ?, ?)",
            (fecha, int(orden), tipo, puntaje)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "id": c.lastrowid}

    @staticmethod
    def eliminar_orden(orden_id):
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM reparaciones WHERE id = ?", (orden_id,))
        if c.rowcount == 0:
            conn.close()
            return {"error": "Orden no encontrada"}, 404
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def listar_puntajes(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT tipo, puntaje FROM puntajes ORDER BY puntaje DESC")
        puntajes = [dict(r) for r in c.fetchall()]
        c.execute("SELECT valor FROM config WHERE clave = 'valor_punto'")
        row = c.fetchone()
        valor_punto = float(row["valor"]) if row else 2000
        conn.close()
        return {"puntajes": puntajes, "valor_punto": valor_punto}

    @staticmethod
    def agregar_puntaje(data):
        tipo = (data.get("tipo") or "").strip().upper()
        puntaje = data.get("puntaje")
        if not tipo: return {"error": "Falta tipo"}, 400
        try:
            puntaje = float(puntaje) if puntaje is not None else 1
        except (ValueError, TypeError):
            return {"error": "Puntaje inválido"}, 400
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO puntajes (tipo, puntaje) VALUES (?, ?)", (tipo, puntaje))
            conn.commit()
            return {"ok": True}
        except sqlite3.IntegrityError:
            return {"error": "Ya existe ese tipo"}, 400
        finally:
            conn.close()

    @staticmethod
    def eliminar_puntaje(data):
        tipo = (data.get("tipo") or "").strip().upper()
        if not tipo: return {"error": "Falta tipo"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM puntajes WHERE tipo = ?", (tipo,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_puntaje(data):
        tipo = (data.get("tipo") or "").strip().upper()
        puntaje = data.get("puntaje")
        if not tipo: return {"error": "Falta tipo"}, 400
        try:
            puntaje = float(puntaje) if puntaje is not None else 1
        except (ValueError, TypeError):
            return {"error": "Puntaje inválido"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE puntajes SET puntaje = ? WHERE tipo = ?", (puntaje, tipo))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_valor_punto(data):
        try:
            valor = float(data.get("valor", 2000))
        except (ValueError, TypeError):
            return {"error": "Valor inválido"}, 400
        if valor <= 0:
            return {"error": "El valor debe ser mayor a 0"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('valor_punto', ?)", (str(valor),))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def listar_tipos(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT tipo FROM puntajes ORDER BY puntaje DESC")
        tipos = [r["tipo"] for r in c.fetchall()]
        conn.close()
        return {"tipos": tipos}

    @staticmethod
    def importar_ordenes(data):
        ordenes = data.get("ordenes", [])
        if not ordenes:
            return {"error": "No hay ordenes"}, 400
        conn = get_db()
        c = conn.cursor()
        importadas = 0
        for o in ordenes:
            fecha = o.get("fecha")
            orden = o.get("orden")
            tipo = o.get("tipo")
            if not all([fecha, orden, tipo]):
                continue
            c.execute("SELECT puntaje FROM puntajes WHERE LOWER(tipo) = LOWER(?)", (tipo,))
            row = c.fetchone()
            puntaje = row["puntaje"] if row else 1
            c.execute("SELECT id FROM reparaciones WHERE orden = ?", (int(orden),))
            if not c.fetchone():
                c.execute(
                    "INSERT INTO reparaciones (fecha, orden, tipo, puntaje) VALUES (?, ?, ?, ?)",
                    (fecha, int(orden), tipo, puntaje)
                )
                importadas += 1
        conn.commit()
        conn.close()
        return {"ok": True, "importadas": importadas}

    # ── Circuitos Integrados ────────────────────────────────
    @staticmethod
    def listar_circuitos(params):
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if q:
            c.execute("""
                SELECT id, codigo, descripcion, placa, cantidad, created_at, info_detallada
                FROM circuitos
                WHERE UPPER(codigo) LIKE ? OR UPPER(descripcion) LIKE ? OR UPPER(placa) LIKE ?
                ORDER BY codigo, placa
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            c.execute("""
                SELECT id, codigo, descripcion, placa, cantidad, created_at, info_detallada
                FROM circuitos
                ORDER BY codigo, placa
            """)
        circuitos = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"circuitos": circuitos}

    @staticmethod
    def agregar_circuito(data):
        codigo = (data.get("codigo") or "").strip().upper()
        placa = (data.get("placa") or "").strip().upper()
        if not codigo or not placa:
            return {"error": "Falta codigo o placa"}, 400
        descripcion = (data.get("descripcion") or "").strip()
        cantidad = int(data.get("cantidad", 1))
        info_detallada = (data.get("info_detallada") or "")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, cantidad FROM circuitos WHERE codigo = ? AND placa = ?", (codigo, placa))
        existing = c.fetchone()
        if existing:
            c.execute("UPDATE circuitos SET cantidad = cantidad + ?, descripcion = COALESCE(NULLIF(?, ''), descripcion), info_detallada = COALESCE(NULLIF(?, ''), info_detallada) WHERE id = ?",
                      (cantidad, descripcion, info_detallada, existing["id"]))
        else:
            c.execute("INSERT INTO circuitos (codigo, descripcion, placa, cantidad, info_detallada) VALUES (?, ?, ?, ?, ?)",
                      (codigo, descripcion, placa, cantidad, info_detallada))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_circuito(data):
        cid = data.get("id")
        if not cid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        updates = []
        vals = []
        for campo in ("codigo", "descripcion", "placa", "cantidad", "info_detallada"):
            if campo in data:
                updates.append(f"{campo} = ?")
                vals.append(data[campo] if campo != "codigo" else data[campo].upper())
        if updates:
            vals.append(cid)
            c.execute(f"UPDATE circuitos SET {', '.join(updates)} WHERE id = ?", vals)
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def eliminar_circuito(data):
        cid = data.get("id")
        if not cid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM circuitos WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Soluciones ──────────────────────────────────────────
    @staticmethod
    def listar_soluciones(params):
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if q:
            c.execute("""
                SELECT id, placa, falla, solucion, ics, created_at
                FROM soluciones
                WHERE UPPER(placa) LIKE ? OR UPPER(falla) LIKE ? OR UPPER(solucion) LIKE ? OR UPPER(ics) LIKE ?
                ORDER BY created_at DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            c.execute("""
                SELECT id, placa, falla, solucion, ics, created_at
                FROM soluciones
                ORDER BY created_at DESC
            """)
        soluciones = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"soluciones": soluciones}

    @staticmethod
    def agregar_solucion(data):
        placa = (data.get("placa") or "").strip().upper()
        if not placa:
            return {"error": "Falta placa"}, 400
        falla = (data.get("falla") or "").strip()
        solucion = (data.get("solucion") or "").strip()
        ics = json.dumps(data.get("ics", []))
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO soluciones (placa, falla, solucion, ics) VALUES (?, ?, ?, ?)",
                  (placa, falla, solucion, ics))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_solucion(data):
        sid = data.get("id")
        if not sid: return {"error": "Falta id"}, 400
        updates = []
        vals = []
        for campo in ("placa", "falla", "solucion"):
            if campo in data:
                updates.append(f"{campo} = ?")
                v = data[campo]
                if campo == "placa": v = v.strip().upper()
                elif isinstance(v, str): v = v.strip()
                vals.append(v)
        if data.get("ics") is not None:
            updates.append("ics = ?")
            vals.append(json.dumps(data["ics"]))
        if updates:
            conn = get_db()
            c = conn.cursor()
            vals.append(sid)
            c.execute(f"UPDATE soluciones SET {', '.join(updates)} WHERE id = ?", vals)
            conn.commit()
            conn.close()
        return {"ok": True}

    @staticmethod
    def eliminar_solucion(data):
        sid = data.get("id")
        if not sid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM soluciones WHERE id = ?", (sid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Empresas ─────────────────────────────────────────────
    @staticmethod
    def listar_empresas(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, nombre, created_at FROM empresas ORDER BY nombre")
        empresas = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"empresas": empresas}

    @staticmethod
    def agregar_empresa(data):
        nombre = (data.get("nombre") or "").strip()
        if not nombre: return {"error": "Falta nombre"}, 400
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO empresas (nombre) VALUES (?)", (nombre,))
            conn.commit()
            return {"ok": True, "id": c.lastrowid}
        except sqlite3.IntegrityError:
            return {"error": "Ya existe esa empresa"}, 400
        finally:
            conn.close()

    @staticmethod
    def eliminar_empresa(data):
        empresa_id = data.get("id")
        if not empresa_id:
            return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM ordenes WHERE empresa_id=?", (empresa_id,))
        count = c.fetchone()[0]
        if count > 0:
            conn.close()
            return {"error": f"No se puede eliminar: tiene {count} orden(es) asociada(s)"}, 400
        c.execute("DELETE FROM empresas WHERE id=?", (empresa_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Órdenes Detalle (reparaciones completas) ────────────
    @staticmethod
    def listar_ordenes_detalle(params):
        empresa_id = params.get("empresa_id", "").strip()
        estado = params.get("estado", "").strip()
        resultado = params.get("resultado", "").strip()
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        sql = """
            SELECT o.id, o.numero, o.empresa_id, e.nombre as empresa_nombre,
                   o.fecha, o.placa, o.falla, o.diagnostico, o.proceso, o.solucion,
                   o.estado, o.resultado, o.tipo, o.puntaje, o.created_at,
                   o.tipo_equipo, o.marca, o.modelo, o.checklist,
                   (SELECT estado FROM sesiones_reparacion WHERE orden_id=o.id AND estado IN ('activa','pausada') ORDER BY inicio DESC LIMIT 1) as sesion_estado
            FROM ordenes o
            JOIN empresas e ON e.id = o.empresa_id
            WHERE 1=1
        """
        vals = []
        if empresa_id:
            sql += " AND o.empresa_id = ?"
            vals.append(int(empresa_id))
        if estado:
            sql += " AND o.estado = ?"
            vals.append(estado)
        if resultado:
            sql += " AND o.resultado = ?"
            vals.append(resultado)
        if q:
            sql += " AND (UPPER(o.placa) LIKE ? OR UPPER(o.falla) LIKE ? OR UPPER(o.solucion) LIKE ? OR CAST(o.numero AS TEXT) LIKE ?)"
            qp = f"%{q}%"
            vals += [qp, qp, qp, qp]
        sql += " ORDER BY o.created_at DESC"
        c.execute(sql, vals)
        ordenes = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"ordenes": ordenes}

    # ── Referencias ───────────────────────────────────────────
    @staticmethod
    def listar_referencias(params):
        categoria = (params.get("categoria") or params.get("cat") or "").strip()
        q = (params.get("q") or "").strip()
        conn = get_db()
        c = conn.cursor()
        if q:
            pat = f"%{q}%"
            if categoria:
                c.execute("SELECT id, categoria, titulo, contenido_html, created_at FROM referencias WHERE categoria = ? AND (titulo LIKE ? OR contenido_html LIKE ?) ORDER BY titulo", (categoria, pat, pat))
            else:
                c.execute("SELECT id, categoria, titulo, contenido_html, created_at FROM referencias WHERE titulo LIKE ? OR contenido_html LIKE ? ORDER BY categoria, titulo", (pat, pat))
        elif categoria:
            c.execute("SELECT id, categoria, titulo, contenido_html, created_at FROM referencias WHERE categoria = ? ORDER BY titulo", (categoria,))
        else:
            c.execute("SELECT id, categoria, titulo, contenido_html, created_at FROM referencias ORDER BY categoria, titulo")
        items = [dict(r) for r in c.fetchall()]
        # Get unique categories
        c.execute("SELECT DISTINCT categoria FROM referencias ORDER BY categoria")
        categorias = [r["categoria"] for r in c.fetchall()]
        conn.close()
        return {"referencias": items, "categorias": categorias}

    @staticmethod
    def obtener_referencia(data):
        ref_id = data.get("id")
        if not ref_id:
            return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, categoria, titulo, contenido_html, created_at FROM referencias WHERE id = ?", (int(ref_id),))
        row = c.fetchone()
        conn.close()
        if not row:
            return {"error": "No encontrada"}, 404
        return {"referencia": dict(row)}

    @staticmethod
    def agregar_referencia(data):
        categoria = (data.get("categoria") or "").strip()
        titulo = (data.get("titulo") or "").strip()
        contenido_html = (data.get("contenido_html") or "").strip()
        if not titulo:
            return {"error": "Falta titulo"}, 400
        if not categoria:
            categoria = "Electronica General"
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO referencias (categoria, titulo, contenido_html) VALUES (?, ?, ?)",
                  (categoria, titulo, contenido_html))
        conn.commit()
        conn.close()
        return {"ok": True, "id": c.lastrowid}

    @staticmethod
    def eliminar_referencia(data):
        ref_id = data.get("id")
        if not ref_id:
            return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM referencias WHERE id = ?", (int(ref_id),))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def agregar_orden_detalle(data):
        numero = data.get("numero")
        empresa_id = data.get("empresa_id")
        fecha = data.get("fecha", datetime.now().strftime("%Y-%m-%d"))
        if not numero or not empresa_id:
            return {"error": "Falta numero o empresa_id"}, 400
        placa = (data.get("placa") or "").strip().upper()
        falla = (data.get("falla") or "").strip()
        diagnostico = (data.get("diagnostico") or "").strip()
        proceso = (data.get("proceso") or "").strip()
        solucion = (data.get("solucion") or "").strip()
        # Normalize legacy estado values
        ndata = _normalize_estado_resultado({"estado": data.get("estado", "en_curso"), "resultado": data.get("resultado")})
        estado = ndata["estado"]
        resultado = ndata["resultado"]
        tipo = (data.get("tipo") or "").strip()
        puntaje = data.get("puntaje", 0)
        if tipo and not puntaje:
            conn2 = get_db()
            try:
                row = conn2.execute("SELECT puntaje FROM puntajes WHERE tipo = ?", (tipo,)).fetchone()
                if row: puntaje = row["puntaje"]
            finally:
                conn2.close()
        tipo_equipo = (data.get("tipo_equipo") or "").strip()
        marca = (data.get("marca") or "").strip()
        modelo_equipo = (data.get("modelo") or "").strip()
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO ordenes (numero, empresa_id, fecha, placa, falla, diagnostico, proceso, solucion, estado, resultado, tipo, puntaje, tipo_equipo, marca, modelo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(numero), int(empresa_id), fecha, placa, falla, diagnostico, proceso, solucion, estado, resultado, tipo, puntaje, tipo_equipo, marca, modelo_equipo))
            conn.commit()
            return {"ok": True, "id": c.lastrowid}
        except sqlite3.IntegrityError:
            return {"error": "Ya existe esa orden para esta empresa"}, 400
        finally:
            conn.close()

    @staticmethod
    def eliminar_orden_detalle(data):
        oid = data.get("id")
        if not oid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM ordenes WHERE id = ?", (oid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_orden_detalle(data):
        oid = data.get("id")
        if not oid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        if data.get("tipo"):
            row = conn.execute("SELECT puntaje FROM puntajes WHERE tipo = ?", (data["tipo"],)).fetchone()
            if row: data["puntaje"] = row["puntaje"]
        # Normalize legacy estado values before update
        data = _normalize_estado_resultado(data)
        updates = []
        vals = []
        for campo in ("placa", "falla", "diagnostico", "proceso", "solucion", "estado", "resultado", "tipo", "puntaje", "tipo_equipo", "marca", "modelo", "checklist"):
            if campo in data:
                updates.append(f"{campo} = ?")
                v = data[campo]
                if campo == "placa": v = v.strip().upper()
                elif isinstance(v, str): v = v.strip()
                vals.append(v)
        if updates:
            vals.append(oid)
            c.execute(f"UPDATE ordenes SET {', '.join(updates)} WHERE id = ?", vals)
            conn.commit()
        conn.close()
        return {"ok": True}

    # ── Mediciones ───────────────────────────────────────────
    @staticmethod
    def listar_mediciones(params):
        codigo = params.get("codigo", "").strip().upper()
        placa = params.get("placa", "").strip().upper()
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if codigo and placa:
            c.execute("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                WHERE codigo = ? AND placa = ?
                ORDER BY pin
            """, (codigo, placa))
        elif q:
            c.execute("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                WHERE UPPER(codigo) LIKE ? OR UPPER(nombre) LIKE ? OR UPPER(placa) LIKE ?
                ORDER BY codigo, placa, pin
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            c.execute("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                ORDER BY codigo, placa, pin
            """)
        mediciones = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"mediciones": mediciones}

    @staticmethod
    def agregar_medicion(data):
        codigo = (data.get("codigo") or "").strip().upper()
        placa = (data.get("placa") or "").strip().upper()
        pin = (data.get("pin") or "").strip()
        if not codigo or not placa or not pin:
            return {"error": "Falta codigo, placa o pin"}, 400
        nombre = (data.get("nombre") or "").strip()
        valor_esperado = (data.get("valor_esperado") or "").strip()
        notas = (data.get("notas") or "").strip()
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO mediciones (codigo, placa, pin, nombre, valor_esperado, notas)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (codigo, placa, pin, nombre, valor_esperado, notas))
        except sqlite3.IntegrityError:
            c.execute("""
                UPDATE mediciones SET nombre=?, valor_esperado=?, notas=?
                WHERE codigo=? AND placa=? AND pin=?
            """, (nombre, valor_esperado, notas, codigo, placa, pin))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def eliminar_medicion(data):
        mid = data.get("id")
        if not mid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM mediciones WHERE id = ?", (mid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Mediciones por Placa ──────────────────────────────────
    @staticmethod
    def listar_mediciones_placa(params):
        modelo = (params.get("modelo") or params.get("modelo_placa") or "").strip().upper()
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if modelo:
            c.execute("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque, checked, created_at, sort_order
                FROM mediciones_placa
                WHERE UPPER(modelo_placa) = ?
                ORDER BY sort_order, punto_medicion
            """, (modelo,))
        elif q:
            c.execute("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque, checked, created_at, sort_order
                FROM mediciones_placa
                WHERE UPPER(modelo_placa) LIKE ? OR UPPER(nombre) LIKE ? OR UPPER(punto_medicion) LIKE ? OR UPPER(ic_referencia) LIKE ?
                ORDER BY modelo_placa, sort_order, punto_medicion
            """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            c.execute("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque, checked, created_at, sort_order
                FROM mediciones_placa
                ORDER BY modelo_placa, sort_order, punto_medicion
            """)
        mediciones = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"mediciones": mediciones}

    @staticmethod
    def agregar_medicion_placa(data):
        modelo_placa = (data.get("modelo_placa") or "").strip().upper()
        punto_medicion = (data.get("punto_medicion") or "").strip()
        if not modelo_placa or not punto_medicion:
            return {"error": "Falta modelo_placa o punto_medicion"}, 400
        nombre = (data.get("nombre") or "").strip()
        valor_esperado = (data.get("valor_esperado") or "").strip()
        categoria = (data.get("categoria") or "").strip()
        ic_referencia = (data.get("ic_referencia") or "").strip()
        notas = (data.get("notas") or "").strip()
        bloque = (data.get("bloque") or "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        # Auto-asignar sort_order: max + 1 dentro del mismo modelo y bloque
        c.execute("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM mediciones_placa
            WHERE modelo_placa = ? AND COALESCE(bloque, '') = ?
        """, (modelo_placa, bloque))
        next_sort = c.fetchone()[0]
        try:
            c.execute("""
                INSERT INTO mediciones_placa (modelo_placa, punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (modelo_placa, punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque, next_sort))
        except sqlite3.IntegrityError:
            c.execute("""
                UPDATE mediciones_placa SET nombre=?, valor_esperado=?, categoria=?, ic_referencia=?, notas=?, bloque=?
                WHERE modelo_placa=? AND punto_medicion=?
            """, (nombre, valor_esperado, categoria, ic_referencia, notas, bloque, modelo_placa, punto_medicion))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_medicion_placa(data):
        mid = data.get("id")
        if not mid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        updates = []
        vals = []
        for campo in ("punto_medicion", "nombre", "valor_esperado", "categoria", "ic_referencia", "notas", "bloque"):
            if campo in data:
                updates.append(f"{campo} = ?")
                v = data[campo]
                if isinstance(v, str): v = v.strip()
                vals.append(v)
        if updates:
            vals.append(mid)
            c.execute(f"UPDATE mediciones_placa SET {', '.join(updates)} WHERE id = ?", vals)
            conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def eliminar_medicion_placa(data):
        mid = data.get("id")
        if not mid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM mediciones_placa WHERE id = ?", (mid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def check_medicion_placa(data):
        mid = data.get("id")
        checked = data.get("checked")
        if not mid: return {"error": "Falta id"}, 400
        val = 1 if checked else 0
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE mediciones_placa SET checked = ? WHERE id = ?", (val, mid))
        conn.commit()
        conn.close()
        return {"ok": True, "checked": bool(val)}

    @staticmethod
    def reset_checklist_placa(data):
        modelo = data.get("modelo_placa")
        if not modelo: return {"error": "Falta modelo_placa"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE mediciones_placa SET checked = 0 WHERE modelo_placa = ?", (modelo,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Tipos de Equipo ────────────────────────────────────────
    @staticmethod
    def listar_tipos_equipo(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, nombre, created_at FROM tipos_equipo ORDER BY nombre")
        tipos = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"tipos": tipos}

    @staticmethod
    def agregar_tipo_equipo(data):
        nombre = (data.get("nombre") or "").strip()
        if not nombre: return {"error": "Falta nombre"}, 400
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO tipos_equipo (nombre) VALUES (?)", (nombre,))
            conn.commit()
            return {"ok": True, "id": c.lastrowid}
        except sqlite3.IntegrityError:
            return {"error": "Ya existe ese tipo de equipo"}, 400
        finally:
            conn.close()

    @staticmethod
    def eliminar_tipo_equipo(data):
        tid = data.get("id")
        if not tid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE placas SET tipo_equipo_id = NULL WHERE tipo_equipo_id = ?", (tid,))
        c.execute("DELETE FROM tipos_equipo WHERE id = ?", (tid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Placas ─────────────────────────────────────────────────
    @staticmethod
    def listar_placas(params):
        q = params.get("q", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if q:
            c.execute("""
                SELECT p.id, p.modelo_placa, p.tipo_equipo_id, t.nombre as tipo_equipo_nombre, p.created_at
                FROM placas p LEFT JOIN tipos_equipo t ON t.id = p.tipo_equipo_id
                WHERE UPPER(p.modelo_placa) LIKE ?
                ORDER BY p.modelo_placa
            """, (f"%{q}%",))
        else:
            c.execute("""
                SELECT p.id, p.modelo_placa, p.tipo_equipo_id, t.nombre as tipo_equipo_nombre, p.created_at
                FROM placas p LEFT JOIN tipos_equipo t ON t.id = p.tipo_equipo_id
                ORDER BY p.modelo_placa
            """)
        placas = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"placas": placas}

    @staticmethod
    def agregar_placa(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        if not modelo: return {"error": "Falta modelo_placa"}, 400
        tipo_id = data.get("tipo_equipo_id")
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO placas (modelo_placa, tipo_equipo_id) VALUES (?, ?)",
                      (modelo, int(tipo_id) if tipo_id else None))
            conn.commit()
            return {"ok": True, "id": c.lastrowid}
        except sqlite3.IntegrityError:
            return {"error": "Ya existe esa placa"}, 400
        finally:
            conn.close()

    @staticmethod
    def eliminar_placa(data):
        pid = data.get("id")
        if not pid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT modelo_placa FROM placas WHERE id = ?", (pid,))
        row = c.fetchone()
        if not row:
            conn.close()
            return {"error": "Placa no encontrada"}, 404
        modelo = row["modelo_placa"]
        c.execute("DELETE FROM notas_placa WHERE modelo_placa = ?", (modelo,))
        c.execute("DELETE FROM mediciones_placa WHERE modelo_placa = ?", (modelo,))
        c.execute("DELETE FROM placas WHERE id = ?", (pid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def actualizar_placa(data):
        pid = data.get("id")
        if not pid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        updates = []
        vals = []
        for campo in ("modelo_placa", "tipo_equipo_id"):
            if campo in data:
                updates.append(f"{campo} = ?")
                v = data[campo]
                if campo == "modelo_placa": v = v.strip().upper()
                vals.append(v)
        if updates:
            vals.append(pid)
            c.execute(f"UPDATE placas SET {', '.join(updates)} WHERE id = ?", vals)
            conn.commit()
        conn.close()
        return {"ok": True}

    # ── Notas de Placa ─────────────────────────────────────────
    @staticmethod
    def listar_notas_placa(params):
        modelo = params.get("modelo_placa", "").strip().upper()
        conn = get_db()
        c = conn.cursor()
        if modelo:
            c.execute("SELECT id, modelo_placa, contenido, bloque, created_at, sort_order FROM notas_placa WHERE modelo_placa = ? ORDER BY sort_order, created_at DESC", (modelo,))
        else:
            c.execute("SELECT id, modelo_placa, contenido, bloque, created_at, sort_order FROM notas_placa ORDER BY sort_order, created_at DESC")
        notas = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"notas": notas}

    @staticmethod
    def agregar_nota_placa(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        contenido = (data.get("contenido") or "").strip()
        bloque = (data.get("bloque") or "").strip().upper()
        if not modelo or not contenido:
            return {"error": "Falta modelo_placa o contenido"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM notas_placa
            WHERE modelo_placa = ? AND COALESCE(bloque, '') = ?
        """, (modelo, bloque))
        next_sort = c.fetchone()[0]
        c.execute("INSERT INTO notas_placa (modelo_placa, contenido, bloque, sort_order) VALUES (?, ?, ?, ?)",
                  (modelo, contenido, bloque, next_sort))
        conn.commit()
        conn.close()
        return {"ok": True, "id": c.lastrowid}

    @staticmethod
    def actualizar_nota_placa(data):
        nid = data.get("id")
        if not nid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        updates = []
        vals = []
        for campo in ("contenido", "bloque"):
            if campo in data:
                updates.append(f"{campo} = ?")
                v = data[campo]
                if isinstance(v, str): v = v.strip()
                vals.append(v)
        if updates:
            vals.append(nid)
            c.execute(f"UPDATE notas_placa SET {', '.join(updates)} WHERE id = ?", vals)
            conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def eliminar_nota_placa(data):
        nid = data.get("id")
        if not nid: return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM notas_placa WHERE id = ?", (nid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @staticmethod
    def renombrar_bloque(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        old = (data.get("old_name") or "").strip().upper()
        new = (data.get("new_name") or "").strip().upper()
        if not modelo or not old or not new:
            return {"error": "Faltan datos"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE mediciones_placa SET bloque = ? WHERE modelo_placa = ? AND bloque = ?", (new, modelo, old))
        c.execute("UPDATE notas_placa SET bloque = ? WHERE modelo_placa = ? AND bloque = ?", (new, modelo, old))
        c.execute("UPDATE bloques_placa SET nombre = ? WHERE modelo_placa = ? AND nombre = ?", (new, modelo, old))
        conn.commit()
        conn.close()
        return {"ok": True, "updated_mediciones": c.rowcount}

    @staticmethod
    def eliminar_bloque(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        name = (data.get("name") or "").strip().upper()
        if not modelo or not name:
            return {"error": "Faltan datos"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE mediciones_placa SET bloque = '' WHERE modelo_placa = ? AND bloque = ?", (modelo, name))
        c.execute("UPDATE notas_placa SET bloque = '' WHERE modelo_placa = ? AND bloque = ?", (modelo, name))
        c.execute("DELETE FROM bloques_placa WHERE modelo_placa = ? AND nombre = ?", (modelo, name))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Bloques CRUD (persistent order) ─────────────────────────
    @staticmethod
    def listar_bloques(params):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, modelo_placa, nombre, sort_order FROM bloques_placa ORDER BY modelo_placa, sort_order, nombre")
        bloques = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"bloques": bloques}

    @staticmethod
    def crear_bloque(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        nombre = (data.get("nombre") or "").strip().upper()
        if not modelo or not nombre:
            return {"error": "Falta modelo_placa o nombre"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM bloques_placa WHERE modelo_placa = ?", (modelo,))
        max_order = c.fetchone()[0]
        try:
            c.execute("INSERT INTO bloques_placa (modelo_placa, nombre, sort_order) VALUES (?, ?, ?)", (modelo, nombre, max_order))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # already exists
        conn.close()
        return {"ok": True}

    @staticmethod
    def _reorder_swap(conn, c, item_id, item_table, sort_order, adj):
        """Swap sort_order between an item and its adjacent (which may be in a different table)."""
        if adj["_t"] == "medicion":
            c.execute("UPDATE mediciones_placa SET sort_order = ? WHERE id = ?", (sort_order, adj["id"]))
        elif adj["_t"] == "nota":
            c.execute("UPDATE notas_placa SET sort_order = ? WHERE id = ?", (sort_order, adj["id"]))
        if item_table == "mediciones_placa":
            c.execute("UPDATE mediciones_placa SET sort_order = ? WHERE id = ?", (adj["sort_order"], item_id))
        else:
            c.execute("UPDATE notas_placa SET sort_order = ? WHERE id = ?", (adj["sort_order"], item_id))
        conn.commit()

    @staticmethod
    def reordenar_medicion_placa(data):
        mid = data.get("id")
        direction = data.get("direction")
        if not mid or direction not in ("up", "down"):
            return {"error": "Falta id o direction"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, modelo_placa, bloque, sort_order FROM mediciones_placa WHERE id = ?", (mid,))
        item = c.fetchone()
        if not item:
            conn.close()
            return {"error": "No encontrado"}, 404
        modelo = item["modelo_placa"]
        bloque = item["bloque"] or ""
        sort_order = item["sort_order"] or 0
        if direction == "up":
            c.execute("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order < ?
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order < ?
                ORDER BY sort_order DESC LIMIT 1
            """, (modelo, bloque, sort_order, modelo, bloque, sort_order))
        else:
            c.execute("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order > ?
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order > ?
                ORDER BY sort_order ASC LIMIT 1
            """, (modelo, bloque, sort_order, modelo, bloque, sort_order))
        adj = c.fetchone()
        if not adj:
            conn.close()
            return {"ok": True, "swapped": False}
        APIHandler._reorder_swap(conn, c, mid, "mediciones_placa", sort_order, adj)
        conn.close()
        return {"ok": True, "swapped": True}

    @staticmethod
    def reordenar_nota_placa(data):
        nid = data.get("id")
        direction = data.get("direction")
        if not nid or direction not in ("up", "down"):
            return {"error": "Falta id o direction"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, modelo_placa, bloque, sort_order FROM notas_placa WHERE id = ?", (nid,))
        item = c.fetchone()
        if not item:
            conn.close()
            return {"error": "No encontrado"}, 404
        modelo = item["modelo_placa"]
        bloque = item["bloque"] or ""
        sort_order = item["sort_order"] or 0
        if direction == "up":
            c.execute("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order < ?
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order < ? AND id != ?
                ORDER BY sort_order DESC LIMIT 1
            """, (modelo, bloque, sort_order, modelo, bloque, sort_order, nid))
        else:
            c.execute("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order > ?
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = ? AND COALESCE(bloque, '') = ? AND sort_order IS NOT NULL AND sort_order > ? AND id != ?
                ORDER BY sort_order ASC LIMIT 1
            """, (modelo, bloque, sort_order, modelo, bloque, sort_order, nid))
        adj = c.fetchone()
        if not adj:
            conn.close()
            return {"ok": True, "swapped": False}
        APIHandler._reorder_swap(conn, c, nid, "notas_placa", sort_order, adj)
        conn.close()
        return {"ok": True, "swapped": True}

    @staticmethod
    def reordenar_bloque(data):
        modelo = (data.get("modelo_placa") or "").strip().upper()
        nombre = (data.get("nombre") or "").strip().upper()
        direction = data.get("direction")
        if not modelo or not nombre or direction not in ("up", "down"):
            return {"error": "Falta modelo_placa, nombre o direction"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, sort_order FROM bloques_placa WHERE modelo_placa = ? AND nombre = ?", (modelo, nombre))
        item = c.fetchone()
        if not item:
            conn.close()
            return {"error": "Bloque no encontrado"}, 404
        sort_order = item["sort_order"] or 0
        if direction == "up":
            c.execute("""
                SELECT id, sort_order FROM bloques_placa
                WHERE modelo_placa = ? AND sort_order IS NOT NULL AND sort_order < ?
                ORDER BY sort_order DESC LIMIT 1
            """, (modelo, sort_order))
        else:
            c.execute("""
                SELECT id, sort_order FROM bloques_placa
                WHERE modelo_placa = ? AND sort_order IS NOT NULL AND sort_order > ?
                ORDER BY sort_order ASC LIMIT 1
            """, (modelo, sort_order))
        adj = c.fetchone()
        if not adj:
            conn.close()
            return {"ok": True, "swapped": False}
        c.execute("UPDATE bloques_placa SET sort_order = ? WHERE id = ?", (adj["sort_order"], item["id"]))
        c.execute("UPDATE bloques_placa SET sort_order = ? WHERE id = ?", (sort_order, adj["id"]))
        conn.commit()
        conn.close()
        return {"ok": True, "swapped": True}

    # ── Reporte detallado ──────────────────────────────────────
    @staticmethod
    def _r_line(c="─", w=62):
        return "  " + c * w + "\n"
    @staticmethod
    def _r_title(text, sep="═", w=62):
        pad = w - len(text) - 2
        if pad < 2: pad = 2
        left = pad // 2
        right = pad - left
        return "  " + sep * left + " " + text + " " + sep * right + "\n"
    @staticmethod
    def _r_section(title, body_lines, w=60):
        """Return a bordered section with title."""
        if not body_lines:
            return ""
        top = "  ┌─ " + title + " " + "─" * (w - 4 - len(title)) + "┐\n"
        mid = ""
        for line in body_lines:
            mid += "  │ " + str(line).ljust(w - 2) + "│\n"
        bot = "  └" + "─" * w + "┘\n\n"
        return top + mid + bot
    @staticmethod
    def _r_wrap(text, w=58):
        if not text:
            return []
        lines = []
        for p in str(text).split("\n"):
            if not p.strip():
                lines.append("")
                continue
            lines.extend(textwrap.wrap(p.strip(), width=w))
        return lines
    @staticmethod
    def _r_table(headers, rows, w=60):
        """Render a simple table, returns list of lines (no borders)."""
        if not rows:
            return []
        # Calculate column widths (simple approach)
        col_w = {}
        n = len(headers)
        avail = w - (n * 3)  # approximate padding
        per_col = max(10, avail // n)
        # Title line
        hdr = "  │ " + " │ ".join(h.ljust(per_col)[:per_col] for h in headers) + " │"
        sep = "  ├" + "─" * (len(hdr) - 4) + "┤"
        lines = [hdr, sep]
        for row in rows:
            vals = [str(v).ljust(per_col)[:per_col] for v in row]
            lines.append("  │ " + " │ ".join(vals) + " │")
        return lines

    @staticmethod
    def generar_reporte_solucion(sid):
        if not sid:
            return {"error": "Falta id"}, 400
        conn = get_db()
        c = conn.cursor()
        w = 62
        wr = 58  # wrap width

        # Try soluciones first
        c.execute("SELECT id, placa, falla, solucion, ics, created_at FROM soluciones WHERE id = ?", (sid,))
        row = c.fetchone()
        if row:
            try:
                ics_list = json.loads(row["ics"]) if row["ics"] else []
            except Exception:
                ics_list = []
            ics_str = ", ".join(ics_list) if ics_list else "—"
            fecha = (row["created_at"][:10] if row["created_at"]
                     else datetime.now().strftime("%Y-%m-%d"))
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            placa = row["placa"]

            lines = []
            lines.append(APIHandler._r_line("█", w))
            lines.append(APIHandler._r_title("INFORME TÉCNICO — SOLUCIÓN", "█", w))
            lines.append(APIHandler._r_line("█", w))
            lines.append("")
            lines.append("  Fecha del informe :  " + now_str)
            lines.append("")

            # ── Board info ──
            lines.append(APIHandler._r_section("PLACA", [
                "Modelo          :  " + placa
            ], w))
            lines.append(APIHandler._r_section("FALLA REPORTADA",
                APIHandler._r_wrap(row["falla"], wr), w))
            lines.append(APIHandler._r_section("SOLUCIÓN APLICADA",
                APIHandler._r_wrap(row["solucion"], wr), w))
            if ics_list:
                lines.append(APIHandler._r_section("CIRCUITOS INTEGRADOS", [
                    ics_str
                ], w))
            lines.append(APIHandler._r_section("FECHA DE CARGA", [fecha], w))

            # ── Mediciones ──
            c.execute(
                "SELECT punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque "
                "FROM mediciones_placa WHERE modelo_placa = ? ORDER BY sort_order, punto_medicion",
                (placa,))
            meds = c.fetchall()
            if meds:
                lines.append(APIHandler._r_title("MEDICIONES DE LA PLACA", "─", w))
                lines.append("")
                # Group by bloque
                current_block = None
                for m in meds:
                    bloque = m["bloque"] or "—"
                    if bloque != current_block:
                        if current_block is not None:
                            lines.append("")
                        lines.append("  ▸ Bloque: " + bloque)
                        lines.append(APIHandler._r_line("·", w - 2))
                        current_block = bloque
                    punto = m["punto_medicion"] or ""
                    nombre = m["nombre"] or ""
                    esperado = m["valor_esperado"] or ""
                    cat = m["categoria"] or ""
                    ic = m["ic_referencia"] or ""
                    notas = m["notas"] or ""
                    lines.append("    " + punto + (" – " + nombre if nombre else ""))
                    if esperado or cat:
                        lines.append("      Valor: " + esperado +
                                     ("  |  " + cat if cat else ""))
                    if ic:
                        lines.append("      IC: " + ic)
                    if notas:
                        for wrapped in APIHandler._r_wrap(notas, wr - 4):
                            lines.append("      " + wrapped)
                lines.append("")

            # ── Notas ──
            c.execute(
                "SELECT contenido, bloque, created_at FROM notas_placa "
                "WHERE modelo_placa = ? ORDER BY sort_order, created_at DESC",
                (placa,))
            notas = c.fetchall()
            if notas:
                lines.append(APIHandler._r_title("NOTAS DE LA PLACA", "─", w))
                lines.append("")
                current_block = None
                for nt in notas:
                    bloque = nt["bloque"] or "—"
                    if bloque != current_block:
                        if current_block is not None:
                            lines.append("")
                        lines.append("  ▸ Bloque: " + bloque)
                        lines.append(APIHandler._r_line("·", w - 2))
                        current_block = bloque
                    for wrapped in APIHandler._r_wrap(nt["contenido"], wr):
                        lines.append("    " + wrapped)
                lines.append("")

            # ── Footer ──
            lines.append(APIHandler._r_line("═", w))
            lines.append("  Generado por :  Sistema de Rendimiento — NSP Notebooks")
            lines.append(APIHandler._r_line("═", w))

            conn.close()
            return {
                "contenido": "\n".join(lines),
                "nombre_archivo": f"informe_{placa.replace('/', '_')}.txt"
            }

        # Try ordenes
        c.execute(
            "SELECT id, numero, placa, falla, diagnostico, solucion, proceso, "
            "created_at FROM ordenes WHERE id = ?", (sid,))
        row = c.fetchone()
        if row:
            fecha = (row["created_at"][:10] if row["created_at"]
                     else datetime.now().strftime("%Y-%m-%d"))
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            placa = row["placa"]
            # Main query done, save data and close this connection
            numero = row["numero"]
            falla = row["falla"]
            diagnostico = row["diagnostico"] or ""
            solucion = row["solucion"]
            proceso = row["proceso"] or ""
            conn.close()

            lines = []
            lines.append(APIHandler._r_line("█", w))
            lines.append(APIHandler._r_title("INFORME TÉCNICO — ORDEN DE TRABAJO", "█", w))
            lines.append(APIHandler._r_line("█", w))
            lines.append("")
            lines.append("  Fecha del informe :  " + now_str)
            lines.append("  N° de orden       :  " + str(numero))
            lines.append("")

            lines.append(APIHandler._r_section("PLACA", [
                "Modelo          :  " + placa
            ], w))
            lines.append(APIHandler._r_section("FALLA REPORTADA",
                APIHandler._r_wrap(falla, wr), w))
            if diagnostico:
                lines.append(APIHandler._r_section("DIAGNÓSTICO",
                    APIHandler._r_wrap(diagnostico, wr), w))
            lines.append(APIHandler._r_section("SOLUCIÓN APLICADA",
                APIHandler._r_wrap(solucion, wr), w))
            if proceso:
                lines.append(APIHandler._r_section("PROCESO",
                    APIHandler._r_wrap(proceso, wr), w))
            lines.append("")
            lines.append(APIHandler._r_section("FECHA DE CARGA", [fecha], w))

            # Open new connection for extra board data
            conn2 = get_db()
            c2 = conn2.cursor()

            # ── Mediciones ──
            c2.execute(
                "SELECT punto_medicion, nombre, valor_esperado, categoria, ic_referencia, notas, bloque "
                "FROM mediciones_placa WHERE modelo_placa = ? ORDER BY sort_order, punto_medicion",
                (placa,))
            meds = c2.fetchall()
            if meds:
                lines.append(APIHandler._r_title("MEDICIONES DE LA PLACA", "─", w))
                lines.append("")
                current_block = None
                for m in meds:
                    bloque = m["bloque"] or "—"
                    if bloque != current_block:
                        if current_block is not None:
                            lines.append("")
                        lines.append("  ▸ Bloque: " + bloque)
                        lines.append(APIHandler._r_line("·", w - 2))
                        current_block = bloque
                    punto = m["punto_medicion"] or ""
                    nombre = m["nombre"] or ""
                    esperado = m["valor_esperado"] or ""
                    cat = m["categoria"] or ""
                    ic_ref = m["ic_referencia"] or ""
                    nts = m["notas"] or ""
                    lines.append("    " + punto + (" – " + nombre if nombre else ""))
                    if esperado or cat:
                        lines.append("      Valor: " + esperado +
                                     ("  |  " + cat if cat else ""))
                    if ic_ref:
                        lines.append("      IC: " + ic_ref)
                    if nts:
                        for wrapped in APIHandler._r_wrap(nts, wr - 4):
                            lines.append("      " + wrapped)
                lines.append("")

            # ── Notas ──
            c2.execute(
                "SELECT contenido, bloque, created_at FROM notas_placa "
                "WHERE modelo_placa = ? ORDER BY sort_order, created_at DESC",
                (placa,))
            notas_rows = c2.fetchall()
            if notas_rows:
                lines.append(APIHandler._r_title("NOTAS DE LA PLACA", "─", w))
                lines.append("")
                current_block = None
                for nt in notas_rows:
                    bloque = nt["bloque"] or "—"
                    if bloque != current_block:
                        if current_block is not None:
                            lines.append("")
                        lines.append("  ▸ Bloque: " + bloque)
                        lines.append(APIHandler._r_line("·", w - 2))
                        current_block = bloque
                    for wrapped in APIHandler._r_wrap(nt["contenido"], wr):
                        lines.append("    " + wrapped)
                lines.append("")

            conn2.close()
            lines.append(APIHandler._r_line("═", w))
            lines.append("  Generado por :  Sistema de Rendimiento — NSP Notebooks")
            lines.append(APIHandler._r_line("═", w))

            return {
                "contenido": "\n".join(lines),
                "nombre_archivo": f"informe_orden_{numero}.txt"
            }

        conn.close()
        return {"error": "Solución no encontrada"}, 404

    @staticmethod
    def buscar(params):
        """Unified search across all data."""
        q = (params.get("q") or "").strip()
        if not q or len(q) < 1:
            return {"error": "Falta término de búsqueda"}, 400
        pat = f"%{q}%"
        conn = get_db()
        c = conn.cursor()
        results = []

        # Soluciones
        c.execute(
            "SELECT id, placa, falla, solucion, created_at FROM soluciones "
            "WHERE placa LIKE ? OR falla LIKE ? OR solucion LIKE ? ORDER BY created_at DESC LIMIT 10",
            (pat, pat, pat))
        for r in c.fetchall():
            results.append({
                "tipo": "solución", "id": r["id"],
                "titulo": r["placa"], "subtitulo": r["falla"][:100],
                "detalle": r["solucion"][:100] if r["solucion"] else ""
            })

        # Órdenes
        c.execute(
            "SELECT id, numero, placa, falla, diagnostico, solucion, proceso FROM ordenes "
            "WHERE placa LIKE ? OR falla LIKE ? OR diagnostico LIKE ? OR solucion LIKE ? OR proceso LIKE ? "
            "ORDER BY id DESC LIMIT 10",
            (pat, pat, pat, pat, pat))
        for r in c.fetchall():
            results.append({
                "tipo": "orden", "id": r["id"],
                "titulo": f"#{r['numero']} — {r['placa']}",
                "subtitulo": r["falla"][:100],
                "detalle": (r["diagnostico"] or r["solucion"] or "")[:100]
            })

        # Mediciones
        c.execute(
            "SELECT modelo_placa, punto_medicion, nombre, valor_esperado, categoria FROM mediciones_placa "
            "WHERE modelo_placa LIKE ? OR punto_medicion LIKE ? OR nombre LIKE ? "
            "ORDER BY modelo_placa, punto_medicion LIMIT 15",
            (pat, pat, pat))
        seen_med = set()
        for r in c.fetchall():
            key = (r["modelo_placa"], r["punto_medicion"])
            if key in seen_med:
                continue
            seen_med.add(key)
            results.append({
                "tipo": "medición", "tab": "puntos-placa",
                "titulo": f"{r['modelo_placa']} — {r['punto_medicion']}",
                "subtitulo": r["nombre"] or "",
                "detalle": f"Esperado: {r['valor_esperado']}" + (f" | {r['categoria']}" if r["categoria"] else "")
            })

        # Notas
        c.execute(
            "SELECT modelo_placa, contenido FROM notas_placa "
            "WHERE modelo_placa LIKE ? OR contenido LIKE ? ORDER BY created_at DESC LIMIT 10",
            (pat, pat))
        seen_nota = set()
        for r in c.fetchall():
            key = (r["modelo_placa"], r["contenido"][:80])
            if key in seen_nota:
                continue
            seen_nota.add(key)
            results.append({
                "tipo": "nota", "tab": "puntos-placa",
                "titulo": r["modelo_placa"],
                "subtitulo": r["contenido"][:120] + ("…" if len(r["contenido"]) > 120 else ""),
                "detalle": ""
            })

        # Referencias
        c.execute(
            "SELECT id, categoria, titulo, substr(contenido_html,1,200) as preview FROM referencias "
            "WHERE titulo LIKE ? OR contenido_html LIKE ? ORDER BY titulo LIMIT 10",
            (pat, pat))
        for r in c.fetchall():
            results.append({
                "tipo": "referencia", "tab": "referencia", "id": r["id"],
                "titulo": r["titulo"],
                "subtitulo": r["categoria"],
                "detalle": r["preview"][:100] if r["preview"] else ""
            })

        conn.close()
        return {"resultados": results}

    # ── Dashboard / Estadísticas ────────────────────────────────
    @staticmethod
    def dashboard(params):
        """Endpoint principal del dashboard. 5 queries en una conexión."""
        conn = get_db()
        c = conn.cursor()

        # valor_punto
        c.execute("SELECT valor FROM config WHERE clave = 'valor_punto'")
        row = c.fetchone()
        valor_punto = float(row["valor"]) if row else 2000

        # 1. Mes actual
        c.execute("""
            SELECT strftime('%Y-%m', fecha) as mes,
                   COUNT(*) as equipos,
                   COUNT(DISTINCT fecha) as dias,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
            GROUP BY mes
        """)
        row = c.fetchone()
        if row:
            mes_actual = dict(row)
            mes_actual["ganancia"] = round(mes_actual["puntos"] * valor_punto, 2)
            parts = mes_actual["mes"].split("-")
            _, days_in_month = calendar.monthrange(int(parts[0]), int(parts[1]))
            mes_actual["promedio_pts_dia"] = round(
                mes_actual["puntos"] / days_in_month, 2) if days_in_month > 0 else 0
            mes_actual["promedio_equipos_dia"] = round(
                mes_actual["equipos"] / mes_actual["dias"], 2) if mes_actual.get("dias", 0) > 0 else 0
        else:
            now = datetime.now()
            _, days_in_month = calendar.monthrange(now.year, now.month)
            mes_actual = {
                "mes": now.strftime("%Y-%m"),
                "equipos": 0, "puntos": 0, "ganancia": 0, "promedio_pts_dia": 0,
                "promedio_equipos_dia": 0
            }

        # 2. Tendencia (últimos 12 meses, orden ASC para running sum)
        c.execute("""
            SELECT strftime('%Y-%m', fecha) as mes,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE fecha >= date('now', '-12 months')
            GROUP BY mes
            ORDER BY mes ASC
        """)
        tendencia = [dict(r) for r in c.fetchall()]
        for t in tendencia:
            t["ganancia"] = round(t["puntos"] * valor_punto, 2)

        # 3. Top 5 tipos
        c.execute("""
            SELECT tipo, COUNT(*) as total, SUM(puntaje) as puntos
            FROM reparaciones
            GROUP BY tipo
            ORDER BY total DESC
            LIMIT 5
        """)
        top_tipos = [dict(r) for r in c.fetchall()]

        # 4. Ganancia acumulada (running sum en Python sobre tendencia ASC)
        ganancia_acumulada = []
        running = 0
        for t in tendencia:
            running += t["ganancia"]
            ganancia_acumulada.append({"mes": t["mes"], "acumulado": round(running, 2)})

        # 5. Resumen anual
        c.execute("""
            SELECT strftime('%Y', fecha) as anio,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE strftime('%Y', fecha) = strftime('%Y', 'now')
            GROUP BY anio
        """)
        row = c.fetchone()
        if row:
            resumen_anual = dict(row)
            resumen_anual["ganancia"] = round(resumen_anual["puntos"] * valor_punto, 2)
        else:
            resumen_anual = {
                "anio": datetime.now().strftime("%Y"),
                "equipos": 0, "puntos": 0, "ganancia": 0
            }

        # 6. Tasa de éxito mensual (últimos 12 meses)
        c.execute("""
            SELECT strftime('%Y-%m', fecha) as mes,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado = 'reparado' THEN 1 ELSE 0 END) as reparados,
                   SUM(CASE WHEN resultado = 'no_reparado' THEN 1 ELSE 0 END) as no_reparados,
                   SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) as en_curso
            FROM ordenes
            WHERE fecha >= date('now', '-12 months')
            GROUP BY mes
            ORDER BY mes ASC
        """)
        tasa_exito_mensual = []
        for r in c.fetchall():
            d = dict(r)
            denom = d["total"] - d["en_curso"]
            d["porcentaje_exito"] = round(d["reparados"] / denom * 100, 2) if denom > 0 else 0
            tasa_exito_mensual.append(d)

        # 7. Tasa de éxito anual
        c.execute("""
            SELECT strftime('%Y', fecha) as anio,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado = 'reparado' THEN 1 ELSE 0 END) as reparados,
                   SUM(CASE WHEN resultado = 'no_reparado' THEN 1 ELSE 0 END) as no_reparados,
                   SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) as en_curso
            FROM ordenes
            GROUP BY anio
            ORDER BY anio DESC
        """)
        row = c.fetchone()
        if row:
            tasa_exito_anual = dict(row)
            denom = tasa_exito_anual["total"] - tasa_exito_anual["en_curso"]
            tasa_exito_anual["porcentaje_exito"] = round(tasa_exito_anual["reparados"] / denom * 100, 2) if denom > 0 else 0
        else:
            tasa_exito_anual = {"anio": "", "total": 0, "reparados": 0, "no_reparados": 0, "en_curso": 0, "porcentaje_exito": 0}

        # 8. Top marcas más reparadas (desde ordenes)
        c.execute("""
            SELECT COALESCE(NULLIF(marca, ''), '—') as marca, COUNT(*) as total
            FROM ordenes
            WHERE marca IS NOT NULL AND marca != ''
            GROUP BY marca
            ORDER BY total DESC
            LIMIT 5
        """)
        top_marcas = [dict(r) for r in c.fetchall()]

        # 9. Top modelos más reparados
        c.execute("""
            SELECT COALESCE(NULLIF(modelo, ''), '—') as modelo, COUNT(*) as total
            FROM ordenes
            WHERE modelo IS NOT NULL AND modelo != ''
            GROUP BY modelo
            ORDER BY total DESC
            LIMIT 5
        """)
        top_modelos = [dict(r) for r in c.fetchall()]

        # 10. Top placas más reparadas
        c.execute("""
            SELECT COALESCE(NULLIF(placa, ''), '—') as placa, COUNT(*) as total
            FROM ordenes
            WHERE placa IS NOT NULL AND placa != ''
            GROUP BY placa
            ORDER BY total DESC
            LIMIT 5
        """)
        top_placas = [dict(r) for r in c.fetchall()]

        conn.close()
        return {
            "mes_actual": mes_actual,
            "tendencia": tendencia,
            "top_tipos": top_tipos,
            "ganancia_acumulada": ganancia_acumulada,
            "resumen_anual": resumen_anual,
            "tasa_exito_mensual": tasa_exito_mensual,
            "tasa_exito_anual": tasa_exito_anual,
            "top_marcas": top_marcas,
            "top_modelos": top_modelos,
            "top_placas": top_placas,
        }

    @staticmethod
    def informe_puntos(params):
        """Endpoint de informe detallado con desglose por tipo, comparativa y TXT."""
        tipo_param = params.get("tipo", "")
        periodo = params.get("periodo", "")

        if tipo_param not in ("mes", "anio"):
            return {"error": "tipo debe ser 'mes' o 'anio'"}, 400

        if tipo_param == "mes":
            if not periodo or len(periodo) != 7 or periodo[4] != "-":
                return {"error": "periodo debe ser YYYY-MM"}, 400
            fmt = "%Y-%m"
        else:
            if not periodo or len(periodo) != 4:
                return {"error": "periodo debe ser YYYY"}, 400
            fmt = "%Y"

        conn = get_db()
        c = conn.cursor()

        # valor_punto
        c.execute("SELECT valor FROM config WHERE clave = 'valor_punto'")
        row = c.fetchone()
        valor_punto = float(row["valor"]) if row else 2000

        # Desglose por tipo
        c.execute(f"""
            SELECT tipo, COUNT(*) as total, SUM(puntaje) as puntos
            FROM reparaciones
            WHERE strftime('{fmt}', fecha) = ?
            GROUP BY tipo
            ORDER BY total DESC
        """, (periodo,))
        desglose = [dict(r) for r in c.fetchall()]

        total_equipos = sum(d["total"] for d in desglose)
        total_puntos = sum(d["puntos"] for d in desglose)
        total_ganancia = round(total_puntos * valor_punto, 2)

        # Período anterior
        if tipo_param == "mes":
            year, month = periodo.split("-")
            y, m = int(year), int(month)
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            prev_periodo = f"{y:04d}-{m:02d}"
        else:
            prev_periodo = str(int(periodo) - 1)

        c.execute(f"""
            SELECT COUNT(*) as equipos, COALESCE(SUM(puntaje), 0) as puntos
            FROM reparaciones
            WHERE strftime('{fmt}', fecha) = ?
        """, (prev_periodo,))
        row = c.fetchone()
        prev_equipos = row["equipos"] if row else 0
        prev_puntos = round(row["puntos"], 2) if row and row["puntos"] else 0
        prev_ganancia = round(prev_puntos * valor_punto, 2)

        comparativa = {
            "periodo_anterior": prev_periodo,
            "equipos": prev_equipos,
            "puntos": prev_puntos,
            "ganancia": prev_ganancia
        }

        # ── TXT content ──
        w = 62
        lines = []
        periodo_label = f"Mes: {periodo}" if tipo_param == "mes" else f"Año: {periodo}"

        lines.append(APIHandler._r_line("█", w))
        lines.append(APIHandler._r_title("INFORME DE PUNTOS", "█", w))
        lines.append(APIHandler._r_line("█", w))
        lines.append("")
        lines.append(f"  Período       :  {periodo_label}")
        lines.append(f"  Valor punto   :  $ {valor_punto:,.0f}")
        lines.append(f"  Total equipos :  {total_equipos}")
        lines.append(f"  Total puntos  :  {total_puntos}")
        lines.append(f"  Ganancia total:  $ {total_ganancia:,.0f}")
        lines.append("")

        if desglose:
            lines.append(APIHandler._r_title("DESGLOSE POR TIPO", "─", w))
            lines.append("")
            table_rows = []
            for d in desglose:
                g = round(d["puntos"] * valor_punto, 2)
                table_rows.append((
                    (d["tipo"][:20] if d["tipo"] else "—"),
                    str(d["total"]),
                    str(int(d["puntos"])),
                    f"${g:,.0f}"
                ))
            for l in APIHandler._r_table(["TIPO", "CANT", "PTS", "GANANCIA"], table_rows, w):
                lines.append(l)
        else:
            lines.append("  No hay reparaciones registradas en este período.")

        lines.append("")
        lines.append(APIHandler._r_title("COMPARATIVA", "─", w))
        lines.append("")
        if prev_equipos > 0:
            dif_pts = int(total_puntos - prev_puntos)
            dif_pct = round((dif_pts / prev_puntos * 100) if prev_puntos > 0 else 0, 1)
            lines.append(f"  Período anterior:  {prev_periodo}")
            lines.append(f"  Equipos         :  {prev_equipos} → {total_equipos}")
            lines.append(f"  Puntos          :  {int(prev_puntos)} → {int(total_puntos)}  ({dif_pts:+d} pts, {dif_pct:+.1f}%)")
            lines.append(f"  Ganancia        :  $ {prev_ganancia:,.0f} → $ {total_ganancia:,.0f}")
        else:
            lines.append(f"  Período anterior:  {prev_periodo}")
            lines.append("  Sin datos en el período anterior.")

        lines.append("")
        lines.append(APIHandler._r_line("═", w))
        lines.append("  Generado por :  Sistema de Rendimiento — NSP Notebooks")
        lines.append(APIHandler._r_line("═", w))

        # ── Detalle de equipos (T-003) ──
        c.execute(f"""
            SELECT r.fecha, r.orden, r.tipo, r.puntaje,
                   COALESCE(o.marca, '') as marca,
                   COALESCE(o.modelo, '') as modelo
            FROM reparaciones r
            LEFT JOIN ordenes o ON r.orden = o.numero
            WHERE strftime('{fmt}', r.fecha) = ?
            ORDER BY r.fecha DESC, r.orden DESC
        """, (periodo,))
        detalle_equipos = [{
            "fecha": r["fecha"],
            "orden": r["orden"],
            "tipo": r["tipo"],
            "puntaje": r["puntaje"],
            "marca": r["marca"],
            "modelo": r["modelo"]
        } for r in c.fetchall()]

        contenido_txt = "\n".join(lines)
        conn.close()

        return {
            "periodo": periodo,
            "tipo": tipo_param,
            "total_equipos": total_equipos,
            "total_puntos": int(total_puntos),
            "total_ganancia": total_ganancia,
            "valor_punto": valor_punto,
            "desglose": desglose,
            "comparativa": comparativa,
            "detalle_equipos": detalle_equipos,
            "contenido_txt": contenido_txt
        }

    # -- Sesiones de reparación --------------------------------------

    @staticmethod
    def iniciar_sesion(data):
        orden_id = data.get("orden_id")
        if not orden_id:
            return {"error": "orden_id requerido"}, 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM ordenes WHERE id=?", (orden_id,))
        if not c.fetchone():
            conn.close()
            return {"error": "orden no encontrada"}, 404
        from datetime import datetime
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Check if there's a PAUSED session for this order
        c.execute("SELECT id, duracion_segundos FROM sesiones_reparacion WHERE orden_id=? AND estado='pausada' ORDER BY inicio DESC LIMIT 1", (orden_id,))
        row = c.fetchone()
        if row:
            # Resume it
            sesion_id, acumulado = row
            c.execute("UPDATE sesiones_reparacion SET estado='activa', inicio=?, fin=NULL WHERE id=?", (ahora, sesion_id))
            conn.commit()
            conn.close()
            return {"ok": True, "id": sesion_id, "inicio": ahora, "duracion_acumulada": acumulado or 0}
        # No paused session, create new
        c.execute("INSERT INTO sesiones_reparacion (orden_id, inicio, estado) VALUES (?, ?, 'activa')", (orden_id, ahora))
        sesion_id = c.lastrowid
        conn.commit()
        conn.close()
        return {"ok": True, "id": sesion_id, "inicio": ahora, "duracion_acumulada": 0}

    @staticmethod
    def pausar_sesion(data):
        sesion_id = data.get("id")
        duracion = data.get("duracion_segundos", 0)
        notas = data.get("notas", "")
        if not sesion_id:
            return {"error": "id requerido"}, 400
        conn = get_db()
        c = conn.cursor()
        from datetime import datetime
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE sesiones_reparacion SET fin=?, duracion_segundos=?, notas=?, estado='pausada' WHERE id=? AND estado='activa'", (ahora, duracion, notas, sesion_id))
        if c.rowcount == 0:
            conn.close()
            return {"error": "sesion no encontrada o ya finalizada"}, 400
        conn.commit()
        conn.close()
        return {"ok": True, "fin": ahora, "duracion_segundos": duracion}

    @staticmethod
    def finalizar_sesion(data):
        sesion_id = data.get("id")
        duracion = data.get("duracion_segundos", 0)
        notas = data.get("notas", "")
        if not sesion_id:
            return {"error": "id requerido"}, 400
        conn = get_db()
        c = conn.cursor()
        from datetime import datetime
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            UPDATE sesiones_reparacion SET fin=?, duracion_segundos=?, notas=?, estado='finalizada'
            WHERE id=?
        """, (ahora, duracion, notas, sesion_id))
        if c.rowcount == 0:
            conn.close()
            return {"error": "sesion no encontrada"}, 400
        conn.commit()
        conn.close()
        return {"ok": True, "fin": ahora}

    @staticmethod
    def listar_sesiones(params):
        orden_id = params.get("orden_id", "")
        conn = get_db()
        c = conn.cursor()
        if orden_id:
            c.execute("SELECT * FROM sesiones_reparacion WHERE orden_id=? ORDER BY inicio DESC", (orden_id,))
        else:
            c.execute("SELECT * FROM sesiones_reparacion ORDER BY inicio DESC LIMIT 50")
        sesiones = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"sesiones": sesiones}

    @staticmethod
    def sesion_pendiente(params):
        """Return the latest non-finalized session (activa or pausada) with calculated total duration."""
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT s.*, o.numero, o.placa
            FROM sesiones_reparacion s
            JOIN ordenes o ON s.orden_id = o.id
            WHERE s.estado IN ('activa', 'pausada')
            ORDER BY s.inicio DESC
            LIMIT 1
        """)
        row = c.fetchone()
        if not row:
            conn.close()
            return {"sesion": None}
        s = dict(row)
        from datetime import datetime
        if s["estado"] == "activa":
            # Calculate elapsed time since session started
            ahora = datetime.now()
            inicio = datetime.strptime(s["inicio"], "%Y-%m-%d %H:%M:%S")
            elapsed = (ahora - inicio).total_seconds()
            s["duracion_total"] = (s["duracion_segundos"] or 0) + int(elapsed)
        else:
            s["duracion_total"] = s["duracion_segundos"] or 0
        conn.close()
        return {"sesion": s}

    @staticmethod
    def tiempos_reparacion(params):
        """Estadisticas de tiempos de reparacion."""
        conn = get_db()
        c = conn.cursor()
        # Tiempo promedio general
        c.execute("""
            SELECT AVG(duracion_segundos) as promedio, COUNT(*) as total
            FROM sesiones_reparacion WHERE duracion_segundos > 0
        """)
        general = dict(c.fetchone())

        # Tiempo promedio por tipo de reparacion
        c.execute("""
            SELECT o.tipo, AVG(s.duracion_segundos) as promedio, COUNT(*) as total
            FROM sesiones_reparacion s
            JOIN ordenes o ON s.orden_id = o.id
            WHERE s.duracion_segundos > 0 AND o.tipo != ''
            GROUP BY o.tipo
            ORDER BY total DESC
        """)
        por_tipo = [dict(r) for r in c.fetchall()]

        conn.close()
        return {
            "promedio_general": round(general["promedio"]) if general["promedio"] else 0,
            "total_sesiones": general["total"],
            "por_tipo": por_tipo
        }

    # ── BoardDoctor Search API ───────────────────────────────────

    @staticmethod
    def buscar_diagramas(params):
        """GET /api/diagramas?q=<texto>"""
        q = (params.get("q") or "").strip()
        if not q or len(q) < 2:
            return {"diagramas": []}
        pat = f"%{q}%"
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT id, marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, ultima_sync
            FROM diagramas
            WHERE modelo LIKE ? OR marca LIKE ? OR nombre_archivo LIKE ?
            ORDER BY modelo ASC LIMIT 50
        """, (pat, pat, pat))
        rows = []
        for r in c.fetchall():
            d = dict(r)
            d["url_descarga"] = f"https://drive.google.com/uc?export=download&id={d['gdrive_id']}" if d["gdrive_id"] else ""
            rows.append(d)
        conn.close()
        return {"diagramas": rows}

    @staticmethod
    def buscar_ic_marca(params):
        """GET /api/ic-marcas?q=<marking>"""
        q = (params.get("q") or "").strip()
        if not q or len(q) < 1:
            return {"resultados": []}
        pat = f"%{q}%"
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT marking, modelo, fabricante, funcion
            FROM ic_marcas
            WHERE marking LIKE ? OR modelo LIKE ?
            ORDER BY marking ASC LIMIT 30
        """, (pat, pat))
        resultados = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"resultados": resultados}

    @staticmethod
    def buscar_ic_compatibles(params):
        """GET /api/ic-compatibles?modelo=<modelo>"""
        q = (params.get("modelo") or "").strip()
        if not q or len(q) < 2:
            return {"resultados": []}
        pat = f"%{q}%"
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT fabricante, modelo as modelo_original, compatibles
            FROM ic_compatibilidad
            WHERE modelo LIKE ? OR fabricante LIKE ?
            ORDER BY modelo ASC LIMIT 20
        """, (pat, pat))
        resultados = [dict(r) for r in c.fetchall()]
        conn.close()
        return {"resultados": resultados}

    @staticmethod
    def buscar_datasheet_externo(params):
        """GET /api/datasheet?componente=<nombre>
        Scrapea alldatasheet.com y datasheet4u.com para obtener URLs de datasheets.
        """
        componente = (params.get("componente") or "").strip()
        if not componente or len(componente) < 2:
            return {"resultados": []}
        resultados = []

        if REQUESTS_AVAILABLE and BS4_AVAILABLE:
            try:
                url_ad = f"https://www.alldatasheet.com/view.jsp?SearchWord={urllib.parse.quote(componente)}"
                resp = requests.get(url_ad, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if resp.ok:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select("a[href*='datasheet']"):
                        href = a.get("href", "")
                        txt = a.get_text(strip=True)
                        if href and txt and componente.lower() in txt.lower():
                            if not href.startswith("http"):
                                href = "https://www.alldatasheet.com" + href
                            resultados.append({"titulo": txt[:120], "url": href, "fuente": "alldatasheet.com"})
                            if len(resultados) >= 5:
                                break
            except Exception as e:
                print(f"[datasheet] alldatasheet error: {e}")

            if not resultados:
                try:
                    url_d4u = f"https://www.datasheet4u.com/search?q={urllib.parse.quote(componente)}"
                    resp = requests.get(url_d4u, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.ok:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for a in soup.select("a[href*='datasheet']"):
                            href = a.get("href", "")
                            txt = a.get_text(strip=True)
                            if href and txt and componente.lower() in txt.lower():
                                if not href.startswith("http"):
                                    href = "https://www.datasheet4u.com" + href
                                resultados.append({"titulo": txt[:120], "url": href, "fuente": "datasheet4u.com"})
                                if len(resultados) >= 5:
                                    break
                except Exception as e:
                    print(f"[datasheet] datasheet4u error: {e}")

        if not resultados:
            resultados.append({"titulo": f"No se encontraron datasheets para '{componente}'", "url": "", "fuente": ""})
        return {"resultados": resultados}

    @staticmethod
    def importar_boarddoctor_api(data):
        """POST /api/importar-boarddoctor — re-importa datos de BoardDoctor."""
        importar_boarddoctor_data()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM diagramas")
        diagramas = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ic_marcas")
        ic_marcas = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ic_compatibilidad")
        ic_comp = c.fetchone()[0]
        conn.close()
        return {"ok": True, "diagramas": diagramas, "ic_marcas": ic_marcas, "ic_compatibilidad": ic_comp}

# -- BoardDoctor Data Import (helper, not in APIHandler) ----------

def importar_boarddoctor_data():
    """Import CSV data from ../boarddoctor_backup/ into DB tables."""
    backup_dir = os.path.join(os.path.dirname(__file__), "..", "boarddoctor_backup")
    if not os.path.isdir(backup_dir):
        print("[boarddoctor] directorio no encontrado:", backup_dir)
        return
    conn = get_db()
    c = conn.cursor()

    # diagramas from cloud_catalog.csv
    csv_path = os.path.join(backup_dir, "cloud_catalog.csv")
    if os.path.isfile(csv_path):
        count = 0
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                marca = (row.get("brand") or "").strip()
                modelo = (row.get("model") or "").strip()
                res_type = (row.get("res_type") or "").strip().lower()
                gdrive_id = (row.get("gdrive_id") or "").strip()
                nombre = (row.get("cloud_filename") or "").strip()
                last_sync = (row.get("last_sync") or "").strip()
                # parse size (CSV has values like "0.12MB")
                size_str = (row.get("file_size") or "0").strip().replace("MB", "").replace(" ", "").replace(",", ".")
                try:
                    size_mb = round(float(size_str), 2)
                except (ValueError, TypeError):
                    size_mb = 0
                tipo = "schematic" if "schematic" in (res_type or "") or "sch" in (res_type or "") else "boardview"
                c.execute("""INSERT OR IGNORE INTO diagramas
                    (marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, ultima_sync)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (marca, modelo, tipo, gdrive_id, nombre, size_mb, last_sync))
                count += 1
        print(f"[boarddoctor] importados {count} diagramas desde cloud_catalog.csv")

    # ic_marcas from ic_catalog.csv
    csv_path = os.path.join(backup_dir, "ic_catalog.csv")
    if os.path.isfile(csv_path):
        count = 0
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                marking = (row.get("marking") or "").strip()
                modelo = (row.get("model") or "").strip()
                fabricante = (row.get("brand") or "").strip()
                funcion = (row.get("function") or "").strip()
                compat = (row.get("compatibility") or "").strip()
                c.execute("""INSERT OR IGNORE INTO ic_marcas
                    (marking, modelo, fabricante, funcion, compatibilidad)
                    VALUES (?, ?, ?, ?, ?)""",
                    (marking, modelo, fabricante, funcion, compat))
                count += 1
        print(f"[boarddoctor] importadas {count} marcas de IC desde ic_catalog.csv")

    # ic_compatibilidad from ic_compatibility.csv
    csv_path = os.path.join(backup_dir, "ic_compatibility.csv")
    if os.path.isfile(csv_path):
        count = 0
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fabricante = (row.get("brand") or "").strip()
                modelo = (row.get("model") or "").strip()
                compatibles = (row.get("compatibles") or "").strip()
                c.execute("""INSERT OR IGNORE INTO ic_compatibilidad
                    (fabricante, modelo, compatibles)
                    VALUES (?, ?, ?)""",
                    (fabricante, modelo, compatibles))
                count += 1
        print(f"[boarddoctor] importadas {count} compatibilidades desde ic_compatibility.csv")

    conn.commit()
    conn.close()

# -- PDF Report (T-002) ------------------------------------------

FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


class PDFReport(FPDF):
    """Professional PDF report for Informe de Puntos."""

    DARK_BLUE = (26, 30, 62)
    LIGHT_GRAY = (245, 245, 245)
    WHITE = (255, 255, 255)
    BLACK = (20, 20, 20)
    MID_GRAY = (180, 180, 180)

    def __init__(self, periodo, valor_punto, tipo_periodo):
        super().__init__()
        self.periodo = periodo
        self.valor_punto = valor_punto
        self.tipo_periodo = tipo_periodo
        self.set_auto_page_break(auto=True, margin=25)
        self._setup_font()
        self.add_page()

    def _setup_font(self):
        """Register Arial (Windows system font) for Unicode support."""
        try:
            self.add_font("Arial", "", FONT_REGULAR)
            self.add_font("Arial", "B", FONT_BOLD)
        except Exception:
            pass  # fallback to Helvetica if Arial not available

    def _use_font(self, style="", size=10):
        key = "arial" + ("B" if style == "B" else "")
        if key in self.fonts:
            self.set_font("Arial", style, size)
        else:
            self.set_font("Helvetica", style, size)

    def header(self):
        self._use_font("B", 10)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        self.rect(0, 0, self.w, 18, "F")
        self.set_y(4)
        periodo_label = f"Mes: {self.periodo}" if self.tipo_periodo == "mes" else f"A\u00f1o: {self.periodo}"
        self.cell(0, 5, "INFORME DE PUNTOS", align="C", new_x="LMARGIN", new_y="NEXT")
        self._use_font("", 7)
        self.cell(0, 4, f"{periodo_label}  |  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self._use_font("", 8)
        self.set_text_color(*self.MID_GRAY)
        self.cell(0, 10, f"Sistema de Rendimiento \u2014 NSP Notebooks | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")

    def build(self, data):
        """Public method: build the full report from API data."""
        detalle = data.get("detalle_equipos", [])
        desglose = data.get("desglose", [])
        comparativa = data.get("comparativa", {})

        if not detalle:
            self._no_data_msg()
        else:
            self._summary_block(data)
            self._equipment_table(detalle)
            if desglose:
                self._type_subtotals(desglose, data["valor_punto"])
            if comparativa:
                self._comparative(comparativa, data)

    def _no_data_msg(self):
        self.ln(20)
        self._use_font("B", 14)
        self.set_text_color(*self.MID_GRAY)
        self.cell(0, 10, "No hay reparaciones registradas en este per\u00edodo", align="C", new_x="LMARGIN", new_y="NEXT")
        self._use_font("", 10)
        self.set_text_color(*self.BLACK)

    def _summary_block(self, data):
        self._use_font("B", 10)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        self.cell(0, 7, "RESUMEN", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self._use_font("", 9)
        self.set_text_color(*self.BLACK)

        items = [
            ("Total equipos", str(data["total_equipos"])),
            ("Total puntos", str(int(data["total_puntos"]))),
            ("Ganancia total", f"${data['total_ganancia']:,.0f}"),
            ("Valor del punto", f"${data['valor_punto']:,.0f}"),
        ]
        for label, value in items:
            self._use_font("", 9)
            self.cell(80, 6, f"  {label}:", new_x="END")
            self._use_font("B", 9)
            self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def _equipment_table(self, rows):
        self._use_font("B", 10)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        self.cell(0, 7, "DETALLE DE EQUIPOS", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

        cols = [("#", 8), ("Fecha", 18), ("N\u00b0 Orden", 18), ("Tipo", 32), ("Puntaje", 14), ("Equipo (Marca/Modelo)", 0)]
        fixed = sum(c[1] for c in cols[:-1]) + 15
        equipo_w = self.w - self.l_margin - self.r_margin - fixed
        col_widths = [8, 18, 18, 32, 14, equipo_w]

        # Header
        self._use_font("B", 7)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        for i, (name, _) in enumerate(cols):
            self.cell(col_widths[i], 6, name, border=1, fill=True, align="C")
        self.ln()

        # Body
        self._use_font("", 7)
        self.set_text_color(*self.BLACK)
        for idx, r in enumerate(rows):
            if self.get_y() > 250:
                self.add_page()
                self._use_font("B", 7)
                self.set_fill_color(*self.DARK_BLUE)
                self.set_text_color(*self.WHITE)
                for i, (name, _) in enumerate(cols):
                    self.cell(col_widths[i], 6, name, border=1, fill=True, align="C")
                self.ln()
                self._use_font("", 7)
                self.set_text_color(*self.BLACK)

            fill = idx % 2 == 1
            self.set_fill_color(*self.LIGHT_GRAY) if fill else self.set_fill_color(*self.WHITE)

            equipo = f"{r.get('marca', '')} / {r.get('modelo', '')}".strip(" /")
            if not equipo:
                equipo = "\u2014"
            row_data = [
                str(idx + 1),
                r.get("fecha", ""),
                str(r.get("orden", "")),
                r.get("tipo", ""),
                str(int(r.get("puntaje", 0))),
                equipo[:40],
            ]
            for i, val in enumerate(row_data):
                self.cell(col_widths[i], 5, val, border=1, fill=fill, align="C" if i < 5 else "L")
            self.ln()

        self.ln(4)

    def _type_subtotals(self, desglose, valor_punto):
        self._use_font("B", 10)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        self.cell(0, 7, "SUBTOTALES POR TIPO", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

        self._use_font("B", 8)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        sw = (self.w - self.l_margin - self.r_margin) / 4
        for h in ["Tipo", "Cantidad", "Puntos", "Ganancia"]:
            self.cell(sw, 6, h, border=1, fill=True, align="C")
        self.ln()

        self._use_font("", 8)
        self.set_text_color(*self.BLACK)
        for idx, d in enumerate(desglose):
            fill = idx % 2 == 1
            self.set_fill_color(*self.LIGHT_GRAY) if fill else self.set_fill_color(*self.WHITE)
            g = round(d["puntos"] * valor_punto, 2)
            row = [d.get("tipo", ""), str(d["total"]), str(int(d["puntos"])), f"${g:,.0f}"]
            for val in row:
                self.cell(sw, 5, val, border=1, fill=fill, align="C")
            self.ln()
        self.ln(4)

    def _comparative(self, comparativa, data):
        self._use_font("B", 10)
        self.set_fill_color(*self.DARK_BLUE)
        self.set_text_color(*self.WHITE)
        self.cell(0, 7, "COMPARATIVA VS PER\u00cdODO ANTERIOR", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

        self._use_font("", 9)
        self.set_text_color(*self.BLACK)
        prev_p = comparativa.get("periodo_anterior", "")
        prev_eq = comparativa.get("equipos", 0)
        prev_pts = int(comparativa.get("puntos", 0))
        prev_gan = comparativa.get("ganancia", 0)
        cur_eq = data["total_equipos"]
        cur_pts = int(data["total_puntos"])
        cur_gan = data["total_ganancia"]

        def diff_str(cur, prev):
            d = cur - prev
            if d > 0:
                return f"\u25b2 +{d}"
            elif d < 0:
                return f"\u25bc {d}"
            return "\u2014 0"

        lines = [
            (f"Per\u00edodo anterior", prev_p),
            (f"Equipos", f"{prev_eq}  \u2192  {cur_eq}   ({diff_str(cur_eq, prev_eq)})"),
            (f"Puntos", f"{prev_pts}  \u2192  {cur_pts}   ({diff_str(cur_pts, prev_pts)})"),
            (f"Ganancia", f"${prev_gan:,.0f}  \u2192  ${cur_gan:,.0f}"),
        ]
        for label, value in lines:
            self._use_font("", 9)
            self.cell(60, 6, f"  {label}:", new_x="END")
            self._use_font("B", 9)
            self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)


# -- HTTP Router -------------------------------------------------

class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server — un request colgado no bloquea los demás."""
    daemon_threads = True


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = dict(urllib.parse.parse_qsl(parsed.query))
            if path == "/api/meses":
                self._json_response(APIHandler.listar_meses(params))
            elif path == "/api/ordenes":
                self._json_response(APIHandler.listar_ordenes(params))
            elif path == "/api/puntajes":
                self._json_response(APIHandler.listar_puntajes(params))
            elif path == "/api/tipos":
                self._json_response(APIHandler.listar_tipos(params))
            elif path == "/api/circuitos":
                self._json_response(APIHandler.listar_circuitos(params))
            elif path == "/api/soluciones":
                self._json_response(APIHandler.listar_soluciones(params))
            elif path.startswith("/api/soluciones/reporte"):
                sid = params.get("id")
                self._json_response(APIHandler.generar_reporte_solucion(sid))
            elif path == "/api/dashboard":
                self._json_response(APIHandler.dashboard(params))
            elif path == "/api/informe-puntos":
                result = APIHandler.informe_puntos(params)
                if isinstance(result, tuple):
                    self._json_response(result[0], result[1])
                else:
                    self._json_response(result)
            elif path == "/api/informe-puntos/pdf":
                result = APIHandler.informe_puntos(params)
                if isinstance(result, tuple):
                    self._json_response(result[0], result[1])
                else:
                    self._pdf_informe_response(result)
            elif path == "/api/buscar":
                self._json_response(APIHandler.buscar(params))
            elif path == "/api/ordenes-detalle":
                self._json_response(APIHandler.listar_ordenes_detalle(params))
            elif path == "/api/mediciones":
                self._json_response(APIHandler.listar_mediciones(params))
            elif path == "/api/mediciones-placa":
                self._json_response(APIHandler.listar_mediciones_placa(params))
            elif path == "/api/notas-placa":
                self._json_response(APIHandler.listar_notas_placa(params))
            elif path == "/api/bloques":
                self._json_response(APIHandler.listar_bloques(params))
            elif path == "/api/placas":
                self._json_response(APIHandler.listar_placas(params))
            elif path == "/api/tipos-equipo":
                self._json_response(APIHandler.listar_tipos_equipo(params))
            elif path == "/api/empresas":
                self._json_response(APIHandler.listar_empresas(params))
            elif path == "/api/referencias":
                self._json_response(APIHandler.listar_referencias(params))
            elif path == "/api/referencias/detalle":
                self._json_response(APIHandler.obtener_referencia(params))
            elif path == "/api/sesiones":
                self._json_response(APIHandler.listar_sesiones(params))
            elif path == "/api/sesiones/tiempos":
                self._json_response(APIHandler.tiempos_reparacion(params))
            elif path == "/api/sesiones/pendiente":
                self._json_response(APIHandler.sesion_pendiente(params))
            elif path == "/api/diagramas":
                self._json_response(APIHandler.buscar_diagramas(params))
            elif path == "/api/ic-marcas":
                self._json_response(APIHandler.buscar_ic_marca(params))
            elif path == "/api/ic-compatibles":
                self._json_response(APIHandler.buscar_ic_compatibles(params))
            elif path == "/api/datasheet":
                self._json_response(APIHandler.buscar_datasheet_externo(params))
            else:
                try:
                    super().do_GET()
                except Exception:
                    self._json_response({"error": "not found"}, 404)
        except Exception as e:
            print(f"[ERROR] do_GET {self.path}: {e}")
            try:
                self._json_response({"error": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b"{}"
            data = json.loads(body) if body else {}
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/api/agregar":
                result = APIHandler.agregar_orden(data)
                status = 200 if result.get("ok") else 400
                self._json_response(result, status)
            elif path == "/api/importar":
                result = APIHandler.importar_ordenes(data)
                status = 200 if result.get("ok") else 400
                self._json_response(result, status)
            elif path == "/api/circuitos":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_circuito(data)
                elif data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_circuito(data)
                else:
                    result = APIHandler.agregar_circuito(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/soluciones":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_solucion(data)
                elif data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_solucion(data)
                else:
                    result = APIHandler.agregar_solucion(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/empresas":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_empresa(data)
                else:
                    result = APIHandler.agregar_empresa(data)
                status = 200 if result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/ordenes-detalle":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_orden_detalle(data)
                elif data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_orden_detalle(data)
                else:
                    result = APIHandler.agregar_orden_detalle(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/mediciones":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_medicion(data)
                else:
                    result = APIHandler.agregar_medicion(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/mediciones-placa":
                if data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_medicion_placa(data)
                elif data.get("_action") == "check":
                    result = APIHandler.check_medicion_placa(data)
                elif data.get("_action") == "reset-checklist":
                    result = APIHandler.reset_checklist_placa(data)
                elif data.get("_action") == "reordenar":
                    result = APIHandler.reordenar_medicion_placa(data)
                elif data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_medicion_placa(data)
                else:
                    result = APIHandler.agregar_medicion_placa(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/tipos-equipo":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_tipo_equipo(data)
                else:
                    result = APIHandler.agregar_tipo_equipo(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/placas":
                if data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_placa(data)
                elif data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_placa(data)
                else:
                    result = APIHandler.agregar_placa(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/notas-placa":
                if data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_nota_placa(data)
                elif data.get("_action") == "reordenar":
                    result = APIHandler.reordenar_nota_placa(data)
                elif data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_nota_placa(data)
                else:
                    result = APIHandler.agregar_nota_placa(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/puntajes":
                if data.get("_action") == "actualizar-valor":
                    result = APIHandler.actualizar_valor_punto(data)
                elif data.get("_action") == "actualizar":
                    result = APIHandler.actualizar_puntaje(data)
                elif data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_puntaje(data)
                else:
                    result = APIHandler.agregar_puntaje(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/bloques":
                if data.get("_action") == "renombrar":
                    result = APIHandler.renombrar_bloque(data)
                elif data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_bloque(data)
                elif data.get("_action") == "reordenar":
                    result = APIHandler.reordenar_bloque(data)
                elif data.get("_action") == "crear":
                    result = APIHandler.crear_bloque(data)
                else:
                    result = {"error": "acción no válida"}, 400
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/referencias":
                if data.get("_method") == "DELETE" or data.get("_action") == "eliminar":
                    result = APIHandler.eliminar_referencia(data)
                else:
                    result = APIHandler.agregar_referencia(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/sesiones/iniciar":
                result = APIHandler.iniciar_sesion(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/sesiones/pausar":
                result = APIHandler.pausar_sesion(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/sesiones/finalizar":
                result = APIHandler.finalizar_sesion(data)
                status = 200 if isinstance(result, dict) and result.get("ok") else (result[1] if isinstance(result, tuple) else 400)
                self._json_response(result, status)
            elif path == "/api/importar-boarddoctor":
                result = APIHandler.importar_boarddoctor_api(data)
                status = 200 if result.get("ok") else 400
                self._json_response(result, status)
            else:
                self._json_response({"error": "ruta no encontrada"}, 404)
        except Exception as e:
            print(f"[ERROR] do_POST {self.path}: {e}")
            try:
                self._json_response({"error": str(e)}, 500)
            except Exception:
                pass

    def do_DELETE(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path.startswith("/api/ordenes/") and path.endswith("/eliminar"):
                try:
                    orden_id = int(path.split("/")[3])
                    result = APIHandler.eliminar_orden(orden_id)
                    status = 200 if result.get("ok") else 404
                    self._json_response(result, status)
                except (ValueError, IndexError):
                    self._json_response({"error": "ID invalido"}, 400)
            else:
                self._json_response({"error": "ruta no encontrada"}, 404)
        except Exception as e:
            print(f"[ERROR] do_DELETE {self.path}: {e}")
            try:
                self._json_response({"error": str(e)}, 500)
            except Exception:
                pass

    def _pdf_informe_response(self, data):
        """Generate and return PDF for informe-puntos data."""
        if not FPDF_AVAILABLE:
            self._json_response({"error": "fpdf2 no está instalado. Ejecutá: pip install fpdf2"}, 500)
            return
        if data.get("error"):
            self._json_response(data, 400)
            return
        try:
            pdf = PDFReport(data["periodo"], data["valor_punto"], data["tipo"])
            pdf.build(data)
            pdf_bytes = bytes(pdf.output())
            periodo = data["periodo"]
            filename = f"informe-puntos_{periodo}.pdf"
            self._binary_response(pdf_bytes, "application/pdf", filename)
        except Exception as e:
            print(f"[ERROR] PDF generation: {e}")
            self._json_response({"error": f"Error al generar PDF: {str(e)}"}, 500)

    def _binary_response(self, bytes_data, content_type, filename):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(bytes_data)))
        self.end_headers()
        self.wfile.write(bytes_data)

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        if len(args) >= 3:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {' '.join(str(a) for a in args)}")

# -- Entry point -------------------------------------------------

if __name__ == "__main__":
    init_db()
    os.chdir(os.path.dirname(__file__))
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    print(f"╔══════════════════════════════════════════╗")
    print(f"║   Rendimiento — Buscador de Diagramas    ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"")
    print(f"  📍 Local:    http://localhost:{PORT}")
    print(f"  🌐 Red:      http://{local_ip}:{PORT}")
    print(f"")
    print(f"  👉 Pasá esta URL de la RED a tus compañeros:")
    print(f"     http://{local_ip}:{PORT}")
    print(f"")
    print(f"  ⚠️  Si es primera vez, Windows Firewall puede")
    print(f"     pedirte permiso — aceptalo.")
    print(f"")
    print(f"Base de datos: {DB_PATH}")
    print("Presiona Ctrl+C para detenerlo.")
    httpd = ThreadingHTTPServer(("", PORT), RequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
