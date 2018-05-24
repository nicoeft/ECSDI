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
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import FOAF, RDF

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
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
    port = 9011
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
AgenteMostrarProductos = Agent('AgenteMostrarProductos',
                  agn.AgenteMostrarProductos,
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

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio

    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    global mss_cnt

    gmess = Graph()

    # Construimos el mensaje de registro
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[AgenteMostrarProductos.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, AgenteMostrarProductos.uri))
    gmess.add((reg_obj, FOAF.Name, Literal(AgenteMostrarProductos.name)))
    gmess.add((reg_obj, DSO.Address, Literal(AgenteMostrarProductos.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.AgenteMostrarProductos))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=AgenteMostrarProductos.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr


def getProducts(gr):
    global products

    model = None
    marca = None
    precioMax = None
    valoracion = None
    tipoProducto = None

    for s,p,o in gr.triples((None,RDF.type, AM2['Restricciones_cliente'])):
        for s2,p2,o2 in gr.triples((s, AM2.modeloRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            model = o2
        
        for s2,p2,o2 in gr.triples((s, AM2.marcaRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            marca = o2
            
        for s2,p2,o2 in gr.triples((s, AM2.precioMaxRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            precioMax = o2
        
        for s2,p2,o2 in gr.triples((s, AM2.valoracionRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            valoracion = o2
                
        for s2,p2,o2 in gr.triples((s, AM2.tipoRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            tipoProducto = o2

    productsGraph = Graph()

    for s,p,o in products.triples((None,AM2.Modelo,model)):
        #print ('--> %s %s %s'%(s,p,o))
        for s2,p2,o2 in products.triples((s,None,None)):
            productsGraph.add((s2,p2,o2))

    #for s,p,o in productsGraph:
        # print ('kkkk -> %s %s %s'%(s,p,o))
        #productsGraph.add((s,p,o))

    # logger.info("EOO" + productsGraph)

    return productsGraph

def initProducts():
    global products

    subjectProducto = AM2['DVD']
    products.add((subjectProducto, RDF.type, AM2.Producto))
    products.add((subjectProducto, AM2.Nombre, Literal("DVD")))
    products.add((subjectProducto, AM2.TipoProducto, Literal("Electronica")))
    products.add((subjectProducto, AM2.Precio, Literal(50)))

    subjectProducto2 = AM2['Televisor_1']
    products.add((subjectProducto2, RDF.type, AM2.Producto))
    products.add((subjectProducto2, AM2.Nombre, Literal("Televisor")))
    products.add((subjectProducto2, AM2.TipoProducto, Literal("Electronica")))
    products.add((subjectProducto2, AM2.Precio, Literal(300)))
    products.add((subjectProducto2, AM2.Modelo, Literal('E1234H')))

    subjectProducto3 = AM2['Camisa']
    products.add((subjectProducto3, RDF.type, AM2.Producto))
    products.add((subjectProducto3, AM2.Nombre, Literal("Camisa")))
    products.add((subjectProducto3, AM2.TipoProducto, Literal("Ropa")))
    products.add((subjectProducto3, AM2.Precio, Literal(15)))

    subjectProducto4 = AM2['Televisor_2']
    products.add((subjectProducto4, RDF.type, AM2.Producto))
    products.add((subjectProducto4, AM2.Nombre, Literal("Televisor")))
    products.add((subjectProducto4, AM2.TipoProducto, Literal("Electronica")))
    products.add((subjectProducto4, AM2.Modelo, Literal('H456K')))
    return

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

    logger.info('Peticion de informacion recibida')

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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteMostrarProductos.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        # logger.info("OOOEOEOEOE %s", perf)
        if perf != ACL.request:
            # logger.info("NOT UNDERSTOOD!")
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteMostrarProductos.uri, msgcnt=mss_cnt)
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
                if accion == AM2.Peticion_productos_disponibles:
                    productsGraph = getProducts(gm)
                    gr = build_message(productsGraph,
                        ACL['inform-done'],
                        sender=AgenteMostrarProductos.uri,
                        msgcnt=mss_cnt,
                        receiver=msgdic['sender'], )
                    # logger.info("AQUI!")
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteMostrarProductos.uri, msgcnt=mss_cnt)
            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteMostrarProductos.uri, msgcnt=mss_cnt)


    # for s,p,o in gr:
    #     print('sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))

    mss_cnt += 1
    logger.info('Respondemos a la peticion')
    return gr.serialize(format='xml')


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
    # Registramos el agente
    gr = register_message()

    # Escuchando la cola hasta que llegue un 0
    fin = False
    while not fin:
        while cola.empty():
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            print(v)

            # Selfdestruct
            # requests.get(AgenteMostrarProductos.stop)

if __name__ == '__main__':

    # Inicializacion de datos
    initProducts()
    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
