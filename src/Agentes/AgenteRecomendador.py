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

import random

from sets import Set

from random import randint
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

def getCategorias(productes):
    categories = Set()
    products = Graph()
    datosProductos = open('../datos/productos')
    products.parse(datosProductos, format='turtle') 

    for s,p,o in products:
        if(s in productes):
            categoria = str(products.value(s, AM2.TipoProducto, None))
            categories.add(categoria)
    
    return categories

def buscaCompras(username):
    compras = Graph()
    datosCompras = open('../datos/compras')
    compras.parse(datosCompras, format='turtle')
    
    query= """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix AM2:<http://www.semanticweb.org/alexh/ontologies/2018/4/amazon2#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?compra ?productos ?username
        where{ 
            ?compra rdf:type AM2:Compra .
            ?compra AM2:productos ?productos .
            ?compra AM2:username ?username .
            FILTER("""
    if username is not None:
        query+= """str(?username) = '""" + username +"""'"""

    query+= """ )} order by asc(UCASE(str(?nombre)))"""
    graph_result = compras.query(query)

    productes = Set()
    for row in graph_result:
        if(row.productos not in productes):
            productes.add(row.productos)
    
    return productes

def buscaProductosRecomendables(username):
    SubjProductes = buscaCompras(username)
    categorias = getCategorias(SubjProductes)

    products = Graph()
    datosProductos = open('../datos/productos')
    products.parse(datosProductos, format='turtle')
    productesRecomendar = Set()

    for s,p,o in products:
        categoria = str(products.value(s,AM2.TipoProducto, None))
        if(categoria in categorias):
            if(s not in SubjProductes):
                productesRecomendar.add(s)

    producto = (random.sample(productesRecomendar,1))
    producto = producto.pop()
    
    query= """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix AM2:<http://www.semanticweb.org/alexh/ontologies/2018/4/amazon2#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?id ?nombre ?tipoProducto ?precio ?modelo ?marca ?tipoEnvio
        where{
            ?producto rdf:type AM2:Producto .
            ?producto AM2:Id ?id .
            ?producto AM2:Nombre ?nombre . 
            ?producto AM2:TipoProducto ?tipoProducto .
            ?producto AM2:Precio ?precio .
            ?producto AM2:Modelo ?modelo .
            ?producto AM2:Marca ?marca .
            ?producto AM2:TipoEnvio ?tipoEnvio
            FILTER("""
    if producto is not None:
        query+= """str(?producto) = '""" + producto +"""'"""
    
    query+= """ )} """

    graph_result = products.query(query)
    result = Graph()
    result.bind('AM2', AM2)
    for row in graph_result:
        Id = row.id
        Name = row.nombre
        Type = row.tipoProducto
        Price = row.precio
        Model = row.modelo
        Brand = row.marca
        Envio = row.tipoEnvio
        sujeto = row.producto
        result.add((sujeto, RDF.type, AM2.Producto))
        result.add((sujeto,AM2.Id,Literal(Id, datatype=XSD.int)))
        result.add((sujeto,AM2.Nombre,Literal(Name, datatype=XSD.string)))
        result.add((sujeto,AM2.TipoProducto,Literal(Type, datatype=XSD.string)))
        result.add((sujeto,AM2.Precio,Literal(Price, datatype=XSD.int)))
        result.add((sujeto,AM2.Modelo,Literal(Model, datatype=XSD.string)))
        result.add((sujeto,AM2.Marca,Literal(Brand, datatype=XSD.string)))
        result.add((sujeto,AM2.TipoEnvio, Literal(Envio, datatype=XSD.string)))
    
    return result

def graphProductoRecomendar(productosRecomendables,agenteCliente):
    totalProductos = productosRecomendables.__len__()
    numRandom = randint(0, int(totalProductos)-1)
    i = 0
    for s in productosRecomendables.subjects(RDF.type,AM2.Producto):
        if i == int(numRandom):
            productoRecomendado = productosRecomendables.triples((s,None,None))
            break
        i += 1
    
    grecommend = Graph()
    sj_contenido = AM2[AgenteRecomendador.name + '-Recomendacion-' + str(mss_cnt)]
    grecommend.add((sj_contenido, RDF.type, AM2.Recomendacion))
    sj_producto = AM2['Producto' + str(mss_cnt)]
    grecommend.add((sj_producto, RDF.type, AM2.Producto))
    grecommend.add((sj_producto, AM2.Producto, URIRef(productoRecomendado.uri))) 
    grecommend.add((sj_contenido, AM2.procuctoRecomendado, URIRef(sj_producto)))
    
    grm = build_message(grecommend,
    perf=ACL.request,
    sender=AgenteRecomendador.uri,
    receiver=agenteCliente.uri,
    content=sj_contenido,
    msgcnt=mss_cnt)

                    
    gr = send_message(grm,agenteCliente.address)
    logger.info('Se ha enviado una recomendacion a un cliente')
    




def recomendarProductosClientes():
    agentesCliente = directory_search_agent(DSO.AgenteCliente,AgenteRecomendador,DirectoryAgent,mss_cnt)
    for agenteCliente in agentesCliente:
        #buscamos los productos de tipo que ha comprado el cliente y que este no haya comprado aun
        productosRecomendables = buscaProductosRecomendables(agenteCliente.name)
        #elegimos de entre los productos relevantes uno al azar y enviamos la recomendacion al cliente
        graphProductoRecomendar(productosRecomendables,agenteCliente)


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
    schedule.every(10).seconds.do(recomendarProductosClientes)
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
