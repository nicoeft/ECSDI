# -*- coding: utf-8 -*-
"""
filename: AgenteCliente

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que interacciona con el usuario


Created on 09/02/2014

@author: amazon2
"""

from __future__ import print_function
from multiprocessing import Process
import socket
import argparse
import json
import re

from flask import Flask, render_template, request
from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD
from rdflib.namespace import FOAF, RDF
import requests

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import get_message_properties, build_message, send_message, directory_search_agent, register_message
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

__author__ = 'amazon2'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default='localhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--username', type=str, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# user Identifier:
username = "generic"

if args.username is None:
    username = "generic"
else:
    username = args.username

# Configuration stuff
if args.port is None:
    port = 9010
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
AgenteCliente = Agent('AgenteCliente',
                       agn.AgenteCliente,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global current_products triplestore
current_products = Graph()

# @app.route("/devolver/:id", methods=['GET', 'POST'])

# def devoluciones(request):
#     gr.parse(compras.txt)
#     listProd = getProductListFromGraph(gr)
#     for s in listProd:
#         s[0] = s[0].strip(',')
#         print("-------> %s"%(s))
#     return render_template('cestaCompra.html',devolucion=True, products=listProd)


@app.route("/busca", methods=['GET', 'POST'])
def browser_busca():
    global mss_cnt
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('busquedaYCompra.html', products=None)
    elif request.method == 'POST':
        # Hacer peticion de busqueda de productos con las restricciones del form
        if request.form['submit'] == 'Buscar':
            return mostrarProductosFiltrados(request)
        elif request.form['submit'] == 'Comprar':
            return comprar(request)



def comprar(request):
    global mss_cnt
    global current_products
    global username
    logger.info("Comprando productos")
    print(request.form.getlist('productsToBuy'))
    gmess = Graph()
    # Creamos el sujeto -> contenido del mensaje
    sj_contenido = agn[AgenteCliente.name + '-Peticion_Compra-' + str(mss_cnt)]
    # le damos un tipo
    gmess.add((sj_contenido, RDF.type, AM2.Peticion_Compra))
    gmess.add((sj_contenido, AM2.username, Literal(username)))
    # sujetoProductos = AM2["Productos"]
    # gmess.add((sujetoProductos,))
    for id in request.form.getlist('productsToBuy'):
        # print("Ids: %s"%id)
        productSubject = current_products.value(predicate=AM2.Id, object=Literal(id, datatype=XSD.int))

        gmess.add((productSubject, RDF.type, AM2['Producto'])) 

        gmess += current_products.triples((productSubject,None,None))

        gmess.add((sj_contenido, AM2.Productos, URIRef(productSubject)))

    vendedor = directory_search_agent(DSO.AgenteVentaProductos,AgenteCliente,DirectoryAgent,mss_cnt)[0]
    msg = build_message(gmess, perf=ACL.request,
                sender=AgenteCliente.uri,
                receiver=vendedor.uri,
                content=sj_contenido,
                msgcnt=mss_cnt)
    print("message BUILD")
    gr = send_message(msg, vendedor.address)
    print("message SENT")
    mss_cnt += 1
    #msgdic = get_message_properties(gr)
    #content = msgdic['content']
    #accion = gr.value(subject=content, predicate=RDF.type)
    #logger.info(accion)
    product_list = getProductListFromGraph(gr)
    return render_template('cestaCompra.html', products=product_list)

def mostrarProductosFiltrados(request):
    global mss_cnt
    global current_products

    logger.info("Creando peticion de productos disponibles")
    gmess = Graph()
    # Creamos el sujeto -> contenido del mensaje
    sj_contenido = agn[AgenteCliente.name + 'Peticion_productos_disponibles' + str(mss_cnt)]
    #le damos un tipo
    gmess.add((sj_contenido, RDF.type, AM2.Peticion_productos_disponibles))
    #Añadimos restricciones
    nombre = request.form['nombre']
    if nombre:
        sj_nombre = AM2['Nombre' + str(mss_cnt)] #creamos una instancia con nombre Modelo1..2.
        gmess.add((sj_nombre, RDF.type, AM2['Restricciones_cliente'])) # indicamos que es de tipo Modelo
        gmess.add((sj_nombre, AM2.nombreRestriccion, Literal(nombre))) #le damos valor a su data property
        #añadimos el modelo al conenido con su object property
        gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_nombre)))
    marca = request.form['marca']
    if marca:
        sj_marca = AM2['Marca' + str(mss_cnt)]
        gmess.add((sj_marca, RDF.type, AM2['Restricciones_cliente'])) 
        gmess.add((sj_marca, AM2.marcaRestriccion, Literal(marca))) 
        gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_marca)))
    tipo = request.form['tipo']
    if tipo:
        sj_tipo = AM2['Tipo' + str(mss_cnt)]
        gmess.add((sj_tipo, RDF.type, AM2['Restricciones_cliente'])) 
        gmess.add((sj_tipo, AM2.tipoProductoRestriccion, Literal(tipo))) 
        gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_tipo)))
    modelo = request.form['modelo']
    if modelo:
        sj_modelo = AM2['Modelo' + str(mss_cnt)]
        gmess.add((sj_modelo, RDF.type, AM2['Restricciones_cliente'])) 
        gmess.add((sj_modelo, AM2.modeloRestriccion, Literal(modelo))) 
        gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_modelo)))
    precio = request.form['precio']
    if precio:
        sj_precio = AM2['Precio' + str(mss_cnt)]
        gmess.add((sj_precio, RDF.type, AM2['Restricciones_cliente'])) 
        gmess.add((sj_precio, AM2.precioMaxRestriccion, Literal(precio))) 
        gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_precio)))
    
    mostrador = directory_search_agent(DSO.AgenteMostrarProductos,AgenteCliente,DirectoryAgent,mss_cnt)[0]
    msg = build_message(gmess, perf=ACL.request,
                sender=AgenteCliente.uri,
                receiver=mostrador.uri,
                content=sj_contenido,
                msgcnt=mss_cnt)
    current_products = send_message(msg, mostrador.address)
    mss_cnt += 1
    logger.info('Recibimos respuesta a la peticion al servicio de informacion')
    
    
    product_list = getProductListFromGraph(current_products)
    print("EEUUU: %s"%(product_list))
    return render_template('busquedaYCompra.html', products=product_list)

def getProductListFromGraph(current_products):
    index = 0
    subject_pos = {}
    product_list = []
    for s, p, o in current_products:
        if s not in subject_pos:
            subject_pos[s] = index
            product_list.append({})
            index += 1
        if s in subject_pos:
            subject_dict = product_list[subject_pos[s]]
            if p == AM2.Modelo:
                subject_dict['modelo'] = o
            elif p == AM2.Marca:
                subject_dict['marca'] = o
            elif p == AM2.Nombre:
                subject_dict['nombre'] = o
            elif p == AM2.Id:
                subject_dict['id'] = o
            elif p == AM2.Precio:
                subject_dict['precio'] = o
            elif p == AM2.TipoProducto:
                subject_dict['tipo'] = o
            product_list[subject_pos[s]] = subject_dict
    return product_list


@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('iface.html')
    else:
        user = request.form['username']
        mess = request.form['message']
        return render_template('riface.html', user=user, mess=mess)


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
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)
    msgdic = get_message_properties(gm)
    logger.info('eeeeeeeeeeeeeeeeeeeeeeeeee')
    mss_cnt += 1
    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCliente.uri, msgcnt=mss_cnt)

    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCliente.uri, msgcnt=mss_cnt)

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                # Aqui realizariamos lo que pide la accion
                if accion == AM2.Emitir_factura:
                    logger.info('Mostrando factura con detalles del envio')
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCliente.uri, msgcnt=mss_cnt) #CAL retornar algo sempre?
                    
                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCliente.uri, msgcnt=mss_cnt)

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCliente.uri, msgcnt=mss_cnt)

    return gr.serialize(format='xml')


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    global mss_cnt

     # Registramos el agente cliente
    logger.info('Nos registramos en el servicio de registro')
    gr = register_message(DSO.AgenteCliente,AgenteCliente,DirectoryAgent,mss_cnt)
    

    # Ahora mandamos un objeto de tipo request mandando una accion de tipo Search
    # que esta en una supuesta ontologia de acciones de agentes
    #gr_productos = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)

    #for s,p,o in gr_productos.triples( (None,  RDF.type, AM2.Producto) ):
      #  print('Producto: sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))
       # for s2,p2,o2 in gr_productos.triples((s,None,None)):
        #    print ('Propiedades: %s | %s | %s'%( s2, p2, o2))

    # gr2 = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)
    # gr3 = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)
    
    # AgenteVentaProductos = directory_search_agent(DSO.AgenteVentaProductos,AgenteCliente,DirectoryAgent,mss_cnt)
    # gr_compra = buy_products(AgenteVentaProductos.address,AgenteVentaProductos.uri)


    # for s,p,o in gr_compra:
    #     print('Respuesta compra producto: sujeto:%s | predicado: %s | objeto: %s'%(s,p,o))
    # r = requests.get(ra_stop)
    # print r.text

    # Selfdestruct
    #requests.get(AgenteCliente.stop)


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
