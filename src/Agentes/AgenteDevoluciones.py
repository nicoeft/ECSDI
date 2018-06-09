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

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties, register_message
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
    port = 9017
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
AgenteDevoluciones = Agent('AgenteDevoluciones',
                  agn.AgenteDevoluciones,
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

    logger.info('Peticion de devolucion recibida')

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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevoluciones.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevoluciones.uri, msgcnt=mss_cnt)
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)

                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Peticion_devolucion:
                    logger.info("Nueva petición de devolución recibida")
                    gmess = Graph()
                    sj_contenido = AM2[AgenteDevoluciones.name + '-Comunicacion_resultado_devolucion-' + str(mss_cnt)]
                    gmess.add((sj_contenido, RDF.type, AM2.Comunicacion_resultado_devolucion))
                    username = gm.value(subject=content, predicate=AM2.username)
                    devolucionValida = True
                    for s in gm.subjects(RDF.type,AM2.Compra):
                        # print("----FOR-----> %s"%(s))
                        esValido = checkProductosComprados(s,username)
                        if not esValido: 
                            devolucionValida = False

                    if devolucionValida:
                        print("Devolución ACEPTADA")
                        gmess.add((sj_contenido, AM2.resultadoDevolucion, Literal("Devolución Aceptada"))) 
                        compraGraph = Graph()
                        for s in gm.subjects(RDF.type,AM2.Compra):
                            compraGraph += gm.triples((s,None,None))
                        addDevolutionToBD(compraGraph,username)
                    else:
                        print("Devolución DENEGADA")
                        gmess.add((sj_contenido, AM2.resultadoDevolucion, Literal("Devolución Denegada")))
                    
                    gr = build_message(gmess,
                        perf=ACL['inform-done'],
                        sender=AgenteDevoluciones.uri,
                        content=sj_contenido,
                        msgcnt=mss_cnt)
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevoluciones.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevoluciones.uri, msgcnt=mss_cnt)


    # for s,p,o in gr:
    #     print('sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))

    mss_cnt += 1
    logger.info('Respondiendo a la peticion')
    return gr.serialize(format='xml')


def checkProductosComprados(sujetoCompra,username):
    compras = Graph()
    datosProductos = open('../datos/compras')
    compras.parse(datosProductos, format='turtle')
    esValido=False
    for s,p,o in compras:
        usernameCompra = compras.value(s,AM2.username)
        if s == sujetoCompra and username == usernameCompra:
            esValido = True
    return esValido


def addDevolutionToBD(gr, username):
    devoluciones = Graph()
    ontologyFile = open('../datos/devoluciones')
    devoluciones.parse(ontologyFile, format='turtle')
    index = devoluciones.__len__()
    currentDevolucion = Graph()
    sujeto = AM2['devolucion-'+str(index)]
    currentDevolucion.add((sujeto,AM2.username,username))
    for s,p,o in gr:
        # print("devolucion %s|%s|%s"%(s,p,o))
        currentDevolucion.add((sujeto,AM2.productos,URIRef(s)))

    devoluciones += currentDevolucion
    # for s,p,o in gr:
    #     print("Compras added: %s | %s | %s"%(s,p,o))

    devoluciones.serialize('../datos/devoluciones', format='turtle') 
    return

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
    # Registramos el agente
    gr = register_message(DSO.AgenteDevoluciones,AgenteDevoluciones,DirectoryAgent,mss_cnt)

    # Escuchando la cola hasta que llegue un 0
    fin = False
    # while not fin:
    #     while cola.empty():
    #         pass
    #     v = cola.get()
    #     if v == 0:
    #         fin = True
    #     else:
    #         print(v)

            # Selfdestruct
            # requests.get(AgenteDevoluciones.stop)

if __name__ == '__main__':
    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
