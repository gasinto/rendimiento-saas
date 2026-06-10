"""initial_schema

Creates all 19 tables for the rendimiento-saas application.

Revision ID: ef7dc8eaafe0
Revises: 
Create Date: 2026-06-10 08:34:28.869300

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ef7dc8eaafe0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""

    # ── 1. tenants — replaces empresas ──────────────────────────
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('config', sa.Text(), server_default='{}'),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])

    # ── 2. users — JWT-authenticated users ──────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='viewer'),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])

    # ── 3. tipos_equipo — equipment types (global) ──────────────
    op.create_table(
        'tipos_equipo',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )

    # ── 4. placas — board models (global) ───────────────────────
    op.create_table(
        'placas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('modelo_placa', sa.String(length=255), nullable=False),
        sa.Column('tipo_equipo_id', sa.Integer(), sa.ForeignKey('tipos_equipo.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('modelo_placa'),
    )

    # ── 5. circuitos — IC references (global) ───────────────────
    op.create_table(
        'circuitos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('codigo', sa.String(length=100), nullable=False),
        sa.Column('descripcion', sa.String(length=255), server_default=''),
        sa.Column('placa', sa.String(length=255), nullable=False),
        sa.Column('cantidad', sa.Integer(), server_default='1'),
        sa.Column('info_detallada', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 6. mediciones — global pin measurements (global) ───────
    op.create_table(
        'mediciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('codigo', sa.String(length=100), nullable=False),
        sa.Column('placa', sa.String(length=255), nullable=False),
        sa.Column('pin', sa.String(length=100), nullable=False),
        sa.Column('nombre', sa.String(length=255), server_default=''),
        sa.Column('valor_esperado', sa.String(length=255), server_default=''),
        sa.Column('notas', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 7. soluciones — repair solutions (optional tenant_id) ───
    op.create_table(
        'soluciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('placa', sa.String(length=255), nullable=False),
        sa.Column('falla', sa.Text(), server_default=''),
        sa.Column('solucion', sa.Text(), server_default=''),
        sa.Column('ics', sa.String(length=500), server_default='[]'),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_soluciones_tenant_id', 'soluciones', ['tenant_id'])

    # ── 8. referencias — technical references (global) ──────────
    op.create_table(
        'referencias',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('categoria', sa.String(length=100), nullable=False, server_default='Electronica General'),
        sa.Column('titulo', sa.String(length=255), nullable=False),
        sa.Column('contenido_html', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 9. puntajes — per-tenant score definitions ──────────────
    op.create_table(
        'puntajes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('tipo', sa.String(length=100), nullable=False),
        sa.Column('puntaje', sa.Float(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_puntajes_tenant_id', 'puntajes', ['tenant_id'])

    # ── 10. config — per-tenant config (composite PK) ───────────
    op.create_table(
        'config',
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('clave', sa.String(length=100), nullable=False),
        sa.Column('valor', sa.Text(), nullable=False, server_default=''),
        sa.PrimaryKeyConstraint('tenant_id', 'clave'),
    )

    # ── 11. ordenes — work orders ───────────────────────────────
    op.create_table(
        'ordenes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.String(length=10), nullable=False),
        sa.Column('placa', sa.String(length=255), server_default=''),
        sa.Column('falla', sa.Text(), server_default=''),
        sa.Column('diagnostico', sa.Text(), server_default=''),
        sa.Column('proceso', sa.Text(), server_default=''),
        sa.Column('solucion', sa.Text(), server_default=''),
        sa.Column('estado', sa.String(length=20), server_default='en_curso'),
        sa.Column('resultado', sa.String(length=20), server_default='n/a'),
        sa.Column('tipo', sa.String(length=100), server_default=''),
        sa.Column('puntaje', sa.Float(), server_default='0'),
        sa.Column('tipo_equipo', sa.String(length=100), server_default=''),
        sa.Column('marca', sa.String(length=100), server_default=''),
        sa.Column('modelo', sa.String(length=100), server_default=''),
        sa.Column('checklist', sa.Text(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ordenes_tenant_id', 'ordenes', ['tenant_id'])

    # ── 12. reparaciones — repair line items (FK to ordenes.id) ─
    op.create_table(
        'reparaciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('orden_id', sa.Integer(), sa.ForeignKey('ordenes.id'), nullable=False),
        sa.Column('fecha', sa.String(length=10), nullable=False),
        sa.Column('tipo', sa.String(length=100), nullable=False),
        sa.Column('puntaje', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reparaciones_tenant_id', 'reparaciones', ['tenant_id'])
    op.create_index('ix_reparaciones_orden_id', 'reparaciones', ['orden_id'])

    # ── 13. sesiones_reparacion — repair session timers ─────────
    # FIX: this table was missing in the original init_db
    op.create_table(
        'sesiones_reparacion',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('orden_id', sa.Integer(), sa.ForeignKey('ordenes.id'), nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('inicio', sa.String(length=19), nullable=False),
        sa.Column('fin', sa.String(length=19), nullable=True),
        sa.Column('duracion_segundos', sa.Integer(), server_default='0'),
        sa.Column('notas', sa.Text(), server_default=''),
        sa.Column('estado', sa.String(length=20), server_default='activa'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sesiones_reparacion_orden_id', 'sesiones_reparacion', ['orden_id'])
    op.create_index('ix_sesiones_reparacion_tenant_id', 'sesiones_reparacion', ['tenant_id'])

    # ── 14. notas_placa — board notes (optional tenant_id) ──────
    op.create_table(
        'notas_placa',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('modelo_placa', sa.String(length=255), nullable=False),
        sa.Column('contenido', sa.Text(), nullable=False),
        sa.Column('bloque', sa.String(length=100), server_default=''),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notas_placa_tenant_id', 'notas_placa', ['tenant_id'])

    # ── 15. mediciones_placa — board measurements (optional tenant_id) ─
    op.create_table(
        'mediciones_placa',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('modelo_placa', sa.String(length=255), nullable=False),
        sa.Column('punto_medicion', sa.String(length=255), nullable=False),
        sa.Column('nombre', sa.String(length=255), server_default=''),
        sa.Column('valor_esperado', sa.String(length=255), server_default=''),
        sa.Column('categoria', sa.String(length=100), server_default=''),
        sa.Column('ic_referencia', sa.String(length=255), server_default=''),
        sa.Column('notas', sa.Text(), server_default=''),
        sa.Column('bloque', sa.String(length=100), server_default=''),
        sa.Column('checked', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mediciones_placa_tenant_id', 'mediciones_placa', ['tenant_id'])

    # ── 16. bloques_placa — board block grouping (global) ───────
    op.create_table(
        'bloques_placa',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('modelo_placa', sa.String(length=255), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 17. diagramas — BoardDoctor diagrams (global) ───────────
    op.create_table(
        'diagramas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marca', sa.String(length=100), server_default=''),
        sa.Column('modelo', sa.String(length=255), server_default=''),
        sa.Column('tipo', sa.String(length=50), server_default=''),
        sa.Column('gdrive_id', sa.String(length=255), server_default=''),
        sa.Column('nombre_archivo', sa.String(length=255), server_default=''),
        sa.Column('tamaño_mb', sa.Float(), nullable=True, server_default='0'),
        sa.Column('ultima_sync', sa.String(length=30), server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 18. ic_marcas — IC marking catalog (global) ─────────────
    op.create_table(
        'ic_marcas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marking', sa.String(length=100), server_default=''),
        sa.Column('modelo', sa.String(length=255), server_default=''),
        sa.Column('fabricante', sa.String(length=255), server_default=''),
        sa.Column('funcion', sa.String(length=255), server_default=''),
        sa.Column('compatibilidad', sa.String(length=255), server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 19. ic_compatibilidad — IC compatibility (global) ───────
    op.create_table(
        'ic_compatibilidad',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fabricante', sa.String(length=255), server_default=''),
        sa.Column('modelo', sa.String(length=255), server_default=''),
        sa.Column('compatibles', sa.Text(), server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table('ic_compatibilidad')
    op.drop_table('ic_marcas')
    op.drop_table('diagramas')
    op.drop_table('bloques_placa')
    op.drop_table('mediciones_placa')
    op.drop_table('notas_placa')
    op.drop_table('sesiones_reparacion')
    op.drop_table('reparaciones')
    op.drop_table('ordenes')
    op.drop_table('config')
    op.drop_table('puntajes')
    op.drop_table('referencias')
    op.drop_table('soluciones')
    op.drop_table('mediciones')
    op.drop_table('circuitos')
    op.drop_table('placas')
    op.drop_table('tipos_equipo')
    op.drop_table('users')
    op.drop_table('tenants')
