from typing import Annotated, Optional, cast
from fastapi import FastAPI, APIRouter, Form, File, UploadFile, Depends, status, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Field, Session, SQLModel, create_engine
from pydantic import EmailStr
from dataclasses import dataclass
from contextlib import asynccontextmanager
import unicodedata
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.discovery import build
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from datetime import datetime, timedelta
import os
import pathlib
import time
import json

# URL de la página estática
URL_BASE = "https://smmun0githubio-production.up.railway.app"

# Lista de comités y tipos no permitidos en codelegación
COMITES_VALIDOS = [
    "SOCHUM",
    "ONU SIDA",
    "ONU-Hábitat",
    "CCPCJ",
    "UNRWA",
    "Cumbre",
    "NASA",
    "WWF",
    "Crisis",
    "FIA",
    "FHCM",
]

TIPOS_SOLO_INDIVIDUAL = {"pilotos", "disenadores_emergentes", "astronautas", "representantes_nasa"}
COMITES_CON_TIPOS = {"fia", "fhcm", "nasa", "cumbre_futuro"}

# Cargar delegaciones para validaciones cruzadas
with open("delegaciones.json", "r", encoding="utf-8") as delegaciones_json:
    delegaciones_data = json.load(delegaciones_json)


# Clase para recibir y validar el forms de delegaciones
@dataclass
class DelegacionFormData:
    modalidad: str = Form(pattern=r"^(individual|pareja)$")
    delegacion_oficial: str = Form(pattern=r"^(si|no)$")
    nombre_delegacion_oficial: Optional[str] = Form(None, max_length=150)
    responsable_delegacion_oficial: Optional[str] = Form(None, max_length=150)

    nombre_0: str = Form(max_length=150)
    apellido_0: str = Form(max_length=150)
    edad_0: str = Form(max_length=2)
    celular_0: str = Form(max_length=30)
    correo_0: EmailStr = Form(max_length=150)
    pais_0: str = Form(max_length=150)
    ciudad_estado_0: str = Form(max_length=150)
    escolaridad_0: str = Form(pattern=r"^(Secundaria|Preparatoria|Universidad|Egresado|No estudio)$", max_length=150)
    escuela_0: Optional[str] = Form(None, max_length=150)
    nombre_contacto_0: str = Form(max_length=150)
    celular_contacto_0: str = Form(max_length=30)
    relacion_contacto_0: str = Form(max_length=150)
    info_extra_0: Optional[str] = Form(None, max_length=150)

    nombre_1: Optional[str] = Form(None, max_length=150)
    apellido_1: Optional[str] = Form(None, max_length=150)
    edad_1: Optional[str] = Form(None, max_length=2)
    celular_1: Optional[str] = Form(None, max_length=30)
    correo_1: Optional[EmailStr | str] = Form(None, max_length=150)
    pais_1: Optional[str] = Form(None, max_length=150)
    ciudad_estado_1: Optional[str] = Form(None, max_length=150)
    escolaridad_1: Optional[str] = Form(None, pattern=r"^(|Secundaria|Preparatoria|Universidad|Egresado|No estudio)$", max_length=150)
    escuela_1: Optional[str] = Form(None, max_length=150)
    nombre_contacto_1: Optional[str] = Form(None, max_length=150)
    celular_contacto_1: Optional[str] = Form(None, max_length=30)
    relacion_contacto_1: Optional[str] = Form(None, max_length=150)
    info_extra_1: Optional[str] = Form(None, max_length=150)

    comite_0: str = Form(pattern=r"^(SOCHUM|ONU SIDA|ONU-Hábitat|CCPCJ|UNRWA|Cumbre|NASA|WWF|Crisis|FIA|FHCM)$")
    comite_0_pais_0: str = Form(max_length=150)
    comite_0_pais_1: str = Form(max_length=150)
    comite_0_pais_2: Optional[str] = Form(None, max_length=150)

    comite_1: str = Form(pattern=r"^(SOCHUM|ONU SIDA|ONU-Hábitat|CCPCJ|UNRWA|Cumbre|NASA|WWF|Crisis|FIA|FHCM)$")
    comite_1_pais_0: str = Form(max_length=150)
    comite_1_pais_1: str = Form(max_length=150)
    comite_1_pais_2: Optional[str] = Form(None, max_length=150)

    comite_2: str = Form(pattern=r"^(SOCHUM|ONU SIDA|ONU-Hábitat|CCPCJ|UNRWA|Cumbre|NASA|WWF|Crisis|FIA|FHCM)$")
    comite_2_pais_0: str = Form(max_length=150)
    comite_2_pais_1: str = Form(max_length=150)
    comite_2_pais_2: Optional[str] = Form(None, max_length=150)


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


# Clase para los datos de PostgreSQL de delegación
class DelegacionSM(SQLModel, table=True): # type: ignore
    id: int | None = Field(default = None, primary_key=True)
    fecha: datetime = Field(default_factory=lambda: datetime.now() - timedelta(hours=6), index=True)
    codelegacion: bool
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

    nombre_co: str | None
    apellido_co: str | None
    edad_co: int | None
    celular_co: str | None
    correo_co: str | None
    pais_co: str | None
    ciudad_estado_co: str | None
    escolaridad_co: str | None
    escuela_co: str | None
    contacto_emergencia_co: str | None
    info_extra_co: str | None

    comite_1: str = Field(index=True)
    comite_1_opcion_1: str
    comite_1_opcion_2: str
    comite_1_opcion_3: str | None

    comite_2: str = Field(index=True)
    comite_2_opcion_1: str
    comite_2_opcion_2: str
    comite_2_opcion_3: str | None

    comite_3: str = Field(index=True)
    comite_3_opcion_1: str
    comite_3_opcion_2: str
    comite_3_opcion_3: str | None


# Clase para los datos de PostgreSQL de faculty
class FacultySM(SQLModel, table=True): # type: ignore
    id: int | None = Field(default = None, primary_key=True)
    fecha: datetime = Field(default_factory=lambda: datetime.now() - timedelta(hours=6), index=True)

    institucion_delegacion_oficial: str
    nombre_faculty: str
    apellido_faculty: str
    celular_faculty: str
    correo_faculty: str
    ciudad_estado_faculty: str
    pais_faculty: str

    numero_delegaciones: int


# Conectar con la base de datos
db_url = os.environ["DATABASE_URL"]
engine = create_engine(db_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


# Inicializar app y router
router = APIRouter()
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


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
        "https://smmun.com",
        "https://smmun0githubio-production.up.railway.app",
        "https://smmun0.github.io",
        "https://github.io"
    ],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)


# Credenciales para APIs de Google
google_credentials = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_KEY"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"])


# HTML y archivos adjuntos de correos para enviar (plantillas de prueba)
with open("email/codelegacion.html", "r", encoding="utf-8") as co, open("email/delegacion.html", "r", encoding="utf-8") as dg, open("email/faculty.html", encoding="utf-8") as fac:
    html_emails = {
        "codelegacion": co.read(),
        "delegacion": dg.read(),
        "faculty": fac.read(),
        #"reglamento": reg.read()
    }


def comite_corto_a_largo(comite):
    match comite:
        case "SOCHUM":
            return "Tercera Comisión de la Asamblea General referente a lo Social, Cultural, Humanitario y de Derechos Humanos (SOCHUM)"
        case "ONU SIDA":
            return "Programa Conjunto de las Naciones Unidas para el VIH-SIDA (ONU SIDA)"
        case "ONU-Hábitat":
            return "Programa de las Naciones Unidas para los Asentamientos Humanos (ONU-Hábitat)"
        case "CCPCJ":
            return "Comisión de prevención del delito y Justicia Penal de las Naciones Unidas (CCPCJ)"
        case "UNRWA":
            return "Agencia de las Naciones Unidas para los Refugiados de Palestina en Oriente Próximo (UNRWA)"
        case "Cumbre":
            return "Cumbre del Futuro"
        case "NASA":
            return "Administración Nacional de Aeronáutica y del Espacio (NASA)"
        case "WWF":
            return "World Wildlife Fund for Nature (WWF)"
        case "Crisis":
            return "Crisis Futura"
        case "FIA":
            return "Federación Internacional del Automóvil (FIA)"
        case "FHCM":
            return "Federación de Alta Costura y Moda (FHCM)"
        case _:
            return comite


def normalizar_comite(siglas: str) -> str:
    texto = unicodedata.normalize("NFD", siglas)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = texto.lower().replace(" ", "_").replace("-", "_")
    if texto == "cumbre":
        return "cumbre_futuro"
    return texto


def obtener_tipo_delegacion(comite_siglas: str, delegacion_nombre: str) -> Optional[str]:
    clave = normalizar_comite(comite_siglas)
    data = delegaciones_data.get(clave)
    if not isinstance(data, dict):
        return None

    for tipo, lista in data.items():
        if any(item.get("nombre") == delegacion_nombre for item in lista):
            return tipo
    return None


def parse_delegacion(valor: str) -> tuple[str, str]:
    if ":" not in valor:
        raise ValueError("Delegación inválida.")
    comite_valor, delegacion = valor.split(":", 1)
    return comite_valor, delegacion


def manejar_inscripcion(inscripcion: DelegacionSM, comprobante: UploadFile):
    # Subir comprobante a drive
    service = build("drive", "v3", credentials=google_credentials)

    file_metadata = {
        "name": f"{'CODELEGACION' if inscripcion.codelegacion else 'DELEGACION'}_{inscripcion.nombre}_{inscripcion.apellido}_{int(time.time())}{pathlib.Path(cast(str, comprobante.filename)).suffix}",
        "parents": ["1XfM0CcaGGQAprXQKs1XSoqU4H7SCb7G4"]
    }

    media = MediaIoBaseUpload(comprobante.file, mimetype=comprobante.content_type, chunksize=-1)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    # Añadir al sheets de inscripciones
    service = build("sheets", "v4", credentials=google_credentials)
    body = {
        "values": [
            [
                False,

                inscripcion.fecha.strftime(r"%d/%m/%Y, %H:%M:%S"),

                inscripcion.codelegacion,
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

                inscripcion.nombre_co,
                inscripcion.apellido_co,
                inscripcion.edad_co,
                f"'{inscripcion.celular_co}",
                inscripcion.correo_co,
                inscripcion.pais_co,
                inscripcion.ciudad_estado_co,
                inscripcion.escolaridad_co,
                inscripcion.escuela_co,
                inscripcion.contacto_emergencia_co,
                inscripcion.info_extra_co,

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

                f"https://drive.google.com/file/d/{file.get('id')}"
            ]
        ]
    }

    service.spreadsheets().values().append(
        spreadsheetId="1EetaVUgXbNUjZ7K2NloWuH1o5kW7usDZKlO9xVMzyic",
        range="A1:AG1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    # Mandar correo
    destinatarios = list(filter(None, [inscripcion.correo, inscripcion.correo_co]))

    comite_1_corto = comite_corto_a_largo(inscripcion.comite_1)
    comite_2_corto = comite_corto_a_largo(inscripcion.comite_2)
    comite_3_corto = comite_corto_a_largo(inscripcion.comite_3)

    if inscripcion.codelegacion:
        html = html_emails["codelegacion"].format(**locals())
    else:
        html = html_emails["delegacion"].format(**locals())

    msg = MIMEMultipart()
    msg["From"] = "secretariadefinanzas@smmun.com"
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = "¡Gracias! - SMMUN 2026: Una Nueva Historia"
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.zoho.com", 587) as smtp:
        smtp.starttls()
        smtp.login(msg["From"], "BZ97NPpWTPLP")
        smtp.sendmail(msg["From"], destinatarios, msg.as_string())

        # Enviar a finanzas
        msg.replace_header("To", msg["From"])
        msg.replace_header("Subject", f"Inscripción: {inscripcion.nombre} {inscripcion.apellido}")
        smtp.sendmail(msg["From"], msg["From"], msg.as_string())


def manejar_inscripcion_faculty(inscripcion: FacultySM, data: FormData, comprobante: UploadFile):
    # Subir comprobante a drive
    service = build("drive", "v3", credentials=google_credentials)

    file_metadata = {
        "name": f"FACULTY_{inscripcion.institucion_delegacion_oficial}_{int(time.time())}{pathlib.Path(cast(str, comprobante.filename)).suffix}",
        "parents": ["1yhuaWkBRT6rdgUPTCdvfmumay5Fkuowp"]
    }

    media = MediaIoBaseUpload(comprobante.file, mimetype=comprobante.content_type, chunksize=-1)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    link_comprobante = f"https://drive.google.com/file/d/{file.get('id')}"

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

    service.spreadsheets().batchUpdate(spreadsheetId="19KPTFOSbkflFMvnp4wb4tpMUTS9o0H14nv02q4magBg", body=body).execute()

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
        spreadsheetId="19KPTFOSbkflFMvnp4wb4tpMUTS9o0H14nv02q4magBg",
        range=f"A1:K1",
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
        spreadsheetId="19KPTFOSbkflFMvnp4wb4tpMUTS9o0H14nv02q4magBg",
        range=f"{title}!A1:H1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    service.spreadsheets().values().append(
        spreadsheetId="19KPTFOSbkflFMvnp4wb4tpMUTS9o0H14nv02q4magBg",
        range=f"DELEGACIONES!A1:I1",
        valueInputOption="USER_ENTERED",
        body=delegaciones
    ).execute()

    # Mandar correo
    msg = MIMEMultipart()
    msg["From"] = "secretariadefinanzas@smmun.com"
    msg["To"] = inscripcion.correo_faculty
    msg["Subject"] = "¡Gracias! - SMMUN 2025: Una Nueva Historia"
    msg["Date"] = formatdate(localtime=True)

    html = html_emails["faculty"].format(**locals())
    msg.attach(MIMEText(html, "html"))

    #part = MIMEApplication(html_emails["reglamento"], Name="REGLAMENTO_FACULTY_PLACEHOLDER.txt")
    #part['Content-Disposition'] = 'attachment; filename="REGLAMENTO_FACULTY_PLACEHOLDER.txt"'
    #msg.attach(part)

    with smtplib.SMTP("smtp.zoho.com", 587) as smtp:
        smtp.starttls()
        smtp.login(msg["From"], "BZ97NPpWTPLP")
        smtp.sendmail(msg["From"], msg["To"], msg.as_string())

        # Enviar a finanzas
        msg.replace_header("To", msg["From"])
        msg.replace_header("Subject", f"FACULTY: {inscripcion.nombre_faculty} {inscripcion.apellido_faculty}")
        smtp.sendmail(msg["From"], msg["From"], msg.as_string())


# Endpoint para el forms
@router.post("/api/registro/delegaciones")
def registrar(background_tasks: BackgroundTasks, session: SessionDep, data: DelegacionFormData = Depends(), comprobante: UploadFile = File(...)):
    # Validar archivo
    if comprobante.content_type is None or comprobante.size is None:
        raise ValueError("No se envió la imagen.")

    if not (comprobante.content_type.startswith("image/") or comprobante.content_type == "application/pdf") or comprobante.size > 5242880:
        raise ValueError("Imagen inválida.")

    # Validar comités
    if data.modalidad == "pareja" and (data.comite_0 in ["Cumbre", "Crisis"] or data.comite_1 in ["Cumbre", "Crisis"] or data.comite_2 in ["Cumbre", "Crisis"]):
        raise ValueError("Opción inválida de comité para codelegación.")

    comites = [data.comite_0, data.comite_1, data.comite_2]
    if len(comites) != len(set(comites)):
        raise ValueError("Opciones de comités repetidas.")

    if data.delegacion_oficial == "si" and (not data.nombre_delegacion_oficial or not data.responsable_delegacion_oficial):
        raise ValueError("Faltan datos de delegación oficial.")

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

    es_codelegacion = data.modalidad == "pareja"
    
    # Validar edades
    if not 11 <= int(data.edad_0) <= 26 or (es_codelegacion and (data.edad_1 is None or not 11 <= int(data.edad_1) <= 26)):
        raise ValueError("Edad inválida.")

    # Validar datos de codelegación obligatorios
    if es_codelegacion:
        requeridos = [
            data.nombre_1,
            data.apellido_1,
            data.edad_1,
            data.celular_1,
            data.correo_1,
            data.pais_1,
            data.ciudad_estado_1,
            data.escolaridad_1,
            data.nombre_contacto_1,
            data.celular_contacto_1,
            data.relacion_contacto_1,
        ]
        if any(item is None or str(item).strip() == "" for item in requeridos):
            raise ValueError("Faltan datos de la codelegación.")

    # Validar tipos no permitidos en codelegación
    if es_codelegacion:
        delegaciones_seleccionadas = [
            (data.comite_0, data.comite_0_pais_0),
            (data.comite_0, data.comite_0_pais_1),
            (data.comite_0, data.comite_0_pais_2),
            (data.comite_1, data.comite_1_pais_0),
            (data.comite_1, data.comite_1_pais_1),
            (data.comite_1, data.comite_1_pais_2),
            (data.comite_2, data.comite_2_pais_0),
            (data.comite_2, data.comite_2_pais_1),
            (data.comite_2, data.comite_2_pais_2),
        ]

        for comite_siglas, valor in delegaciones_seleccionadas:
            if not valor:
                continue
            _, delegacion_nombre = parse_delegacion(valor)
            tipo = obtener_tipo_delegacion(comite_siglas, delegacion_nombre)
            if tipo in TIPOS_SOLO_INDIVIDUAL:
                raise ValueError("Delegación no disponible para codelegación.")

    # Modelo base de datos
    delegacion_oficial_nombre = data.nombre_delegacion_oficial or "No aplica"
    info_extra_principal = data.info_extra_0 if data.info_extra_0 else None
    if data.delegacion_oficial == "si":
        info_extra_principal = (info_extra_principal + " | " if info_extra_principal else "") + f"Delegación oficial: {delegacion_oficial_nombre}"

    inscripcion = DelegacionSM(
        codelegacion=es_codelegacion,
        delegacion_oficial=data.delegacion_oficial,
        responsable_delegacion_oficial=data.responsable_delegacion_oficial or "No aplica",

        nombre=data.nombre_0,
        apellido=data.apellido_0,
        edad=int(data.edad_0),
        celular=data.celular_0,
        correo=data.correo_0,
        pais=data.pais_0,
        ciudad_estado=data.ciudad_estado_0,
        escolaridad=data.escolaridad_0,
        escuela=data.escuela_0 or "No aplica",
        contacto_emergencia=f"{data.nombre_contacto_0} ({data.relacion_contacto_0}): {data.celular_contacto_0}",
        info_extra=info_extra_principal,

        nombre_co=data.nombre_1 if es_codelegacion else None,
        apellido_co=data.apellido_1 if es_codelegacion else None,
        edad_co=int(cast(str, data.edad_1)) if es_codelegacion else None,
        celular_co=data.celular_1 if es_codelegacion else None,
        correo_co=data.correo_1 if es_codelegacion else None,
        pais_co=data.pais_1 if es_codelegacion else None,
        ciudad_estado_co=data.ciudad_estado_1 if es_codelegacion else None,
        escolaridad_co=data.escolaridad_1 if es_codelegacion else None,
        escuela_co=(data.escuela_1 or "No aplica") if es_codelegacion else None,
        contacto_emergencia_co=f"{data.nombre_contacto_1} ({data.relacion_contacto_1}): {data.celular_contacto_1}" if es_codelegacion else None,
        info_extra_co=data.info_extra_1 if es_codelegacion and data.info_extra_1 else None,

        comite_1=data.comite_0,
        comite_1_opcion_1=data.comite_0_pais_0.split(":")[1],
        comite_1_opcion_2=data.comite_0_pais_1.split(":")[1],
        comite_1_opcion_3=data.comite_0_pais_2.split(":")[1] if data.comite_0_pais_2 else None,

        comite_2=data.comite_1,
        comite_2_opcion_1=data.comite_1_pais_0.split(":")[1],
        comite_2_opcion_2=data.comite_1_pais_1.split(":")[1],
        comite_2_opcion_3=data.comite_1_pais_2.split(":")[1] if data.comite_1_pais_2 else None,

        comite_3=data.comite_2,
        comite_3_opcion_1=data.comite_2_pais_0.split(":")[1],
        comite_3_opcion_2=data.comite_2_pais_1.split(":")[1],
        comite_3_opcion_3=data.comite_2_pais_2.split(":")[1] if data.comite_2_pais_2 else None
    )

    # Subir a base de datos
    session.add(inscripcion)
    session.commit()
    session.refresh(inscripcion)

    # Manejar inscripción
    background_tasks.add_task(manejar_inscripcion, inscripcion, comprobante)

    # Redirigir a página de confirmación
    return RedirectResponse(f"{URL_BASE}/registro/confirmacion/", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/api/registro/faculty")
async def registrar_faculty(background_tasks: BackgroundTasks, session: SessionDep, request: Request, data: FacultyFormData = Depends(), comprobante: UploadFile = File(...)):
    # Validar archivo
    if comprobante.content_type is None or comprobante.size is None:
        raise ValueError("No se envió la imagen.")

    if not (comprobante.content_type.startswith("image/") or comprobante.content_type == "application/pdf") or comprobante.size > 5242880:
        raise ValueError("Imagen inválida.")

    if int(data.numero_delegaciones) < 4:
        raise ValueError("Número de delegaciones inválido.")

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

    # Subir a base de datos
    session.add(inscripcion)
    session.commit()
    session.refresh(inscripcion)

    # Manejar inscripción
    background_tasks.add_task(manejar_inscripcion_faculty, inscripcion, await request.form(), comprobante)

    return RedirectResponse(f"{URL_BASE}/registro/confirmacion/", status_code=status.HTTP_303_SEE_OTHER)

# Usar el router y montar el folder de comprobantes como estático
app.include_router(router)
