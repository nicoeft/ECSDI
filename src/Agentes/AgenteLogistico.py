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

from rdflib import Namespace, Graph,Literal
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
port = 9013

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9013
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

AgenteLogistico = Agent('AgenteLogistico',
                       agn.AgenteLogistico,
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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteLogistico.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteLogistico.uri, msgcnt=mss_cnt)
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                # Aqui realizariamos lo que pide la accion

                if accion == AM2.Solicitud_envio: 
                    logger.info("Petición de envio recibida")
                    productsInternos = Graph()
                    productsExternos = Graph()
                    # Productos recibidos
                    hayExterno = False
                    hayInterno = False
                    for s in gm.subjects(RDF.type,AM2["Producto"]):
                        tipoEnvio = gm.value(s,AM2.TipoEnvio)
                        if str(tipoEnvio) == 'Interno':
                            hayInterno = True
                            productsInternos += gm.triples((s,None,None))
                        else:
                            hayExterno = True
                            productsExternos += gm.triples((s,None,None))
                    
                    if hayExterno and not hayInterno:
                        gr = confirmaEnvio(msgdic,productsExternos)
                        colaAvisarAgenteVendedorExterno(productsExternos)
                    else:
                        gmess = Graph()
                        sj_contenido = MSG[AgenteLogistico.name + '-Realiza_envio-' + str(mss_cnt)]
                        gmess.add((sj_contenido, RDF.type, AM2.Realiza_envio))
                        gmess += productsInternos
                        agenteAlmacen = directory_search_agent(DSO.AgenteAlmacen,AgenteLogistico,DirectoryAgent,mss_cnt)[0]
                        grm = build_message(gmess,
                            perf=ACL.request,
                            sender=AgenteLogistico.uri,
                            receiver=agenteAlmacen.uri,
                            content=sj_contenido,
                            msgcnt=mss_cnt)
                        gr = send_message(grm,agenteAlmacen.address)
                        logger.info('Se ha informado al almacen que debe realizar envio')
                        if hayExterno:
                            gmess2 = Graph()
                            sj_contenido = MSG[AgenteLogistico.name + '-Confirmacion_envio_externo_interno-' + str(mss_cnt)]
                            gmess2.add((sj_contenido, RDF.type, AM2.Confirmacion_envio_externo_interno))
                            gr = build_message(gmess2,
                                ACL['inform-done'],
                                sender=AgenteLogistico.uri,
                                msgcnt=mss_cnt,
                                content=sj_contenido,
                                receiver=msgdic['sender'])
                            colaAvisarAgenteVendedorExterno(productsExternos)      
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteLogistico.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteLogistico.uri, msgcnt=mss_cnt)

    mss_cnt += 1
    logger.info('Respondemos a la solicitud de envio')
    return gr.serialize(format='xml')

def colaAvisarAgenteVendedorExterno(productsExternos):
    gmess = Graph()
    global cola1
    sj_contenido = MSG[AgenteLogistico.name + '-Avisar_vendedor_externo_envio-' + str(mss_cnt)]
    gmess.add((sj_contenido, RDF.type, AM2.Avisar_vendedor_externo_envio))
    gmess += productsExternos
    cola1.put(gmess)

def confirmaEnvio(msgdic,productsExternos):
    global mss_cnt
    gmess = Graph()
    sj_contenido = MSG[AgenteLogistico.name + '-Confirmacion_envio_externo-' + str(mss_cnt)]
    gmess.add((sj_contenido, RDF.type, AM2.Confirmacion_envio_externo))
    gmess += productsExternos
    gr = build_message(gmess,
        ACL['inform-done'],
        sender=AgenteLogistico.uri,
        msgcnt=mss_cnt,
        content=sj_contenido,
        receiver=msgdic['sender'])
    logger.info('Confirmacion Envio Externo')
    return gr

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
    register_message(DSO.AgenteLogistico,AgenteLogistico,DirectoryAgent,mss_cnt)
    fin = False
    while not fin:
        while cola.empty():
            pass
        gmess = cola.get()
        if gmess == 0:
            fin = True
        else:
            agenteVendedorExterno = directory_search_agent(DSO.AgenteVendedorExterno,AgenteLogistico,DirectoryAgent,mss_cnt)[0]
            content = gmess.value(predicate=RDF.type,object=AM2.Avisar_vendedor_externo_envio)
            grm = build_message(gmess,
                perf=ACL.request,
                sender=AgenteLogistico.uri,
                receiver=agenteVendedorExterno.uri,
                content=content,
                msgcnt=mss_cnt)
            send_message(grm,agenteVendedorExterno.address)
            logger.info('Se ha notificado al vendedor externo para que se encargue del envio')

if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


