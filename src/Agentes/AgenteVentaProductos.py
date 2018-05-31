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
from flask import Flask, request, render_template

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
port = 9010

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9012
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

AgenteVentaProductos = Agent('AgenteVentaProductos',
                       agn.AgenteVentaProductos,
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
    # TODO: quitar el pass y hacer la funcion

    logger.info('Peticion de Compra')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    # sender = gm.triples((None,ACL['sender'],None))
    # for s,p,o in gm.triples((None,ACL['sender'],None)):
    #     logger.info('[-->>]sujeto:%s | predicado: %s | objeto: %s', s, p,o)
    #     senderURI = o
    
    msgdic = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        # logger.info("OOOEOEOEOE %s", perf)
        if perf != ACL.request:
            # logger.info("NOT UNDERSTOOD!")
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)
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
                if accion == AM2.Peticion_Compra:
                    # productsGraph = getProducts(gm)
                    productsGraph = Graph()

                    for s in gm.subjects(RDF.type,AM2["Producto"]):
                        # print("Productos a comprar: %s | %s | %s"%(s,p,o))
                        productsGraph += gm.triples((s,None,None))
                    
                    # TODO: productos --> hay que tratarlos?
                    # for s2,p2,o2 in productsGraph:
                    #     print("Productos recibidos: %s | %s | %s"%(s2,p2,o2))

                    gmess = Graph()
                    sj_contenido = MSG[AgenteVentaProductos.name + '-Solicitud_envio-' + str(mss_cnt)]
                    gmess.add((sj_contenido, RDF.type, AM2.Solicitud_envio))

                    # productSubject = current_products.value(predicate=AM2.Id, object=Literal(id))
                    # gmess.add((productSubject, RDF.type, AM2['Producto'])) 
                    gmess += productsGraph
                    # gmess.add((sj_contenido, AM2.Productos, URIRef(productSubject)))

                    
                    agenteLogistico = directory_search_agent(DSO.AgenteLogistico,AgenteVentaProductos,DirectoryAgent,mss_cnt)[0]
                    grm = build_message(gmess,
                        perf=ACL.request,
                        sender=AgenteVentaProductos.uri,
                        receiver=agenteLogistico.uri,
                        content=sj_contenido,
                        msgcnt=mss_cnt)
                    
                    cola1.put(grm)

                    gmess2 = Graph()
                    sj_contenido = MSG[AgenteVentaProductos.name + '-Confirmacion_cesta-' + str(mss_cnt)]
                    gmess2.add((sj_contenido, RDF.type, AM2.Confirmacion_cesta))
                    gr = build_message(gmess2,
                        ACL['inform-done'],
                        sender=AgenteVentaProductos.uri,
                        msgcnt=mss_cnt,
                        content=sj_contenido,
                        receiver=msgdic['sender'])
                    
                    # gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)
                    logger.info('Se ha enviado al centro logístico la solicitud de envio')
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)


    # for s,p,o in gr:
    #     print('sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))

    mss_cnt += 1
    logger.info('Respondemos a la peticion')
    return gr.serialize(format='xml')



@app.route("/")
def ventas():
    return render_template('peticionesCompra.html')

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
    register_message(DSO.AgenteVentaProductos,AgenteVentaProductos,DirectoryAgent,mss_cnt)
    fin = False
    agenteLogistico = directory_search_agent(DSO.AgenteLogistico,AgenteVentaProductos,DirectoryAgent,mss_cnt)[0]

    while not fin:
        while cola.empty():
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            gr = send_message(v,agenteLogistico.address)
            # TODO: send message to client

            print("Recibida! %s "%gr)


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


