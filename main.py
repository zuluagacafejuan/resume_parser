from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    description: str = Field(description="descripción profesional del candidato")
    career: str = Field(description="carrera que estudió el candidato. Extraer: solo la carrera, no la universidad.")
    experience: list = Field(description="experiencia laboral del candidato. Cada experiencia es un json con keys company (compañia), dates (fecha) y role (cargo). Si no encuentras uno de los valores pon un string vacio. Si no encuentras fecha para esa experiencia pon '-' en la fecha")
    education: list = Field(description="educación del candidato. De cada uno extraer: Universidad, estudio y fecha. Cada educacion es un json con keys university (universidad), dates (fecha) y program (estudio realizado). Si no encuentras fecha para ese estudio pon '-' en la fecha")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/parse_resume")
def parse_resume(resume: str):     
    query = f"""Esta es la hoja de vida de un candidato, de la cual debes extraer nombre de la persona, habilidades, descripcion profesional, carrera profesional, experiencia y educación:
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
        temp_list.append({
            'university':estudio['university'], 
            'dates': estudio['dates'] if any([char.isnumeric() for char in estudio['dates']]) or any([word in estudio['dates'].lower() for word in ['curso', 'present', 'current']]) else '-',
            'program': estudio['program']
            })
        
    respuesta['education'] = temp_list

    temp_list = []
    for trabajo in respuesta['experience']:
        temp_list.append({
            'company':trabajo['company'], 
            'dates': trabajo['dates'] if any([char.isnumeric() for char in trabajo['dates']]) or any([word in trabajo['dates'].lower() for word in ['curso', 'present', 'current']]) else '-',
            'role': trabajo['role']
            })
        
    respuesta['experience'] = temp_list
    return respuesta
