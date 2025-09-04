from typing import Optional, cast
from fastapi import FastAPI, APIRouter, Form, File, UploadFile, Depends, status, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from pydantic import EmailStr
from dataclasses import dataclass
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.discovery import build
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from datetime import datetime, timedelta
import os
import pathlib
import time
import json

# URL de la página estática
URL_BASE = os.environ["URL_BASE"]

# Clase para recibir y validar el forms de delegaciones
@dataclass
class DelegacionFormData:
    delegacion_oficial: str = Form(pattern=r"^(si|no)$")
    nombre_delegacion_oficial: Optional[str] = Form(None, max_length=150)
    responsable_delegacion_oficial: Optional[str] = Form(None, max_length=150)

    nombre: str = Form(max_length=150)
    apellido: str = Form(max_length=150)
    edad: str = Form(max_length=2)
    celular: str = Form(max_length=30)
    correo: EmailStr = Form(max_length=150)
    pais: str = Form(max_length=150)
    ciudad_estado: str = Form(max_length=150)
    escolaridad: str = Form(pattern=r"^(Secundaria|Preparatoria|Universidad|Egresado|No estudio)$", max_length=150)
    escuela_rlm: str = Form(pattern=r"^(RLM|Otra)$", max_length=150)
    escuela: Optional[str] = Form(None, max_length=150)
    nombre_contacto: str = Form(max_length=150)
    celular_contacto: str = Form(max_length=30)
    relacion_contacto: str = Form(max_length=150)
    info_extra: Optional[str] = Form(None, max_length=150)

    comite_0: str = Form(pattern=r"^(OPS|CEPAL|OEA|CRM|CNDH|CED)$")
    comite_0_pais_0: str = Form(max_length=150)
    comite_0_pais_1: str = Form(max_length=150)
    comite_0_pais_2: str = Form(max_length=150)

    comite_1: str = Form(pattern=r"^(OPS|CEPAL|OEA|CRM|CNDH|CED)$")
    comite_1_pais_0: str = Form(max_length=150)
    comite_1_pais_1: str = Form(max_length=150)
    comite_1_pais_2: str = Form(max_length=150)

    comite_2: str = Form(pattern=r"^(OPS|CEPAL|OEA|CRM|CNDH|CED)$")
    comite_2_pais_0: str = Form(max_length=150)
    comite_2_pais_1: str = Form(max_length=150)
    comite_2_pais_2: str = Form(max_length=150)


@dataclass
class FacultyFormData:
    institucion_delegacion_oficial: str = Form(max_length=150)
    nombre_faculty: str = Form(max_length=150)
    apellido_faculty: str = Form(max_length=150)
    celular_faculty: str = Form(max_length=150)
    correo_faculty: EmailStr = Form(max_length=150)
    ciudad_estado_faculty: str = Form(max_length=150)
    pais_faculty: str = Form(max_length=150)
    numero_delegaciones: str = Form(max_length=2)


# Clase para los datos de delegación
class DelegacionSM():
    fecha: datetime
    delegacion_oficial: str | None
    responsable_delegacion_oficial: str | None

    nombre: str
    apellido: str
    edad: int
    celular: str
    correo: str
    pais: str
    ciudad_estado: str
    escolaridad: str
    escuela: str | None
    contacto_emergencia: str
    info_extra: str | None

    comite_1: str
    comite_1_opcion_1: str
    comite_1_opcion_2: str
    comite_1_opcion_3: str | None

    comite_2: str
    comite_2_opcion_1: str
    comite_2_opcion_2: str
    comite_2_opcion_3: str | None

    comite_3: str
    comite_3_opcion_1: str
    comite_3_opcion_2: str
    comite_3_opcion_3: str | None

    def __init__(self, **kwargs) -> None:
        self.fecha = datetime.now() - timedelta(hours=6)

        for key, value in kwargs.items():
            setattr(self, key, value)


# Clase para los datos de faculty
class FacultySM():
    fecha: datetime

    institucion_delegacion_oficial: str
    nombre_faculty: str
    apellido_faculty: str
    celular_faculty: str
    correo_faculty: str
    ciudad_estado_faculty: str
    pais_faculty: str

    numero_delegaciones: int

    def __init__(self, **kwargs) -> None:
        self.fecha = datetime.now() - timedelta(hours=6)

        for key, value in kwargs.items():
            setattr(self, key, value)


# Inicializar app y router
router = APIRouter()
app = FastAPI(docs_url=None, redoc_url=None)


# Mostrar página de error en vez de error en JSON
@app.exception_handler(StarletteHTTPException)
@app.exception_handler(RequestValidationError)
async def http_exception_handler(request, exc):
    return RedirectResponse(f"{URL_BASE}/registro/error/", status_code=status.HTTP_303_SEE_OTHER)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8080",
        "https://rlmmun.smmun.com",
        "https://jellyfish-app-iyb7k.ondigitalocean.app",
        "https://rlmmun.github.io",
        "https://github.io"
    ],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)


# Credenciales para APIs de Google
google_credentials = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_KEY"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"])


# HTML y archivos adjuntos de correos para enviar
with open("email/delegacion.html", "r") as dg, open("email/faculty.html") as fac:
    html_emails = {
        "delegacion": dg.read(),
        "faculty": fac.read()
    }


def comite_corto_a_largo(comite):
    match comite:
        case "OPS":
            return "Organización Panamericana de la Salud (OPS)"
        case "CEPAL":
            return "Comisión Económica para América Latina y el Caribe (CEPAL)"
        case "OEA":
            return "Organización de los Estados Americanos (OEA)"
        case "CRM":
            return "Conferencia Regional sobre la Mujer de América Latina y el Caribe (CRM)"
        case "CNDH":
            return "Comisión Nacional de los Derechos Humanos (CNDH)"
        case "CED":
            return "Comité contra la Desaparición Forzada (CED)"
        case _:
            return comite


def manejar_inscripcion(inscripcion: DelegacionSM, drive_id: str):
    # Añadir al sheets de inscripciones
    service = build("sheets", "v4", credentials=google_credentials)
    body = {
        "values": [
            [
                False,

                inscripcion.fecha.strftime(r"%d/%m/%Y, %H:%M:%S"),

                inscripcion.delegacion_oficial,
                inscripcion.responsable_delegacion_oficial,

                inscripcion.nombre,
                inscripcion.apellido,
                inscripcion.edad,
                f"'{inscripcion.celular}",
                inscripcion.correo,
                inscripcion.pais,
                inscripcion.ciudad_estado,
                inscripcion.escolaridad,
                inscripcion.escuela,
                inscripcion.contacto_emergencia,
                inscripcion.info_extra,

                inscripcion.comite_1,
                inscripcion.comite_1_opcion_1,
                inscripcion.comite_1_opcion_2,
                inscripcion.comite_1_opcion_3,

                inscripcion.comite_2,
                inscripcion.comite_2_opcion_1,
                inscripcion.comite_2_opcion_2,
                inscripcion.comite_2_opcion_3,

                inscripcion.comite_3,
                inscripcion.comite_3_opcion_1,
                inscripcion.comite_3_opcion_2,
                inscripcion.comite_3_opcion_3,

                f"https://drive.google.com/file/d/{drive_id}"
            ]
        ]
    }

    service.spreadsheets().values().append(
        spreadsheetId="1sMjRWL62Ntu5n4sz9OFrvPNUL_o7Xcj1uOcC-ynLOVU",
        range="GENERAL!A1:AC1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    # Mandar correo
    comite_1_largo = comite_corto_a_largo(inscripcion.comite_1)
    comite_2_largo = comite_corto_a_largo(inscripcion.comite_2)
    comite_3_largo = comite_corto_a_largo(inscripcion.comite_3)

    delegacion_oficial = inscripcion.delegacion_oficial if inscripcion.delegacion_oficial else "No"
    responsable_delegacion_oficial = inscripcion.responsable_delegacion_oficial if inscripcion.delegacion_oficial else "No aplica"

    html = html_emails["delegacion"].format(**locals())

    msg = MIMEMultipart()
    msg["From"] = "secretariadefinanzas@smmun.com"
    msg["To"] = inscripcion.correo
    msg["Subject"] = "¡Gracias! - RLM-MUN 2026 Latinoamérica: Conectando culturas"
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.zoho.com", 587) as smtp:
        smtp.starttls()
        smtp.login(msg["From"], os.environ["MAIL_PASS"])
        smtp.sendmail(msg["From"], msg["To"], msg.as_string())

        # Enviar a finanzas
        msg.replace_header("To", msg["From"])
        msg.replace_header("Subject", f"Inscripción: {inscripcion.nombre} {inscripcion.apellido}")
        smtp.sendmail(msg["From"], msg["From"], msg.as_string())


def manejar_inscripcion_faculty(inscripcion: FacultySM, data: FormData, drive_id: str):
    link_comprobante = f"https://drive.google.com/file/d/{drive_id}"

    # Añadir nueva página al sheets
    service = build("sheets", "v4", credentials=google_credentials)
    title = f"{inscripcion.institucion_delegacion_oficial}_{int(time.time())}"
    body = {
        "requests": {
            "addSheet": {
                "properties": {
                    "title": title
                }
            }
        }
    }

    service.spreadsheets().batchUpdate(spreadsheetId="1z0qs3SmXNdTxUBK1tkU29SJJhH9G0ny3cmmCtWYnABs", body=body).execute()

    # Añadir valores a la tabla general
    body = {
        "values": [
            [
                False,
                inscripcion.fecha.strftime(r"%d/%m/%Y, %H:%M:%S"),
                inscripcion.institucion_delegacion_oficial,
                inscripcion.numero_delegaciones,
                inscripcion.nombre_faculty,
                inscripcion.apellido_faculty,
                f"'{inscripcion.celular_faculty}",
                inscripcion.correo_faculty,
                inscripcion.pais_faculty,
                inscripcion.ciudad_estado_faculty,
                link_comprobante
            ]
        ]
    }

    service.spreadsheets().values().append(
        spreadsheetId="1z0qs3SmXNdTxUBK1tkU29SJJhH9G0ny3cmmCtWYnABs",
        range=f"FACULTYS!A1:K1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    # Añadir valores al sheets
    body = {
        "values": [
            [
                inscripcion.institucion_delegacion_oficial,
            ],
            [
                "Nombre:",
                f"{inscripcion.nombre_faculty} {inscripcion.apellido_faculty}",
            ],
            [
                "Celular:",
                inscripcion.celular_faculty
            ],
            [
                "Correo:",
                inscripcion.correo_faculty
            ],
            [
                "Lugar de residencia:",
                f"{inscripcion.ciudad_estado_faculty}, {inscripcion.pais_faculty}"
            ],
            [
                "Número de delegaciones:",
                inscripcion.numero_delegaciones
            ],
            [
                "Fecha de inscripción",
                inscripcion.fecha.strftime(r"%d/%m/%Y, %H:%M:%S")
            ],
            [
                "Comprobante de pago:",
                link_comprobante
            ],
            [],
            [
                "Nombre",
                "Apellido",
                "Edad",
                "Celular",
                "Correo",
                "Lugar de residencia",
                "Escolaridad",
                "Escuela"
            ]
        ]
    }

    delegaciones = {
        "values": []
    }

    for i in range(inscripcion.numero_delegaciones):
        body["values"].append([
            data.get(f"nombre_d{i}"),
            data.get(f"apellido_d{i}"),
            data.get(f"edad_d{i}"),
            data.get(f"celular_d{i}"),
            data.get(f"correo_d{i}"),
            f"{data.get(f'ciudad_estado_d{i}')}, {data.get(f'pais_d{i}')}",
            data.get(f"escolaridad_d{i}"),
            data.get(f"escuela_d{i}")
        ])

        delegaciones["values"].append([
            inscripcion.institucion_delegacion_oficial,
            data.get(f"nombre_d{i}"),
            data.get(f"apellido_d{i}"),
            data.get(f"edad_d{i}"),
            data.get(f"celular_d{i}"),
            data.get(f"correo_d{i}"),
            f"{data.get(f'ciudad_estado_d{i}')}, {data.get(f'pais_d{i}')}",
            data.get(f"escolaridad_d{i}"),
            data.get(f"escuela_d{i}")
        ])

    service.spreadsheets().values().append(
        spreadsheetId="1z0qs3SmXNdTxUBK1tkU29SJJhH9G0ny3cmmCtWYnABs",
        range=f"{title}!A1:H1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    service.spreadsheets().values().append(
        spreadsheetId="1z0qs3SmXNdTxUBK1tkU29SJJhH9G0ny3cmmCtWYnABs",
        range=f"DELEGACIONES!A1:I1",
        valueInputOption="USER_ENTERED",
        body=delegaciones
    ).execute()

    # Mandar correo
    msg = MIMEMultipart()
    msg["From"] = "secretariadefinanzas@smmun.com"
    msg["To"] = inscripcion.correo_faculty
    msg["Subject"] = "¡Gracias! - RLM-MUN 2026 Latinoamérica: Conectando culturas"
    msg["Date"] = formatdate(localtime=True)

    html = html_emails["faculty"].format(**locals())
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.zoho.com", 587) as smtp:
        smtp.starttls()
        smtp.login(msg["From"], os.environ["MAIL_PASS"])
        smtp.sendmail(msg["From"], msg["To"], msg.as_string())

        # Enviar a finanzas
        msg.replace_header("To", msg["From"])
        msg.replace_header("Subject", f"FACULTY: {inscripcion.nombre_faculty} {inscripcion.apellido_faculty}")
        smtp.sendmail(msg["From"], msg["From"], msg.as_string())


# Endpoint para el forms
@router.post("/registro/delegaciones")
def registrar(background_tasks: BackgroundTasks, data: DelegacionFormData = Depends(), comprobante: UploadFile = File(...)):
    # Validar archivo
    if comprobante.content_type is None or comprobante.size is None:
        raise ValueError("No se envió la imagen.")

    if not (comprobante.content_type.startswith("image/") or comprobante.content_type == "application/pdf") or comprobante.size > 5242880:
        raise ValueError("Imagen inválida.")

    comites = [data.comite_0, data.comite_1, data.comite_2]
    if len(comites) != len(set(comites)):
        raise ValueError("Opciones de comités repetidas.")

    # Validar países
    paises_0 = [data.comite_0_pais_0, data.comite_0_pais_1, data.comite_0_pais_2]
    if len(paises_0) != len(set(paises_0)):
        raise ValueError("Opciones de delegación repetidas.")
    
    paises_1 = [data.comite_1_pais_0, data.comite_1_pais_1, data.comite_1_pais_2]
    if len(paises_1) != len(set(paises_1)):
        raise ValueError("Opciones de delegación repetidas.")
    
    paises_2 = [data.comite_2_pais_0, data.comite_2_pais_1, data.comite_2_pais_2]
    if len(paises_2) != len(set(paises_2)):
        raise ValueError("Opciones de delegación repetidas.")
    
    # Validar edades
    if not 11 <= int(data.edad) <= 26:
        raise ValueError("Edad inválida.")

    # Modelo base de datos
    inscripcion = DelegacionSM(
        delegacion_oficial=data.nombre_delegacion_oficial or "No",
        responsable_delegacion_oficial=data.responsable_delegacion_oficial or "No aplica",

        nombre=data.nombre,
        apellido=data.apellido,
        edad=int(data.edad),
        celular=data.celular,
        correo=data.correo,
        pais=data.pais,
        ciudad_estado=data.ciudad_estado,
        escolaridad=data.escolaridad,
        escuela="Secundaria Ricardo López Méndez" if data.escuela_rlm == "RLM" else (data.escuela or "No aplica"),
        contacto_emergencia=f"{data.nombre_contacto} ({data.relacion_contacto}): {data.celular_contacto}",
        info_extra=data.info_extra if data.info_extra else None,

        comite_1=data.comite_0,
        comite_1_opcion_1=data.comite_0_pais_0.split(":")[1],
        comite_1_opcion_2=data.comite_0_pais_1.split(":")[1],
        comite_1_opcion_3=data.comite_0_pais_2.split(":")[1],

        comite_2=data.comite_1,
        comite_2_opcion_1=data.comite_1_pais_0.split(":")[1],
        comite_2_opcion_2=data.comite_1_pais_1.split(":")[1],
        comite_2_opcion_3=data.comite_1_pais_2.split(":")[1],

        comite_3=data.comite_2,
        comite_3_opcion_1=data.comite_2_pais_0.split(":")[1],
        comite_3_opcion_2=data.comite_2_pais_1.split(":")[1],
        comite_3_opcion_3=data.comite_2_pais_2.split(":")[1]
    )

    # Subir comprobante a drive
    service = build("drive", "v3", credentials=google_credentials)

    file_metadata = {
        "name": f"DELEGACION_{inscripcion.nombre}_{inscripcion.apellido}_{int(time.time())}{pathlib.Path(cast(str, comprobante.filename)).suffix}",
        "parents": ["1AUby3HWkATfS2tZPnUlGi8Ri6FWx2OZg"]
    }

    media = MediaIoBaseUpload(comprobante.file, mimetype=comprobante.content_type, chunksize=-1)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    # Manejar inscripción
    background_tasks.add_task(manejar_inscripcion, inscripcion, file.get("id"))

    # Redirigir a página de confirmación
    return RedirectResponse(f"{URL_BASE}/registro/confirmacion/", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/registro/faculty")
async def registrar_faculty(background_tasks: BackgroundTasks, request: Request, data: FacultyFormData = Depends(), comprobante: UploadFile = File(...)):
    # Validar archivo
    if comprobante.content_type is None or comprobante.size is None:
        raise ValueError("No se envió la imagen.")

    if not (comprobante.content_type.startswith("image/") or comprobante.content_type == "application/pdf") or comprobante.size > 5242880:
        raise ValueError("Imagen inválida.")

    # Modelo base de datos
    inscripcion = FacultySM(
        institucion_delegacion_oficial=data.institucion_delegacion_oficial,
        nombre_faculty=data.nombre_faculty,
        apellido_faculty=data.apellido_faculty,
        celular_faculty=data.celular_faculty,
        correo_faculty=data.correo_faculty,
        ciudad_estado_faculty=data.ciudad_estado_faculty,
        pais_faculty=data.pais_faculty,
        numero_delegaciones=int(data.numero_delegaciones)
    )

    # Subir comprobante a drive
    service = build("drive", "v3", credentials=google_credentials)

    file_metadata = {
        "name": f"FACULTY_{inscripcion.institucion_delegacion_oficial}_{int(time.time())}{pathlib.Path(cast(str, comprobante.filename)).suffix}",
        "parents": ["1P1HBXBWCaolwoEWyqvgcwyP_E48PCHba"]
    }

    media = MediaIoBaseUpload(comprobante.file, mimetype=comprobante.content_type, chunksize=-1)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    # Manejar inscripción
    background_tasks.add_task(manejar_inscripcion_faculty, inscripcion, await request.form(), file.get("id"))

    return RedirectResponse(f"{URL_BASE}/registro/confirmacion/", status_code=status.HTTP_303_SEE_OTHER)

# Usar el router y montar el folder de comprobantes como estático
app.include_router(router)
