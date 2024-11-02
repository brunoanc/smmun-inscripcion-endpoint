from typing import Annotated, Optional, cast
from fastapi import FastAPI, APIRouter, Form, File, UploadFile, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, Session, SQLModel, create_engine
from pydantic import EmailStr
from dataclasses import dataclass
from contextlib import asynccontextmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import os
import pathlib
import time
import datetime

# URL de la página estática
URL_BASE = "http://192.168.1.81:8080"

# Clase para los datos de PostgreSQL
class DelegacionSM(SQLModel, table=True): # type: ignore
    id: int | None = Field(default = None, primary_key=True)
    fecha: datetime.datetime = Field(default_factory=datetime.datetime.utcnow, index=True)
    codelegacion: bool
    delegacion_oficial: str | None

    nombre: str
    apellido: str
    edad: int
    celular: str
    correo: str
    pais: str
    ciudad_estado: str
    escolaridad: str
    escuela: str

    nombre_co: str | None
    apellido_co: str | None
    edad_co: int | None
    celular_co: str | None
    correo_co: str | None
    pais_co: str | None
    ciudad_estado_co: str | None
    escolaridad_co: str | None
    escuela_co: str | None

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

    comprobante: str

# Conectar con la base de datos
"""
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
"""

# Clase para recibir y validar el forms
@dataclass
class FormData:
    modalidad: str = Form(pattern=r"^(individual|pareja)$")
    delegacion_oficial: str = Form(pattern=r"^(si|no)$")
    nombre_delegacion_oficial: Optional[str] = Form(None, max_length=100)

    nombre_0: str = Form(max_length=100)
    apellido_0: str = Form(max_length=100)
    edad_0: str = Form(max_length=2)
    celular_0: str = Form(max_length=30)
    correo_0: EmailStr = Form(max_length=100)
    pais_0: str = Form(max_length=100)
    ciudad_estado_0: str = Form(max_length=100)
    escolaridad_0: str = Form(pattern=r"^(secundaria|preparatoria|universidad|egresado|otra)$", max_length=100)
    escolaridad_otra_0: Optional[Annotated[str, Form(max_length=20)]] = None
    escuela_0: str = Form(max_length=100)

    nombre_1: Optional[str] = Form(None, max_length=100)
    apellido_1: Optional[str] = Form(None, max_length=100)
    edad_1: Optional[str] = Form(None, max_length=2)
    celular_1: Optional[str] = Form(max_length=30)
    correo_1: Optional[EmailStr | str] = Form(None, max_length=100)
    pais_1: Optional[str] = Form(None, max_length=100)
    ciudad_estado_1: Optional[str] = Form(None, max_length=100)
    escolaridad_1: Optional[str] = Form(None, pattern=r"^(|secundaria|preparatoria|universidad|egresado|otra)$", max_length=100)
    escolaridad_otra_1: Optional[str] = Form(None, max_length=100)
    escuela_1: Optional[str] = Form(None, max_length=100)

    comite_0: str = Form(pattern=r"^(CSTD|CRC|OIT|NOBEL|CRM|UNFPA|OSGEY|CIDH|CIJ|COI)$")
    comite_0_pais_0: str = Form(max_length=100)
    comite_0_pais_1: str = Form(max_length=100)
    comite_0_pais_2: str = Form(max_length=100)

    comite_1: str = Form(pattern=r"^(CSTD|CRC|OIT|NOBEL|CRM|UNFPA|OSGEY|CIDH|CIJ|COI)$")
    comite_1_pais_0: str = Form(max_length=100)
    comite_1_pais_1: str = Form(max_length=100)
    comite_1_pais_2: str = Form(max_length=100)

    comite_2: str = Form(pattern=r"^(CSTD|CRC|OIT|NOBEL|CRM|UNFPA|OSGEY|CIDH|CIJ|COI)$")
    comite_2_pais_0: str = Form(max_length=100)
    comite_2_pais_1: str = Form(max_length=100)
    comite_2_pais_2: str = Form(max_length=100)

# Inicializar app y router
router = APIRouter()
"""app = FastAPI(lifespan=lifespan)"""
app = FastAPI()

# Mostrar página de error en vez de error en JSON
@app.exception_handler(StarletteHTTPException)
@app.exception_handler(RequestValidationError)
async def http_exception_handler(request, exc):
    """return RedirectResponse("https://0a3f-189-172-176-98.ngrok-free.app/error-registro", status_code=status.HTTP_303_SEE_OTHER)"""
    return RedirectResponse(f"{URL_BASE}/error-registro/", status_code=status.HTTP_303_SEE_OTHER)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8080",
        "https://smmun.com",
        "https://smmun0.github.io",
    ],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Endpoint para el forms
@router.post("/registro-delegaciones")
def registrar(data: FormData = Depends(), comprobante: UploadFile = File(...)):
    """def registrar(session: SessionDep, data: FormData = Depends(), comprobante: UploadFile = File(...)):"""
    # Validar archivo
    if comprobante.content_type is None or comprobante.size is None:
        raise ValueError("No se envió la imagen.")

    if not (comprobante.content_type.startswith("image/") or comprobante.content_type.startswith("pdf/")) or comprobante.size > 5242880:
        raise ValueError("Imagen inválida.")

    # Validar comités
    if data.modalidad == "pareja":
        if data.comite_0 in ["CRC", "NOBEL", "CIJ"] or data.comite_1 in ["CRC", "NOBEL", "CIJ"] or data.comite_2 in ["CRC", "NOBEL", "CIJ"]:
            raise ValueError("Opción inválida de comité.")

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

    es_codelegacion = data.modalidad == "pareja"
    
    # Validar edades
    if not 12 <= int(data.edad_0) <= 26 or (es_codelegacion and (data.edad_1 is None or not 12 <= int(data.edad_1) <= 26)):
        raise ValueError("Edad inválida.")
    
    comprobante_path = f"/comprobantes/{'CODELEGACION' if es_codelegacion else "DELEGACION"}_{data.nombre_0}_{data.apellido_0}_{int(time.time())}{pathlib.Path(cast(str, comprobante.filename)).suffix}"

    # Añadir a base de datos
    inscripcion = DelegacionSM(
        codelegacion=es_codelegacion,
        delegacion_oficial=data.nombre_delegacion_oficial,

        nombre=data.nombre_0,
        apellido=data.apellido_0,
        edad=int(data.edad_0),
        celular=data.celular_0,
        correo=data.correo_0,
        pais=data.pais_0,
        ciudad_estado=data.ciudad_estado_0,
        escolaridad=data.escolaridad_0 if data.escolaridad_0 is not None else data.escolaridad_otra_0,
        escuela=data.escuela_0, 

        nombre_co=data.nombre_1 if es_codelegacion else None,
        apellido_co=data.apellido_1 if es_codelegacion else None,
        edad_co=int(cast(str, data.edad_1)) if es_codelegacion else None,
        celular_co=data.celular_1 if es_codelegacion else None,
        correo_co=data.correo_1 if es_codelegacion else None,
        pais_co=data.pais_1 if es_codelegacion else None,
        ciudad_estado_co=data.ciudad_estado_1 if es_codelegacion else None,
        escolaridad_co=(data.escolaridad_1 if data.escolaridad_1 is not None else data.escolaridad_otra_1) if es_codelegacion else None,
        escuela_co=data.escuela_1 if es_codelegacion else None,

        comite_1=data.comite_0,
        comite_1_opcion_1=data.comite_0_pais_0.split(":")[1],
        comite_1_opcion_2=data.comite_0_pais_1.split(":")[1],
        comite_1_opcion_3=data.comite_0_pais_2.split(":")[1] if data.comite_0 != "CIJ" else None,

        comite_2=data.comite_1,
        comite_2_opcion_1=data.comite_1_pais_0.split(":")[1],
        comite_2_opcion_2=data.comite_1_pais_1.split(":")[1],
        comite_2_opcion_3=data.comite_1_pais_2.split(":")[1] if data.comite_1 != "CIJ" else None,

        comite_3=data.comite_2,
        comite_3_opcion_1=data.comite_2_pais_0.split(":")[1],
        comite_3_opcion_2=data.comite_2_pais_1.split(":")[1],
        comite_3_opcion_3=data.comite_2_pais_2.split(":")[1] if data.comite_2 != "CIJ" else None,

        comprobante=""#f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}{comprobante_path}"
    )

    """
    session.add(inscripcion)
    session.commit()
    session.refresh(inscripcion)

    # 1EetaVUgXbNUjZ7K2NloWuH1o5kW7usDZKlO9xVMzyic

    with open(comprobante_path, "wb+") as f:
        f.write(comprobante.file.read())
    """

    # Añadir al sheets de inscripciones
    spreadsheet_id = "1EetaVUgXbNUjZ7K2NloWuH1o5kW7usDZKlO9xVMzyic"
    credentials = service_account.Credentials.from_service_account_file("sheets-api-440213-0217b00115e9.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=credentials)
    body = {
        "values": [
            [
                inscripcion.fecha.strftime(r"%d/%m/%Y, %H:%M:%S"),

                inscripcion.codelegacion,
                inscripcion.delegacion_oficial,

                inscripcion.nombre,
                inscripcion.apellido,
                inscripcion.edad,
                inscripcion.celular,
                inscripcion.correo,
                inscripcion.pais,
                inscripcion.ciudad_estado,
                inscripcion.escolaridad,
                inscripcion.escuela,

                inscripcion.nombre_co,
                inscripcion.apellido_co,
                inscripcion.edad_co,
                inscripcion.celular_co,
                inscripcion.correo_co,
                inscripcion.pais_co,
                inscripcion.ciudad_estado_co,
                inscripcion.escolaridad_co,
                inscripcion.escuela_co,

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

                inscripcion.comprobante
            ]
        ]
    }

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="A1:AG1",
        valueInputOption="USER_ENTERED",
        body=body,
        insertDataOption="INSERT_ROWS"
    ).execute()

    # Redirigir a página de confirmación
    return RedirectResponse(f"{URL_BASE}/confirmar-registro/", status_code=status.HTTP_303_SEE_OTHER)

# Usar el router y montar el folder de comprobantes como estático
app.include_router(router)
"""app.mount("/comprobantes", StaticFiles(directory="/comprobantes"), name="comprobantes")"""
