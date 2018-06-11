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




def getProducts(gr):
    marca = None
    precioMax = None
    tipoProducto = None
    nombre = None
    modelo = None

    for s in gr.subjects(RDF.type, AM2['Restricciones_cliente']):
        
        for s2,p2,o2 in gr.triples((s, AM2.marcaRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            marca = Literal(o2)
            
        for s2,p2,o2 in gr.triples((s, AM2.precioMaxRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            precioMax = Literal(o2)
            # Provar precio
                
        for s2,p2,o2 in gr.triples((s, AM2.tipoProductoRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            tipoProducto = Literal(o2)

        for s2,p2,o2 in gr.triples((s, AM2.nombreRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            nombre = Literal(o2)

        for s2,p2,o2 in gr.triples((s, AM2.modeloRestriccion, None)):
            print('restricciones: %s | %s | %s'%(s2,p2,o2))
            modelo = Literal(o2)

    return buscaProductos(marca, nombre, tipoProducto, modelo, precioMax)


def buscaProductos(marca, nombre, tipoProducto, modelo, precioMax):

    products = Graph()
    datosProductos = open('../datos/productos')
    products.parse(datosProductos, format='turtle')

    if marca or nombre or tipoProducto or modelo or precioMax:
        afegit = False
        # products.serialize('../path', format='turtle') para guardar
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
        if marca is not None:
            query+= """str(?marca) = '""" + marca +"""'"""
            afegit = True
        if nombre is not None:
            if afegit == True:
                query+= """ && """
            query+= """str(?nombre) = '""" + nombre +"""'"""
            afegit = True
        if tipoProducto is not None:
            if afegit == True:
                query+= """ && """
            query+= """str(?tipoProducto) = '""" + tipoProducto +"""'"""
            afegit = True
        if modelo is not None:
            if afegit == True:
                query+= """ && """
            query+= """str(?modelo) = '""" + modelo +"""'"""
            afegit = True
        if precioMax is not None:
            if afegit == True:
                query+= """ && """
            query+= """ ?precio <= """ + str(precioMax)
        
        query+= """ )} order by asc(UCASE(str(?nombre)))"""

    else:
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
                } """
                
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
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)

                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Peticion_productos_disponibles:
                    logger.info("Nueva petición de mostrar productos")
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
    global mss_cnt
    # Registramos el agente
    gr = register_message(DSO.AgenteMostrarProductos,AgenteMostrarProductos,DirectoryAgent,mss_cnt)

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
            # requests.get(AgenteMostrarProductos.stop)

if __name__ == '__main__':

    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
