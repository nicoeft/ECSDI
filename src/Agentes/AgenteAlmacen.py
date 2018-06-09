# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket
import argparse
import sys
import time

from rdflib import Namespace, Graph,Literal, URIRef
from rdflib.namespace import FOAF, RDF
from flask import Flask, request

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION,MSG
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties, directory_search_agent, register_message
from AgentUtil.FlaskServer import shutdown_server
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

# Configuration stuff
hostname = socket.gethostname()
port = 9014

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9014
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

    # dhostname = socket.gethostname()
if args.dhost is None:
    dhostname = "localhost"
else:
    dhostname = args.dhost


agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgenteAlmacen = Agent('AgenteAlmacen',
                       agn.AgenteAlmacen,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)
    msgdic = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteAlmacen.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteAlmacen.uri, msgcnt=mss_cnt)
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Realiza_envio:
                    logger.info('Realizando el envio')

                    products = Graph()
                    for s in gm.subjects(RDF.type,AM2["Producto"]):
                        products += gm.triples((s,None,None))

                    # for s,p,o in products:
                    #     print("Procesando productos: %s | %s | %s"%(s,p,o))

                    negociaEnvio()
                    time.sleep(10) #Hacemos que tarde un tiempo en procesar antes de confirmar el envio
                    gr = confirmaEnvio(msgdic)
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteAlmacen.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteAlmacen.uri, msgcnt=mss_cnt)

    mss_cnt += 1
    logger.info('Confirmamos que se ha relizado el envio')
    return gr.serialize(format='xml')

def confirmaEnvio(msgdic):
    global mss_cnt
    gmess = Graph()
    sj_contenido = MSG[AgenteAlmacen.name + '-Confirmacion_envio-' + str(mss_cnt)]
    gmess.add((sj_contenido, RDF.type, AM2.Confirmacion_envio))
    gr = build_message(gmess,
        ACL['inform-done'],
        sender=AgenteAlmacen.uri,
        msgcnt=mss_cnt,
        content=sj_contenido,
        receiver=msgdic['sender'])
    logger.info('Confirmacion Envio')
    return gr

def negociaEnvio():
    logger.info('Negociando el envio con transportistas')
    global mss_cnt
    gmess = Graph()
    sj_contenido = MSG[AgenteAlmacen.name + '-Pedir_precio_envio-' + str(mss_cnt)]
    gmess.add((sj_contenido, RDF.type, AM2.Pedir_precio_envio))
    agentesTransportistas = directory_search_agent(DSO.AgenteTransportista,AgenteAlmacen,DirectoryAgent,mss_cnt)
    mejorOferta = sys.maxint
    for agenteTransportista in agentesTransportistas:
        grm = build_message(gmess,
            perf=ACL.request,
            sender=AgenteAlmacen.uri,
            receiver=agenteTransportista.uri,
            content=sj_contenido,
            msgcnt=mss_cnt)
        gr = send_message(grm,agenteTransportista.address)
        sj_precios = gr.value(predicate = RDF.type, object = AM2['Precios_envio'])
        precio = gr.value(sj_precios,AM2.precioEnvioTransportista)
        if int(precio)<mejorOferta:
            mejorOferta = int(precio)
            agenteElegido = agenteTransportista
    logger.info(agenteElegido.name)
    transportistaContraoferta = contraOfertaEnvio(mejorOferta,agentesTransportistas)
    if(agenteElegido.name != transportistaContraoferta.name):
        logger.info("Se ha mejorado la oferta")
        logger.info(transportistaContraoferta.name)

def contraOfertaEnvio(mejorOferta, agentesTransportistas):
    logger.info("Realizando Contraoferta")
    gmess = Graph
    precioContraoferta = mejorOferta -10
    gmess = Graph()
    sj_contenido = MSG[AgenteAlmacen.name + '-Contraoferta_envio-' + str(mss_cnt)]
    gmess.add((sj_contenido, RDF.type, AM2.Contraoferta_envio))
    sj_contraoferta = AM2['Contraoferta' + str(mss_cnt)]
    gmess.add((sj_contraoferta, RDF.type, AM2['Contraoferta'])) 
    gmess.add((sj_contraoferta, AM2.precioContraoferta, Literal(precioContraoferta))) 
    gmess.add((sj_contenido, AM2.tieneContraoferta, URIRef(sj_contraoferta)))
    for agenteTransportista in agentesTransportistas:
        grm= build_message(gmess,
            perf=ACL.request,
            sender=AgenteAlmacen.uri,
            receiver=agenteTransportista.uri,
            content=sj_contenido,
            msgcnt=mss_cnt)
        gr = send_message(grm,agenteTransportista.address)
        sj_precios = gr.value(predicate = RDF.type, object = AM2['Precios_envio'])
        precio = gr.value(sj_precios,AM2.precioEnvioTransportista)
        if int(precio)<mejorOferta:
            mejorOferta = int(precio)
            agenteElegidoContraoferta = agenteTransportista
    return agenteElegidoContraoferta

@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    """
    global cola1
    cola1.put(0)


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    global mss_cnt
    logger.info('Nos registramos en el servicio de registro')
    register_message(DSO.AgenteAlmacen,AgenteAlmacen,DirectoryAgent,mss_cnt)
    fin = False
    # while not fin:
    #     while cola.empty():
    #         pass
    #     v = cola.get()
    #     if v == 0:
    #         fin = True
    #     else:
    #         print(v)


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


