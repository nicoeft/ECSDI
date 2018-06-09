# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier
"""
from __future__ import print_function
from multiprocessing import Process, Queue
import socket
import argparse
import schedule
import time

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties,directory_search_agent, register_message
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

__author__ = 'amazon2'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default='localhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9015
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = "localhost"
    # hostname = socket.gethostname()

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

# Flask stuff
app = Flask(__name__)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
AgenteRecomendador = Agent('AgenteRecomendador',
                  agn.AgenteRecomendador,
                  'http://%s:%d/comm' % (hostname, port),
                  'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()

# Cola de comunicacion entre procesos
cola1 = Queue()

# Productos
products = Graph()

@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    Simplemente retorna un objeto fijo que representa una
    respuesta a una busqueda de hotel

    Asumimos que se reciben siempre acciones que se refieren a lo que puede hacer
    el agente (buscar con ciertas restricciones, reservar)
    Las acciones se mandan siempre con un Request
    Prodriamos resolver las busquedas usando una performativa de Query-ref
    """
    global dsgraph
    global mss_cnt

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    # for s,p,o in gm:
    #     logger.info('[-->]sujeto:%s | predicado: %s | objeto: %s', s, p,o)
    
    msgdic = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteRecomendador.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        # logger.info("OOOEOEOEOE %s", perf)
        if perf != ACL.request:
            # logger.info("NOT UNDERSTOOD!")
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteRecomendador.uri, msgcnt=mss_cnt)
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            # logger.info("GOT this one %s", msgdic)
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                # logger.info("PPPPvPPPPPPPPP %s %s",accion, AM2.Peticion_productos_disponibles )

                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Nueva_compra:
                    time.sleep(10)
                    logger.info("Nueva compra efectuada")
                    productsGraph = Graph()
                    for s in gm.subjects(RDF.type,AM2["Producto"]):
                        productsGraph += gm.triples((s,None,None))

                    gmess = Graph()
                    sj_contenido = AM2[AgenteRecomendador.name + '-Peticion_valoracion-' + str(mss_cnt)]
                    gmess.add((sj_contenido, RDF.type, AM2.Peticion_valoracion))
                    gmess += productsGraph
                    cola1.put(gmess)

                    gr = build_message(Graph(), ACL['inform-done'], sender=AgenteRecomendador.uri, msgcnt=mss_cnt)

                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteRecomendador.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteRecomendador.uri, msgcnt=mss_cnt)


    # for s,p,o in gr:
    #     print('sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))

    mss_cnt += 1
    logger.info('Respondemos a con un ack')
    return gr.serialize(format='xml')

def addValoracionToBD(gr):
    valoraciones = Graph()
    ontologyFile = open('../datos/valoraciones')
    valoraciones.parse(ontologyFile, format='turtle')
    index = valoraciones.__len__()
    currentValoracion = Graph()
    sujeto = AM2['valoracion-'+str(index)]
    #currentValoracion.add((sujeto,AM2.username,username))
    for s,p,o in gr.triples((None,AM2.Valoracion,None)):
        currentValoracion.add((sujeto,AM2.productos,URIRef(s)))
        currentValoracion.add((sujeto,AM2.valoraciones,Literal(o)))

    valoraciones += currentValoracion
    # for s,p,o in gr:
    #     print("Compras added: %s | %s | %s"%(s,p,o))

    valoraciones.serialize('../datos/valoraciones', format='turtle') 
    return


def tidyup():
    """
    Acciones previas a parar el agente

    """
    global cola1
    cola1.put(0)

def recomendar():
    print("I'm working...")

def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    global mss_cnt
    # Registramos el agente
    gr = register_message(DSO.AgenteRecomendador,AgenteRecomendador,DirectoryAgent,mss_cnt)

    # Escuchando la cola hasta que llegue un 0
    fin = False
    schedule.every(10).seconds.do(recomendar)
    while not fin:
        while cola.empty():
            schedule.run_pending()
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            agenteCliente = directory_search_agent(DSO.AgenteCliente,AgenteRecomendador,DirectoryAgent,mss_cnt)[0]
            content = v.value(predicate=RDF.type,object=AM2.Peticion_valoracion)
            grm = build_message(v,
                perf=ACL.request,
                sender=AgenteRecomendador.uri,
                receiver=agenteCliente.uri,
                content=content,
                msgcnt=mss_cnt)
            gRespuesta = send_message(grm,agenteCliente.address)
            logger.info('Se ha enviado una peticion de valoraciones al cliente')
            gValoraciones = Graph()
            for s in gRespuesta.subjects(RDF.type,AM2.Producto):
                print("------------------>%s"%(s))
                gValoraciones += gRespuesta.triples((s,None,None))
            addValoracionToBD(gValoraciones)
            logger.info('Se ha añadido la valoracion a la base de datos')


if __name__ == '__main__':
    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
