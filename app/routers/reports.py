"""
Reports router — Informe de puntos with desglose/comparativa + PDF (weasyprint).

Replicates server.py APIHandler: informe_puntos + PDFReport.
Uses weasyprint for cross-platform PDF generation.
"""

import textwrap
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.user import User

router = APIRouter(prefix="/api/reports", tags=["reports"])

# ── Format mapping ────────────────────────────────────────────────────────
# SQLite strftime → PostgreSQL TO_CHAR format mapping
_PG_FORMATS = {"%Y-%m": "YYYY-MM", "%Y": "YYYY"}


# ── TXT helpers ─────────────────────────────────────────────────────────


def _r_line(c: str = "─", w: int = 62) -> str:
    return "  " + c * w + "\n"


def _r_title(text: str, sep: str = "═", w: int = 62) -> str:
    pad = w - len(text) - 2
    if pad < 2:
        pad = 2
    left = pad // 2
    right = pad - left
    return "  " + sep * left + " " + text + " " + sep * right + "\n"


def _r_table(headers: list[str], rows: list[tuple], w: int = 60) -> list[str]:
    if not rows:
        return []
    n = len(headers)
    avail = w - (n * 3)
    per_col = max(10, avail // n)
    hdr = "  │ " + " │ ".join(str(h).ljust(per_col)[:per_col] for h in headers) + " │"
    sep = "  ├" + "─" * (len(hdr) - 4) + "┤"
    lines = [hdr, sep]
    for row in rows:
        vals = [str(v).ljust(per_col)[:per_col] for v in row]
        lines.append("  │ " + " │ ".join(vals) + " │")
    return lines


# ── Schemas ──────────────────────────────────────────────────────────────


class DesgloseItem(BaseModel):
    tipo: str
    total: int = 0
    puntos: float = 0


class Comparativa(BaseModel):
    periodo_anterior: str = ""
    equipos: int = 0
    puntos: float = 0
    ganancia: float = 0


class DetalleEquipo(BaseModel):
    fecha: str
    orden: int
    tipo: str
    puntaje: float
    marca: str = ""
    modelo: str = ""


class InformePuntosResponse(BaseModel):
    periodo: str
    tipo: str
    total_equipos: int
    total_puntos: int
    total_ganancia: float
    valor_punto: float
    desglose: list[DesgloseItem]
    comparativa: Comparativa
    detalle_equipos: list[DetalleEquipo]
    contenido_txt: str


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/puntos")
async def informe_puntos(
    tipo: str = "mes",
    periodo: str = "",
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Detailed points report with breakdown by type and comparison with previous period."""
    if tipo not in ("mes", "anio"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "tipo debe ser 'mes' o 'anio'"},
        )

    if tipo == "mes":
        if not periodo or len(periodo) != 7 or periodo[4] != "-":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "validation_error", "detail": "periodo debe ser YYYY-MM"},
            )
        fmt = "%Y-%m"
    else:
        if not periodo or len(periodo) != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "validation_error", "detail": "periodo debe ser YYYY"},
            )
        fmt = "%Y"

    # valor_punto
    result = await db.execute(
        text("SELECT valor FROM config WHERE tenant_id = :tid AND clave = 'valor_punto'"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    valor_punto = float(row[0]) if row else 2000

    # Map format for PostgreSQL TO_CHAR
    fmt_sql = _PG_FORMATS.get(fmt, "YYYY-MM")

    # Desglose by type
    result = await db.execute(
        text(f"""
            SELECT tipo, COUNT(*) as total, SUM(puntaje) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
              AND TO_CHAR(fecha, '{fmt_sql}') = :periodo
            GROUP BY tipo
            ORDER BY total DESC
        """),
        {"tid": tenant_id, "periodo": periodo},
    )
    desglose_rows = result.fetchall()
    desglose = [
        DesgloseItem(tipo=r[0], total=r[1], puntos=float(r[2] or 0))
        for r in desglose_rows
    ]

    total_equipos = sum(d.total for d in desglose)
    total_puntos = sum(d.puntos for d in desglose)
    total_ganancia = round(total_puntos * valor_punto, 2)

    # Previous period
    if tipo == "mes":
        year, month = periodo.split("-")
        y, m = int(year), int(month)
        m -= 1
        if m < 1:
            m = 12
            y -= 1
        prev_periodo = f"{y:04d}-{m:02d}"
    else:
        prev_periodo = str(int(periodo) - 1)

    result = await db.execute(
        text(f"""
            SELECT COUNT(*) as equipos, COALESCE(SUM(puntaje), 0) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
              AND TO_CHAR(fecha, '{fmt_sql}') = :prev
        """),
        {"tid": tenant_id, "prev": prev_periodo},
    )
    row = result.fetchone()
    prev_equipos = row[0] if row else 0
    prev_puntos = round(float(row[1]), 2) if row and row[1] else 0
    prev_ganancia = round(prev_puntos * valor_punto, 2)

    comparativa = Comparativa(
        periodo_anterior=prev_periodo,
        equipos=prev_equipos,
        puntos=prev_puntos,
        ganancia=prev_ganancia,
    )

    # ── TXT content ──
    w = 62
    lines = []
    periodo_label = f"Mes: {periodo}" if tipo == "mes" else f"Año: {periodo}"

    lines.append(_r_line("█", w))
    lines.append(_r_title("INFORME DE PUNTOS", "█", w))
    lines.append(_r_line("█", w))
    lines.append("")
    lines.append(f"  Período       :  {periodo_label}")
    lines.append(f"  Valor punto   :  $ {valor_punto:,.0f}")
    lines.append(f"  Total equipos :  {total_equipos}")
    lines.append(f"  Total puntos  :  {total_puntos}")
    lines.append(f"  Ganancia total:  $ {total_ganancia:,.0f}")
    lines.append("")

    if desglose:
        lines.append(_r_title("DESGLOSE POR TIPO", "─", w))
        lines.append("")
        table_rows = []
        for d in desglose:
            g = round(d.puntos * valor_punto, 2)
            table_rows.append(
                (
                    (d.tipo[:20] if d.tipo else "—"),
                    str(d.total),
                    str(int(d.puntos)),
                    f"${g:,.0f}",
                )
            )
        for l in _r_table(["TIPO", "CANT", "PTS", "GANANCIA"], table_rows, w):
            lines.append(l)
    else:
        lines.append("  No hay reparaciones registradas en este período.")

    lines.append("")
    lines.append(_r_title("COMPARATIVA", "─", w))
    lines.append("")
    if prev_equipos > 0:
        dif_pts = int(total_puntos - prev_puntos)
        dif_pct = round((dif_pts / prev_puntos * 100) if prev_puntos > 0 else 0, 1)
        lines.append(f"  Período anterior:  {prev_periodo}")
        lines.append(f"  Equipos         :  {prev_equipos} → {total_equipos}")
        lines.append(
            f"  Puntos          :  {int(prev_puntos)} → {int(total_puntos)}  "
            f"({dif_pts:+d} pts, {dif_pct:+.1f}%)"
        )
        lines.append(f"  Ganancia        :  $ {prev_ganancia:,.0f} → $ {total_ganancia:,.0f}")
    else:
        lines.append(f"  Período anterior:  {prev_periodo}")
        lines.append("  Sin datos en el período anterior.")

    lines.append("")
    lines.append(_r_line("═", w))
    lines.append("  Generado por :  Sistema de Rendimiento — NSP Notebooks")
    lines.append(_r_line("═", w))

    # ── Detalle de equipos ──
    result = await db.execute(
        text(f"""
            SELECT r.fecha, r.orden_id, r.tipo, r.puntaje,
                   COALESCE(o.marca, '') as marca,
                   COALESCE(o.modelo, '') as modelo
            FROM reparaciones r
            LEFT JOIN ordenes o ON r.orden_id = o.id
            WHERE r.tenant_id = :tid
              AND TO_CHAR(r.fecha, '{fmt_sql}') = :periodo
            ORDER BY r.fecha DESC, r.orden_id DESC
        """),
        {"tid": tenant_id, "periodo": periodo},
    )
    detalle_equipos = [
        DetalleEquipo(
            fecha=r[0],
            orden=r[1],
            tipo=r[2],
            puntaje=r[3],
            marca=r[4],
            modelo=r[5],
        )
        for r in result.fetchall()
    ]

    contenido_txt = "\n".join(lines)

    return InformePuntosResponse(
        periodo=periodo,
        tipo=tipo,
        total_equipos=total_equipos,
        total_puntos=int(total_puntos),
        total_ganancia=total_ganancia,
        valor_punto=valor_punto,
        desglose=desglose,
        comparativa=comparativa,
        detalle_equipos=detalle_equipos,
        contenido_txt=contenido_txt,
    )


@router.get("/puntos/pdf")
async def informe_puntos_pdf(
    tipo: str = "mes",
    periodo: str = "",
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Generate a PDF for the Informe de Puntos using weasyprint."""
    try:
        import weasyprint
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "dependency_missing",
                "detail": "weasyprint no está instalado. Ejecutá: pip install weasyprint",
            },
        )

    # Get the report data first
    report = await informe_puntos(
        tipo=tipo, periodo=periodo, db=db,
        tenant_id=tenant_id, current_user=current_user,
    )

    periodo_label = f"Mes: {periodo}" if tipo == "mes" else f"Año: {periodo}"
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Build HTML for weasyprint
    html_rows = ""
    for idx, d in enumerate(report.detalle_equipos, 1):
        equipo = f"{d.marca} / {d.modelo}".strip(" /") or "—"
        html_rows += f"""
            <tr{' style="background:#f5f5f5"' if idx % 2 == 0 else ''}>
                <td>{idx}</td>
                <td>{d.fecha}</td>
                <td>{d.orden}</td>
                <td>{d.tipo}</td>
                <td style="text-align:center">{int(d.puntaje)}</td>
                <td>{equipo}</td>
            </tr>"""

    desglose_rows = ""
    for d in report.desglose:
        g = round(d.puntos * report.valor_punto, 2)
        desglose_rows += f"""
            <tr>
                <td>{d.tipo}</td>
                <td style="text-align:center">{d.total}</td>
                <td style="text-align:center">{int(d.puntos)}</td>
                <td style="text-align:right">${g:,.0f}</td>
            </tr>"""

    # Comparison diff logic
    cur_eq = report.total_equipos
    cur_pts = report.total_puntos
    cur_gan = report.total_ganancia
    prev_eq = report.comparativa.equipos
    prev_pts = int(report.comparativa.puntos)
    prev_gan = report.comparativa.ganancia
    prev_per = report.comparativa.periodo_anterior

    def diff_str(cur, prev):
        d = cur - prev
        if d > 0:
            return f"▲ +{d}"
        elif d < 0:
            return f"▼ {d}"
        return "— 0"

    comparativa_html = f"""
    <div class="section">
        <h3>COMPARATIVA VS PERÍODO ANTERIOR</h3>
        <table>
            <tr><td style="width:180px;font-weight:600">Período anterior</td><td>{prev_per}</td></tr>
            <tr><td style="font-weight:600">Equipos</td><td>{prev_eq} → {cur_eq} ({diff_str(cur_eq, prev_eq)})</td></tr>
            <tr><td style="font-weight:600">Puntos</td><td>{prev_pts} → {cur_pts} ({diff_str(cur_pts, prev_pts)})</td></tr>
            <tr><td style="font-weight:600">Ganancia</td><td>${prev_gan:,.0f} → ${cur_gan:,.0f}</td></tr>
        </table>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
    @page {{
        size: A4;
        margin: 2cm 1.5cm;
        @bottom-center {{
            content: "Sistema de Rendimiento — NSP Notebooks | Generado: {now_str}";
            font-size: 8pt;
            color: #999;
        }}
    }}
    body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; color: #333; }}
    h1 {{ font-size: 16pt; color: #1a1e3e; text-align: center; margin-bottom: 0; }}
    h2 {{ font-size: 12pt; color: #1a1e3e; margin-top: 20px; margin-bottom: 8px; }}
    h3 {{ font-size: 10pt; color: #1a1e3e; background: #1a1e3e; color: white;
          padding: 4px 8px; margin-top: 16px; margin-bottom: 6px; text-align: center; }}
    table {{ width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 8pt; }}
    th {{ background: #1a1e3e; color: white; padding: 4px 6px; text-align: center; font-size: 7pt; }}
    td {{ padding: 3px 6px; border: 1px solid #ddd; }}
    .summary {{ margin: 10px 0; }}
    .summary td {{ border: none; padding: 2px 0; font-size: 9pt; }}
    .header {{ text-align: center; margin-bottom: 20px; }}
    .header .sub {{ font-size: 8pt; color: #666; }}
</style>
</head>
<body>
    <div class="header">
        <h1>INFORME DE PUNTOS</h1>
        <div class="sub">{periodo_label} | Generado: {now_str}</div>
    </div>

    <h3>RESUMEN</h3>
    <table class="summary">
        <tr><td style="width:180px;font-weight:600">Total equipos</td><td>{report.total_equipos}</td></tr>
        <tr><td style="font-weight:600">Total puntos</td><td>{report.total_puntos}</td></tr>
        <tr><td style="font-weight:600">Ganancia total</td><td>${report.total_ganancia:,.0f}</td></tr>
        <tr><td style="font-weight:600">Valor del punto</td><td>${report.valor_punto:,.0f}</td></tr>
    </table>

    <h3>DETALLE DE EQUIPOS</h3>
    <table>
        <tr>
            <th style="width:20px">#</th>
            <th style="width:50px">Fecha</th>
            <th style="width:35px">Orden</th>
            <th>Tipo</th>
            <th style="width:35px">Puntaje</th>
            <th>Equipo</th>
        </tr>
        {html_rows}
    </table>

    <h3>SUBTOTALES POR TIPO</h3>
    <table>
        <tr>
            <th>Tipo</th>
            <th style="width:50px">Cantidad</th>
            <th style="width:50px">Puntos</th>
            <th style="width:70px">Ganancia</th>
        </tr>
        {desglose_rows}
    </table>

    {comparativa_html if report.comparativa.equipos > 0 else ''}

</body>
</html>"""

    try:
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        filename = f"informe-puntos_{periodo}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "pdf_error",
                "detail": f"Error al generar PDF: {str(e)}",
            },
        )
