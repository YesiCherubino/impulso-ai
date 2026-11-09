"""V3: calendario interno, configuracion de IA, gestiones y datos simulados.
No conecta sistemas externos y evita modificar historiales reales al sembrar la demo.
"""
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from .db import connect
from .business_v2 import current, create_ficha, sender_email, sender_phone, stamp

V3_SCHEMA = """
CREATE TABLE IF NOT EXISTS actividades_comerciales (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 ficha_id INTEGER REFERENCES fichas_consulta(id),
 oportunidad_id INTEGER REFERENCES oportunidades(id),
 titulo TEXT NOT NULL,
 tipo TEXT NOT NULL DEFAULT 'seguimiento',
 inicio TEXT NOT NULL,
 fin TEXT,
 responsable TEXT NOT NULL DEFAULT '',
 notas TEXT NOT NULL DEFAULT '',
 estado TEXT NOT NULL DEFAULT 'programada',
 creada_en TEXT NOT NULL,
 actualizada_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agenda_fecha ON actividades_comerciales(inicio);
CREATE INDEX IF NOT EXISTS idx_agenda_ficha ON actividades_comerciales(ficha_id);
CREATE TABLE IF NOT EXISTS ia_configuracion (
 id INTEGER PRIMARY KEY CHECK(id = 1),
 tono TEXT NOT NULL DEFAULT 'profesional',
 tratamiento TEXT NOT NULL DEFAULT 'ustedes',
 signos_apertura INTEGER NOT NULL DEFAULT 1,
 extension TEXT NOT NULL DEFAULT 'media',
 instrucciones TEXT NOT NULL DEFAULT ''
);
INSERT OR IGNORE INTO ia_configuracion(id) VALUES (1);
CREATE TABLE IF NOT EXISTS preferencias_usuarios (
 usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id),
 vista_contactos TEXT NOT NULL DEFAULT 'lista'
);
CREATE TABLE IF NOT EXISTS remitentes_gestiones (
 clave TEXT PRIMARY KEY,
 ficha_id INTEGER NOT NULL REFERENCES fichas_consulta(id)
);
CREATE TABLE IF NOT EXISTS fixtures_v3 (
 clave TEXT PRIMARY KEY,
 mensaje_id INTEGER NOT NULL REFERENCES bandeja_consultas(id)
);
"""


def init_v3(db_path: Path):
    with connect(db_path) as con:
        con.executescript(V3_SCHEMA)
        cols={r['name'] for r in con.execute('PRAGMA table_info(fichas_consulta)')}
        was_migrated='estado_gestion' not in cols
        for col,sql in {
            'estado_gestion':"TEXT NOT NULL DEFAULT 'sin_atender'",
            'cerrada_en':'TEXT',
            'motivo_cierre':"TEXT NOT NULL DEFAULT ''",
            'requisitos_check_json':"TEXT NOT NULL DEFAULT '[]'",
            'faltantes_check_json':"TEXT NOT NULL DEFAULT '[]'"
        }.items():
            if col not in cols:
                con.execute(f'ALTER TABLE fichas_consulta ADD COLUMN {col} {sql}')
        # Los datos v2 previos no se descartan; se mantiene su asociación.
        if was_migrated:
            con.execute("UPDATE fichas_consulta SET estado_gestion='en_gestion' WHERE oportunidad_id IN (SELECT id FROM oportunidades WHERE estado IN ('contactada','cotizada','negociacion')) AND estado_gestion='sin_atender'")
            con.execute("UPDATE fichas_consulta SET estado_gestion='concretada' WHERE oportunidad_id IN (SELECT id FROM oportunidades WHERE estado='ganada') AND estado_gestion='sin_atender'")
            con.execute("UPDATE fichas_consulta SET estado_gestion='no_concretada' WHERE oportunidad_id IN (SELECT id FROM oportunidades WHERE estado='perdida') AND estado_gestion='sin_atender'")


class Activity(BaseModel):
    titulo: str=Field(min_length=3,max_length=180)
    tipo: Literal['llamada','reunion','seguimiento','pendiente']='seguimiento'
    inicio: datetime
    fin: datetime|None=None
    ficha_id: int|None=None
    oportunidad_id: int|None=None
    responsable: str=Field(default='',max_length=120)
    notas: str=Field(default='',max_length=1500)
    estado: Literal['programada','realizada','cancelada']='programada'


class AISettings(BaseModel):
    tono: Literal['formal','profesional','cercano']='profesional'
    tratamiento: Literal['vos','tu','ustedes']='ustedes'
    signos_apertura: bool=True
    extension: Literal['breve','media','detallada']='media'
    instrucciones: str=Field(default='',max_length=1000)


class CaseStatus(BaseModel):
    estado: Literal['sin_atender','en_gestion','concretada','no_concretada','resuelta']
    motivo: str=Field(default='',max_length=400)


class ChecklistData(BaseModel):
    requisitos: list[dict]=Field(default_factory=list,max_length=40)
    faltantes: list[dict]=Field(default_factory=list,max_length=40)


class DemoSeed(BaseModel):
    incluir_web: bool=True


DEMO_CONTACTS = [
 ('Aurora Cosmética','Martina López','Crema corporal de 250 ml','fabricación de cremas'),
 ('Nova Beauty','Martín Álvarez','Shampoo y acondicionador','desarrollo de fórmulas'),
 ('Natural Care','Valentina Ríos','Jabón líquido de 500 ml','envasado de jabón'),
 ('Botánica Studio','Andrés Molina','Máscara capilar de 300 ml','packaging'),
 ('Luna Natural','Florencia Vega','Crema facial de 50 ml','fabricación cosmética'),
 ('Esencia Sur','Carolina Ponce','Perfume de 100 ml','elaboración de perfumes'),
 ('Oliva Labs','Federico Paz','Gel de ducha de 400 ml','compra mayorista'),
 ('Vita Belle','Sofía Acosta','Acondicionador de 250 ml','producción para terceros'),
 ('Estudio Luma','Julia Fernández','Crema de manos','fórmula y envase'),
 ('Cielo Verde','Paula Rivera','Protector labial','fabricación'),
 ('Distribuidora del Sur','Agustín Beltrán','Productos de cuidado personal','compra mayorista'),
 ('Laboratorio Andina','Camila Navarro','Shampoo sólido','producción'),
 ('Ámbar Botanics','Irene Gallo','Jabón en barra','elaboración'),
 ('Pampa Cosmética','Mateo Quiroga','Emulsión corporal','desarrollo'),
 ('Verde Clara','Ana López','Perfumería','envasado'),
 ('Dalia Care','Sol Torres','Sérum facial','fabricación'),
 ('Brisa Natural','Luciano Díaz','Crema hidratante','fórmula'),
 ('Prisma Beauty','Rocío Gómez','Loción corporal','packaging'),
 ('Marea Sur','Eugenia Peralta','Productos capilares','mayorista'),
 ('Nativa Laboratorios','Mariano Ruiz','Jabón líquido','producción'),
]


def seed_demo_v3(con, include_web=True):
    """Inserta 15 WhatsApp, 15 Email (20 contactos) y 5 Web opcionales.
    Idempotente por clave. NO elimina ni modifica mensajes históricos.
    La carga es explícita, exclusiva de administración.
    """
    demo=0
    base=datetime.now(timezone.utc)
    templates=[
        'Hola, queremos averiguar por {producto}. Necesitaríamos orientación para una posible cotización.',
        'Buen día. Tenemos interés en {producto}. Queremos definir cantidad y presentación.',
        'ola qeria consultar por {producto}, cuanto tda y q datos nesesitan?',
        'Les compartimos más información sobre {producto}. El envase sería personalizado.',
        'Nos pueden indicar qué datos necesitan para evaluar {producto}?'
    ]
    fixtures=[]
    for i in range(30):
        # Primeros diez contactos reciben dos mensajes, uno por cada canal.
        # Los otros diez reciben un solo mensaje, 5 por canal.
        if i<10:idx=i;channel='WhatsApp'
        elif i<20:idx=i-10;channel='Correo'
        elif i<25:idx=i-10;channel='WhatsApp'
        else:idx=i-10;channel='Correo'
        client,person,product,_=DEMO_CONTACTS[idx]
        email=f'contacto{idx+1}@ejemplo.test'  # dominio reservado para ejemplos
        phone=f'549110000{idx+1:04d}'
        text=templates[i%len(templates)].format(producto=product)
        subject=f'Consulta sobre {product}' if channel=='Correo' else ''
        fixtures.append((f'v3-{i+1:02d}',client,person,channel,text,email if channel=='Correo' else '',phone if channel=='WhatsApp' else '',subject,i,idx))
    if include_web:
        for j in range(5):
            idx=j
            client,person,product,_=DEMO_CONTACTS[idx]
            text=f'Solicitud desde el formulario de Pasmanter. Producto: {product}. Cantidad estimada: {2000+j*1000} unidades. Localidad: CABA. Solicitamos información comercial.'
            fixtures.append((f'v3-web-{j+1:02d}',client,person,'Formulario web',text,f'contacto{idx+1}@ejemplo.test',f'549110000{idx+1:04d}',f'Formulario web · {product}',30+j,idx))
    demo_contacts={}
    for key,client,person,channel,body,email,phone,subject,offset,idx in fixtures:
        if con.execute('SELECT 1 FROM fixtures_v3 WHERE clave=?',(key,)).fetchone():continue
        # Una gestion inicial por contacto en esta tanda demo; los mensajes adicionales
        # se asocian al mismo numero sin crear otro expediente.
        existing=con.execute('''SELECT b.ficha_id FROM bandeja_consultas b JOIN fixtures_v3 fx ON fx.mensaje_id=b.id
                      WHERE fx.clave LIKE 'v3-%' AND b.cliente=? AND b.ficha_id IS NOT NULL LIMIT 1''',(client,)).fetchone()
        received=(base-timedelta(hours=offset+1)).isoformat(timespec='seconds')
        if existing:
            ficha_id=existing['ficha_id']
            contact_row=con.execute('SELECT oportunidad_id FROM fichas_consulta WHERE id=?',(ficha_id,)).fetchone()
            contact_id=contact_row['oportunidad_id'] if contact_row else None
        else:
            contact_id=demo_contacts.get(client)
            if contact_id is None:
                row=con.execute("SELECT id FROM oportunidades WHERE cliente=? AND notas='Ejemplo ficticio de Impulso V3' LIMIT 1",(client,)).fetchone()
                if row:contact_id=row['id']
                else:
                    cur=con.execute('''INSERT INTO oportunidades(cliente,contacto,producto,cantidad,monto_estimado_usd,estado,creada_el,ultimo_contacto,notas,
                             tipo_consulta,canal_origen,presentacion,packaging,responsable,email,telefono)
                             VALUES(?,?,?,?,NULL,'nueva',?,?,'Ejemplo ficticio de Impulso V3','sin_clasificar',?,?,?,'',?,?)''',
                             (client,person,DEMO_CONTACTS[idx][2],None,received[:10],received[:10],channel,'','',f'contacto{idx+1}@ejemplo.test',f'549110000{idx+1:04d}'))
                    contact_id=cur.lastrowid
                demo_contacts[client]=contact_id
            ficha_id=create_ficha(con,cliente=client,contacto=person,titulo=f'Consulta sobre {DEMO_CONTACTS[idx][2]}',incoming_stamp=received,opportunity_id=contact_id)
        cur=con.execute('''INSERT INTO bandeja_consultas(cliente,contacto,canal,texto,recibido_el,estado,
                 email_remitente,telefono_remitente,asunto,ficha_id,oportunidad_id) VALUES(?,?,?,?,?,'nueva',?,?,?,?,?)''',
                 (client,person,channel,body,received,email,phone,subject,ficha_id,contact_id))
        con.execute('INSERT INTO fixtures_v3(clave,mensaje_id) VALUES(?,?)',(key,cur.lastrowid))
        demo+=1
    return demo


def register_business_v3(app:FastAPI,db_path:Path):
    @app.get('/api/ai/settings')
    def get_ai_settings(request:Request):
        current(request,db_path,'administrador')
        with connect(db_path) as con:
            return dict(con.execute('SELECT * FROM ia_configuracion WHERE id=1').fetchone())

    @app.post('/api/ai/settings')
    def save_ai_settings(request:Request,payload:AISettings):
        current(request,db_path,'administrador')
        with connect(db_path) as con:
            con.execute('''UPDATE ia_configuracion SET tono=?,tratamiento=?,signos_apertura=?,extension=?,instrucciones=? WHERE id=1''',
                    (payload.tono,payload.tratamiento,int(payload.signos_apertura),payload.extension,payload.instrucciones))
        return {'ok':True}

    @app.get('/api/me/view')
    def get_view(request:Request):
        user=current(request,db_path)
        if not user:return {'vista_contactos':'lista'}
        with connect(db_path) as con:
            row=con.execute('SELECT vista_contactos FROM preferencias_usuarios WHERE usuario_id=?',(user['id'],)).fetchone()
            return {'vista_contactos':row['vista_contactos'] if row else 'lista'}

    @app.post('/api/me/view')
    def save_view(request:Request,payload:dict):
        user=current(request,db_path,'ventas','gerencia','administrador')
        view=payload.get('vista_contactos')
        if view not in ('lista','tablero'):raise HTTPException(422,'Vista inválida')
        with connect(db_path) as con:
            con.execute('INSERT INTO preferencias_usuarios(usuario_id,vista_contactos) VALUES(?,?) ON CONFLICT(usuario_id) DO UPDATE SET vista_contactos=excluded.vista_contactos',(user['id'],view))
        return {'vista_contactos':view}

    @app.get('/api/calendar/events')
    def calendar_list(request:Request):
        user=current(request,db_path)
        with connect(db_path) as con:
            if user and user['role']=='ventas':
                rows=con.execute('SELECT * FROM actividades_comerciales WHERE responsable=? ORDER BY inicio',(user['username'],)).fetchall()
            else:rows=con.execute('SELECT * FROM actividades_comerciales ORDER BY inicio').fetchall()
            return [dict(r) for r in rows]

    @app.post('/api/calendar/events',status_code=201)
    def calendar_add(request:Request,payload:Activity):
        user=current(request,db_path)
        if user and user['role']=='gerencia':raise HTTPException(403,'Gerencia solo consulta')
        if payload.fin and payload.fin<=payload.inicio:raise HTTPException(422,'La fecha de fin debe ser posterior al inicio')
        owner=user['username'] if user and user['role']=='ventas' else (payload.responsable or (user['username'] if user else ''))
        with connect(db_path) as con:
            if payload.ficha_id and not con.execute('SELECT 1 FROM fichas_consulta WHERE id=?',(payload.ficha_id,)).fetchone():
                raise HTTPException(404,'Consulta no encontrada')
            if payload.oportunidad_id and not con.execute('SELECT 1 FROM oportunidades WHERE id=?',(payload.oportunidad_id,)).fetchone():
                raise HTTPException(404,'Contacto no encontrado')
            vals=(payload.ficha_id,payload.oportunidad_id,payload.titulo,payload.tipo,payload.inicio.isoformat(),
                  payload.fin.isoformat() if payload.fin else None,owner,payload.notas,payload.estado,stamp(),stamp())
            cur=con.execute('''INSERT INTO actividades_comerciales(ficha_id,oportunidad_id,titulo,tipo,inicio,fin,responsable,notas,estado,creada_en,actualizada_en)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)''',vals)
            return dict(con.execute('SELECT * FROM actividades_comerciales WHERE id=?',(cur.lastrowid,)).fetchone())

    @app.post('/api/calendar/events/{event_id}')
    def calendar_edit(event_id:int,request:Request,payload:Activity):
        user=current(request,db_path)
        if user and user['role']=='gerencia':raise HTTPException(403,'Gerencia solo consulta')
        if payload.fin and payload.fin<=payload.inicio:raise HTTPException(422,'La fecha de fin debe ser posterior al inicio')
        with connect(db_path) as con:
            row=con.execute('SELECT * FROM actividades_comerciales WHERE id=?',(event_id,)).fetchone()
            if not row:raise HTTPException(404,'Actividad no encontrada')
            if user and user['role']=='ventas' and row['responsable']!=user['username']:raise HTTPException(403,'No se puede modificar una actividad de otra persona')
            owner=row['responsable'] if user and user['role']=='ventas' else (payload.responsable or row['responsable'])
            con.execute('''UPDATE actividades_comerciales SET titulo=?,tipo=?,inicio=?,fin=?,ficha_id=?,oportunidad_id=?,responsable=?,notas=?,estado=?,actualizada_en=? WHERE id=?''',
                (payload.titulo,payload.tipo,payload.inicio.isoformat(),payload.fin.isoformat() if payload.fin else None,
                 payload.ficha_id,payload.oportunidad_id,owner,payload.notas,payload.estado,stamp(),event_id))
            return dict(con.execute('SELECT * FROM actividades_comerciales WHERE id=?',(event_id,)).fetchone())

    @app.post('/api/fichas/{ficha_id}/estado')
    def set_case_status(ficha_id:int,request:Request,payload:CaseStatus):
        user=current(request,db_path)
        if user and user['role']=='gerencia':raise HTTPException(403,'Gerencia solo consulta')
        with connect(db_path) as con:
            row=con.execute('SELECT * FROM fichas_consulta WHERE id=?',(ficha_id,)).fetchone()
            if not row:raise HTTPException(404,'Consulta no encontrada')
            closed=payload.estado in ('concretada','no_concretada','resuelta')
            con.execute('UPDATE fichas_consulta SET estado_gestion=?,cerrada_en=?,motivo_cierre=?,actualizada_en=? WHERE id=?',
                (payload.estado,stamp() if closed else None,payload.motivo,stamp(),ficha_id))
            return {'id':ficha_id,'estado':payload.estado,'codigo':row['codigo']}

    @app.get('/api/fichas/{ficha_id}/checklists')
    def get_checklists(ficha_id:int,request:Request):
        current(request,db_path)
        with connect(db_path) as con:
            row=con.execute('SELECT requisitos_json,datos_faltantes_json,requisitos_check_json,faltantes_check_json FROM fichas_consulta WHERE id=?',(ficha_id,)).fetchone()
            if not row:raise HTTPException(404,'Consulta no encontrada')
            def normalized(edit,old):
                try: data=json.loads(row[edit])
                except (ValueError,TypeError):data=[]
                if data:return data
                return [{'text':v,'done':False} for v in json.loads(row[old] or '[]')]
            return {'requisitos':normalized('requisitos_check_json','requisitos_json'),
                    'faltantes':normalized('faltantes_check_json','datos_faltantes_json')}

    @app.post('/api/fichas/{ficha_id}/checklists')
    def save_checklists(ficha_id:int,request:Request,payload:ChecklistData):
        user=current(request,db_path)
        if user and user['role']=='gerencia':raise HTTPException(403,'Gerencia solo consulta')
        def clean(items):
            out=[]
            for item in items:
                value=str(item.get('text','')).strip()[:250]
                if value:out.append({'text':value,'done':bool(item.get('done',False))})
            return out
        req,missing=clean(payload.requisitos),clean(payload.faltantes)
        with connect(db_path) as con:
            cur=con.execute('''UPDATE fichas_consulta SET requisitos_check_json=?,faltantes_check_json=?,requisitos_json=?,datos_faltantes_json=?,actualizada_en=? WHERE id=?''',
                    (json.dumps(req,ensure_ascii=False),json.dumps(missing,ensure_ascii=False),json.dumps([x['text'] for x in req],ensure_ascii=False),json.dumps([x['text'] for x in missing],ensure_ascii=False),stamp(),ficha_id))
            if not cur.rowcount:raise HTTPException(404,'Consulta no encontrada')
        return {'requisitos':req,'faltantes':missing}

    @app.get('/api/inbox/threads')
    def threads(request:Request):
        current(request,db_path)
        with connect(db_path) as con:
            rows=[dict(r) for r in con.execute('''SELECT b.*,COALESCE(b.oportunidad_id,f.oportunidad_id) AS related_contact_id
                    FROM bandeja_consultas b LEFT JOIN fichas_consulta f ON f.id=b.ficha_id
                    ORDER BY b.recibido_el,b.id''')]
            # Un hilo es un remitente, NO una gestión. Coincidencias exactas verificadas
            # de teléfono/correo, asociación de contacto o ficha enlazan canales.
            parent={int(r['id']):int(r['id']) for r in rows}
            def find(x):
                while parent[x]!=x:
                    parent[x]=parent[parent[x]]
                    x=parent[x]
                return x
            def union(a,b):
                a,b=find(a),find(b)
                if a!=b:parent[max(a,b)]=min(a,b)
            seen={}
            for m in rows:
                ident=[]
                email=sender_email(m.get('email_remitente') or '')
                phone=sender_phone(m.get('telefono_remitente') or '')
                if email:ident.append('email:'+email)
                if phone:ident.append('phone:'+phone)
                if m['related_contact_id']:ident.append('contact:'+str(m['related_contact_id']))
                if m['ficha_id']:ident.append('case:'+str(m['ficha_id']))
                for token in ident:
                    if token in seen:union(m['id'],seen[token])
                    else:seen[token]=m['id']
            groups={}
            for m in rows:
                k=find(m['id'])
                t=groups.setdefault(k,{'key':'contact-'+str(k),'cliente':m['cliente'],'contacto':m['contacto'],'mensajes':[]})
                t['mensajes'].append(m)
            out=list(groups.values())
            for t in out:
                t['mensajes'].sort(key=lambda m:(m['recibido_el'],m['id']))
                t['ultimo']=t['mensajes'][-1]['recibido_el']
                t['no_leidos']=sum(1 for m in t['mensajes'] if not m['leido_en'])
            return sorted(out,key=lambda x:x['ultimo'],reverse=True)

    @app.post('/api/inbox/{message_id}/new-case')
    def start_new_case(message_id:int,request:Request,payload:dict):
        user=current(request,db_path)
        if user and user['role']=='gerencia':raise HTTPException(403,'Gerencia solo consulta')
        title=str(payload.get('titulo','Nueva gestión')).strip()[:200]
        with connect(db_path) as con:
            m=con.execute('SELECT * FROM bandeja_consultas WHERE id=?',(message_id,)).fetchone()
            if not m:raise HTTPException(404,'Mensaje no encontrado')
            con.execute('BEGIN IMMEDIATE')
            case_id=create_ficha(con,cliente=m['cliente'],contacto=m['contacto'],titulo=title or 'Nueva gestión',incoming_stamp=stamp(),opportunity_id=m['oportunidad_id'])
            for key in [('e:'+sender_email(m['email_remitente']) if m['email_remitente'] else ''),
                        ('t:'+sender_phone(m['telefono_remitente']) if m['telefono_remitente'] else '')]:
                if key:con.execute('INSERT INTO remitentes_gestiones(clave,ficha_id) VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET ficha_id=excluded.ficha_id',(key,case_id))
            return {'id':case_id,'codigo':con.execute('SELECT codigo FROM fichas_consulta WHERE id=?',(case_id,)).fetchone()['codigo']}

    @app.post('/api/demo/seed')
    def demo_seed(request:Request,payload:DemoSeed):
        current(request,db_path,'administrador')
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            added=seed_demo_v3(con,include_web=payload.incluir_web)
            total=con.execute('SELECT COUNT(*) FROM fixtures_v3').fetchone()[0]
        return {'added':added,'demo_messages':total,'whatsapp':15,'email':15,'web':5 if payload.incluir_web else 0}
