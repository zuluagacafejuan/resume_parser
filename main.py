from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel as BaseModelPydantic

import re
import os
from typing import List
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI

model = ChatOpenAI(temperature=0)

class Resume(BaseModel):
    name: str = Field(description="nombre del candidato")
    skills: list = Field(description="lista de habilidades del candidato presentes en todo el documento, identificalas a partir de descripcion, educacion y experiencia. En español.")
    softskills: list = Field(description="lista de habilidades blandas del candidato presentes en todo el documento, identificalas a partir de descripcion, educacion y experiencia. En español.")
    hardskills: list = Field(description="lista de habilidades técnicas del candidato presentes en todo el documento, identificalas a partir de descripcion, educacion y experiencia. En español.")
    description: str = Field(description="descripción profesional del candidato")
    career: str = Field(description="carrera que estudió el candidato. Extraer: solo la carrera, no la universidad.")
    experience: list = Field(description="experiencia laboral del candidato. Cada experiencia es un json con keys company (compañia), description (descripcion), dates (fecha formato aaaa-mm-dd, si no conoces dia pon 01 en el dia, si no conoces mes pon 01 en el mes. Si la actividad sigue en curso, usa 'Presente' en la fecha de finalizacion) y role (cargo). Si no encuentras uno de los valores pon un string vacio. Si no encuentras fecha para esa experiencia pon '-' en la fecha. Si no encuentras descripcion para esa experiencia pon '-' en la descripcion")
    education: list = Field(description="educación del candidato. De cada uno extraer: Universidad, estudio y fecha. Cada educacion es un json con keys university (universidad), dates (fecha formato aaaa-mm-dd, si no conoces dia pon 01 en el dia, si no conoces mes pon 01 en el mes. Si la actividad sigue en curso, usa 'Presente' en la fecha de finalizacion) y program (estudio realizado). Si no encuentras fecha para ese estudio pon '-' en la fecha")

class Request(BaseModelPydantic):
    resume: str

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def formatear_fechas(string):
    # Caso -
    if string.strip() == "-":
        return "|"
    # Caso 2015-2016
    patron = re.compile(r'^\d{4}-\d{4}$')
    if patron.match(string):
        parte1 = string.split("-")[0]
        parte2 = string.split("-")[1]
        inicial = parte1+"-01-01"
        final = parte2+"-01-01"
        respuesta = inicial+"|"+final
        return respuesta

    # Caso 2015
    patron = re.compile(r'^\d{4}$')
    if patron.match(string):
        respuesta = string+"-01-01"
        return respuesta
    
    # Caso Enero de 2012 - Julio de 2012
    meses = {
        'ene':'01',
        'feb':'02',
        'mar': '03',
        'abr':'04',
        'may': '05',
        'jun':'06',
        'jul':'07',
        'ago':'08',
        'sep':'09',
        'oct':'10',
        'nov':'11',
        'dic':'12',
        'jan':'01',
        'apr':'04',
        'aug':'08',
        'dec':'12'
    }

    def obtener_año(frase):
        patron_anio = re.compile(r'\d{4}')
        coincidencias = patron_anio.findall(frase)
        if coincidencias:
            return coincidencias[0]
        else:
            return None
        
    def eliminar_año(frase):
        patron_anio = re.compile(r'\d{4}')
        frase_sin_año = patron_anio.sub('', frase)     
        return frase_sin_año.strip()
    
    def obtener_dia(frase):
        patron_dia = re.compile(r'\d{2}')
        coincidencias = patron_dia.findall(frase)
        if coincidencias:
            return coincidencias[0]
        else:
            patron_dia = re.compile(r'\d{1}')
            coincidencias2 = patron_dia.findall(frase)
            if coincidencias2:
                return coincidencias2[0]
            else:
                return "01"

    if len([i for i in string if i == "-"]) == 1:
        fecha_inicio = ""
        fecha_fin = ""

        segmento_inicio = string.split("-")[0].strip().lower()
        segmento_fin = string.split("-")[1].strip().lower()

        for mes, numero in meses.items():
            if segmento_inicio.find(mes) != -1:

                año = obtener_año(segmento_inicio)
                segmento_inicio = eliminar_año(segmento_inicio)
                dia = obtener_dia(segmento_inicio)

                fecha_inicio = str(año)+"-"+str(numero)+"-"+str(dia)
                continue

        for mes, numero in meses.items():
            if segmento_fin.find(mes) != -1:

                año = obtener_año(segmento_fin)
                segmento_inicio = eliminar_año(segmento_fin)
                dia = obtener_dia(segmento_fin)

                fecha_fin = str(año)+"-"+str(numero)+"-"+str(dia)
                continue
        return fecha_inicio+"|"+fecha_fin
    return string.replace(" - ", "|")

@app.post("/parse_resume")
def parse_resume(request: Request):
    try:

        resume = request.resume    
        query = f"""Esta es la hoja de vida de un candidato, de la cual debes extraer nombre de la persona, habilidades, descripcion profesional, carrera profesional, experiencias y educaciones:
        {resume}
        """

        parser = JsonOutputParser(pydantic_object=Resume)

        prompt = PromptTemplate(
            template="Answer the user query.\n{format_instructions}\n{query}\n",
            input_variables=["query"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | model | parser

        respuesta = chain.invoke({"query": query})

        temp_list = []
        for estudio in respuesta['education']:
            if estudio['university'].lower().find('andes') == -1:
                temp_list.append({
                    'university':estudio['university'], 
                    'dates': formatear_fechas(estudio['dates'] if any([char.isnumeric() for char in estudio['dates']]) or any([word in estudio['dates'].lower() for word in ['curso', 'present', 'current']]) else '-'),
                    'program': estudio['program']
                    })
            
        respuesta['education'] = temp_list

        temp_list = []
        for trabajo in respuesta['experience']:
            temp_list.append({
                'company':trabajo['company'], 
                'dates': formatear_fechas(trabajo['dates'] if any([char.isnumeric() for char in trabajo['dates']]) or any([word in trabajo['dates'].lower() for word in ['curso', 'present', 'current']]) else '-'),
                'description': trabajo['description'],
                'role': trabajo['role']
                })
            
        respuesta['experience'] = temp_list
        return respuesta
    except Exception as e:
        return e
