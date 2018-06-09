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

from rdflib import Namespace, Graph,Literal, URIRef
from rdflib.namespace import FOAF, RDF
from flask import Flask, request, render_template

from AgentUtil.OntoNamespaces import ACL, DSO, AM2
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
port = 9012

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
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)

                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Peticion_Compra:
                    logger.info("Petición de Compra recibida")
                    # productsGraph = getProducts(gm)
                    productsGraph = Graph()

                    for s in gm.subjects(RDF.type,AM2["Producto"]):
                        productsGraph += gm.triples((s,None,None))

                    #añadimos a la cola un aviso al AgenteRecomendador sobre la compra, para que pasado un tiempo pida valoraciones
                    grecommend = Graph()
                    sj_contenido = AM2[AgenteVentaProductos.name + '-Nueva_compra-' + str(mss_cnt)]
                    grecommend.add((sj_contenido, RDF.type, AM2.Nueva_compra))
                    grecommend += productsGraph

                    cola1.put(grecommend)


                    username = gm.value(subject=content, predicate=AM2.username)

                    addPurchaseToBD(productsGraph, username)
                    # for s2,p2,o2 in productsGraph:
                    #     print("Productos recibidos: %s | %s | %s"%(s2,p2,o2))

                    #añadimos a la cola una solicitud de envio para el AgenteLogistico
                    gmess = Graph()
                    sj_contenido = AM2[AgenteVentaProductos.name + '-Solicitud_envio-' + str(mss_cnt)]
                    gmess.add((sj_contenido, RDF.type, AM2.Solicitud_envio))
                    gmess += productsGraph
                    cola1.put(gmess)

                    #retornamos un inform-done con los productos a mostar en la cesta
                    gmess2 = Graph()
                    sj_contenido = AM2[AgenteVentaProductos.name + '-Confirmacion_cesta-' + str(mss_cnt)]
                    gmess2.add((sj_contenido, RDF.type, AM2.Confirmacion_cesta))
                    gmess2 += productsGraph
                    gr = build_message(gmess2,
                        ACL['inform-done'],
                        sender=AgenteVentaProductos.uri,
                        msgcnt=mss_cnt,
                        content=sj_contenido,
                        receiver=msgdic['sender'])
                
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVentaProductos.uri, msgcnt=mss_cnt)


    # for s,p,o in gr:
    #     print('sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))

    mss_cnt += 1
    logger.info('Respondemos a la peticion de compra')
    return gr.serialize(format='xml')

def addPurchaseToBD(gr, username):
    purchases = Graph()
    # print("ADDPURCHASE TO BD!")
    ontologyFile = open('../datos/compras')
    purchases.parse(ontologyFile, format='turtle')
    index = purchases.__len__()
    currentPurchase = Graph()
    sujeto = AM2['compra-'+str(index)]
    currentPurchase.add((sujeto,AM2.username,username))
    for s,p,o in gr.triples((None,AM2.TipoProducto,None)):
        # print("purchase %s|%s|%s"%(s,p,o))
        currentPurchase.add((sujeto,AM2.productos,URIRef(s)))
        currentPurchase.add((sujeto,AM2.TipoProducto,URIRef(o)))

    purchases += currentPurchase
    # for s,p,o in gr:
    #     print("Compras added: %s | %s | %s"%(s,p,o))

    purchases.serialize('../datos/compras', format='turtle') 
    return

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
    while not fin:
        while cola.empty():
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            sj_avisar_recomendador = v.value(predicate=RDF.type,object=AM2.Nueva_compra)
            sj_solicitud_envio = v.value(predicate=RDF.type,object=AM2.Solicitud_envio)
            print("-------->sj_avisar_recomendador-->%s"%(sj_avisar_recomendador))
            print("-------->sj_solicitud_envio-->%s"%(sj_solicitud_envio))

            if sj_solicitud_envio != None:
                #enviamos mensaje
                agenteLogistico = directory_search_agent(DSO.AgenteLogistico,AgenteVentaProductos,DirectoryAgent,mss_cnt)[0]
                grm = build_message(v,
                    perf=ACL.request,
                    sender=AgenteVentaProductos.uri,
                    receiver=agenteLogistico.uri,
                    content=sj_solicitud_envio,
                    msgcnt=mss_cnt)
                logger.info('Se ha enviado al centro logístico la solicitud de envio')                
                gr = send_message(grm,agenteLogistico.address)
                logger.info('Se ha recibido la respuesta del centro logístico, notificando al cliente')
                
                agenteCliente = directory_search_agent(DSO.AgenteCliente,AgenteVentaProductos,DirectoryAgent,mss_cnt)[0]
                msgdic = get_message_properties(gr)
                content = msgdic['content']
                confirmacion = gr.value(subject=content, predicate=RDF.type)
                if confirmacion == AM2.Confirmacion_envio:
                    logger.info("Confirmacion del envio")
                elif confirmacion == AM2.Confirmacion_envio_externo:
                    logger.info("Confirmacion del envio externo")
                elif confirmacion == AM2.Confirmacion_envio_externo_interno:
                    logger.info("Confirmacion del envio externo e interno")
                gmess = Graph()
                sj_contenido = AM2[AgenteVentaProductos.name + '-Factura_Compra-' + str(mss_cnt)]
                gmess.add((sj_contenido, RDF.type, AM2.Emitir_factura))
                grm = build_message(gmess,
                        perf=ACL.request,
                        sender=AgenteVentaProductos.uri,
                        receiver=agenteCliente.uri,
                        content=sj_contenido,
                        msgcnt=mss_cnt)
                send_message(grm,agenteCliente.address)
                logger.info('Se han enviado los detalles de la entrega al cliente')
            elif sj_avisar_recomendador != None:
                #avisar al recomendador
                agenteRecomendador = directory_search_agent(DSO.AgenteRecomendador,AgenteVentaProductos,DirectoryAgent,mss_cnt)[0]
                grm = build_message(v,
                    perf=ACL.request,
                    sender=AgenteVentaProductos.uri,
                    receiver=agenteRecomendador.uri,
                    content=sj_avisar_recomendador,
                    msgcnt=mss_cnt) 
                send_message(grm,agenteRecomendador.address)
                logger.info('El AgenteRecomendador ha sido notificado de la compra')
                




if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


